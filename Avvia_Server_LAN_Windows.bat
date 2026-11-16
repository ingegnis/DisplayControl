@echo off
setlocal
cd /d "%~dp0"
echo CARISMA - AVVIO PER PLAYER FISICI SULLA LAN
echo Usa solo su rete privata fidata. Nessuna modifica automatica al firewall.
if exist "%~dp0Config_Locale.bat" call "%~dp0Config_Locale.bat"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Windows_Carisma.ps1" -Action StartLan
pause
