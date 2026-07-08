@echo off
setlocal EnableExtensions

set "REPO_URL=https://github.com/linaelmarzouki-etu-dev/interview-screen.git"
if not defined INSTALL_DIR set "INSTALL_DIR=%USERPROFILE%\interview-screen-client"
if not defined VPS_URL set "VPS_URL=https://139-84-130-152.sslip.io"
set "BRANCH=main"

echo === MCQ Laptop Client (Windows) ===
echo Install dir: %INSTALL_DIR%
echo VPS URL:     %VPS_URL%
echo.
echo Note: Laptop does NOT need a license key.
echo       Open your license URL on PHONE only.
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo Python is required. Install from https://www.python.org/downloads/
  exit /b 1
)

if not exist "%INSTALL_DIR%\.git" (
  echo Cloning from GitHub...
  git clone --depth 1 --branch %BRANCH% %REPO_URL% "%INSTALL_DIR%"
  if errorlevel 1 (
    echo Git clone failed. Install Git or download ZIP from GitHub.
    exit /b 1
  )
) else (
  echo Updating existing install...
  git -C "%INSTALL_DIR%" pull --ff-only origin %BRANCH%
)

cd /d "%INSTALL_DIR%"

if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
)

call .venv\Scripts\pip install --upgrade pip -q
call .venv\Scripts\pip install -r requirements-client.txt -q

> client.env echo VPS_URL=%VPS_URL%
>> client.env echo SCREEN_MONITOR=1

echo.
echo Installed successfully.
echo.
echo Before exam (run once on laptop, leave open):
echo   cd /d %INSTALL_DIR%
echo   start-laptop-client.bat
echo.
echo On phone, open your license URL:
echo   %VPS_URL%/u/YOURKEY
echo.
pause