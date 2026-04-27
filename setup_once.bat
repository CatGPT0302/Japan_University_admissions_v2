@echo off
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"

echo [1/6] Preparing Python virtual environment...
if not exist ".venv\Scripts\activate.bat" (
  py -3.13 -m venv .venv
  if errorlevel 1 (
    echo Failed to create .venv. Please make sure Python 3.13 is installed.
    pause
    exit /b 1
  )
)

echo [2/6] Installing backend dependencies...
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pypdfium2 Pillow
if errorlevel 1 (
  echo Failed to install Python dependencies.
  pause
  exit /b 1
)

echo [3/6] Preparing backend env file...
if not exist ".env" (
  copy ".env.example" ".env" >nul
)

echo [4/6] Preparing frontend env file...
if not exist "frontend\.env" (
  copy "frontend\.env.example" "frontend\.env" >nul
)

echo [5/6] Installing frontend dependencies...
cd /d "%ROOT%frontend"
npm install
if errorlevel 1 (
  echo Failed to install frontend dependencies.
  pause
  exit /b 1
)

echo [6/6] Done.
echo Please edit "%ROOT%.env" and set OPENAI_API_KEY before extraction.
pause

