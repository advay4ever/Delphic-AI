@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0" || exit /b 1

if not exist "run_app.py" goto incomplete
if not exist "requirements.txt" goto incomplete

call py -3 -I -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_COMMAND=py -3"
  goto launch
)
call python -I -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_COMMAND=python"
  goto launch
)
call python3 -I -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_COMMAND=python3"
  goto launch
)
echo Delphic AI needs a working Python 3.10 or newer installation.
echo Install Python from https://www.python.org/downloads/ and include the Python launcher or add Python to PATH.
echo If Python opens the Microsoft Store instead, install Python and reopen this launcher.
set "launcher_status=1"
goto finish

:incomplete
echo Extract the entire ZIP into a writable folder before starting Delphic AI.
echo Keep run_windows.bat with all the other app files.
set "launcher_status=1"
goto finish

:launch
echo Starting Delphic AI. First startup downloads its Python libraries.
echo Keep this command window open while using the app.
call %PYTHON_COMMAND% run_app.py
set "launcher_status=%ERRORLEVEL%"
if "%launcher_status%"=="0" goto finish
if "%launcher_status%"=="130" goto finish
echo Delphic AI stopped with an error. Read the message above before retrying.

:finish
echo.
if not "%DELPHIC_NO_PAUSE%"=="true" pause
exit /b %launcher_status%
