@echo off
setlocal enabledelayedexpansion
title 留学生招生系统

set "ROOT=%~dp0"
cd /d "%ROOT%"

:: ─────────────────────────────────────────
::  颜色工具（只在支持的终端生效）
:: ─────────────────────────────────────────
set "LINE==================================================="

cls
echo %LINE%
echo   留学生招生系统  admissions_v2
echo %LINE%
echo.

:: ─────────────────────────────────────────
::  Step 1  Python 虚拟环境
:: ─────────────────────────────────────────
echo [1/5] 检查 Python 环境...

if exist ".venv\Scripts\activate.bat" (
    echo       已存在，跳过创建。
    goto :activate
)

echo       首次运行，创建虚拟环境（约需 1 分钟）...
py -3 -m venv .venv >nul 2>&1
if errorlevel 1 (
    echo.
    echo [错误] 未找到 Python。
    echo        请先安装 Python 3.10 以上版本：
    echo        https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)
echo       虚拟环境创建完成。

:activate
call ".venv\Scripts\activate.bat"

:: ─────────────────────────────────────────
::  Step 2  后端依赖
:: ─────────────────────────────────────────
echo [2/5] 检查后端依赖...

python -c "import fastapi, uvicorn, pdfplumber, openai" >nul 2>&1
if errorlevel 1 (
    echo       安装中，请稍候...
    python -m pip install --upgrade pip -q
    pip install -r requirements.txt -q
    pip install pypdfium2 Pillow openpyxl openai -q
    if errorlevel 1 (
        echo.
        echo [错误] 后端依赖安装失败，请检查网络连接。
        pause
        exit /b 1
    )
    echo       安装完成。
) else (
    echo       已安装，跳过。
)

:: ─────────────────────────────────────────
::  Step 3  环境变量文件
:: ─────────────────────────────────────────
echo [3/5] 检查配置文件...

if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo.
        echo ┌─────────────────────────────────────────┐
        echo │  首次运行：需要填写 API Key             │
        echo │                                         │
        echo │  请用记事本打开：                       │
        echo │    %ROOT%.env
        echo │                                         │
        echo │  填写 OPENAI_API_KEY=sk-proj-...        │
        echo │  保存后关闭记事本，按任意键继续。       │
        echo └─────────────────────────────────────────┘
        echo.
        start notepad "%ROOT%.env"
        pause
    ) else (
        echo       未找到 .env.example，跳过。
    )
) else (
    :: 检查 key 是否已填写
    findstr /c:"OPENAI_API_KEY=sk-" ".env" >nul 2>&1
    if errorlevel 1 (
        echo.
        echo [警告] .env 中尚未填写 OPENAI_API_KEY。
        echo        抽取功能将无法使用。
        echo        请编辑：%ROOT%.env
        echo.
    ) else (
        echo       配置正常。
    )
)

if not exist "frontend\.env" (
    if exist "frontend\.env.example" (
        copy "frontend\.env.example" "frontend\.env" >nul
    )
)

:: ─────────────────────────────────────────
::  Step 4  前端依赖
:: ─────────────────────────────────────────
echo [4/5] 检查前端依赖...

if exist "frontend\node_modules\.package-lock.json" (
    echo       已安装，跳过。
) else (
    echo       安装中（首次约需 1-2 分钟）...
    cd /d "%ROOT%frontend"
    npm install --silent
    if errorlevel 1 (
        echo.
        echo [错误] 前端依赖安装失败。
        echo        请确认已安装 Node.js：https://nodejs.org/
        pause
        exit /b 1
    )
    cd /d "%ROOT%"
    echo       安装完成。
)

:: ─────────────────────────────────────────
::  Step 5  启动服务
:: ─────────────────────────────────────────
echo [5/5] 启动服务...
echo.

:: 检查端口是否已占用
netstat -ano | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo       后端已在运行（端口 8000）。
    goto :start_frontend
)

start "后端 · admissions_v2" cmd /k "title 后端 · admissions_v2 && cd /d ""%ROOT%"" && call "".venv\Scripts\activate.bat"" && echo 后端启动中... && python -m uvicorn scripts.api:app --reload --host 127.0.0.1 --port 8000"
echo       后端已启动 → http://localhost:8000

:start_frontend
timeout /t 2 /nobreak >nul

netstat -ano | findstr ":5173 " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo       前端已在运行（端口 5173）。
    goto :open_browser
)

start "前端 · admissions_v2" cmd /k "title 前端 · admissions_v2 && cd /d ""%ROOT%frontend"" && npm run dev"
echo       前端已启动 → http://localhost:5173

:open_browser
echo.
echo       等待服务就绪...
timeout /t 4 /nobreak >nul

start "" "http://localhost:5173"

echo.
echo %LINE%
echo   启动完成！浏览器应已自动打开。
echo.
echo   后端  →  http://localhost:8000
echo   前端  →  http://localhost:5173
echo.
echo   关闭系统：直接关闭「后端」和「前端」两个窗口即可。
echo %LINE%
echo.
pause
