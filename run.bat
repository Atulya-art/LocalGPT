@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title LocalGPT

set "MODEL=%LOCALGPT_MODEL%"
if not defined MODEL set "MODEL=llama3.2:3b"
set "HOST=%LOCALGPT_HOST%"
if not defined HOST set "HOST=127.0.0.1"
set "PORT=%LOCALGPT_PORT%"
if not defined PORT set "PORT=5000"
set "BROWSER_HOST=%HOST%"
if "%HOST%"=="0.0.0.0" set "BROWSER_HOST=127.0.0.1"

echo ============================================================
echo  LocalGPT - private local AI assistant
echo  Model: %MODEL%
echo  URL:   http://%BROWSER_HOST%:%PORT%
echo ============================================================
echo.

where ollama >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Ollama was not found in PATH.
    echo Install Ollama from https://ollama.com/download and run this file again.
    echo.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creating Python virtual environment...
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3 -m venv .venv
    ) else (
        python -m venv .venv
    )
    if errorlevel 1 (
        echo [ERROR] Could not create the virtual environment.
        echo Install Python 3.9 or newer from https://www.python.org/downloads/ and retry.
        echo.
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" -c "import flask, requests" >nul 2>nul
if errorlevel 1 (
    echo [2/3] Installing Python dependencies...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Dependency installation failed. Check your internet connection and retry.
        echo.
        pause
        exit /b 1
    )
)

echo [3/3] Checking Ollama...
powershell -NoProfile -Command "try { Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 3 | Out-Null; exit 0 } catch { exit 1 }"
if errorlevel 1 (
    echo Ollama is not running. Starting it in the background...
    start "" /min ollama serve
    timeout /t 4 /nobreak >nul
)

ollama list 2>nul | findstr /I /C:"%MODEL%" >nul
if errorlevel 1 (
    echo Model "%MODEL%" is not installed. Downloading it now...
    ollama pull "%MODEL%"
    if errorlevel 1 (
        echo [ERROR] Could not download the model. Run "ollama pull %MODEL%" manually.
        echo.
        pause
        exit /b 1
    )
)

echo.
echo Starting LocalGPT. Press Ctrl+C to stop the server.
if not "%LOCALGPT_NO_BROWSER%"=="1" (
    echo Opening http://%BROWSER_HOST%:%PORT% in your browser...
    start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://%BROWSER_HOST%:%PORT%'"
)
".venv\Scripts\python.exe" app.py

echo.
echo LocalGPT has stopped.
pause
endlocal
