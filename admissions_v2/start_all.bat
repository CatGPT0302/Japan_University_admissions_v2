@echo off
setlocal

set "ROOT=%~dp0"

echo admissions_v2 now uses separate local systems.
echo Redirecting to start_all_surfaces.bat ...
echo.

call "%ROOT%start_all_surfaces.bat"
