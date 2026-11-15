@echo off
:: =========================================================================
:: AI Clipper Agent Pro - Autonomous Short-Form Video Generator
:: Converts Long-Form Videos (YouTube/Local) into 9:16 Viral Shorts
:: =========================================================================
title AI Clipper Agent Pro
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python 3.10+ is required but not found in PATH.
    pause
    exit /b 1
)

if not exist "ffmpeg.exe" (
    where ffmpeg >nul 2>nul
    if %ERRORLEVEL% neq 0 (
        echo [INFO] FFmpeg binary not found. Running auto-setup...
        call setup_ffmpeg.bat
    )
)

echo ===================================================
echo     Launching AI Clipper Agent Pro Web Studio...
echo ===================================================
echo.
echo URL: http://localhost:8501
echo Opening your default browser...
echo Press Ctrl+C in this terminal window to stop the server.
echo.

python -m streamlit run app.py --server.headless false --browser.gatherUsageStats false

if %ERRORLEVEL% neq 0 (
    echo.
    echo [NOTICE] Application closed with exit code %ERRORLEVEL%.
    pause
)
