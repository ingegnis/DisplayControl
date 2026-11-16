@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if exist ".controller-venv\Scripts\python.exe" (
  ".controller-venv\Scripts\python.exe" controller_service.py --diagnose --seconds 30
) else (
  if errorlevel 1 (python controller_service.py --diagnose --seconds 30) else (py -3 controller_service.py --diagnose --seconds 30)
)
pause
