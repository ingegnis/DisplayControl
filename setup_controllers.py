#!/usr/bin/env python3
"""Install pinned binary HID and image dependencies, not vendor applications."""
import importlib.util
import subprocess
import sys

REQUIREMENTS = {'hid':'hidapi==0.15.0', 'PIL':'Pillow==13.0.0'}

def main():
    if sys.version_info < (3,11):
        print('Per il servizio controller occorre Python 3.11 o successivo.');return 2
    missing = [pin for module,pin in REQUIREMENTS.items() if importlib.util.find_spec(module) is None]
    if missing:
        result = subprocess.run([sys.executable,'-m','pip','install','--only-binary=:all:',
                                 '--disable-pip-version-check',*missing])
        if result.returncode:return result.returncode
    import hid
    from controller_devices import identify
    print('Dipendenze controller: OK')
    for info in hid.enumerate():
        profile = identify(info)
        if profile:print('Riconosciuto:',profile.name)
    print('Genera un codice in Prompt, poi esegui controller_service.py --setup.')
    print('Se il servizio è già abbinato non serve ripetere il pairing per cambiare controller.')
    return 0

if __name__ == '__main__':raise SystemExit(main())
