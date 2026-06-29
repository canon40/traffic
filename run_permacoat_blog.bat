@echo off
chcp 65001 >nul
cd /d "%~dp0"
call run_blog_post.bat
