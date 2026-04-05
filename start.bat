@echo off
chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8

cd /d "%~dp0"

echo ========================================
echo         Ralph GUI Launcher
echo ========================================
echo.

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

echo [CHECK] PySide6...
python -c "import PySide6" 2>nul
if %errorlevel% neq 0 (
    echo [INSTALL] Installing PySide6...
    pip install PySide6 PyYAML
)

echo.
echo [START] Launching Ralph GUI...
echo.
python run.py

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to start Ralph GUI
)
pause
