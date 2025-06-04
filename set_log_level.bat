@echo off
echo Accredit Helper Pro - Logging Level Configuration
echo ==================================================
echo.
echo Current logging levels:
echo 1. CRITICAL - Only critical errors (least logging)
echo 2. ERROR    - Errors only  
echo 3. WARNING  - Warnings and errors (RECOMMENDED)
echo 4. INFO     - General information + warnings + errors
echo 5. DEBUG    - All detailed information (MOST logging, slowest)
echo.
echo WARNING: DEBUG and INFO levels can generate massive log files
echo and significantly slow down the /calculation/all_courses page.
echo.

set /p choice="Enter your choice (1-5) or press Enter for default (WARNING): "

if "%choice%"=="1" (
    set LOG_LEVEL=CRITICAL
) else if "%choice%"=="2" (
    set LOG_LEVEL=ERROR
) else if "%choice%"=="3" (
    set LOG_LEVEL=WARNING
) else if "%choice%"=="4" (
    set LOG_LEVEL=INFO
) else if "%choice%"=="5" (
    set LOG_LEVEL=DEBUG
) else (
    set LOG_LEVEL=WARNING
    echo Using default: WARNING
)

echo.
echo Setting LOG_LEVEL to %LOG_LEVEL%
echo This will reduce excessive logging and improve performance.
echo.
echo Starting Accredit Helper Pro...
python app.py

pause 