@echo off
setlocal
cd /d "%~dp0"

set "REPO_URL=https://github.com/mzage31/psx-texture-lab.git"

where git >nul 2>nul
if errorlevel 1 (
    echo Git is not installed or is not available in PATH.
    echo Download it from https://git-scm.com/download/win
    pause
    exit /b 1
)

echo Checking connection to GitHub...
git ls-remote "%REPO_URL%" HEAD >nul 2>nul
if errorlevel 1 (
    echo Unable to connect to the repository.
    echo Check your internet connection and GitHub access, then try again.
    pause
    exit /b 1
)

if not exist ".git" goto copied_folder

set "ORIGIN_URL="
for /f "delims=" %%R in ('git remote get-url origin 2^>nul') do set "ORIGIN_URL=%%R"
if not defined ORIGIN_URL (
    git remote add origin "%REPO_URL%"
) else if /i not "%ORIGIN_URL%"=="%REPO_URL%" (
    echo This folder is connected to a different repository:
    echo %ORIGIN_URL%
    echo Update cancelled to protect that repository.
    pause
    exit /b 1
)

echo Updating existing clone...
git fetch origin main
if errorlevel 1 goto update_failed
git switch main >nul 2>nul
if errorlevel 1 goto update_failed
git pull --ff-only origin main
if errorlevel 1 (
    echo.
    echo Update stopped because local changes or commits need attention.
    echo Your files were not overwritten.
    pause
    exit /b 1
)
goto update_complete

:copied_folder
echo This appears to be a copied folder. Connecting it to the official repository...
git init -b main
if errorlevel 1 goto update_failed
git remote add origin "%REPO_URL%"
if errorlevel 1 goto update_failed
git fetch origin main
if errorlevel 1 goto update_failed
git reset --hard origin/main
if errorlevel 1 goto update_failed
git branch --set-upstream-to=origin/main main >nul 2>nul
goto update_complete

:update_failed
echo.
echo Update failed. Review the message above and try again.
pause
exit /b 1

:update_complete
echo.
echo PSX Texture Lab is up to date.
pause
