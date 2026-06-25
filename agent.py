import sys
import os
import time
import subprocess
import re

# 1. 윈도우 인코딩 설정 (로그 출력 에러 방지)
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.platform == "win32":
    import io
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

class UltimateAutoAgent:
    def __init__(self, target_file, target_args=None):
        self.target_file = target_file
        # 기본: --monitor-only (브라우저/input 없이 끝남). 전체 UI는 target_args=[] 또는 ["--full-ui"]
        self.target_args = target_args if target_args is not None else ["--monitor-only"]
        self.api_key = os.environ.get("GOOGLE_API_KEY", "")
        self.llm = None

    def _get_llm(self):
        if not self.api_key:
            return None
        if self.llm is None:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
            except ModuleNotFoundError:
                print(
                    "⚠️ langchain-google-genai 미설치: pip install langchain-google-genai",
                    flush=True,
                )
                return None
            self.llm = ChatGoogleGenerativeAI(
                model="models/gemini-1.5-pro",
                google_api_key=self.api_key,
                temperature=0,
            )
        return self.llm

    def run_target(self):
        """대상 프로그램을 실행하고 에러 결과를 반환 (출력은 즉시 터미널에도 표시)"""
        cmd = [sys.executable, self.target_file] + (self.target_args or [])
        print(f"[*] 실행: {' '.join(cmd)}", flush=True)
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        if result.stdout:
            print(result.stdout, end="" if result.stdout.endswith("\n") else "\n", flush=True)
        if result.stderr:
            print(result.stderr, end="" if result.stderr.endswith("\n") else "\n", flush=True)
        return result.returncode, result.stdout, result.stderr

    def extract_code(self, text):
        """AI 응답에서 코드 블록만 추출"""
        code_block = re.search(r"```python\n(.*?)\n```", text, re.DOTALL)
        if code_block:
            return code_block.group(1).strip()
        return text.replace("```", "").strip()

    def fix_and_run(self, max_retries=15):
        for i in range(max_retries):
            print(f"\n--- [자율 수정 시뮬레이션 {i+1}회차] ---")
            return_code, stdout, stderr = self.run_target()

            if return_code == 0:
                print("✅ 대상 스크립트가 정상 종료했습니다.", flush=True)
                break
            
            combined_err = (stderr or "") + "\n" + (stdout or "")
            # 에러 로그가 너무 길면 핵심(마지막 20줄)만 추출
            error_msg = "\n".join(combined_err.splitlines()[-20:])
            print(f"❌ 에러 발생 (코드 {return_code}):\n{error_msg}")

            # 패키지 미설치 자동 해결
            if "ModuleNotFoundError" in combined_err:
                try:
                    lib_name = re.search(r"named '([^']+)'", combined_err).group(1)
                    print(f"📦 패키지 설치 시도: {lib_name}")
                    subprocess.run(
                        [sys.executable, "-m", "pip", "install", lib_name],
                        check=False,
                    )
                    continue
                except Exception:
                    pass

            llm = self._get_llm()
            if llm is None:
                print(
                    "⚠️ GOOGLE_API_KEY 또는 langchain이 없어 AI 자동 수정을 할 수 없습니다. "
                    "위 에러를 수동으로 수정하세요.",
                    flush=True,
                )
                break

            # AI에게 수정 요청
            try:
                from langchain_core.messages import HumanMessage

                with open(self.target_file, "r", encoding="utf-8") as f:
                    current_code = f.read()

                prompt = f"""
                너는 파이썬 자율 수정 에이전트야. 아래 코드를 실행했을 때 발생한 에러를 분석해서 전체 코드를 다시 짜줘.
                
                [현재 코드]
                {current_code}
                
                [에러 메시지]
                {combined_err}
                
                반드시 다른 설명 없이 ```python ... ``` 블록 안에 수정된 전체 코드를 넣어줘.
                특히 Playwright 사용 시 user_agent를 중복으로 넣지 않도록 주의해.
                """

                print("🤖 AI 분석 및 코드 수정 중...")
                response = llm.invoke([HumanMessage(content=prompt)])
                fixed_code = self.extract_code(response.content)

                if fixed_code and len(fixed_code) > 50:
                    with open(self.target_file, "w", encoding="utf-8") as f:
                        f.write(fixed_code)
                    print("🛠️ 파일 수정 완료. 다시 시뮬레이션을 시작합니다.")
                    time.sleep(2)
                else:
                    print("⚠️ AI 응답이 유효하지 않습니다. 다시 시도합니다.")

            except Exception as e:
                print(f"⚠️ 에이전트 내부 오류 발생: {e}")
                time.sleep(5)

if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(
        description="대상 파이썬 스크립트를 실행하고, 실패 시(선택) Gemini로 수정 시도"
    )
    p.add_argument(
        "target_script",
        nargs="?",
        default="smartstore_monitor_and_editor.py",
        help="실행할 파이썬 스크립트 파일명",
    )
    p.add_argument(
        "--full-ui",
        action="store_true",
        help="브라우저·URL 입력 모드 (출력 가로채기 없음 — 이 터미널에서만 실행하세요)",
    )
    args = p.parse_args()

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    if args.full_ui:
        cmd = [sys.executable, args.target_script]
        print(f"[agent] 전체 UI 모드 — {args.target_script} 실행 중 (Ctrl+C 중단)\n", flush=True)
        raise SystemExit(subprocess.run(cmd, env=env).returncode)

    # Par défaut, on exécute en mode non-interactif si le script le supporte
    # (ici: smartstore_monitor_and_editor.py --monitor-only). Pour l'UI, utiliser --full-ui.
    agent = UltimateAutoAgent(args.target_script)
    print(f"[agent] Exécution (mode par défaut) : {args.target_script}\n", flush=True)
    agent.fix_and_run()