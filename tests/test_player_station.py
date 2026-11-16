"""Local station permission boundaries and persisted scoped identity over real HTTP."""
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

from player_station import allowed

ROOT = Path(__file__).resolve().parents[1]


class StationPermissionTests(unittest.TestCase):
    def test_admin_and_cluster_apis_are_never_forwarded(self):
        for mode in ('signage', 'prompt'):
            for path in ('/api/state', '/api/prompt/command', '/api/show/export', '/api/cluster/checkpoint', '/api/ha/status'):
                for method in ('GET', 'POST'):
                    self.assertFalse(allowed(path, method, mode))

    def test_station_modes_have_separate_token_scopes(self):
        self.assertTrue(allowed('/api/prompt/player/state', 'GET', 'prompt'))
        self.assertFalse(allowed('/api/player/state', 'GET', 'prompt'))
        self.assertFalse(allowed('/api/prompt/player/state', 'GET', 'signage'))
        self.assertTrue(allowed('/api/player/ndi/start', 'POST', 'signage'))


class StationHttpTests(unittest.TestCase):
    def test_pairing_persists_locally_and_shell_survives_server_outage(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            holders = [socket.socket(), socket.socket()]
            for holder in holders:
                holder.bind(('127.0.0.1', 0))
            core_port, local_port = [s.getsockname()[1] for s in holders]
            for holder in holders:
                holder.close()
            origin = f'http://127.0.0.1:{core_port}'
            local = f'http://127.0.0.1:{local_port}'
            core = subprocess.Popen([sys.executable, str(ROOT / 'server.py'), '--port', str(core_port), '--data-dir', str(folder / 'core'), '--prompt-osc-port', '0'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            station = subprocess.Popen([sys.executable, str(ROOT / 'player_station.py'), '--port', str(local_port), '--server', origin, '--mode', 'prompt', '--config', str(folder / 'station.json')], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            def request(base, path, body=None, admin=None):
                headers = {'Content-Type': 'application/json'}
                if admin:
                    headers['X-Control-Token'] = admin
                request = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(), headers=headers)
                try:
                    with urllib.request.urlopen(request, timeout=5) as response:
                        return response.status, response.read()
                except urllib.error.HTTPError as exc:
                    raw = exc.read()
                    exc.close()
                    return exc.code, raw
            try:
                for _ in range(100):
                    try:
                        if request(origin, '/api/info')[0] == 200 and request(local, '/prompt_player.html')[0] == 200:
                            break
                    except OSError:
                        pass
                    time.sleep(.05)
                admin = (folder / 'core/access.key').read_text().strip()
                code = json.loads(request(origin, '/api/prompt/pair-code', {'station': 'local', 'role': 'PRIMARY'}, admin)[1])['code']
                status, raw = request(local, '/api/prompt/pair', {'code': code, 'name': 'Synthetic local player'})
                self.assertEqual(status, 201)
                identity = json.loads(raw)
                self.assertEqual(json.loads((folder / 'station.json').read_text())['token'], identity['token'])
                self.assertEqual(request(local, '/api/prompt/player/state')[0], 200)
                self.assertEqual(request(local, '/api/state', admin=admin)[0], 403)
                html = request(local, '/prompt_player.html')[1]
                self.assertIn(b'carisma-prompt-token-v1', html)
                core.terminate()
                core.wait(timeout=5)
                self.assertEqual(request(local, '/prompt_player.html')[0], 200)
                self.assertEqual(request(local, '/api/prompt/player/state')[0], 503)
            finally:
                for proc in (core, station):
                    if proc.poll() is None:
                        proc.terminate()
                    proc.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()
