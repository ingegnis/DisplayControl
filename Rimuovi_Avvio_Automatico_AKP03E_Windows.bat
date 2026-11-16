@echo off
setlocal
set "OUT=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Carisma_AKP03E_Controller.cmd"
if exist "%OUT%" del "%OUT%"
echo Avvio automatico Carisma AKP03E rimosso.
pause
