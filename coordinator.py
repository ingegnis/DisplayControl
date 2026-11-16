#!/usr/bin/env python3
"""Single Core lease authority and stable browser/controller HTTP entry point."""
from __future__ import annotations

import argparse
import hmac
import hashlib
import http.client
import json
import os
from pathlib import Path
import signal
import socket
import shutil
import threading
import time
import io
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from cluster import load_config, MAX_CHECKPOINT, hash_path, network_response, verified_media
from storage import exclusive_file_lock
from prompt_module import parse_osc_packet

LEASE_SECONDS = 6.0
ROOT = Path(__file__).resolve().parent
SHELL = {name: name.lstrip('/') for name in ('/index.html', '/player.html', '/prompt.html', '/prompt_player.html',
         '/monitor.html', '/show.html', '/players.html', '/connect.html', '/branding.js', '/prompt_shared.js',
         '/physical_boot.js', '/sw.js', '/favicon.svg')}
SHELL['/'] = 'index.html'
HOP_HEADERS = {'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
               'te', 'trailer', 'transfer-encoding', 'upgrade', 'host', 'x-cluster-key'}


class Authority:
    def __init__(self, config, state_path):
        self.config, self.path = config, state_path
        self.lock = threading.RLock()
        self.active = None
        self.active_boot = None
        self.term, self.committed, self.next_index = 0, 0, 0
        self.deadline = 0
        self.nodes = {}
        self.started = time.monotonic()
        self.recover_until = 0
        if self.path.exists():
            value = json.loads(self.path.read_text())
            self.active, self.term = value['active'], int(value['term'])
            self.active_boot = value.get('activeBoot')
            self.committed, self.next_index = int(value['committed']), int(value['nextIndex'])
            # Existing grants may outlive a coordinator restart.
            self.recover_until = self.started + LEASE_SECONDS
        self.initial = config.get('initialPrimary', next(iter(config['nodes'])))
        self.media = self.path.parent / 'assets'
        self.media_cache = {}
        self.media.mkdir(parents=True, exist_ok=True)
        if self.initial not in config['nodes']:
            raise ValueError('initialPrimary is not a configured Core.')

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        with temporary.open('w', encoding='utf-8') as output:
            json.dump({'active': self.active, 'activeBoot': self.active_boot, 'term': self.term, 'committed': self.committed,
                       'nextIndex': self.next_index}, output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, self.path)

    def valid(self, node, term):
        with self.lock:
            return (time.monotonic() >= self.recover_until and self.active == node and
                    self.term == term and time.monotonic() < self.deadline)

    def lease(self, body):
        node = body.get('node')
        if node not in self.config['nodes']:
            raise ValueError('Unknown Core.')
        now = time.monotonic()
        with self.lock:
            self.nodes[node] = dict(body, seen=now)
            if self.term == 0 and any(int(info.get('checkpoint', 0)) > 0 for info in self.nodes.values()):
                raise ValueError('Coordinator history missing; restore its private backup.')
            if now < self.recover_until:
                return {'active': None, 'term': self.term, 'ttl': 0, 'recoveryIndex': self.committed}
            if now >= self.deadline:
                candidates = [n for n, info in self.nodes.items()
                              if now - info['seen'] < 1.5 and
                              ((info.get('ready') and int(info.get('checkpoint', -1)) >= self.committed)
                               or (self.term == 0 and n == self.initial and self.committed == 0))]
                chosen = self.active if self.active in candidates else next(iter(candidates), None)
                if chosen is not None:
                    self.active, self.term = chosen, self.term + 1
                    self.active_boot = self.nodes[chosen].get('boot')
                    self.save()
                    self.deadline = now + LEASE_SECONDS
            same_process = self.active_boot == body.get('boot')
            if self.active == node and same_process and now < self.deadline:
                self.deadline = now + LEASE_SECONDS
            return {'active': self.active if now < self.deadline else None, 'term': self.term,
                    'ttl': max(0, self.deadline - now) if self.active == node and same_process else 0,
                    'recoveryIndex': self.committed}

    def prepare(self, body):
        with self.lock:
            if not self.valid(body.get('node'), body.get('term')):
                raise ValueError('Expired lease.')
            self.next_index += 1
            self.save()
            return {'index': self.next_index}

    def commit(self, body):
        with self.lock:
            index = int(body.get('index', -1))
            if (not self.valid(body.get('node'), body.get('term')) or
                    body.get('peer') not in self.config['nodes'] or body['peer'] == body['node'] or
                    not self.committed < index <= self.next_index or not self.checkpoint_path(index).is_file()):
                raise ValueError('Invalid commit.')
            self.committed = index
            self.save()
            archives = sorted(self.path.parent.glob('checkpoint-*.zip'), key=lambda p: int(p.stem.split('-')[1]), reverse=True)
            for path in archives[2:]:
                path.unlink(missing_ok=True)
            return {'committed': self.committed}

    def checkpoint_path(self, index):
        return self.path.parent / f'checkpoint-{int(index)}.zip'

    def store_checkpoint(self, raw):
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if sorted(archive.namelist()) != ['identity.key', 'manifest.json', 'snapshot.sqlite3'] or sum(i.file_size for i in archive.infolist()) > MAX_CHECKPOINT:
                raise ValueError('Invalid checkpoint.')
            manifest = json.loads(archive.read('manifest.json'))
            if hashlib.sha256(archive.read('snapshot.sqlite3')).hexdigest() != manifest.get('databaseSha256'):
                raise ValueError('Invalid database checksum.')
        with self.lock:
            if not self.valid(manifest.get('node'), manifest.get('term')) or not self.committed < int(manifest['index']) <= self.next_index:
                raise ValueError('Expired checkpoint.')
        for item in manifest['media']:
            ident = str(item['id'])
            if len(ident) != 64 or any(c not in '0123456789abcdef' for c in ident) or not 0 <= int(item['size']) <= 300 * 1024**2:
                raise ValueError('Invalid media metadata.')
            target = self.media / ident
            if verified_media(target, ident, item['size'], self.media_cache):
                continue
            temporary = target.with_name('.incoming-' + ident)
            try:
                request = urllib.request.Request(self.config['nodes'][manifest['node']] + '/api/cluster/media/' + ident,
                                                 headers={'X-Cluster-Key': self.config['key']})
                with network_response(request, timeout=20) as source, temporary.open('wb') as output:
                    remaining = int(item['size'])
                    while remaining:
                        chunk = source.read(min(1024**2, remaining))
                        if not chunk:
                            raise ValueError('Interrupted media.')
                        output.write(chunk)
                        remaining -= len(chunk)
                    if source.read(1):
                        raise ValueError('Media exceeds declared size.')
                    output.flush()
                    os.fsync(output.fileno())
                if hash_path(temporary) != ident:
                    raise ValueError('Invalid media checksum.')
                os.replace(temporary, target)
                info = target.stat()
                self.media_cache[ident] = (info.st_size, info.st_mtime_ns)
            finally:
                temporary.unlink(missing_ok=True)
        with self.lock:
            if not self.valid(manifest['node'], manifest['term']):
                raise ValueError('Lease expired during checkpoint.')
            target = self.checkpoint_path(manifest['index'])
            temporary = target.with_suffix('.tmp')
            with temporary.open('wb') as output:
                output.write(raw)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, target)
        return {'checkpoint': manifest['index']}

    def recovery_valid(self, body):
        with self.lock:
            if body.get('node') not in self.config['nodes'] or (self.route() and body['node'] == self.active) or int(body.get('index', -1)) != self.committed:
                return False
            with zipfile.ZipFile(self.checkpoint_path(self.committed)) as archive:
                manifest = json.loads(archive.read('manifest.json'))
            return manifest['databaseSha256'] == body.get('databaseSha256')

    def route(self):
        with self.lock:
            if not self.valid(self.active, self.term):
                return None
            return self.config['nodes'].get(self.active)

    def status(self):
        with self.lock:
            return {'active': self.active if self.route() else None, 'term': self.term,
                    'needsRecovery': self.term == 0 and any(int(info.get('checkpoint', 0)) > 0 for info in self.nodes.values()),
                    'committed': self.committed, 'nodes': {
                        node: {'ready': bool(self.nodes.get(node, {}).get('ready')),
                               'checkpoint': self.nodes.get(node, {}).get('checkpoint', 0),
                               'reachable': time.monotonic() - self.nodes.get(node, {}).get('seen', 0) < 1.5}
                        for node in self.config['nodes']}}


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *args):
        pass

    def reply(self, value, code=200):
        body = json.dumps(value).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def private(self):
        path = urlsplit(self.path).path
        if not path.startswith('/cluster/'):
            return False
        if not hmac.compare_digest(self.headers.get('X-Cluster-Key', ''), self.server.authority.config['key']):
            self.reply({'error': 'Accesso coordinatore non autorizzato.'}, 403)
            return True
        try:
            if path == '/cluster/checkpoint' and self.command == 'POST':
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= MAX_CHECKPOINT:
                    raise ValueError('Invalid checkpoint size.')
                raw = self.rfile.read(size)
                self.reply(self.server.authority.store_checkpoint(raw))
                return True
            if path == '/cluster/checkpoint' and self.command == 'GET':
                return self.send_file(self.server.authority.checkpoint_path(self.server.authority.committed))
            if path.startswith('/cluster/media/') and self.command == 'GET':
                ident = path.rsplit('/', 1)[-1]
                if len(ident) != 64 or any(c not in '0123456789abcdef' for c in ident):
                    raise ValueError('Invalid media ID.')
                return self.send_file(self.server.authority.media / ident)
            if path == '/cluster/status' and self.command in ('GET', 'HEAD'):
                self.reply(self.server.authority.status())
                return True
            size = int(self.headers.get('Content-Length', '0'))
            if self.command != 'POST' or not 0 < size <= 16384:
                raise ValueError('Invalid request.')
            body = json.loads(self.rfile.read(size))
            authority = self.server.authority
            if path == '/cluster/lease':
                value = authority.lease(body)
            elif path == '/cluster/prepare':
                value = authority.prepare(body)
            elif path == '/cluster/commit':
                value = authority.commit(body)
            elif path == '/cluster/check':
                value = {'valid': authority.valid(body.get('node'), body.get('term'))}
            elif path == '/cluster/recovery-check':
                value = {'valid': authority.recovery_valid(body)}
            else:
                raise ValueError('Unknown endpoint.')
            self.reply(value)
        except (ValueError, TypeError, KeyError, OSError, zipfile.BadZipFile):
            self.reply({'error': 'Concessione o richiesta cluster non valida.'}, 409)
        return True

    def send_file(self, path):
        if not path.is_file() or path.is_symlink():
            self.reply({'error': 'Copia di recupero non disponibile.'}, 404)
            return True
        self.send_response(200)
        self.send_header('Content-Length', str(path.stat().st_size))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        with path.open('rb') as source:
            shutil.copyfileobj(source, self.wfile, 1024**2)
        return True

    def proxy(self):
        if self.private():
            return
        path = urlsplit(self.path).path
        if self.command in ('GET', 'HEAD') and path in SHELL:
            file = ROOT / SHELL[path]
            raw = file.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.svg': 'image/svg+xml'}[file.suffix])
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(raw)
            return
        if urlsplit(self.path).path.startswith('/api/cluster/'):
            return self.reply({'error': 'Usa gli endpoint privati dei Core per la replica.'}, 403)
        origin = self.server.authority.route()
        if not origin:
            return self.reply({'error': 'Nessun Core con concessione valida. I player conservano il contenuto locale.'}, 503)
        connection = None
        sent = False
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 <= length <= 2 * 1024**3 + 8 * 1024**2 or self.headers.get('Transfer-Encoding'):
                return self.reply({'error': 'Richiesta troppo grande o non supportata.'}, 413)
            target = urlsplit(origin)
            cls = http.client.HTTPSConnection if target.scheme == 'https' else http.client.HTTPConnection
            connection = cls(target.hostname, target.port, timeout=40)
            connection.putrequest(self.command, self.path)
            for key, value in self.headers.items():
                if key.lower() not in HOP_HEADERS:
                    connection.putheader(key, value)
            connection.endheaders()
            remaining = length
            while remaining:
                chunk = self.rfile.read(min(1024**2, remaining))
                if not chunk:
                    raise OSError('Interrupted request.')
                connection.send(chunk)
                remaining -= len(chunk)
            response = connection.getresponse()
            self.send_response(response.status)
            for key, value in response.getheaders():
                if key.lower() not in HOP_HEADERS | {'server', 'date'}:
                    self.send_header(key, value)
            if response.getheader('Content-Length') is None:
                self.send_header('Connection', 'close')
                self.close_connection = True
            self.end_headers()
            sent = True
            if self.command != 'HEAD':
                for chunk in iter(lambda: response.read(1024**2), b''):
                    self.wfile.write(chunk)
        except (OSError, http.client.HTTPException, ValueError):
            self.close_connection = True
            # Never replay an ambiguous mutation against another Core.
            if not sent:
                self.reply({'error': 'Core non raggiungibile. Attendi il subentro; nessun comando è stato ripetuto automaticamente.'}, 503)
        finally:
            if connection:
                connection.close()

    do_GET = do_HEAD = do_POST = do_PUT = proxy


