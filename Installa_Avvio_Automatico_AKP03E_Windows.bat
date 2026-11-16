@echo off
setlocal
cd /d "%~dp0"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "OUT=%STARTUP%\Carisma_AKP03E_Controller.cmd"
>"%OUT%" echo @echo off
>>"%OUT%" echo cd /d "%~dp0"
>>"%OUT%" echo start "Carisma AKP03E" /min "%~dp0Avvia_Controller_AKP03E_Windows.bat"
echo Avvio automatico installato per l'utente corrente:
echo %OUT%
echo Il controller partira al prossimo accesso Windows.
pause
