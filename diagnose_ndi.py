#!/usr/bin/env python3
"""Read-only dependency and optional LAN discovery checks. No downloads/install."""
from __future__ import annotations
import argparse
import ctypes
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import time
from ndi.native import Runtime, NDIError
from ndi.gateway import ffmpeg_binary

VERSION = '0.4.1'


def encoder_names(text: str) -> set[str]:
    """Parse codec names, not substrings in descriptions or build options."""
    return set(re.findall(r'^\s*[A-Za-z.]{6}\s+(\S+)\s', text, re.MULTILINE))


def probe_ffmpeg(binary: str, smoke: bool = False) -> dict:
    result = {'available': False, 'path': binary, 'encoders': False,
              'smoke_test': 'non eseguito', 'error': ''}
    if not binary:
        result['error'] = 'FFmpeg non trovato.'
        return result
    try:
        p = subprocess.run([binary, '-hide_banner', '-encoders'], capture_output=True,
                           text=True, encoding='utf-8', errors='replace', timeout=20)
        names = encoder_names(p.stdout)
        result['encoders'] = p.returncode == 0 and {'libx264', 'aac'} <= names
        if not result['encoders']:
            result['error'] = 'FFmpeg non utilizzabile o encoder libx264/AAC assenti. ' + p.stderr[-600:]
            return result
        if smoke:
            with tempfile.TemporaryDirectory(prefix='carisma-codec-test-') as folder:
                output = Path(folder) / 'codec-test.mp4'
                command = [binary, '-hide_banner', '-nostdin', '-loglevel', 'error', '-y',
                           '-f', 'lavfi', '-i', 'color=c=black:s=64x64:r=15:d=1',
                           '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo',
                           '-t', '1', '-pix_fmt', 'yuv420p', '-c:v', 'libx264',
                           '-preset', 'ultrafast', '-c:a', 'aac',
                           '-movflags', '+frag_keyframe+empty_moov', '-shortest', str(output)]
                p = subprocess.run(command, capture_output=True, text=True,
                                   encoding='utf-8', errors='replace', timeout=45)
                blob = output.read_bytes() if output.is_file() else b''
                if p.returncode or len(blob) < 1024 or not all(tag in blob for tag in (b'ftyp', b'avcC', b'mp4a')):
                    result['smoke_test'] = 'fallito'
                    result['error'] = 'Conversione di prova H.264/AAC fallita. ' + p.stderr[-1200:]
                    return result
                result['smoke_test'] = 'OK'
        result['available'] = True
    except (OSError, subprocess.SubprocessError) as exc:
        result['error'] = str(exc)
    return result


def probe_ndi(root: Path, library: str = '', seconds: float = 0) -> dict:
    runtime = Runtime(root, library, os.environ.get('CARISMA_NDI_EXTRA_IPS', ''))
    result = {'available': False, 'version': '', 'path': '', 'error': '',
              'sources': [], 'discovery': 'non eseguita', 'discovery_error': ''}
    try:
        result.update(runtime.status())
        result['path'] = runtime.path
        if result['available'] and seconds > 0:
            try:
                deadline = time.monotonic() + min(30, seconds)
                while time.monotonic() < deadline:
                    result['sources'] = runtime.sources()
                    time.sleep(.25)
                result['discovery'] = 'OK'
            except (NDIError, OSError) as exc:
                result['discovery'] = 'errore'
                result['discovery_error'] = str(exc)
    except (OSError, NDIError) as exc:
        result['error'] = str(exc)
    finally:
        runtime.close()
    return result


def check(root: Path, library: str = '', ffmpeg: str = '', seconds: float = 0,
          smoke: bool = False) -> dict:
    py_ok = sys.version_info >= (3, 9) and ctypes.sizeof(ctypes.c_void_p) == 8
    ff = probe_ffmpeg(ffmpeg_binary(root, ffmpeg), smoke)
    ndi = probe_ndi(root, library, seconds)
    return {'schema': 1, 'version': VERSION,
            'system': platform.system() + ' ' + platform.machine(),
            'python': {'available': py_ok, 'version': platform.python_version(),
                       'bits': ctypes.sizeof(ctypes.c_void_p) * 8, 'path': sys.executable},
            'ffmpeg': ff, 'ndi': ndi,
            'dependencies_ok': bool(py_ok and ff['available'] and ndi['available'])}


def print_report(report: dict) -> None:
    print('\nCARISMA / VERIFICA NDI v' + VERSION + '\n')
    print('Sistema:', report['system'])
    py, ff, ndi = report['python'], report['ffmpeg'], report['ndi']
    print('Python:', py['version'], str(py['bits']) + ' bit', '- OK' if py['available'] else '- NON COMPATIBILE')
    print('Interprete:', py['path'])
    print('FFmpeg:', ff['path'] or 'NON TROVATO')
    print('Encoder H.264/AAC:', 'OK' if ff['encoders'] else 'NON DISPONIBILI')
    print('Conversione di prova:', ff['smoke_test'])
    if ff['error']:
        print('Dettaglio FFmpeg:', ff['error'])
    print('Runtime NDI:', ndi['version'] if ndi['available'] else ndi['error'])
    if ndi['path']:
        print('Libreria NDI:', ndi['path'])
    if ndi['discovery'] == 'OK':
        print('Sorgenti NDI rilevate:', len(ndi['sources']))
        for source in ndi['sources']:
            print(' -', source['name'], '/', source['address'])
        if not ndi['sources']:
            print('AVVISO: nessuna sorgente attiva. Non e un errore di installazione.')
    elif ndi['discovery_error']:
        print('AVVISO discovery:', ndi['discovery_error'])
    print('\nDIPENDENZE:', 'OK' if report['dependencies_ok'] else 'DA COMPLETARE')
    print('Questi controlli non certificano ancora ricezione NDI reale o sorgenti HX/H.265.')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Verifica locale in sola lettura NDI / FFmpeg')
    parser.add_argument('--library', default='')
    parser.add_argument('--ffmpeg', default='')
    parser.add_argument('--seconds', type=float, default=5)
    parser.add_argument('--smoke-test', action='store_true')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    report = check(Path(__file__).resolve().parent, args.library, args.ffmpeg,
                   max(0, args.seconds), args.smoke_test)
    if args.json:
        print(json.dumps(report, ensure_ascii=True))
    else:
        print_report(report)
        print('Verifica in sola lettura: nessun download e nessuna installazione.')
    return 0 if report['dependencies_ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
