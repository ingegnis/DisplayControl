#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ ! -x .controller-venv/bin/python ]; then python3 -m venv .controller-venv; fi
.controller-venv/bin/python setup_controllers.py
printf '\nLinux: se necessario installa manualmente 99-displaycontrol-controllers.rules nelle regole udev.\n'
printf 'Configurazione: sh Avvia_Controller_Linux_Mac.sh --setup\n'
