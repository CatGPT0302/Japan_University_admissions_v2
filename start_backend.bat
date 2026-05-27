@echo off
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"

echo Starting backend at http://127.0.0.1:8000 ...
start "admissions_v2_backend" cmd /k "cd /d ""%ROOT%"" && python -m uvicorn scripts.api:app --host 127.0.0.1 --port 8000"

echo.
echo Backend window opened.
