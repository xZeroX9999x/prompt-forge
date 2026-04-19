@echo off
setlocal

echo ============================================
echo   Prompt Forge -- install (Windows)
echo ============================================

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: python not found. Install Python 3.8+ from python.org first.
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo [OK] Python %PYVER% detected

if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat
echo [OK] venv activated

echo Installing dependencies...
python -m pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
pip install --quiet -e .
echo [OK] Dependencies installed

echo Initializing database...
python forge.py init

echo.
echo ============================================
echo   [OK] Installation complete
echo ============================================
echo.
echo Activate the environment before using:
echo   .venv\Scripts\activate.bat
echo.
echo Then try:
echo   forge compile "help me write an email declining a meeting"
echo   forge learn
echo   forge stats
echo.

endlocal
