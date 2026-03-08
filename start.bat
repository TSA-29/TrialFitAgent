@echo off
REM BulkBot Web UI Starter
REM Make sure STEP_API_KEY is set before running this script

echo Checking for STEP_API_KEY...
if "%STEP_API_KEY%"=="" (
    echo WARNING: STEP_API_KEY environment variable is not set!
    echo.
    echo Please set your API key in one of these ways:
    echo.
    echo Option 1: Create a .env file (Easiest)
    echo   1. Copy .env.example to .env
    echo   2. Edit .env and add: STEP_API_KEY=your_actual_key_here
    echo.
    echo Option 2: Set environment variable temporary
    echo   set STEP_API_KEY=your_api_key_here
    echo.
    echo Option 3: Set permanent environment variable
    echo   setx STEP_API_KEY "your_api_key_here"
    echo.
    pause
    exit /b 1
)

echo.
echo Starting BulkBot Web UI...
echo The UI will open in your browser at http://localhost:8000
echo Press Ctrl+C to stop the server
echo.

chainlit run ui.py -w
