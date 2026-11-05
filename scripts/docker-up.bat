@echo off
chcp 65001 > nul
cd /d "%~dp0\.."
python tools.py docker-up %*
exit /b %errorlevel%
