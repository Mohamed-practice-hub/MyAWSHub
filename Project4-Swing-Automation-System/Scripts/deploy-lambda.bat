@echo off
REM Windows batch wrapper for Lambda deployment script
REM This allows running the deployment from Windows Command Prompt

echo Starting Lambda Auto-Deployment...
echo.

REM Check if Git Bash is available
where bash >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Git Bash not found. Please install Git for Windows.
    echo Download from: https://git-scm.com/download/win
    pause
    exit /b 1
)

REM Run the bash script
bash "%~dp0deploy-lambda.sh" %*

REM Pause to see results
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Deployment failed. Check the error messages above.
    pause
) else (
    echo.
    echo Deployment completed successfully!
    timeout /t 3 >nul
)