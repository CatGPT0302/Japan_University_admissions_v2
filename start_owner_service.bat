@echo off
setlocal

set "ROOT=%~dp0"
set "FRONTEND=%ROOT%frontend"

echo Starting Owner partner-management site at http://127.0.0.1:5174 ...
start "admissions_v2_owner_service" cmd /k "cd /d ""%FRONTEND%"" && set VITE_APP_SURFACE=owner-service&& set VITE_API_BASE_URL=http://127.0.0.1:8000&& npm run dev:owner-service"

echo.
echo Owner partner-management window opened.
