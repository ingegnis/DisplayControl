@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0Config_Locale.bat" call "%~dp0Config_Locale.bat"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Windows_Carisma.ps1" -Action Check
set "CARISMA_EXIT=%ERRORLEVEL%"
echo.
if not "%CARISMA_EXIT%"=="0" echo Operazione non completata. Leggi il messaggio sopra.
pause
exit /b %CARISMA_EXIT%
