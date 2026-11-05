@echo off
chcp 65001 > nul
cd /d "%~dp0\.."
python tools.py restore %*
exit /b %errorlevel%
