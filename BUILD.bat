@echo off
python --version > nul 2>&1
if %errorlevel% equ 0 (
    echo Python is installed.
) else (
    echo Python is not installed.
)
pip install -U pyinstaller
pyinstaller --onefile --noconsole %cd%\TexturePacker_V3.py
move dist\TexturePacker_V3.exe %cd%\TexturePacker_V3.exe
pause