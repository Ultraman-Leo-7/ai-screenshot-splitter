@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
set "PYTHONUTF8=1"
set "VENV_PY=%~dp0.venv\Scripts\python.exe"
if exist "%VENV_PY%" goto check_dependencies
where py >nul 2>nul
if not errorlevel 1 goto create_with_py
where python >nul 2>nul
if errorlevel 1 goto no_python
python -m venv "%~dp0.venv"
if errorlevel 1 goto failed
goto install_dependencies
:create_with_py
py -3 -m venv "%~dp0.venv"
if errorlevel 1 goto failed
goto install_dependencies
:check_dependencies
"%VENV_PY%" -c "from PIL import Image, ImageOps" >nul 2>nul
if not errorlevel 1 goto run
:install_dependencies
"%VENV_PY%" -m pip install --index-url https://pypi.org/simple -r "%~dp0requirements.txt"
if errorlevel 1 goto failed
:run
"%VENV_PY%" "%~dp0split_img.py" %*
set "RESULT=%ERRORLEVEL%"
if "%~1"=="" exit /b %RESULT%
pause
exit /b %RESULT%
:no_python
echo Python 3.11 or newer is required. Install Python and try again.
pause
exit /b 2
:failed
echo Setup failed. Check Python and your network, then try again.
pause
exit /b 2
