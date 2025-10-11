@echo off
echo ========================================
echo AWS Lambda Auto-Deploy Watcher
echo ========================================
echo.
echo Watching Lambda/ folder for changes...
echo Press Ctrl+C to stop
echo.

cd /d "%~dp0.."

:watch_loop
timeout /t 5 /nobreak >nul

REM Check if any Lambda files changed in last 10 seconds
forfiles /p Lambda /m *.py /c "cmd /c if @fdate gtr %date:~-4%-%date:~4,2%-%date:~7,2% echo File changed: @file && call Scripts\deploy-clean.bat" 2>nul

goto watch_loop