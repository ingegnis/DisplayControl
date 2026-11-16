"""Self-contained server tests; Python standard library only."""
import base64
import hashlib
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

ROOT = Path(__file__).resolve().parents[1]


class ControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='carisma-test-')
        cls.data = Path(cls.temp.name)
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            cls.port = s.getsockname()[1]
        cls.start_server()
        cls.token = (cls.data / 'access.key').read_text().strip()
        cls.project = json.loads((ROOT / 'example_project.json').read_text(encoding='utf-8'))
        status, _, _ = cls.request('/api/state', 'PUT', {'revision': 0, 'state': cls.project})
        if status != 200:
            raise RuntimeError('Cannot seed test state')

    @classmethod
    def start_server(cls):
        cls.proc = subprocess.Popen([sys.executable, str(ROOT / 'server.py'), '--port', str(cls.port), '--data-dir', str(cls.data)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                with urllib.request.urlopen('http://127.0.0.1:%d/api/info' % cls.port, timeout=.3):
                    return
            except (OSError, urllib.error.URLError):
                time.sleep(.05)
        cls.proc.terminate()
        raise RuntimeError('Test server failed to start')

    @classmethod
    def stop_server(cls):
        cls.proc.terminate()
        try:
            cls.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.proc.kill()
            cls.proc.wait(timeout=5)

    @classmethod
    def tearDownClass(cls):
        cls.stop_server()
        cls.temp.cleanup()

    @classmethod
    def request(cls, path, method='GET', body=None, token=None, headers=None):
        hs = {'X-Control-Token': cls.token if token is None else token, **(headers or {})}
        if isinstance(body, dict):
            body = json.dumps(body).encode()
            hs['Content-Type'] = 'application/json'
        req = urllib.request.Request('http://127.0.0.1:%d%s' % (cls.port, path), data=body, headers=hs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, r.read(), dict(r.headers)
        except urllib.error.HTTPError as err:
            with err:
                return err.code, err.read(), dict(err.headers)

    def test_authentication(self):
        self.assertEqual(self.request('/api/info', token='')[0], 200)
        self.assertEqual(self.request('/api/state', token='')[0], 401)
        self.assertEqual(self.request('/api/state', token='wrong')[0], 401)
        self.assertEqual(self.request('/api/state')[0], 200)

    def test_branding_roundtrip_and_public_identity_only(self):
        from test_branding import png
        import copy
        current=json.loads(self.request('/api/state')[1]);project=copy.deepcopy(current['state'])
        project['site']={'name':'Ente dimostrativo','branding':{'logo':'data:image/png;base64,'+base64.b64encode(png()).decode(),'theme':{'accent':'#146ef0','sidebar':'#112745'}}}
        self.assertEqual(self.request('/api/state','PUT',{'revision':current['revision'],'state':project})[0],200)
        status,body,_=self.request('/api/branding',token='');self.assertEqual(status,200)
        self.assertEqual(json.loads(body),project['site']);self.assertNotIn(self.token,body.decode())
        for path in ['/branding.js','/prompt_shared.js']:self.assertEqual(self.request(path,token='')[0],200)
        latest=json.loads(self.request('/api/state')[1]);project['site']['branding']['logo']='https://outside/logo.png'
        self.assertEqual(self.request('/api/state','PUT',{'revision':latest['revision'],'state':project})[0],400)
        self.assertEqual(self.request('/api/state','PUT',{'revision':latest['revision'],'state':current['state']})[0],200)

    def test_ndi_api_protection_and_validation(self):
        for endpoint in ['/api/ndi/status','/api/ndi/sources','/api/ndi/manifest/x','/api/ndi/media/x/y/z']:
            self.assertEqual(self.request(endpoint, token='')[0],401)
        self.assertEqual(self.request('/api/ndi/start','POST',{'test':True},token='')[0],401)
        self.assertEqual(self.request('/api/ndi/status')[0],200)
        self.assertEqual(self.request('/api/ndi/start','POST',{'sourceName':'x','profile':'bad'})[0],400)
        self.assertEqual(self.request('/api/ndi/start','POST',b'[]',headers={'Content-Type':'application/json'})[0],400)

    def test_optimistic_revision(self):
        current = json.loads(self.request('/api/state')[1])
        self.assertEqual(self.request('/api/state', 'PUT', {'revision': -1, 'state': current['state']})[0], 409)
        self.assertEqual(self.request('/api/state', 'PUT', current)[0], 200)

    def test_invalid_payload(self):
        current = json.loads(self.request('/api/state')[1])
        self.assertEqual(self.request('/api/state', 'PUT', {'revision': current['revision'], 'state': {'bad': True}})[0], 400)
        self.assertEqual(self.request('/api/assets', 'POST', b'<html>bad</html>', headers={'Content-Type': 'text/html'})[0], 400)

    def test_upload_hash_and_download(self):
        data = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2nAAAAABJRU5ErkJggg==')
        status, body, _ = self.request('/api/assets', 'POST', data, headers={'Content-Type': 'image/png', 'X-File-Name': 'sample.png'})
        self.assertEqual(status, 201)
        meta = json.loads(body)
        self.assertEqual(meta['sha256'], hashlib.sha256(data).hexdigest())
        status, result, _ = self.request('/api/assets/' + meta['fileId'])
        self.assertEqual(status, 200)
        self.assertEqual(result, data)
        self.assertEqual(self.request('/api/assets/' + meta['fileId'], token='')[0], 401)
        self.assertIn(self.request('/api/assets/../../server.py')[0], (400, 404))

    def test_heartbeat(self):
        self.assertEqual(self.request('/api/heartbeat', 'POST', {'screenId': 'test-screen', 'title': 'Test', 'cacheCount': 2, 'revision': 1})[0], 200)
        runtime = json.loads(self.request('/api/runtime')[1])
        self.assertEqual(runtime['players']['test-screen']['cacheCount'], 2)

    def test_persistence_after_restart(self):
        current = json.loads(self.request('/api/state')[1])
        current['state']['site']['name'] = 'Persistence verified'
        self.assertEqual(self.request('/api/state', 'PUT', current)[0], 200)
        self.stop_server()
        self.start_server()
        result = json.loads(self.request('/api/state')[1])
        self.assertEqual(result['state']['site']['name'], 'Persistence verified')
        self.assertEqual((self.data / 'access.key').read_text().strip(), self.token)


if __name__ == '__main__':
    unittest.main()
