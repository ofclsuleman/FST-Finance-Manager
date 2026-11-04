@echo off
cd /d "%~dp0"
where pythonw >nul 2>nul && (start "" pythonw fst_finance.py & exit /b)
python fst_finance.py
if errorlevel 1 pause
