"""Lease-fenced Core replication. Private cluster archives never become show packages."""
from __future__ import annotations

from contextlib import closing, contextmanager
import hashlib
import hmac
import io
import json
import os
import secrets
from pathlib import Path
import shutil
import sqlite3
import tempfile
import threading
import time
from urllib.parse import urlsplit
import urllib.request
import zipfile

from ndi.gateway import GatewayError
from storage import database_lock, transaction_hooks

MAX_CHECKPOINT = 64 * 1024**2


def endpoint(value):
    parts = urlsplit(value)
    if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment or parts.path not in ('', '/'):
        raise ValueError('Cluster endpoints must be HTTP(S) origins without credentials.')
    return value.rstrip('/')


def verified_media(path, ident, size, cache):
    if not path.is_file() or path.is_symlink():
        return False
    info = path.stat()
    stamp = (info.st_size, info.st_mtime_ns)
    if info.st_size != size:
        return False
    if cache.get(ident) == stamp:
        return True
    if hash_path(path) != ident:
        return False
    cache[ident] = stamp
    return True


def load_config(path):
    config = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(config.get('key'), str) or len(config['key']) < 32:
        raise ValueError('Cluster key must contain at least 32 characters.')
    nodes = config.get('nodes')
    if not isinstance(nodes, dict) or len(nodes) != 2 or any(not isinstance(k, str) or not k or len(k) > 40 for k in nodes):
        raise ValueError('Configure exactly two named Core nodes.')
    config['nodes'] = {key: endpoint(value) for key, value in nodes.items()}
    if len(set(config['nodes'].values())) != 2:
        raise ValueError('Core endpoints must be distinct.')
    if 'coordinator' in config:
        config['coordinator'] = endpoint(config['coordinator'])
    return config


