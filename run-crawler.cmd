@echo off
setlocal EnableExtensions DisableDelayedExpansion
pushd "%~dp0" || (
    echo Extract all files to a writable folder and run this file again.
    pause
    exit /b 1
)
if not exist "crawler.py" goto :missing_files
if not exist "requirements.txt" goto :missing_files

set "gwtp_python=.venv\Scripts\python.exe"
if exist "%gwtp_python%" goto :run
set "gwtp_launcher=py -3"
%gwtp_launcher% -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>&1
if not errorlevel 1 goto :create_env
set "gwtp_launcher=python"
%gwtp_launcher% -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>&1
if errorlevel 1 goto :need_python

:create_env
%gwtp_launcher% -m venv ".venv" || goto :failed

:run
"%gwtp_python%" -c "import sys; sys.exit(sys.version_info < (3, 10))" || goto :need_python
"%gwtp_python%" -m pip --disable-pip-version-check install -r "requirements.txt" || goto :failed
"%gwtp_python%" "crawler.py" --output "result.csv" || goto :failed
echo.
echo CSV saved to "%CD%\result.csv"
pause
popd
exit /b 0

:missing_files
echo Extract the entire ZIP first. Keep this launcher beside crawler.py and requirements.txt.
goto :failed

:need_python
echo This crawler needs Python 3.10 or newer for Windows.
echo Download Python from https://www.python.org/downloads/windows/ and run this file in a freshly extracted folder.

:failed
echo.
echo The run did not finish. Please copy the error message above.
pause
popd
exit /b 1
