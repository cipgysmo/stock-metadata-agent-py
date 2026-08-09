@echo off
REM Build script for Windows
echo === AI Stock Metadata Agent - Windows Build ===

REM Create virtual environment if needed
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt
pip install pyinstaller

REM Build with PyInstaller
echo Building application...
pyinstaller --clean stock-metadata-agent.spec

echo.
echo === Build Complete ===
echo App location: dist\stock-metadata-agent.exe

pause
