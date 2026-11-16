@echo off
setlocal
cd /d "%~dp0"
echo CARISMA / ABBINAMENTO CONTROLLER AJAZZ AKP03E
where py >nul 2>nul && (py -3 akp03e_controller.py --setup) || (python akp03e_controller.py --setup)
pause