def json_request(url, key, body=None, timeout=2):
    request = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(),
                                     headers={'X-Cluster-Key': key, 'Content-Type': 'application/json'})
    try:
        with network_response(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        exc.close()
        raise


@contextmanager
def network_response(request, timeout):
    try:
        response = urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        exc.close()
        raise
    try:
        yield response
    finally:
        response.close()


class ClusterCore:
    def __init__(self, server, config_path):
        self.server = server
        self.config = load_config(config_path)
        self.node = self.config['node']
        self.boot = secrets.token_hex(16)
        if self.node not in self.config['nodes']:
            raise ValueError('Unknown cluster node identity.')
        self.peer = next(n for n in self.config['nodes'] if n != self.node)
        self.key = self.config['key']
        self.witness = self.config['coordinator']
        self.cluster_id = hashlib.sha256(json.dumps([self.key, self.witness, self.config['nodes']], sort_keys=True).encode()).hexdigest()
        self.lock = threading.RLock()
        self.sync_lock = threading.RLock()
        self.local = threading.local()
        self.stop = threading.Event()
        self.deadline, self.term = 0.0, 0
        self.active = None
        self.error = 'Coordinatore non ancora raggiunto.'
        self.index, self.ready = 0, False
        self.record = server.data_dir / '.cluster-checkpoint.json'
        if self.record.is_file():
            value = json.loads(self.record.read_text())
            if value.get('cluster') == self.cluster_id:
                self.index, self.ready = int(value['index']), bool(value['ready'])
                self.ready = self.ready and value.get('fingerprint') == self.fingerprint()
        transaction_hooks(server.data_dir / 'controller.sqlite3', self.before_commit, self.after_commit)
        self.worker = threading.Thread(target=self.run, daemon=True, name='cluster-lease')
        self.peer_condition = threading.Condition()
        self.pending_checkpoint = None
        self.media_cache = {}
        self.peer_worker = threading.Thread(target=self.copy_peer, daemon=True, name='cluster-replica')

    def start(self):
        self.worker.start()
        self.peer_worker.start()

    def copy_peer(self):
        while not self.stop.is_set():
            with self.peer_condition:
                self.peer_condition.wait_for(lambda: self.pending_checkpoint is not None or self.stop.is_set(), timeout=1)
                raw, self.pending_checkpoint = self.pending_checkpoint, None
            if raw is None or not self.can_write():
                continue
            try:
                request = urllib.request.Request(self.config['nodes'][self.peer] + '/api/cluster/checkpoint',
                                                 data=raw, method='POST', headers={'X-Cluster-Key': self.key,
                                                 'Content-Type': 'application/zip'})
                with network_response(request, timeout=25) as response:
                    json.load(response)
            except Exception:
                pass

    def report(self):
        with self.lock:
            return {'node': self.node, 'boot': self.boot, 'checkpoint': self.index, 'ready': self.ready,
                    'active': self.active, 'term': self.term, 'writable': self.can_write(),
                    'error': self.error}

    def can_write(self):
        return self.active == self.node and time.monotonic() < self.deadline

    def require_write(self):
        if not self.can_write():
            raise GatewayError('Core non attivo o concessione del coordinatore scaduta. Usa l’indirizzo del coordinatore.', 503)

    @contextmanager
    def maintenance(self):
        previous = getattr(self.local, 'maintenance', False)
        self.local.maintenance = True
        try:
            yield
        finally:
            self.local.maintenance = previous

    def before_commit(self):
        if not getattr(self.local, 'maintenance', False):
            self.require_write()

    def after_commit(self):
        if not getattr(self.local, 'maintenance', False):
            try:
                self.synchronize()
            except Exception as exc:
                self.error = 'Scrittura locale non confermata sulla riserva.'
                raise GatewayError('Operazione locale eseguita, ma replica non confermata. Verifica i Core prima di ripetere comandi relativi.', 503) from exc

    def persist(self):
        temporary = self.record.with_suffix('.tmp')
        temporary.write_text(json.dumps({'index': self.index, 'ready': self.ready, 'cluster': self.cluster_id,
                                         'fingerprint': self.fingerprint()}), encoding='utf-8')
        os.replace(temporary, self.record)

    def fingerprint(self):
        digest = hashlib.sha256()
        with closing(sqlite3.connect(self.server.data_dir / 'controller.sqlite3')) as conn:
            names = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            for name in names:
                digest.update(name.encode())
                quoted = '"' + name.replace('"', '""') + '"'
                for row in conn.execute('SELECT * FROM ' + quoted + ' ORDER BY rowid'):
                    digest.update(repr(row).encode())
        digest.update(self.server.control_token.encode())
        return digest.hexdigest()

    def run(self):
        next_sync = 0
        while not self.stop.is_set():
            try:
                with self.lock:
                    started = time.monotonic()
                    result = json_request(self.witness + '/cluster/lease', self.key, self.report(), timeout=1)
                    self.active, self.term = result.get('active'), int(result['term'])
                    self.deadline = started + max(0, float(result.get('ttl', 0)) - .5) if self.active == self.node else 0
                    self.error = '' if self.can_write() or self.ready else 'In attesa della prima replica.'
                recovery_index = int(result.get('recoveryIndex', 0))
                if not self.can_write() and (recovery_index > self.index or (recovery_index > 0 and not self.ready)):
                    request = urllib.request.Request(self.witness + '/cluster/checkpoint', headers={'X-Cluster-Key': self.key})
                    with network_response(request, timeout=10) as response:
                        raw = response.read(MAX_CHECKPOINT + 1)
                    if len(raw) > MAX_CHECKPOINT:
                        raise GatewayError('Checkpoint di recupero troppo grande.', 413)
                    self.apply(raw, recovery=True)
                if self.can_write() and time.monotonic() >= next_sync:
                    # Replication runs separately so large media cannot stop lease renewals.
                    next_sync = time.monotonic() + 2
                    threading.Thread(target=self.background_sync, daemon=True).start()
            except Exception:
                self.error = 'Coordinatore non raggiungibile; scritture sospese alla scadenza della concessione.'
            self.stop.wait(.35)

    def background_sync(self):
        db_lock = database_lock(self.server.data_dir / 'controller.sqlite3')
        if not db_lock.acquire(blocking=False):
            return
        try:
            if self.sync_lock.acquire(blocking=False):
                try:
                    if self.can_write():
                        self.synchronize()
                finally:
                    self.sync_lock.release()
        except Exception:
            self.error = 'Riserva non sincronizzata.'
        finally:
            db_lock.release()

    def synchronize(self):
        with self.sync_lock:
            self.require_write()
            proposal = json_request(self.witness + '/cluster/prepare', self.key, {'node': self.node, 'term': self.term})
            index = proposal['index']
            with self.checkpoint(index) as archive:
                request = urllib.request.Request(self.witness + '/cluster/checkpoint', data=archive,
                                                 method='POST', headers={'X-Cluster-Key': self.key, 'Content-Type': 'application/zip'})
                with network_response(request, timeout=25) as response:
                    durable = json.load(response)
                if durable.get('checkpoint') != index:
                    raise GatewayError('Il coordinatore non ha confermato il checkpoint.', 503)
            json_request(self.witness + '/cluster/commit', self.key,
                         {'node': self.node, 'term': self.term, 'index': index, 'peer': self.peer})
            with self.lock:
                self.index, self.ready = index, True
                self.persist()
            with self.peer_condition:
                # Coalesce replica work; the coordinator already holds the durable copy.
                self.pending_checkpoint = archive
                self.peer_condition.notify()

    @contextmanager
    def checkpoint(self, index):
        dbpath = self.server.data_dir / 'controller.sqlite3'
        with tempfile.TemporaryDirectory(prefix='displaycontrol-checkpoint-') as temporary:
            snapshot = Path(temporary) / 'snapshot.sqlite3'
            with closing(sqlite3.connect(dbpath)) as source, closing(sqlite3.connect(snapshot)) as target:
                source.backup(target)
            with closing(sqlite3.connect(snapshot)) as compact:
                compact.execute('VACUUM')
            raw = snapshot.read_bytes()
            if len(raw) > MAX_CHECKPOINT - 1024**2:
                raise GatewayError('Checkpoint HA troppo grande.', 413)
            with closing(sqlite3.connect(snapshot)) as conn:
                media = [{'id': row[0], 'size': row[1]} for row in conn.execute('SELECT id,size FROM asset_files')]
            manifest = {'node': self.node, 'term': self.term, 'index': index,
                        'databaseSha256': hashlib.sha256(raw).hexdigest(), 'media': media}
            output = io.BytesIO()
            with zipfile.ZipFile(output, 'w') as archive:
                archive.writestr('manifest.json', json.dumps(manifest))
                archive.writestr('snapshot.sqlite3', raw)
                archive.writestr('identity.key', self.server.control_token)
            yield output.getvalue()

    def apply(self, raw, recovery=False):
        with database_lock(self.server.data_dir / 'controller.sqlite3'), self.lock:
            if self.can_write():
                raise GatewayError('Il Core attivo non accetta checkpoint in ingresso.', 409)
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                names = archive.namelist()
                if sorted(names) != ['identity.key', 'manifest.json', 'snapshot.sqlite3'] or sum(i.file_size for i in archive.infolist()) > MAX_CHECKPOINT:
                    raise GatewayError('Checkpoint non valido.', 400)
                manifest = json.loads(archive.read('manifest.json'))
                db = archive.read('snapshot.sqlite3')
                identity = archive.read('identity.key').decode('utf-8').strip()
            if len(identity) < 20 or len(identity) > 200 or hashlib.sha256(db).hexdigest() != manifest.get('databaseSha256'):
                raise GatewayError('Integrità checkpoint non valida.', 400)
            if (not recovery and manifest.get('node') != self.peer) or int(manifest['index']) < self.index:
                raise GatewayError('Checkpoint precedente o proveniente dal Core errato.', 409)
            permission = json_request(self.witness + ('/cluster/recovery-check' if recovery else '/cluster/check'), self.key,
                                      {'node': self.node if recovery else self.peer, 'term': manifest['term'],
                                       'index': manifest['index'], 'databaseSha256': manifest['databaseSha256']})
            if not permission.get('valid'):
                raise GatewayError('Il mittente non possiede la concessione attiva.', 409)
            for item in manifest['media']:
                ident = str(item['id'])
                if len(ident) != 64 or any(ch not in '0123456789abcdef' for ch in ident) or not 0 <= int(item['size']) <= 300 * 1024**2:
                    raise GatewayError('Media checkpoint non valido.', 400)
                target = self.server.data_dir / 'assets' / ident
                if verified_media(target, ident, item['size'], self.media_cache):
                    continue
                temporary = target.with_name('.ha-' + ident)
                try:
                    media_url = self.witness + '/cluster/media/' if recovery else self.config['nodes'][self.peer] + '/api/cluster/media/'
                    request = urllib.request.Request(media_url + ident,
                                                     headers={'X-Cluster-Key': self.key})
                    with network_response(request, timeout=20) as source, temporary.open('wb') as output:
                        remaining = item['size']
                        while remaining:
                            data = source.read(min(1024**2, remaining))
                            if not data:
                                raise GatewayError('Trasferimento media interrotto.', 503)
                            output.write(data)
                            remaining -= len(data)
                        if source.read(1):
                            raise GatewayError('Media oltre la dimensione dichiarata.', 400)
                    if hash_path(temporary) != ident:
                        raise GatewayError('SHA-256 media non corrispondente.', 400)
                    os.replace(temporary, target)
                    info = target.stat()
                    self.media_cache[ident] = (info.st_size, info.st_mtime_ns)
                finally:
                    temporary.unlink(missing_ok=True)
            with tempfile.TemporaryDirectory(prefix='displaycontrol-apply-') as temporary:
                snapshot = Path(temporary) / 'snapshot.sqlite3'
                snapshot.write_bytes(db)
                with closing(sqlite3.connect(snapshot)) as source:
                    if source.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                        raise GatewayError('Database checkpoint danneggiato.', 400)
                    required = {'state', 'asset_files', 'devices', 'prompt_project', 'prompt_runtime', 'prompt_devices', 'prompt_controllers'}
                    tables = {r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    if not required.issubset(tables):
                        raise GatewayError('Schema checkpoint incompleto.', 400)
                    # The hot-backup API commits the complete database atomically.
                    with closing(sqlite3.connect(self.server.data_dir / 'controller.sqlite3')) as target:
                        source.backup(target)
            keyfile = self.server.data_dir / '.access-key.tmp'
            keyfile.write_text(identity, encoding='utf-8')
            os.replace(keyfile, self.server.data_dir / 'access.key')
            self.server.control_token = identity
            self.index, self.ready = int(manifest['index']), True
            self.persist()
            return self.report()

    def close(self):
        self.stop.set()
        with self.peer_condition:
            self.peer_condition.notify_all()
        self.worker.join(timeout=2)
        self.peer_worker.join(timeout=2)


def hash_path(path):
    result = hashlib.sha256()
    with path.open('rb') as source:
        for data in iter(lambda: source.read(1024**2), b''):
            result.update(data)
    return result.hexdigest()


def handle_cluster(h, path):
    if not path.startswith('/api/cluster/'):
        return False
    core = getattr(h.server, 'cluster', None)
    if core is None or not hmac.compare_digest(h.headers.get('X-Cluster-Key', ''), core.key):
        h.reply({'error': 'Accesso cluster non autorizzato.'}, 403)
        return True
    try:
        if path == '/api/cluster/health' and h.command in ('GET', 'HEAD'):
            h.reply(core.report())
        elif path == '/api/cluster/checkpoint' and h.command == 'POST':
            size = int(h.headers.get('Content-Length', '0'))
            if not 0 < size <= MAX_CHECKPOINT:
                raise GatewayError('Dimensione checkpoint non valida.', 413)
            raw = h.rfile.read(size)
            if len(raw) != size:
                raise GatewayError('Checkpoint interrotto.', 400)
            h.reply(core.apply(raw))
        elif path.startswith('/api/cluster/media/') and h.command in ('GET', 'HEAD'):
            ident = path.rsplit('/', 1)[-1]
            if len(ident) != 64 or any(c not in '0123456789abcdef' for c in ident):
                raise GatewayError('Identificativo media non valido.', 400)
            target = core.server.data_dir / 'assets' / ident
            if not target.is_file() or target.is_symlink():
                raise GatewayError('Media non disponibile.', 404)
            h.send_response(200)
            h.send_header('Content-Length', str(target.stat().st_size))
            h.send_header('Cache-Control', 'no-store')
            h.end_headers()
            if h.command != 'HEAD':
                with target.open('rb') as source:
                    shutil.copyfileobj(source, h.wfile, 1024**2)
        else:
            h.reply({'error': 'Endpoint cluster non trovato.'}, 404)
    except GatewayError as exc:
        h.reply({'error': str(exc)}, exc.status)
    except Exception:
        h.reply({'error': 'Replica cluster non riuscita.'}, 503)
    return True
