@echo off
cd /d "%~dp0"
python -m pip install --upgrade pyinstaller || goto :fail
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name "FST - Finance Management" ^
  --icon "assets\icon.ico" ^
  --add-data "assets;assets" ^
  fst_finance.py || goto :fail
echo.
echo Build complete: dist\FST - Finance Management.exe
exit /b 0
:fail
echo Build failed.
pause
exit /b 1
