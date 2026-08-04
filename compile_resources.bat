@echo off
echo Compiling Qt Resources...

REM Try Python module method
python -m PyQt6.pyrcc_main resources/resources.qrc -o resources_rc.py

if %errorlevel% == 0 (
    echo ✅ Resources compiled successfully!
) else (
    echo ❌ Failed to compile resources
    pause
)