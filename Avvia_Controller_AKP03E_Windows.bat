@echo off
setlocal
cd /d "%~dp0"
title Carisma Prompt - AJAZZ AKP03E
where py >nul 2>nul && (py -3 akp03e_controller.py) || (python akp03e_controller.py)
pause
