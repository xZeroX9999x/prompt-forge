@echo off
REM Run all Prompt Forge tests on Windows

echo ========================================
echo   Running all Prompt Forge tests
echo ========================================

python tests\test_compiler.py
if errorlevel 1 exit /b 1

echo.
python tests\test_integration.py
