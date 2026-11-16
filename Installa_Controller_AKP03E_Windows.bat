@echo off
setlocal
cd /d "%~dp0"
echo CARISMA / INSTALLA CONTROLLER AJAZZ AKP03E
where py >nul 2>nul && (py -3 setup_akp03e.py) || (python setup_akp03e.py)
pause
