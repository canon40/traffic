@echo off
REM Resolve a real python.exe (skip Microsoft Store stub).
set "PYEXE="
if exist "%~dp0.venv\Scripts\python.exe" (
  set "PYEXE=%~dp0.venv\Scripts\python.exe"
  goto :done
)
if exist "%LocalAppData%\Python\bin\python.exe" (
  set "PYEXE=%LocalAppData%\Python\bin\python.exe"
  goto :done
)
where py >nul 2>&1 && (
  for /f "delims=" %%I in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PYEXE=%%I"
  if defined PYEXE goto :done
)
for /f "delims=" %%I in ('where python 2^>nul') do (
  echo %%I | findstr /i "WindowsApps" >nul
  if errorlevel 1 (
    set "PYEXE=%%I"
    goto :done
  )
)
echo [ERROR] Python 3 을 찾을 수 없습니다. python.org 에서 설치하세요.
exit /b 1
:done
if not defined PYEXE (
  echo [ERROR] Python 3 을 찾을 수 없습니다.
  exit /b 1
)
