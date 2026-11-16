"""Real HTTP browser checks and optional screenshots with disposable demo data.

Needs development-only Playwright and installed Chrome; no physical devices.
"""
import argparse
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


def run(capture_dir=None):
    checks, images, errors = [], [], []
    if capture_dir:
        capture_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='displaycontrol-docs-') as folder:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        origin = f'http://127.0.0.1:{port}'
        proc = subprocess.Popen(
            [sys.executable, str(ROOT / 'server.py'), '--port', str(port),
             '--data-dir', folder, '--prompt-osc-port', '0'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(100):
                try:
                    urllib.request.urlopen(origin + '/api/info', timeout=.3).close()
                    break
                except OSError:
                    time.sleep(.1)
            admin = (Path(folder) / 'access.key').read_text().strip()

            def api(path, body=None):
                method = 'GET' if body is None else 'POST'
                if path == '/api/state' and body is not None:
                    method = 'PUT'
                request = urllib.request.Request(
                    origin + path, method=method,
                    data=None if body is None else json.dumps(body).encode(),
                    headers={'X-Control-Token': admin, 'Content-Type': 'application/json'})
                with urllib.request.urlopen(request, timeout=8) as response:
                    return json.load(response)

            state = json.loads((ROOT / 'example_project.json').read_text(encoding='utf-8')
                               .replace('Teatro Carisma', 'DisplayControl Demo')
                               .replace('TEATRO CARISMA', 'DISPLAYCONTROL DEMO')
                               .replace('al Carisma', 'alla Demo'))
            assignments = ['orologio', 'programma', 'intervallo', 'ingresso']
            for screen, asset in zip(state['screens'], assignments):
                screen['override'] = {'type': 'asset', 'id': asset}
                screen['fallbackAssetId'] = 'orologio'
            api('/api/state', {'revision': 0, 'state': state})
            api('/api/prompt/project', {
                'revision': 1, 'title': 'Demo / prova generale',
                'text': '[[CUE: APERTURA]]\nBenvenuti alla prova generale.\n'
                        'Il testo rimane allineato tra regia e player.\n\n'
                        '[[CUE: SCENA 1]]\nOgni voce trova il proprio ritmo.\n'
                        'Una pausa, poi riprendiamo insieme.\n\n'
                        '[[CUE: FINALE]]\nGrazie e buona serata.',
                'settings': {'font': 'classic', 'size': 'large',
                             'theme': 'white', 'readingLine': True}})

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel='chrome', headless=True)
                try:
                    def context(admin_access=False):
                        ctx = browser.new_context(viewport={'width': 1440, 'height': 1000},
                                                  device_scale_factor=1, reduced_motion='reduce')
                        ctx.on('page', lambda page: page.on('pageerror', lambda err: errors.append(str(err))))
                        if admin_access:
                            ctx.add_init_script('if(location.origin===' + json.dumps(origin) + '){localStorage.setItem("carisma-access-key",' + json.dumps(admin) + ');}')
                        return ctx

                    def capture(page, name, locator=None):
                        if not capture_dir:
                            return
                        page.evaluate('document.fonts.ready')
                        page.screenshot(path=str(capture_dir / name), full_page=True) if locator is None else locator.screenshot(path=str(capture_dir / name))
                        images.append(name)

                    admin_ctx = context(True)
                    players = []
                    for screen in state['screens']:
                        code = api('/api/devices/pair-code', {'screenId': screen['id']})['code']
                        player = context().new_page()
                        player.goto(origin + '/connect.html')
                        player.locator('#code').fill(code)
                        player.locator('#button').click()
                        player.wait_for_url('**/player.html?**')
                        try:
                            player.wait_for_function('playerState.connected && !!playerState.effectiveTitle', timeout=12000)
                        except Exception as exc:
                            status = player.evaluate('({mode, message: playerState.message, connected: playerState.connected})')
                            raise RuntimeError({'player': status, 'pageErrors': errors}) from exc
                        players.append(player)
                    checks.append('Four browser players paired through the real connect page and HTTP API')

                    monitor = admin_ctx.new_page()
                    monitor.goto(origin + '/monitor.html')
                    monitor.wait_for_function('document.querySelectorAll(".card img:not([hidden])").length === 4 && [...document.querySelectorAll(".card img")].every(i => i.naturalWidth > 0)', timeout=30000)
                    assert monitor.locator('#more').inner_text() == 'More'
                    assert monitor.locator('#more').get_attribute('aria-expanded') == 'false'
                    assert monitor.locator('[data-monitor-detail]:visible').count() == 0
                    assert monitor.locator('.card:visible').count() == 4
                    capture(monitor, 'monitor-matrix.png')
                    checks.append('Default monitor shows the matrix and More; every details region is hidden')

                    monitor.locator('#more').focus()
                    monitor.keyboard.press('Enter')
                    assert monitor.locator('#more').get_attribute('aria-expanded') == 'true'
                    assert monitor.locator('[data-monitor-detail]:visible').count() == 7
                    capture(monitor, 'monitor-more.png')
                    monitor.select_option('#columns', '2')
                    assert monitor.locator('#grid').get_attribute('data-cols') == '2'
                    monitor.select_option('#interval', '1')
                    monitor.wait_for_function('snapshot.policy.interval === 1')
                    group = state['screens'][0]['group']
                    monitor.select_option('#group', group)
                    assert monitor.locator('.card:visible').count() == sum(s['group'] == group for s in state['screens'])
                    monitor.select_option('#group', '')
                    checks.append('Keyboard More reveals all details; column, interval and group controls work')

                    monitor.click('#pause')
                    monitor.wait_for_function('paused')
                    monitor.click('#more')
                    assert monitor.locator('#pause').is_hidden()
                    assert monitor.locator('.stale:visible').count() == 4
                    monitor.click('#more')
                    monitor.click('#pause')
                    monitor.wait_for_function('!paused && snapshot.policy.enabled')
                    checks.append('Pause/stale indicators and resume survive collapsing details')

                    monitor.click('#more')
                    first_update = monitor.evaluate('lastPoll')
                    monitor.wait_for_function('lastPoll > ' + str(first_update), timeout=6000)
                    assert api('/api/monitor?viewer=docs-check&interval=1')['policy']['enabled']
                    monitor.reload()
                    monitor.wait_for_selector('.card')
                    assert monitor.locator('#more').get_attribute('aria-expanded') == 'false'
                    assert monitor.locator('[data-monitor-detail]:visible').count() == 0
                    checks.append('Matrix keeps polling; reload returns to the default collapsed view')

                    monitor.set_viewport_size({'width': 390, 'height': 844})
                    assert monitor.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    monitor.click('#more')
                    assert monitor.locator('#group').is_visible()
                    assert monitor.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    monitor.click('#more')
                    capture(monitor, 'monitor-mobile.png')
                    checks.append('Matrix and expanded controls fit a 390px mobile viewport')
                    monitor.set_viewport_size({'width': 1440, 'height': 1000})

                    console = admin_ctx.new_page()
                    console.goto(origin + '/')
                    console.wait_for_selector('[data-nav="screens"]')
                    console.wait_for_function('mode === "server" && state.screens.length === 4')
                    for section in ['screens', 'contents', 'playlists', 'schedules', 'ndi', 'diagnostics', 'settings']:
                        console.click('[data-nav="' + section + '"]')
                        console.wait_for_function('page === ' + json.dumps(section))
                        console.wait_for_timeout(200)
                        capture(console, 'console-' + section + '.png')

                    prompt_player = context().new_page()
                    code = api('/api/prompt/pair-code', {'station': 'demo', 'role': 'PRIMARY'})['code']
                    prompt_player.goto(origin + '/prompt_player.html')
                    prompt_player.locator('#pname').fill('Browser demo PRIMARY')
                    prompt_player.locator('#pcode').fill(code)
                    prompt_player.locator('#pairbtn').click()
                    prompt_player.wait_for_function('online && !!project && document.getElementById("pair").style.display === "none"')
                    capture(prompt_player, 'prompt-player.png')
                    prompt = admin_ctx.new_page()
                    prompt.goto(origin + '/prompt.html')
                    prompt.wait_for_function('state && state.project.title === "Demo / prova generale"')
                    prompt.wait_for_function('state.devices.some(d => d.role === "PRIMARY" && d.online)')
                    assert prompt.locator('#primaryCode').inner_text() == '--------'
                    capture(prompt, 'prompt-console.png')
                    capture(prompt, 'prompt-controllers.png', prompt.locator('.panel').filter(has=prompt.locator('#akpPairCode')))

                    pairing = admin_ctx.new_page()
                    pairing.goto(origin + '/players.html')
                    pairing.wait_for_function('document.querySelectorAll("#devices .device").length === 4')
                    assert pairing.locator('#pair').is_hidden()
                    capture(pairing, 'player-pairing.png')
                    connect = context().new_page()
                    connect.goto(origin + '/connect.html')
                    capture(connect, 'player-connect.png')
                    capture(players[0], 'signage-player.png')
                    checks.append('Main pages captured via normal HTTP navigation with disposable demo data and no displayed credentials')

                    monitor.context.route('**/api/monitor?**', lambda route: route.abort())
                    monitor.evaluate('resume()')
                    monitor.wait_for_selector('#alert:visible')
                    assert monitor.locator('[data-monitor-detail]:visible').count() == 0
                    assert monitor.locator('.stale:visible').count() == 4
                    monitor.context.unroute('**/api/monitor?**')
                    monitor.evaluate('resume()')
                    monitor.wait_for_function('serverOK && document.getElementById("alert").hidden')
                    checks.append('Server failure remains visible in matrix mode and recovers on reconnect')
                    assert not errors, errors
                finally:
                    browser.close()
        finally:
            proc.terminate()
            proc.wait(timeout=8)
    return {'checks': checks, 'images': images, 'pageErrors': errors,
            'limits': ['Local Chrome and loopback HTTP only',
                       'Browser players with synthetic demonstration content; no physical panels/controllers/NDI']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture-dir', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    result = run(args.capture_dir)
    if args.report:
        args.report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
