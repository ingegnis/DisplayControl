@echo off
setlocal
cd /d "%~dp0"
echo CARISMA / TEST USB AJAZZ AKP03E
where py >nul 2>nul && (py -3 akp03e_controller.py --diagnose --diagnose-seconds 12) || (python akp03e_controller.py --diagnose --diagnose-seconds 12)
pause
