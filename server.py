#!/usr/bin/env python3
"""Carisma Display Control - local demonstration server.
Python 3.9+, standard library controller. Optional NDI runtime + FFmpeg gateway.
No internet access required after local dependency provisioning.
"""
from __future__ import annotations
import argparse
import hashlib
import hmac
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import socket
import signal
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit
import webbrowser
from ndi.gateway import Gateway, GatewayError
from physical_players import init_players, handle_players
from monitoring import MonitorStore, handle_monitor
from prompt_module import PromptStore, PromptOscServer, handle_prompt
from storage import database, exclusive_file_lock
from branding import valid_branding, identity
from show_package import ShowPackages, handle_show
from cluster import ClusterCore, handle_cluster

ROOT = Path(__file__).resolve().parent
MAX_UPLOAD = 300 * 1024 * 1024
MAX_JSON = 2 * 1024 * 1024
ALLOWED_MIME = {'image/jpeg', 'image/png', 'image/webp', 'image/gif', 'video/mp4', 'video/webm'}
ASSET_ID = re.compile(r'^[a-f0-9]{64}$')
HEARTBEATS: dict = {}
HEARTBEATS_LOCK = threading.Lock()
DB_LOCK = threading.RLock()


def json_bytes(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def valid_state(state):
    if not isinstance(state, dict) or state.get('schemaVersion') != 1:
        return False
    if not isinstance(state.get('site'), dict):
        return False
    if not valid_branding(state['site']):
        return False
    if any(not isinstance(state.get(k), list) for k in ('screens', 'assets', 'playlists', 'schedules')):
        return False
    for key in ('screens', 'assets', 'playlists', 'schedules'):
        ids = [x.get('id') if isinstance(x, dict) else None for x in state[key]]
        if any(not isinstance(i, str) or not i or len(i) > 120 for i in ids):
            return False
        if len(ids) != len(set(ids)):
            return False
    return len(state['screens']) <= 200 and len(state['assets']) <= 2000


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class Handler(BaseHTTPRequestHandler):
    server_version = 'CarismaDisplay/0.11.0-alpha'

    def log_message(self, fmt, *args):
        if not any(p in str(args) for p in ('/api/state', '/api/runtime', '/api/ndi/manifest/', '/api/ndi/media/', '/api/heartbeat', '/api/player/', '/api/preview', '/api/monitor', '/api/prompt')):
            print('[%s] %s' % (self.log_date_time_string(), fmt % args), flush=True)

    def send_data(self, status, body=b'', ctype='application/json; charset=utf-8', extra=None):
        self.send_response(status)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Cache-Control', 'no-store')
        if extra:
            for key, value in extra.items():
                self.send_header(key, str(value))
        self.end_headers()
        try:
            if self.command != 'HEAD':
                self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def reply(self, obj, status=200):
        self.send_data(status, json_bytes(obj))

    def authorized(self):
        given = self.headers.get('X-Control-Token', '')
        if not hmac.compare_digest(given, self.server.control_token):
            self.reply({'error': 'Chiave locale mancante o non valida.'}, 401)
            return False
        return True

    def body_json(self):
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if size <= 0 or size > MAX_JSON:
                raise ValueError('invalid body length')
            value = json.loads(self.rfile.read(size))
            if not isinstance(value, dict):
                raise ValueError('Expected an object')
            return value
        except (ValueError, json.JSONDecodeError):
            self.reply({'error': 'JSON non valido o troppo grande.'}, 400)
            return None

    def db(self):
        return database(self.server.data_dir / 'controller.sqlite3')

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = urlsplit(self.path).path
        if handle_cluster(self, path):
            return
        if handle_show(self, path):
            return
        if handle_prompt(self, path):
            return
        if handle_monitor(self, path, HEARTBEATS, HEARTBEATS_LOCK):
            return
        if handle_players(self, path, HEARTBEATS, HEARTBEATS_LOCK):
            return
        if path == '/api/info':
            return self.reply({'product': 'carisma-display-control', 'version': '0.11.0-alpha', 'authRequired': True, 'serverTime': time.time()})
        if path == '/api/branding':
            # Public login/pairing identity; exclude project data and keys.
            with self.db() as conn:
                row = conn.execute('SELECT payload FROM state WHERE id=1').fetchone()
            state = json.loads(row[0]) if row and row[0] else {}
            return self.reply(identity(state.get('site', {})))
        if path.startswith('/api/') and not self.authorized():
            return
        if path == '/api/ha/status':
            core = getattr(self.server, 'cluster', None)
            if core is None:
                return self.reply({'enabled': False})
            try:
                from cluster import json_request
                return self.reply({'enabled': True, 'core': core.report(),
                                   'coordinator': json_request(core.witness + '/cluster/status', core.key)})
            except Exception:
                return self.reply({'enabled': True, 'core': core.report(), 'error': 'Coordinatore non raggiungibile.'})
        if path.startswith('/api/ndi/'):
            try:
                g = self.server.gateway
                if path == '/api/ndi/status':
                    return self.reply(g.status())
                if path == '/api/ndi/sources':
                    return self.reply(g.sources())
                if path.startswith('/api/ndi/manifest/'):
                    return self.reply(g.get(path.rsplit('/', 1)[-1]).manifest())
                if path.startswith('/api/ndi/media/'):
                    parts = path.split('/')
                    if len(parts) != 7:
                        raise GatewayError('Percorso media non valido.')
                    data = g.media(parts[4], parts[5], parts[6])
                    return self.send_data(200, data, 'video/mp4')
                return self.reply({'error': 'Endpoint NDI non trovato.'}, 404)
            except GatewayError as exc:
                return self.reply({'error': str(exc)}, exc.status)
        if path == '/api/state':
            with self.db() as conn:
                row = conn.execute('SELECT version,payload FROM state WHERE id=1').fetchone()
            return self.reply({'revision': row[0], 'state': json.loads(row[1]) if row[1] else None})
        if path == '/api/runtime':
            with HEARTBEATS_LOCK:
                result = {key: value for key, value in HEARTBEATS.items() if time.time() - value['lastSeen'] < 86400}
            return self.reply({'players': result, 'serverTime': time.time()})
        if path.startswith('/api/assets/'):
            asset_id = path.rsplit('/', 1)[-1]
            if not ASSET_ID.fullmatch(asset_id):
                return self.reply({'error': 'ID non valido.'}, 400)
            with self.db() as conn:
                row = conn.execute('SELECT mime,name FROM asset_files WHERE id=?', (asset_id,)).fetchone()
            fpath = self.server.data_dir / 'assets' / asset_id
            if not row or not fpath.is_file():
                return self.reply({'error': 'File non trovato.'}, 404)
            self.send_response(200)
            self.send_header('Content-Type', row[0])
            self.send_header('Content-Length', str(fpath.stat().st_size))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Cache-Control', 'private, max-age=86400')
            self.end_headers()
            try:
                if self.command != 'HEAD':
                    with fpath.open('rb') as fp:
                        while True:
                            chunk = fp.read(1024 * 1024)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return
        public = {'/': 'index.html', '/index.html': 'index.html', '/sw.js': 'sw.js', '/favicon.svg': 'favicon.svg', '/players.html': 'players.html', '/connect.html': 'connect.html', '/player.html': 'player.html', '/physical_boot.js': 'physical_boot.js', '/monitor.html': 'monitor.html', '/prompt.html': 'prompt.html', '/prompt_player.html': 'prompt_player.html', '/branding.js': 'branding.js', '/prompt_shared.js': 'prompt_shared.js', '/show.html': 'show.html'}
        if path not in public:
            return self.reply({'error': 'Risorsa non trovata.'}, 404)
        fp = ROOT / public[path]
        if not fp.is_file():
            return self.reply({'error': 'File dell\'app mancante.'}, 404)
        ctype = {'html': 'text/html; charset=utf-8', 'js': 'text/javascript; charset=utf-8', 'svg': 'image/svg+xml'}[fp.suffix[1:]]
        self.send_data(200, fp.read_bytes(), ctype)

    def do_PUT(self):
        try:
            if getattr(self.server, 'cluster', None):
                self.server.cluster.require_write()
            return self._put()
        except GatewayError as exc:
            return self.reply({'error': str(exc)}, exc.status)

    def _put(self):
        if not self.authorized():
            return
        if urlsplit(self.path).path != '/api/state':
            return self.reply({'error': 'Endpoint non trovato.'}, 404)
        body = self.body_json()
        if body is None:
            return
        state = body.get('state')
        if not valid_state(state):
            return self.reply({'error': 'Configurazione non valida.'}, 400)
        with DB_LOCK, self.db() as conn:
            version = conn.execute('SELECT version FROM state WHERE id=1').fetchone()[0]
            if body.get('revision') != version:
                return self.reply({'error': 'La configurazione e\' cambiata. Ricarica e ripeti.', 'revision': version}, 409)
            version += 1
            conn.execute('UPDATE state SET version=?,payload=? WHERE id=1', (version, json.dumps(state)))
        self.reply({'revision': version})

    def do_POST(self):
        path = urlsplit(self.path).path
        if handle_cluster(self, path):
            return
        try:
            if getattr(self.server, 'cluster', None):
                self.server.cluster.require_write()
            return self._post()
        except GatewayError as exc:
            return self.reply({'error': str(exc)}, exc.status)

    def _post(self):
        if handle_show(self, urlsplit(self.path).path):
            return
        if handle_prompt(self, urlsplit(self.path).path):
            return
        if handle_monitor(self, urlsplit(self.path).path, HEARTBEATS, HEARTBEATS_LOCK):
            return
        if handle_players(self, urlsplit(self.path).path, HEARTBEATS, HEARTBEATS_LOCK):
            return
        if not self.authorized():
            return
        path = urlsplit(self.path).path
        if path.startswith('/api/ndi/'):
            body = self.body_json()
            if body is None:
                return
            try:
                if path == '/api/ndi/start':
                    return self.reply(self.server.gateway.start(body))
                if path == '/api/ndi/stop':
                    return self.reply(self.server.gateway.stop(str(body.get('id', ''))))
                return self.reply({'error': 'Endpoint NDI non trovato.'}, 404)
            except GatewayError as exc:
                return self.reply({'error': str(exc)}, exc.status)
        if path == '/api/heartbeat':
            body = self.body_json()
            if body is None:
                return
            sid = body.get('screenId', '')
            if not isinstance(sid, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,120}', sid):
                return self.reply({'error': 'ID schermo non valido.'}, 400)
            clean = {
                'lastSeen': time.time(), 'title': str(body.get('title', ''))[:200],
                'cacheCount': int(body.get('cacheCount', 0)), 'revision': int(body.get('revision', 0)),
                'offlineTest': bool(body.get('offlineTest', False)), 'message': str(body.get('message', ''))[:300]
            }
            with HEARTBEATS_LOCK:
                HEARTBEATS[sid] = clean
            return self.reply({'ok': True, 'monitor': self.server.monitor.policy()})
        if path == '/api/assets':
            try:
                size = int(self.headers.get('Content-Length', '0'))
            except ValueError:
                size = 0
            mime = self.headers.get('Content-Type', '').split(';')[0]
            if size <= 0 or size > MAX_UPLOAD or mime not in ALLOWED_MIME:
                return self.reply({'error': 'Usa immagini o video supportati, massimo 300 MB per file.'}, 400)
            name = Path(unquote(self.headers.get('X-File-Name', 'media'))).name[:240]
            temp = self.server.data_dir / 'assets' / ('.upload-' + secrets.token_hex(8))
            sha = hashlib.sha256()
            remaining = size
            try:
                with temp.open('wb') as fp:
                    while remaining:
                        chunk = self.rfile.read(min(1024 * 1024, remaining))
                        if not chunk:
                            raise OSError('Upload interrotto.')
                        sha.update(chunk)
                        fp.write(chunk)
                        remaining -= len(chunk)
                digest = sha.hexdigest()
                dest = self.server.data_dir / 'assets' / digest
                os.replace(temp, dest)
                with self.db() as conn:
                    conn.execute('INSERT OR IGNORE INTO asset_files(id,mime,name,size) VALUES(?,?,?,?)', (digest, mime, name, size))
                return self.reply({'fileId': digest, 'sha256': digest, 'size': size, 'mime': mime, 'name': name}, 201)
            except (OSError, sqlite3.Error) as exc:
                temp.unlink(missing_ok=True)
                return self.reply({'error': 'Upload fallito: ' + str(exc)}, 500)
        self.reply({'error': 'Endpoint non trovato.'}, 404)


def main():
    parser = argparse.ArgumentParser(description='Server offline Carisma Display Control')
    parser.add_argument('--host', default='127.0.0.1', help='Default: solo questo computer. Per LAN: 0.0.0.0')
    parser.add_argument('--port', default=8787, type=int)
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'data')
    parser.add_argument('--cluster-config', type=Path, help='Configurazione privata Core A/B e coordinatore')
    parser.add_argument('--open', action='store_true', help='Apri la console nel browser')
    parser.add_argument('--ndi-library', default='', help='Percorso assoluto runtime NDI 64 bit')
    parser.add_argument('--ffmpeg', default='', help='Percorso assoluto ffmpeg/ffmpeg.exe')
    parser.add_argument('--ndi-extra-ips', default=os.environ.get('CARISMA_NDI_EXTRA_IPS', ''),
                        help='IP aggiuntivi per discovery NDI, separati da virgola')
    parser.add_argument('--ndi-max-streams', default=2, type=int,
                        help='Numero massimo encoder simultanei (1-8, predefinito 2)')
    parser.add_argument('--live-mode', choices=['responsive', 'stable'],
                        default=os.environ.get('CARISMA_LIVE_MODE', 'responsive'),
                        help='Reattiva (default) o stabile: segmento e buffer condivisi dai player')
    parser.add_argument('--prompt-osc-port', default=int(os.environ.get('CARISMA_PROMPT_OSC_PORT', '9000')), type=int,
                        help='Porta UDP OSC Carisma Prompt; 0 disabilita (default 9000)')
    parser.add_argument('--prompt-osc-bind', default=os.environ.get('CARISMA_PROMPT_OSC_BIND', '127.0.0.1'),
                        help='Indirizzo di ascolto OSC (default 0.0.0.0)')
    parser.add_argument('--prompt-osc-allow', default=os.environ.get('CARISMA_PROMPT_OSC_ALLOW', ''),
                        help='IP OSC consentiti separati da virgola; vuoto = qualunque host della LAN fidata')
    args = parser.parse_args()
    if args.live_mode not in ['responsive', 'stable']:
        parser.error('CARISMA_LIVE_MODE non valido: usare responsive o stable.')
    args.data_dir.mkdir(parents=True, exist_ok=True)
    instance_lock = exclusive_file_lock(args.data_dir / '.server.lock')
    (args.data_dir / 'assets').mkdir(exist_ok=True)
    tokenfile = args.data_dir / 'access.key'
    if not tokenfile.exists():
        tokenfile.write_text(secrets.token_urlsafe(30), encoding='utf-8')
        try:
            tokenfile.chmod(0o600)
        except OSError:
            pass
    token = tokenfile.read_text(encoding='utf-8').strip()
    with database(args.data_dir / 'controller.sqlite3') as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS state(id INTEGER PRIMARY KEY CHECK(id=1),version INTEGER NOT NULL,payload TEXT)')
        conn.execute('INSERT OR IGNORE INTO state(id,version,payload) VALUES(1,0,NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS asset_files(id TEXT PRIMARY KEY,mime TEXT,name TEXT,size INTEGER)')
    init_players(args.data_dir)
    prompt = PromptStore(args.data_dir)
    try:
        server = Server((args.host, args.port), Handler)
    except OSError as exc:
        raise SystemExit('Impossibile avviare il server: ' + str(exc))
    server.data_dir = args.data_dir.resolve()
    server.control_token = token
    server.monitor = MonitorStore()
    server.prompt = prompt
    server.shows = ShowPackages(server, valid_state, DB_LOCK)
    server.cluster = ClusterCore(server, args.cluster_config) if args.cluster_config else None
    server.prompt_osc = PromptOscServer(prompt, bind=args.prompt_osc_bind, port=args.prompt_osc_port, allow=args.prompt_osc_allow)
    if args.prompt_osc_port > 0:
        server.prompt_osc.start()
    server.gateway = Gateway(ROOT, server.data_dir, library=args.ndi_library,
                             ffmpeg=args.ffmpeg, extra_ips=args.ndi_extra_ips,
                             max_streams=args.ndi_max_streams, live_mode=args.live_mode)
    if server.cluster:
        server.cluster.start()
    url = 'http://127.0.0.1:%d/?key=%s' % (args.port, token)
    print('\nCARISMA / DISPLAY CONTROL v0.11.0-alpha / PROMPT + AKP03E\n')
    print('Apri nel browser: ' + url)
    print('Diretta: ' + server.gateway.playback['label'])
    print('Dati: ' + str(server.data_dir))
    print('Chiave locale: ' + token)
    print('Prompt: http://127.0.0.1:%d/prompt.html?key=%s' % (args.port, token))
    print('OSC Prompt: ' + (('%s:%d UDP' % (args.prompt_osc_bind, args.prompt_osc_port)) if server.prompt_osc.sock else ('DISABILITATO' if args.prompt_osc_port == 0 else 'ERRORE: '+server.prompt_osc.error)))
    print('Internet non richiesto. CTRL+C per arrestare.\n', flush=True)
    if args.host != '127.0.0.1':
        print('TEST LAN: usa http://IP-DEL-SERVER:%d e la chiave sopra.' % args.port)
        print('HTTP non cifrato: solo rete fidata; non esporre su Internet.\n', flush=True)
    if args.open:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    def shutdown_signal(signum, frame):
        raise KeyboardInterrupt
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, shutdown_signal)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print('\nServer arrestato. I dati sono conservati.')
    finally:
        if server.cluster:
            server.cluster.close()
        server.prompt_osc.close()
        server.gateway.close()
        server.server_close()
        instance_lock.close()


if __name__ == '__main__':
    main()
