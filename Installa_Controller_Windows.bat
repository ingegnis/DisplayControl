@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if exist ".controller-venv\Scripts\python.exe" goto install
if errorlevel 1 (python -m venv .controller-venv) else (py -3 -m venv .controller-venv)
if errorlevel 1 goto failed
:install
".controller-venv\Scripts\python.exe" setup_controllers.py
if errorlevel 1 goto failed
echo Installazione completata. Esegui Configura_Controller_Windows.bat una sola volta.
goto end
:failed
echo Installazione non completata. Controlla il messaggio sopra.
:end
pause
