@echo off
cd /d "%~dp0"
if exist "%~dp0Output\TouchPrintBridge\KAY_Touch_Print_Bridge.exe" (
  start "" "%~dp0Output\TouchPrintBridge\KAY_Touch_Print_Bridge.exe"
  exit /b
)
py -3 local_print_bridge.py
if errorlevel 1 (
  echo Install Python and run: py -3 -m pip install -r requirements-pos-lite.txt
  pause
)
