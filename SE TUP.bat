@echo off
python --version > nul 2>&1
if %errorlevel% equ 0 (
    echo Python is installed.
) else (
    echo Python is not installed.
)
pip install -r %cd%\requires.txt
pause