#!/usr/bin/env python3
"""Local player shell for Raspberry/PC kiosks; scoped API proxy, no remote code."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from cluster import endpoint

ROOT = Path(__file__).resolve().parent
SHELL = {'/prompt_player.html': 'prompt_player.html', '/prompt_shared.js': 'prompt_shared.js',
         '/branding.js': 'branding.js', '/favicon.svg': 'favicon.svg', '/connect.html': 'connect.html',
         '/player.html': 'player.html', '/physical_boot.js': 'physical_boot.js', '/sw.js': 'station_sw.js'}


def allowed(path, method, mode):
    if path in ('/api/branding', '/api/info'):
        return method in ('GET', 'HEAD')
    if mode == 'prompt':
        return ((path == '/api/prompt/pair' and method == 'POST') or
                (path == '/api/prompt/player/state' and method in ('GET', 'HEAD')) or
                (path == '/api/prompt/player/heartbeat' and method == 'POST'))
    if path == '/api/player/pair':
        return method == 'POST'
    if path in ('/api/player/state',) or path.startswith(('/api/player/assets/', '/api/player/ndi/manifest/', '/api/player/ndi/media/')):
        return method in ('GET', 'HEAD')
    return path in ('/api/player/heartbeat', '/api/player/preview', '/api/player/ndi/start') and method == 'POST'


class Station(ThreadingHTTPServer):
    daemon_threads = True

    def save_identity(self, value):
        with self.identity_lock:
            self.config['token'] = value['token']
            if 'screenId' in value:
                self.config['screenId'] = value['screenId']
            temporary = self.config_path.with_suffix('.tmp')
            temporary.write_text(json.dumps(self.config, indent=2), encoding='utf-8')
            try:
                temporary.chmod(0o600)
            except OSError:
                pass
            os.replace(temporary, self.config_path)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, code, body, content_type='application/json', extra=None):
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = urlsplit(self.path).path
        config = self.server.config
        if path.startswith('/api/'):
            return self.proxy()
        if path == '/':
            target = '/prompt_player.html' if config['mode'] == 'prompt' else (
                '/player.html?player=' + config['screenId'] + '&kiosk=1' if config.get('screenId') else '/connect.html')
            return self.send(302, b'', extra={'Location': target})
        if path not in SHELL:
            return self.send(404, b'{"error":"Risorsa locale non disponibile."}')
        file = ROOT / SHELL[path]
        raw = file.read_bytes()
        if path == '/prompt_player.html' and config.get('token'):
            # Restore only this station's scoped token if browser storage was cleared.
            value = json.dumps(config['token']).replace('<', '\\u003c')
            script = '<script>localStorage.setItem("carisma-prompt-token-v1",' + value + ');</script>'
            raw = raw.replace(b'<script src="./branding.js">', script.encode() + b'<script src="./branding.js">', 1)
        content_type = {'html': 'text/html; charset=utf-8', 'js': 'text/javascript; charset=utf-8', 'svg': 'image/svg+xml'}[file.suffix[1:]]
        self.send(200, raw, content_type)

    def do_POST(self):
        self.proxy()

    def proxy(self):
        path = urlsplit(self.path).path
        config = self.server.config
        if not allowed(path, self.command, config['mode']):
            return self.send(403, b'{"error":"API non consentita alla postazione player."}')
        response = None
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 <= size <= 2 * 1024**2:
                return self.send(413, b'{"error":"Richiesta troppo grande."}')
            body = self.rfile.read(size) if self.command == 'POST' else None
            token_header = 'X-Prompt-Token' if config['mode'] == 'prompt' else 'X-Player-Token'
            headers = {'Content-Type': self.headers.get('Content-Type', 'application/json'),
                       token_header: config.get('token', '')}
            request = urllib.request.Request(config['server'] + self.path, data=body, headers=headers, method=self.command)
            try:
                response = urllib.request.urlopen(request, timeout=4)
            except urllib.error.HTTPError as exc:
                response = exc
            content_type = response.headers.get('Content-Type', 'application/octet-stream')
            if self.command == 'POST' and path in ('/api/prompt/pair', '/api/player/pair') and response.status == 201:
                raw = response.read(16384)
                value = json.loads(raw)
                self.server.save_identity(value)
                return self.send(response.status, raw, content_type)
            self.send_response(response.status)
            self.send_header('Content-Type', content_type)
            self.send_header('Cache-Control', 'no-store')
            if response.headers.get('Content-Length'):
                self.send_header('Content-Length', response.headers['Content-Length'])
            self.end_headers()
            if self.command != 'HEAD':
                for chunk in iter(lambda: response.read(1024**2), b''):
                    self.wfile.write(chunk)
        except (OSError, ValueError):
            if response is None:
                self.send(503, b'{"error":"Regia non raggiungibile. Il player mantiene la copia locale disponibile."}')
        finally:
            if response:
                response.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'data/station.json')
    parser.add_argument('--server', help='Coordinator/server HTTP(S) origin; saves first setup')
    parser.add_argument('--mode', choices=('prompt', 'signage'))
    parser.add_argument('--port', type=int, default=8877)
    args = parser.parse_args()
    if args.config.exists():
        config = json.loads(args.config.read_text(encoding='utf-8'))
        if args.server and endpoint(args.server) != config['server']:
            parser.error('Per cambiare server crea una nuova configurazione e ripeti il pairing.')
    else:
        if not args.server or not args.mode:
            parser.error('Prima configurazione: --server http://COORDINATORE:8787 --mode prompt|signage')
        config = {'server': endpoint(args.server), 'mode': args.mode}
        args.config.parent.mkdir(parents=True, exist_ok=True)
        args.config.write_text(json.dumps(config, indent=2), encoding='utf-8')
        try:
            args.config.chmod(0o600)
        except OSError:
            pass
    config['server'] = endpoint(config['server'])
    if config.get('mode') not in ('prompt', 'signage'):
        parser.error('Modalità player non valida.')
    server = Station(('127.0.0.1', args.port), Handler)
    server.config, server.config_path, server.identity_lock = config, args.config, threading.Lock()
    def stop(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    print(f'DisplayControl player station: http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever(poll_interval=.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
