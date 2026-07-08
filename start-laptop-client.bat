@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if exist client.env (
  for /f "usebackq tokens=1,* delims==" %%A in ("client.env") do (
    if /I "%%A"=="VPS_URL" set "VPS_URL=%%B"
    if /I "%%A"=="SCREEN_MONITOR" set "SCREEN_MONITOR=%%B"
  )
)

if not defined VPS_URL set "VPS_URL=https://139-84-130-152.sslip.io"
if not defined SCREEN_MONITOR set "SCREEN_MONITOR=1"

if not exist ".venv\Scripts\python.exe" (
  echo Run install-windows-client.bat first.
  exit /b 1
)

echo Connecting laptop to %VPS_URL% ...
echo Laptop: no license key needed - keep this window open.
echo Phone:  open https://139-84-130-152.sslip.io/u/YOURKEY then tap Grab laptop screen.
echo.

.venv\Scripts\python.exe laptop_agent.py --vps %VPS_URL% --monitor %SCREEN_MONITOR%
pause