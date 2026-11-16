#!/usr/bin/env python3
"""Generate Linux desktop/user-service files for a local Prompt or signage station."""
import argparse
import json
from pathlib import Path
import shlex
import shutil

from cluster import endpoint

ROOT = Path(__file__).resolve().parent


def prepare(server, mode, output, browser=None, port=8877):
    server = endpoint(server)
    if mode not in ('prompt', 'signage') or not 1 <= port <= 65535:
        raise ValueError('Invalid station mode or port.')
    browser = browser or shutil.which('chromium') or shutil.which('chromium-browser')
    if not browser:
        raise ValueError('Install Chromium first, or provide --browser /actual/path/to/chromium.')
    folder = Path(output).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    for name in ('displaycontrol-station.service', 'displaycontrol-kiosk.desktop', 'launch-kiosk.sh'):
        if (folder / name).exists():
            raise ValueError('Setup files already exist; select a new output folder.')
    config = ROOT / 'data/station.json'
    profile = ROOT / 'data/kiosk-profile'
    def unit_quote(value):
        return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'
    command = ' '.join(unit_quote(value) for value in [shutil.which('python3') or '/usr/bin/python3', ROOT / 'player_station.py',
                '--config', config, '--server', server, '--mode', mode, '--port', str(port)])
    unit = f'''[Unit]
Description=DisplayControl local {mode} shell

[Service]
Type=simple
ExecStart={command}
WorkingDirectory={unit_quote(ROOT)}
Restart=always
RestartSec=2
UMask=0077
NoNewPrivileges=true

[Install]
WantedBy=default.target
'''
    (folder / 'displaycontrol-station.service').write_text(unit, encoding='utf-8')
    launch = f'''#!/bin/sh
set -eu
while ! python3 -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:{port}/prompt_shared.js",timeout=1).close()' 2>/dev/null; do sleep 1; done
exec {shlex.quote(str(browser))} --kiosk --no-first-run --disable-session-crashed-bubble --user-data-dir={shlex.quote(str(profile))} http://127.0.0.1:{port}/
'''
    script = folder / 'launch-kiosk.sh'
    script.write_text(launch, encoding='utf-8')
    script.chmod(0o700)
    desktop = f'''[Desktop Entry]
Type=Application
Name=DisplayControl player
Exec=/bin/sh {unit_quote(script)}
Terminal=false
X-GNOME-Autostart-enabled=true
'''
    (folder / 'displaycontrol-kiosk.desktop').write_text(desktop, encoding='utf-8')
    (folder / 'INSTALL.txt').write_text('''Generated files only; nothing has been installed or enabled.
Run on the intended Raspberry/Linux desktop as the kiosk user:

mkdir -p ~/.config/systemd/user ~/.config/autostart
cp displaycontrol-station.service ~/.config/systemd/user/
cp displaycontrol-kiosk.desktop ~/.config/autostart/
systemctl --user daemon-reload
systemctl --user enable --now displaycontrol-station.service

Keep this setup folder: the desktop launcher references launch-kiosk.sh here.
Log out/in to launch the kiosk. Configure desktop auto-login through the OS.
Pair PRIMARY and BACKUP independently. Use separate storage and power supplies.
Keep the same localhost port/browser profile to retain cached show data.
Actual Raspberry boot, persistent cache, HDMI and power-loss tests remain required.
''', encoding='utf-8')
    return folder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', required=True)
    parser.add_argument('--mode', choices=('prompt', 'signage'), required=True)
    parser.add_argument('--browser')
    parser.add_argument('--port', type=int, default=8877)
    parser.add_argument('--output', type=Path, default=ROOT / 'data/kiosk-setup')
    args = parser.parse_args()
    try:
        print(prepare(args.server, args.mode, args.output, args.browser, args.port))
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