class OscRelay:
    def __init__(self, authority, host, port, allow):
        self.authority, self.allow = authority, set(allow)
        self.stop = threading.Event()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((host, port))
        self.socket.settimeout(.25)
        self.thread = threading.Thread(target=self.run, daemon=True, name='coordinator-osc')

    def run(self):
        while not self.stop.is_set():
            try:
                data, source = self.socket.recvfrom(16385)
                if len(data) > 16384 or (self.allow and source[0] not in self.allow):
                    continue
                messages = parse_osc_packet(data)
                if not messages or any(not address.startswith('/carisma/prompt/') for address, _ in messages):
                    continue
                target = self.authority.route()
                if target:
                    node = self.authority.active
                    port = int(self.authority.config.get('oscPorts', {}).get(node, 9001))
                    self.socket.sendto(data, (urlsplit(target).hostname, port))
            except (OSError, ValueError, KeyError):
                pass

    def close(self):
        self.stop.set()
        self.thread.join(timeout=1)
        self.socket.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--data-dir', type=Path, default=Path(__file__).resolve().parent / 'data/coordinator')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8787)
    parser.add_argument('--osc-port', type=int, default=0, help='0 disables OSC relay; typical LAN setup: 9000')
    parser.add_argument('--osc-allow', default='127.0.0.1', help='Comma-separated allowed sender IPs')
    args = parser.parse_args()
    args.data_dir.mkdir(parents=True, exist_ok=True)
    instance_lock = exclusive_file_lock(args.data_dir / '.coordinator.lock')
    authority = Authority(load_config(args.config), args.data_dir / 'authority.json')
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.daemon_threads = True
    server.authority = authority
    relay = OscRelay(authority, args.host, args.osc_port, [value.strip() for value in args.osc_allow.split(',') if value.strip()]) if args.osc_port else None
    if relay:
        relay.thread.start()
    def stop(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    print(f'DisplayControl coordinator: http://{args.host}:{args.port}; trusted LAN only.', flush=True)
    try:
        server.serve_forever(poll_interval=.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if relay:
            relay.close()
        instance_lock.close()


if __name__ == '__main__':
    main()
