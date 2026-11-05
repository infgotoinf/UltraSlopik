@echo off
chcp 65001 > nul
cd /d "%~dp0\.."
python tools.py ports-check %*
exit /b %errorlevel%
