@echo off
REM Configure port (change this value to use a different port)
set PORT=5000

echo Starting Accredit Helper Pro...
echo.


cd Abet-Helper-Pro

REM Activate virtual environment and install dependencies if needed
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if requirements are installed
pip freeze | findstr /c:"Flask" > nul
if %errorlevel% neq 0 (
    echo Installing dependencies...
    pip install -r requirements.txt
    echo Dependencies installed.
)

echo.
echo Starting Accredit Helper Pro application...
echo The application will be available at http://localhost:%PORT%
echo Press Ctrl+C to stop the server
echo.

REM Start the application
python app.py %PORT%

REM Keep window open if there's an error
if %errorlevel% neq 0 (
    echo.
    echo An error occurred while running the application.
    pause
) 