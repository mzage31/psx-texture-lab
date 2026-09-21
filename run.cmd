@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON=py"
) else (
    set "PYTHON=python"
)

%PYTHON% -c "import PIL" >nul 2>nul
if errorlevel 1 (
    echo Installing required packages...
    %PYTHON% -m pip install -r "app\requirements.txt"
    if errorlevel 1 (
        echo.
        echo Installation failed. Make sure Python is installed and available in PATH.
        pause
        exit /b 1
    )
)

cd /d "%~dp0app"
%PYTHON% PSXTextureWeb.py

if errorlevel 1 (
    echo.
    echo The playground stopped with an error.
    pause
)
