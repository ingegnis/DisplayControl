#!/usr/bin/env python3
"""Install the local player as the current Linux desktop user; preserve private data."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time
import urllib.request
from urllib.parse import urlsplit

SOURCE = Path(__file__).resolve().parents[1]
FILES = ('player_station.py', 'cluster.py', 'storage.py', 'ndi/__init__.py', 'ndi/gateway.py',
         'ndi/native.py', 'player.html', 'prompt_player.html', 'prompt_shared.js', 'branding.js',
         'favicon.svg', 'connect.html', 'physical_boot.js', 'station_sw.js', 'raspberry/kiosk.py')
MARKER = '# DisplayControl managed'
BEGIN, END = '# BEGIN DisplayControl player', '# END DisplayControl player'


def origin(value):
    if any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError('Server URL contains whitespace/control characters.')
    p = urlsplit(value)
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password or p.path not in ('', '/') or p.query or p.fragment:
        raise ValueError('Use http://COORDINATOR-IP:8787 without path, credentials or query.')
    p.port
    return value.rstrip('/')


def quote(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'


def write(path, text, mode=0o600):
    if path.is_symlink():
        raise ValueError('Refusing symlink: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.new')
    if temp.is_symlink():
        raise ValueError('Refusing symlink: ' + str(temp))
    temp.write_text(text, encoding='utf-8', newline='\n')
    temp.chmod(mode)
    temp.replace(path)


def managed_block(text, command=None):
    if text.count(BEGIN) != text.count(END) or text.count(BEGIN) > 1:
        raise ValueError('Malformed DisplayControl autostart block; review it manually.')
    if BEGIN in text:
        first, rest = text.split(BEGIN, 1)
        _, last = rest.split(END, 1)
        text = first + last.lstrip('\r\n')
    if command:
        text = text.rstrip() + '\n\n' + BEGIN + '\n' + command + ' &\n' + END + '\n'
    return text


def disable_screen_blanking(home):
    tool = shutil.which('raspi-config')
    if not tool:
        raise ValueError('raspi-config missing. Use Raspberry Pi OS or --keep-screen-settings and configure blanking manually.')
    labwc = home / '.config/labwc/autostart'
    if labwc.is_symlink() or not labwc.resolve().is_relative_to(home.resolve()):
        raise ValueError('Screen configuration escapes user home.')
    if labwc.is_file():
        backup = home / '.local/state/displaycontrol-screen-backups' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        if not backup.resolve().is_relative_to(home.resolve()):
            raise ValueError('Screen backup escapes user home.')
        backup.mkdir(parents=True, mode=0o700)
        shutil.copy2(labwc, backup / 'labwc-autostart')
    # Official tool handles labwc and X11 settings for the sudo caller's account.
    subprocess.run(['sudo', tool, 'nonint', 'do_blanking', '1'], check=True)
    result = subprocess.run(['sudo', tool, 'nonint', 'get_blanking'], check=True, capture_output=True, text=True)
    if result.stdout.strip() != '1':
        raise ValueError('OS did not confirm screen blanking is disabled. Review Raspberry screen settings.')
    print('OS screen blanking disabled and verified. Reboot to apply it to the desktop session.')


def validate(home, source, server, mode, port):
    server = origin(server)
    if mode not in ('prompt', 'signage') or not 1024 <= port <= 65535:
        raise ValueError('Mode must be prompt/signage; local port must be 1024..65535.')
    if any(c in str(home) for c in '\n\r\x00'):
        raise ValueError('Unsupported home path.')
    base = home / '.local/share/displaycontrol-player'
    # Resolve existing parents before any installation writes.
    if not base.resolve().is_relative_to(home.resolve()) or base.is_symlink():
        raise ValueError('Installation directory must remain inside the user home.')
    if base.exists() and not (base / 'installation.json').is_file():
        raise ValueError('Existing directory is not a managed installation: ' + str(base))
    for path in (base / 'data', base / 'releases', base / 'backups'):
        if path.is_symlink() or not path.resolve().is_relative_to(base.resolve()):
            raise ValueError('Private installation path escapes its directory.')
    config = base / 'data/station.json'
    if config.is_file():
        previous = json.loads(config.read_text(encoding='utf-8'))
        if previous['server'] != server or previous['mode'] != mode:
            raise ValueError('Server/mode differs from saved pairing. Use the documented re-pair procedure first.')
    if (base / 'installation.json').is_file():
        meta = json.loads((base / 'installation.json').read_text())
        if meta['port'] != port:
            raise ValueError('Keep the installed local port to retain the browser cache.')
    for name in FILES:
        if not (source / name).is_file() or (source / name).is_symlink():
            raise ValueError('Missing or linked runtime file: ' + name)
    manifest = source / 'raspberry/SHA256.json'
    if manifest.is_file():
        expected = json.loads(manifest.read_text())
        for name in FILES:
            if expected.get(name) != hashlib.sha256((source / name).read_bytes()).hexdigest():
                raise ValueError('Runtime checksum mismatch: ' + name)
    return base, server


def install(home, source, server, mode, port, browser, apply=True):
    base, server = validate(home, source, server, mode, port)
    units = home / '.config/systemd/user'
    unit = units / 'displaycontrol-station.service'
    desktop = home / '.config/autostart/displaycontrol-player.desktop'
    if (home / '.config/autostart/displaycontrol-kiosk.desktop').exists():
        raise ValueError('Legacy kiosk autostart exists. Disable it before installing; see the guide.')
    for p in (unit, desktop):
        if p.exists() and MARKER not in p.read_text():
            raise ValueError('Existing unmanaged startup file: ' + str(p))
    labwc = home / '.config/labwc/autostart'
    for p in (unit, desktop, labwc):
        if p.is_symlink() or not p.resolve().is_relative_to(home.resolve()):
            raise ValueError('Startup path escapes user home: ' + str(p))
    existing = labwc.read_text() if labwc.exists() else (
        Path('/etc/xdg/labwc/autostart').read_text() if Path('/etc/xdg/labwc/autostart').is_file() else '#!/bin/sh\n')
    digest = hashlib.sha256()
    for name in FILES:
        digest.update(name.encode())
        digest.update((source / name).read_bytes())
    release = base / 'releases' / digest.hexdigest()[:16]
    if release.is_symlink() or not release.resolve().is_relative_to(base.resolve()):
        raise ValueError('Runtime release escapes installation directory.')
    launcher = base / 'launch-kiosk.sh'
    labtext = managed_block(existing, '/bin/sh ' + shlex.quote(str(launcher)))
    if not apply:
        return {'directory': str(base), 'server': server, 'mode': mode, 'port': port, 'browser': browser}
    # An interrupted first install remains recognizable and can be retried.
    if not (base / 'installation.json').exists():
        write(base / 'installation.json', json.dumps({'port': port, 'state': 'installing'}))
    backup = base / 'backups' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    for p in (unit, desktop, labwc):
        if p.is_file():
            backup.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, backup / (p.parent.name + '-' + p.name))
    if unit.exists():
        subprocess.run(['systemctl', '--user', 'stop', 'displaycontrol-station.service'], check=True)
    release.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        target = release / name
        if not target.resolve().is_relative_to(release.resolve()):
            raise ValueError('Runtime destination escapes release directory.')
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink():
            raise ValueError('Refusing linked runtime destination.')
        shutil.copyfile(source / name, target)
    state = base / 'data'
    state.mkdir(mode=0o700, exist_ok=True)
    state.chmod(0o700)
    if not (state / 'station.json').exists():
        write(state / 'station.json', json.dumps({'server': server, 'mode': mode}, indent=2))
    write(base / 'installation.json', json.dumps({'server': server, 'mode': mode, 'port': port,
                                                 'release': str(release), 'browser': browser}, indent=2))
    command = ' '.join(quote(x) for x in [sys.executable, release / 'player_station.py',
                        '--config', state / 'station.json', '--port', str(port)])
    write(unit, f'''{MARKER}
[Unit]
Description=DisplayControl local player station
[Service]
Type=simple
ExecStart={command}
WorkingDirectory={quote(release)}
Restart=always
RestartSec=3
UMask=0077
NoNewPrivileges=true
[Install]
WantedBy=default.target
''')
    kiosk = [sys.executable, str(release / 'raspberry/kiosk.py')]
    common = ['--state-dir', str(state), '--url', f'http://127.0.0.1:{port}/']
    write(launcher, '#!/bin/sh\nexec ' + shlex.join(kiosk + ['run'] + common + ['--browser', browser]) + '\n', 0o700)
    write(base / 'manage.sh', '#!/bin/sh\nexec ' + shlex.join(kiosk) + ' "${1:-status}" ' + shlex.join(common) + '\n', 0o700)
    write(desktop, f'''{MARKER}
[Desktop Entry]
Type=Application
Name=DisplayControl player
Exec=/bin/sh {quote(launcher)}
Terminal=false
X-GNOME-Autostart-enabled=true
''')
    write(labwc, labtext, 0o700)
    subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', '--user', 'enable', '--now', 'displaycontrol-station.service'], check=True)
    return {'directory': str(base), 'server': server, 'mode': mode, 'port': port, 'browser': browser}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server')
    parser.add_argument('--mode', choices=('prompt', 'signage'))
    parser.add_argument('--port', type=int, default=8877)
    parser.add_argument('--install-deps', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--keep-screen-settings', action='store_true', help='Leave OS screen blanking unchanged')
    parser.add_argument('--screen-only', action='store_true', help='Disable OS screen blanking without reinstalling/re-pairing')
    args = parser.parse_args()
    if sys.platform != 'linux' or os.geteuid() == 0:
        parser.error('Run on Raspberry/Linux as the desktop user, without sudo.')
    if sys.version_info < (3, 11):
        parser.error('Python 3.11+ required. Use current Raspberry Pi OS Desktop or Bookworm Desktop.')
    if args.screen_only:
        if args.keep_screen_settings:
            parser.error('--screen-only conflicts with --keep-screen-settings')
        try:
            if args.dry_run:
                print('Would run sudo raspi-config nonint do_blanking 1, verify get_blanking, and back up user labwc startup.')
            else:
                disable_screen_blanking(Path.home())
            return
        except (OSError, ValueError, subprocess.CalledProcessError) as exc:
            parser.exit(1, 'SCREEN CONFIGURATION INCOMPLETE: ' + str(exc) + '\n')
    guided = not args.server or not args.mode
    if args.dry_run and guided:
        parser.error('--dry-run requires --server and --mode')
    server = args.server or input('Coordinator/server URL (http://IP:8787): ').strip()
    mode = args.mode
    if not mode:
        mode = {'1': 'prompt', '2': 'signage'}.get(input('1 = Prompt / 2 = Signage [1]: ').strip() or '1')
    try:
        validate(Path.home(), SOURCE, server, mode, args.port)
        sessions = list(Path('/usr/share/xsessions').glob('*.desktop')) + list(Path('/usr/share/wayland-sessions').glob('*.desktop'))
        if not args.dry_run and not sessions:
            raise ValueError('No graphical desktop found. Install Raspberry Pi OS Desktop, not Lite.')
        browser = shutil.which('chromium') or shutil.which('chromium-browser')
        install(Path.home(), SOURCE, server, mode, args.port, browser or '/usr/bin/chromium', False)
        deps = args.install_deps or (guided and not args.dry_run and input('Install/update Chromium and fonts with apt? [Y/n]: ').strip().lower() not in ('n', 'no'))
        if deps and not args.dry_run:
            subprocess.run(['sudo', 'apt-get', 'update'], check=True)
            subprocess.run(['sudo', 'apt-get', 'install', '-y', 'python3', 'chromium', 'fonts-dejavu-core', 'fonts-liberation'], check=True)
            browser = shutil.which('chromium') or shutil.which('chromium-browser')
        if not browser and not args.dry_run:
            raise ValueError('Chromium missing; rerun with --install-deps on Raspberry Pi OS Desktop.')
        if not args.dry_run:
            subprocess.run(['systemctl', '--user', 'show-environment'], check=True, stdout=subprocess.DEVNULL)
            if not args.keep_screen_settings:
                disable_screen_blanking(Path.home())
        result = install(Path.home(), SOURCE, server, mode, args.port, browser or '/usr/bin/chromium', not args.dry_run)
        print(json.dumps(result, indent=2))
        if not args.dry_run:
            for attempt in range(40):
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{args.port}/prompt_shared.js', timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    pass
                time.sleep(.25)
            else:
                raise ValueError('Local station did not become reachable. Check systemctl --user status displaycontrol-station.service.')
            print('Installed. Enable DESKTOP auto-login in Raspberry Pi settings.')
            if args.keep_screen_settings:
                print('OS screen settings left unchanged; disable screen blanking manually if needed.')
            print('Then reboot. Pair using the code generated in the regia console; no administrator key belongs here.')
            print('Private data/cache retained. Manage with: ' + result['directory'] + '/manage.sh status')
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, 'INSTALLATION INCOMPLETE: ' + str(exc) + '\nFix the issue and rerun; retain the data folder.\n')


if __name__ == '__main__':
    main()
