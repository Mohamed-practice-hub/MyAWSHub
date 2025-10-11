@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Smart Lambda Deployment
echo ========================================

cd /d "%~dp0.."

REM Check if deployment folder exists and has recent files
set NEED_DEPLOY=0

REM Check if Lambda source files are newer than deployment
if exist Lambda\lambda_function.py (
    if not exist deployment\main-lambda\lambda_function.py (
        set NEED_DEPLOY=1
        echo Main Lambda needs deployment - no deployment copy found
    ) else (
        forfiles /p Lambda /m lambda_function.py /c "cmd /c if @fdate gtr %date:~-4%-%date:~4,2%-%date:~7,2% set NEED_DEPLOY=1" 2>nul
    )
)

if exist Lambda\performance-analyzer.py (
    if not exist deployment\performance-lambda\performance-analyzer.py (
        set NEED_DEPLOY=1
        echo Performance Lambda needs deployment - no deployment copy found
    )
)

if exist Lambda\sentiment-simple-lambda.py (
    if not exist deployment\sentiment-lambda\sentiment-simple-lambda.py (
        set NEED_DEPLOY=1
        echo Sentiment Lambda needs deployment - no deployment copy found
    )
)

if !NEED_DEPLOY! == 1 (
    echo.
    echo Changes detected - deploying...
    call Scripts\deploy-clean.bat
) else (
    echo.
    echo No changes detected - deployment up to date
    echo.
    echo To force deployment, run: Scripts\deploy-clean.bat
)

echo.
pause