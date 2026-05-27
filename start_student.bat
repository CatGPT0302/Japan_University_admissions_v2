@echo off
setlocal

set "ROOT=%~dp0"
set "FRONTEND=%ROOT%frontend"

echo Starting Student frontend at http://127.0.0.1:5176 ...
start "admissions_v2_student" cmd /k "cd /d ""%FRONTEND%"" && set VITE_APP_SURFACE=student&& set VITE_API_BASE_URL=http://127.0.0.1:8000&& npm run dev:student"

echo.
echo Student frontend window opened.
