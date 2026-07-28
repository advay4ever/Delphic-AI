@echo off
cd /d "%~dp0"

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  py -3 run_app.py
) else (
  python run_app.py
)

echo.
pause
