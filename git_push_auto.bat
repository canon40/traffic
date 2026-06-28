@echo off
chcp 65001 >nul
cd /d "D:\@code\traffic"

echo [0/3] 변경 사항 확인...
git status --short
git diff --quiet
set UNSTAGED=%errorlevel%
git diff --cached --quiet
set STAGED=%errorlevel%
if %UNSTAGED%==0 if %STAGED%==0 (
    echo === 커밋할 변경 없음 ===
    pause
    exit /b 0
)

echo [1/3] 변경 사항 스테이징 중 (.gitignore 반영)...
git add -A

:: .env 유출 방지
git reset HEAD .env >nul 2>&1

echo [2/3] PowerShell 기반 날짜/시간 포맷으로 자동 커밋 생성 중...
for /f "usebackq tokens=*" %%i in (`powershell -NoProfile -Command "Get-Date -Format 'yyyy-MM-dd_HHmm'"`) do set "datetime=%%i"

git commit -m "auto: 캠페인 작업 완료 및 스케줄러 업데이트 (%datetime%)"
if errorlevel 1 (
    echo === 커밋 실패 또는 변경 없음 ===
    pause
    exit /b 1
)

echo [3/3] 원격 저장소(canon40/traffic main)로 안전하게 푸시 중...
git push origin main
if errorlevel 1 (
    echo === 푸시 실패 — 인증 또는 네트워크 확인 ===
    pause
    exit /b 1
)

echo === 자동 깃푸시 완료 함 ===
git log -1 --oneline
pause
