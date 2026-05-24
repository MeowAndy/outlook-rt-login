@echo off
cd /d %~dp0
py -m venv .venv
.venv\Scripts\python.exe -m pip install -U pip
.venv\Scripts\pip.exe install -r requirements.txt
if "%HOST%"=="" set HOST=0.0.0.0
if "%PORT%"=="" set PORT=8765
.venv\Scripts\python.exe -m outlook_rt_login.web
pause
