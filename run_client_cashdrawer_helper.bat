@echo off
setlocal

set "PRINTER=%~1"
if "%PRINTER%"=="" (
    set /p "PRINTER=Receipt printer name [GA-E200 Series]: "
)
if "%PRINTER%"=="" set "PRINTER=GA-E200 Series"

cd /d "%~dp0"
echo ZAY POS Client Cash Drawer Helper
echo Printer: %PRINTER%
echo URL:     http://127.0.0.1:8765
echo.
echo Keep this window open while using browser cashier on this client PC.
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 "%~dp0run_client_cashdrawer_helper.py" --printer "%PRINTER%" --port 8765
) else (
    python "%~dp0run_client_cashdrawer_helper.py" --printer "%PRINTER%" --port 8765
)

echo.
echo Client cash drawer helper stopped.
pause
