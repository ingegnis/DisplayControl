"""Native Chrome cache/reopen checks for local Prompt/signage stations."""
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def run():
    checks, errors = [], []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='chrome', headless=True)
        try:
            for mode in ('prompt', 'signage'):
                with tempfile.TemporaryDirectory(prefix='displaycontrol-local-browser-') as temporary:
                    folder = Path(temporary)
                    holders = [socket.socket(), socket.socket()]
                    for sock in holders:
                        sock.bind(('127.0.0.1', 0))
                    ports = [sock.getsockname()[1] for sock in holders]
                    for sock in holders:
                        sock.close()
                    remote, local = [f'http://127.0.0.1:{port}' for port in ports]
                    core = subprocess.Popen([sys.executable, str(ROOT / 'server.py'), '--port', str(ports[0]), '--data-dir', str(folder / 'core'), '--prompt-osc-port', '0'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    station_args = [sys.executable, str(ROOT / 'player_station.py'), '--port', str(ports[1]), '--server', remote, '--mode', mode, '--config', str(folder / 'station.json')]
                    station = subprocess.Popen(station_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    def wait_http(url):
                        for _ in range(100):
                            try:
                                urllib.request.urlopen(url, timeout=.2).close()
                                return
                            except OSError:
                                time.sleep(.05)
                        raise RuntimeError('Local process did not start.')
                    def api(path, body=None, method=None):
                        request = urllib.request.Request(remote + path, data=None if body is None else json.dumps(body).encode(),
                                                         method=method, headers={'X-Control-Token': admin, 'Content-Type': 'application/json'})
                        with urllib.request.urlopen(request, timeout=6) as response:
                            return json.load(response)
                    context = browser.new_context(viewport={'width': 1280, 'height': 720})
                    page = context.new_page()
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    try:
                        wait_http(remote + '/api/info')
                        wait_http(local + '/prompt_shared.js')
                        admin = (folder / 'core/access.key').read_text().strip()
                        if mode == 'prompt':
                            api('/api/prompt/project', {'revision': 1, 'title': 'Local cache proof', 'text': '[[CUE: START]]\nLocal cache proof\nSecond line', 'settings': {}})
                            code = api('/api/prompt/pair-code', {'station': 'local-browser', 'role': 'PRIMARY'})['code']
                            page.goto(local + '/')
                            page.fill('#pcode', code)
                            page.click('#pairbtn')
                            page.wait_for_function('online && project && project.title === "Local cache proof"')
                            api('/api/prompt/command', {'command': 'play'})
                            page.wait_for_function('runtime.playing')
                        else:
                            state = json.loads((ROOT / 'example_project.json').read_text(encoding='utf-8'))
                            screen = state['screens'][0]
                            screen['override'] = {'type': 'asset', 'id': 'orologio'}
                            api('/api/state', {'revision': 0, 'state': state}, 'PUT')
                            code = api('/api/devices/pair-code', {'screenId': screen['id']})['code']
                            page.goto(local + '/')
                            page.fill('#code', code)
                            page.click('#button')
                            page.wait_for_url('**/player.html?**')
                            page.wait_for_function('playerState.connected && !!document.querySelector(".dc-time")')
                        checks.append(mode + ': real local-origin pairing and first synchronization')
                        page.wait_for_timeout(1200)
                        core.terminate()
                        core.wait(timeout=5)
                        if mode == 'prompt':
                            page.wait_for_function('!online')
                            before = page.evaluate('currentOffset()')
                            page.wait_for_timeout(600)
                            assert page.evaluate('currentOffset()') > before
                            checks.append('Prompt: local monotonic scrolling continues through remote server loss')
                        else:
                            page.evaluate('syncPlayer()')
                            page.wait_for_function('!playerState.connected')
                        page.reload()
                        if mode == 'prompt':
                            page.wait_for_function('project && project.title === "Local cache proof" && document.getElementById("pair").style.display === "none"')
                        else:
                            page.wait_for_function('playerState.snapshot && !!document.querySelector(".dc-time")')
                        checks.append(mode + ': browser reload while remote server is unavailable restores native cached content')
                        station.terminate()
                        station.wait(timeout=5)
                        station = subprocess.Popen(station_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        wait_http(local + '/prompt_shared.js')
                        page.goto(local + '/')
                        if mode == 'prompt':
                            page.wait_for_function('project && project.title === "Local cache proof"')
                        else:
                            page.wait_for_function('playerState.snapshot && !!document.querySelector(".dc-time")')
                        checks.append(mode + ': local service restart preserves origin, scoped identity and browser cache')
                    finally:
                        context.close()
                        for process in (core, station):
                            if process.poll() is None:
                                process.terminate()
                            process.wait(timeout=5)
        finally:
            browser.close()
    assert not errors, errors
    return {'checks': checks, 'pageErrors': errors,
            'limits': ['Local Windows Chrome and real HTTP/native browser storage', 'No Raspberry SD, physical power loss, HDMI or Chromecast test']}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    result = run()
    if args.report:
        args.report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
