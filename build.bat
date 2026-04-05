@echo off
echo Building Ralph GUI...

REM Install dependencies if needed
pip install -r requirements.txt

REM Install PyInstaller
pip install pyinstaller

REM Build
pyinstaller pyinstaller.spec --clean

echo.
echo Build complete! Executable is in dist/RalphGUI/
pause
