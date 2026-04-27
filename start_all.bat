@echo off
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"

if not exist ".venv\Scripts\activate.bat" (
  echo .venv not found. Run setup_once.bat first.
  pause
  exit /b 1
)

echo Starting backend at http://localhost:8000 ...
start "admissions_v2_backend" cmd /k "cd /d ""%ROOT%"" && call "".venv\Scripts\activate.bat"" && python -m uvicorn scripts.api:app --reload --host 127.0.0.1 --port 8000"

echo Starting frontend at http://localhost:5173 ...
start "admissions_v2_frontend" cmd /k "cd /d ""%ROOT%frontend"" && npm run dev"

echo.
echo Started:
echo   Backend  - http://localhost:8000
echo   Frontend - http://localhost:5173
echo.
pause

