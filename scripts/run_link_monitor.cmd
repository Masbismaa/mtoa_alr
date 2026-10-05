@echo off
setlocal

cd /d "%~dp0.."
if not exist "logs" mkdir "logs"

".venv\Scripts\python.exe" -m flask --app run check-links >> "logs\link-monitor.log" 2>&1

