@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\serve_app.py
) else (
  python scripts\serve_app.py
)
if errorlevel 1 pause
