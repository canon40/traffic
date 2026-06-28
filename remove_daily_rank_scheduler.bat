@echo off
chcp 65001 >nul
set TASK_NAME=NanumLab-DailyRankTrack
schtasks /delete /tn "%TASK_NAME%" /f
if %errorlevel%==0 (
    echo 작업 스케줄러에서 %TASK_NAME% 삭제 완료
) else (
    echo 등록된 작업이 없거나 삭제 실패
)
pause
