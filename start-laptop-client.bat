@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if exist client.env (
  for /f "usebackq tokens=1,* delims==" %%A in ("client.env") do (
    if /I "%%A"=="VPS_URL" set "VPS_URL=%%B"
    if /I "%%A"=="SCREEN_MONITOR" set "SCREEN_MONITOR=%%B"
    if /I "%%A"=="LICENSE_KEY" set "LICENSE_KEY=%%B"
  )
)

if not defined VPS_URL set "VPS_URL=https://139-84-130-152.sslip.io"
if not defined SCREEN_MONITOR set "SCREEN_MONITOR=1"
if not "%~1"=="" set "LICENSE_KEY=%~1"

if not defined LICENSE_KEY (
  set /p LICENSE_KEY="Enter your 8-letter license key (same as phone): "
)

if not exist ".venv\Scripts\python.exe" (
  echo Run install-windows-client.bat YOURKEY first.
  exit /b 1
)

echo Laptop key: %LICENSE_KEY%
echo Phone URL:  %VPS_URL%/u/%LICENSE_KEY%
echo.

.venv\Scripts\python.exe laptop_agent.py --vps %VPS_URL% --monitor %SCREEN_MONITOR% --key %LICENSE_KEY%
pause