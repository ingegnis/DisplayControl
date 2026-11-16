#!/usr/bin/env python3
"""Provision the only runtime dependency needed by Carisma AKP03E controller."""
from __future__ import annotations
import importlib.util, subprocess, sys

PIN='hidapi==0.15.0'

def main():
    print('CARISMA / SETUP CONTROLLER AKP03E')
    print('Python:',sys.version.split()[0],sys.executable)
    if sys.version_info < (3,11):
        print('ERRORE: serve Python 3.11 o successivo.');return 2
    if importlib.util.find_spec('hid') is None:
        print('hidapi non trovato. Installazione wheel binaria fissata:',PIN)
        cmd=[sys.executable,'-m','pip','install','--only-binary=:all:','--disable-pip-version-check',PIN]
        r=subprocess.run(cmd)
        if r.returncode:
            print('ERRORE: installazione hidapi fallita.');return r.returncode
    try:
        import hid
        devices=hid.enumerate(0x0300,0x3002)
        print('hidapi: OK')
        print('AKP03E collegati:',len(devices))
        for d in devices:
            print(' -',d.get('product_string') or 'AKP03E','usage_page=',hex(d.get('usage_page') or 0))
    except Exception as exc:
        print('ERRORE hidapi:',exc);return 3
    print('\nSETUP: OK')
    print('Ora genera un codice in Carisma Prompt e avvia Configura_Controller_AKP03E_Windows.bat')
    return 0

if __name__=='__main__':raise SystemExit(main())
