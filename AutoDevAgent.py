import subprocess
import sys
import os
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

# 1. 설정 (본인의 API 키 입력)
API_KEY = "AIzaSyDK0OQ9UwfnXt7sBjfaWKFsc3zlGr-UeMc"
TARGET_FILE = "traffic_service.py" # 완성될 프로그램 파일명

class AutoDevAgent:
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o", openai_api_key=API_KEY, temperature=0)
        self.iteration = 0

    def run_command(self, command):
        """터미널 명령어를 실행하고 결과와 에러를 반환"""
        print(f"🚀 실행 중: {command}")
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return result.returncode, result.stdout, result.stderr

    def ask_ai(self, prompt):
        """AI에게 코드 작성 및 수정을 요청"""
        messages = [
            SystemMessage(content="당신은 자율형 소프트웨어 엔지니어입니다. 반드시 실행 가능한 '전체 코드'만 출력하세요. 설명은 필요 없습니다."),
            HumanMessage(content=prompt)
        ]
        response = self.llm.invoke(messages)
        # 코드 블록 기호 제거
        return response.content.replace("```python", "").replace("```", "").strip()

    def self_heal(self, requirement):
        """메인 루프: 설치 -> 실행 -> 에러 분석 -> 수정"""
        current_code = f"# Initial requirement: {requirement}"
        
        while True:
            self.iteration += 1
            print(f"\n--- 🔄 시뮬레이션 {self.iteration}회차 시작 ---")
            
            # 1. 파일 저장
            with open(TARGET_FILE, "w", encoding="utf-8") as f:
                f.write(current_code)

            # 2. 프로그램 실행
            code, stdout, stderr = self.run_command(f"{sys.executable} {TARGET_FILE}")

            if code == 0:
                print("✅ 성공: 프로그램이 에러 없이 완벽하게 작동합니다!")
                break
            
            print(f"❌ 에러 발생: {stderr}")

            # 3. 에러 분석 및 자동 해결 (라이브러리 설치 포함)
            if "ModuleNotFoundError" in stderr or "No module named" in stderr:
                # 모듈이 없는 경우 AI에게 설치 명령어 추출 요청
                install_prompt = f"다음 에러를 해결하기 위한 'pip install 패키지명' 명령어를 알려줘. 명령어만 딱 한 줄 출력해: {stderr}"
                install_cmd = self.ask_ai(install_prompt)
                self.run_command(install_cmd)
                continue # 설치 후 다시 실행

            # 4. 코드 자체의 로직 에러 수정
            fix_prompt = f"""
            [요구사항]
            {requirement}

            [현재 코드]
            {current_code}

            [발생한 에러]
            {stderr}

            이 에러를 수정하고 요구사항을 완벽히 충족하는 전체 코드를 다시 작성해줘. 
            라이브러리가 필요하다면 상단에 import 문을 반드시 포함해.
            """
            current_code = self.ask_ai(fix_prompt)
            print("🛠️ AI가 코드를 수정했습니다. 다시 시뮬레이션합니다.")

# 2. 에이전트 가동
if __name__ == "__main__":
    agent = AutoDevAgent()
    # 만들고자 하는 트래픽 프로그램의 상세 요구사항을 적으세요.
    user_goal = "특정 URL에 주기적으로 접속하여 트래픽을 발생시키고, 응답 속도를 로그 파일로 기록하는 프로그램을 만들어줘. 결과는 시각화해야해."
    agent.self_heal(user_goal)