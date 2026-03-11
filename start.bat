@echo off
REM DeskPilot local starter (Vercel-compatible architecture)
REM Starts the local API at http://127.0.0.1:8000

echo Checking for STEP_API_KEY...
if "%STEP_API_KEY%"=="" (
    echo WARNING: STEP_API_KEY environment variable is not set!
    echo.
    echo Set it in your environment before running:
    echo   set STEP_API_KEY=your_api_key_here
    echo.
    pause
    exit /b 1
)

echo.
echo Starting DeskPilot API on http://127.0.0.1:8000
echo Open index.html in your browser to use the chat UI.
echo Press Ctrl+C to stop the server.
echo.

python api\index.py
