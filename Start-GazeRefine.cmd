@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m desktop.app
) else (
  python -m desktop.app
)
if errorlevel 1 pause
