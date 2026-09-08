@echo off
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"

call "%ROOT%start_backend.bat"
call "%ROOT%start_owner.bat"
call "%ROOT%start_owner_service.bat"
call "%ROOT%start_partner.bat"
call "%ROOT%start_student.bat"

echo.
echo Started separate local systems:
echo   Backend                 http://127.0.0.1:8000
echo   Owner data workspace    http://127.0.0.1:5173
echo   Owner partner service   http://127.0.0.1:5174
echo   Partner service center  http://127.0.0.1:5175
echo   Student frontend        http://127.0.0.1:5176
echo.
