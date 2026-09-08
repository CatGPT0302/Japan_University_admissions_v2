@echo off
setlocal

set "ROOT=%~dp0"
set "FRONTEND=%ROOT%frontend"

echo Starting Owner data workspace at http://127.0.0.1:5173 ...
start "admissions_v2_owner" cmd /k "cd /d ""%FRONTEND%"" && set VITE_APP_SURFACE=owner&& set VITE_API_BASE_URL=http://127.0.0.1:8000&& npm run dev:owner"

echo.
echo Owner data workspace window opened.
