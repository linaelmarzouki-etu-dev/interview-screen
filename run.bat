@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
  call .venv\Scripts\pip install -r requirements.txt
)

if not exist ".env" (
  echo Copy .env.example to .env and set GROQ_API_KEY first.
  exit /b 1
)

.venv\Scripts\python.exe -m interview_assistent %*