@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PY=C:\Users\hymin\AppData\Local\Python\bin\python.exe
echo [스마트스토어 SEO] 판매자센터 메타/태그 가이드 생성
"%PY%" seo_fixes.py
echo.
echo 가이드: generated_content\SEO_붙여넣기_가이드.md
pause
