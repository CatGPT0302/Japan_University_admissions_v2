@echo off
setlocal

set "ROOT=%~dp0"
set "FRONTEND=%ROOT%frontend"

echo Starting Partner service center at http://127.0.0.1:5175 ...
start "admissions_v2_partner" cmd /k "cd /d ""%FRONTEND%"" && set VITE_APP_SURFACE=partner&& set VITE_API_BASE_URL=http://127.0.0.1:8000&& npm run dev:partner"

echo.
echo Partner service center window opened.
