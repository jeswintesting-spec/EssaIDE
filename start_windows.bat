@echo off
echo Starting EssaIDE Setup...

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in your PATH.
    echo Please install Python 3.10 or newer from python.org
    pause
    exit /b
)

:: Create virtual environment if it doesn't exist
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
)

:: Activate and run
call venv\Scripts\activate.bat
echo Installing dependencies...
pip install -r requirements.txt -q
echo Launching IDE...
python main.py
pause
