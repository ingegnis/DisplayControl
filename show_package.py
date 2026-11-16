"""Portable show archives: content hashes, bounded validation and atomic activation."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import tempfile
import threading
import time
from urllib.parse import urlsplit
import zipfile

from ndi.gateway import GatewayError
from prompt_module import parse_script, _clean_settings
from storage import database

FORMAT = 'DisplayControl.ShowPackage'
MAX_PACKAGE = 2 * 1024**3
MAX_METADATA = 8 * 1024**2
MAX_FILES = 2003
HEX = re.compile(r'^[a-f0-9]{64}$')
SENSITIVE = re.compile(r'(?i)^(?:.*token|.*password|.*secret|credentials?|(?:access|api|cluster|private|signing)[_-]?key|key|authorization|serverTokens|serverControllerIds)$')
MIMES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif', 'video/mp4', 'video/webm'}


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def decoded(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON field.')
            result[key] = value
        return result
    def finite(_):
        raise ValueError('Non-finite JSON number.')
    return json.loads(raw, object_pairs_hook=unique, parse_constant=finite)


def sha_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024**2), b''):
            digest.update(chunk)
    return digest.hexdigest()


def portable(value):
    if isinstance(value, dict):
        return {key: portable(item) for key, item in value.items() if not SENSITIVE.fullmatch(key)}
    if isinstance(value, list):
        return [portable(item) for item in value]
    return value


def validate_project(state, validator):
    if not validator(state):
        raise GatewayError('Progetto SHOW PACKAGE non valido.', 400)
    assets = {a['id']: a for a in state['assets']}
    playlists = {p['id']: p for p in state['playlists']}
    screens = {s['id'] for s in state['screens']}

    def reference(value):
        if value is None:
            return
        if not isinstance(value, dict):
            raise GatewayError('Riferimento contenuto non valido.', 400)
        kind = value.get('type')
        if kind == 'black':
            return
        if kind not in ('asset', 'playlist') or value.get('id') not in (assets if kind == 'asset' else playlists):
            raise GatewayError('Il pacchetto contiene riferimenti a contenuti mancanti.', 400)

    for asset in assets.values():
        if asset.get('kind') not in {'clock', 'poster', 'image', 'video', 'live'}:
            raise GatewayError('Tipo di contenuto non supportato.', 400)
        if asset.get('kind') in {'image', 'video'}:
            if not HEX.fullmatch(str(asset.get('fileId', ''))):
                raise GatewayError('Media senza identificativo SHA-256 valido.', 400)
            if type(asset.get('size')) is not int or not 0 < asset['size'] <= 300 * 1024**2 or (asset.get('sha256') and asset['sha256'] != asset['fileId']):
                raise GatewayError('Dimensione o SHA-256 del media non valido.', 400)
        url = asset.get('url', '')
        if isinstance(url, str) and url:
            parts = urlsplit(url)
            if parts.username or parts.password or parts.query:
                raise GatewayError('Rimuovi credenziali e query private dagli URL live prima di esportare.', 400)
    for playlist in playlists.values():
        if not isinstance(playlist.get('items'), list):
            raise GatewayError('Playlist non valida.', 400)
        for item in playlist['items']:
            if not isinstance(item, dict) or item.get('assetId') not in assets:
                raise GatewayError('Playlist con contenuti mancanti.', 400)
    for screen in state['screens']:
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,120}', screen['id']):
            raise GatewayError('Identificativo schermo non valido.', 400)
        reference(screen.get('base'))
        reference(screen.get('override'))
        if screen.get('fallbackAssetId') and screen['fallbackAssetId'] not in assets:
            raise GatewayError('Contenuto di riserva mancante.', 400)
    for rule in state['schedules']:
        if not isinstance(rule.get('screenIds'), list) or any(s not in screens for s in rule['screenIds']):
            raise GatewayError('Palinsesto con schermi mancanti.', 400)
        reference(rule.get('content'))


class ShowPackages:
    def __init__(self, server, validator, db_lock):
        self.server, self.validator, self.db_lock = server, validator, db_lock
        self.root = server.data_dir
        self.lock = threading.RLock()
        self.staging = self.root / '.show-staging'
        self.staging.mkdir(exist_ok=True)
        if self.root.resolve() not in self.staging.resolve().parents:
            raise RuntimeError('La cartella temporanea deve restare nella cartella dati.')
        # Staged uploads are session-local; never reactivate one after a restart.
        for path in self.staging.iterdir():
            if path.is_dir() and not path.is_symlink():
                self.remove_stage(path)
        with database(self.root / 'controller.sqlite3') as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS show_active(id INTEGER PRIMARY KEY CHECK(id=1),package_id TEXT,title TEXT,activated REAL)')
        self.pending = {}

    def remove_stage(self, folder):
        folder = Path(folder)
        if self.staging.resolve() not in folder.resolve().parents:
            raise RuntimeError('Cartella temporanea fuori dal progetto; nessun file eliminato.')
        shutil.rmtree(folder, ignore_errors=True)

    def status(self):
        with database(self.root / 'controller.sqlite3') as conn:
            row = conn.execute('SELECT package_id,title,activated FROM show_active WHERE id=1').fetchone()
            versions = conn.execute('SELECT state.version,prompt_project.version FROM state,prompt_project WHERE state.id=1 AND prompt_project.id=1').fetchone()
        return {'active': dict(zip(('id', 'title', 'activated'), row)) if row else None,
                'formatVersion': 1, 'maxBytes': MAX_PACKAGE,
                'revision': versions[0], 'promptVersion': versions[1],
                'rollbackAvailable': (self.root / 'show-previous.show.zip').is_file()}

    @contextmanager
    def export(self):
        with self.lock, self.server.prompt.lock, self.db_lock:
            with database(self.root / 'controller.sqlite3') as conn:
                row = conn.execute('SELECT version,payload FROM state WHERE id=1').fetchone()
                media = {r[0]: {'mime': r[1], 'name': r[2], 'size': r[3]} for r in conn.execute('SELECT id,mime,name,size FROM asset_files')}
                project = self.server.prompt.project()
            if not row or not row[1]:
                raise GatewayError('Crea e salva prima il progetto dalla regia.', 409)
            state = portable(json.loads(row[1]))
            state['events'] = []
            validate_project(state, self.validator)
            prompt = {'title': project['title'], 'text': project['script']['text'], 'settings': project['settings']}
            payload = {'project.json': encoded(state), 'prompt.json': encoded(prompt)}
            files = {name: {'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data)} for name, data in payload.items()}
            paths = {}
            for asset in state['assets']:
                if asset.get('kind') not in {'image', 'video'}:
                    continue
                ident = asset['fileId']
                if ident in paths:
                    continue
                path = self.root / 'assets' / ident
                info = media.get(ident)
                if not info or not path.is_file() or path.is_symlink() or info['mime'] not in MIMES:
                    raise GatewayError('Media mancante o non supportato: ' + str(asset.get('title', ident)), 409)
                size = path.stat().st_size
                if sha_file(path) != ident or size != info['size']:
                    raise GatewayError('Integrità media non valida: ' + str(asset.get('title', ident)), 409)
                paths[ident] = path
                files['media/' + ident] = dict(info, size=size, sha256=ident, name=Path(info['name']).name)
            if sum(v['size'] for v in files.values()) > MAX_PACKAGE:
                raise GatewayError('Lo spettacolo supera il limite di 2 GiB.', 413)
            manifest = {'format': FORMAT, 'version': 1, 'id': secrets.token_hex(16),
                        'title': project['title'], 'created': time.time(), 'files': files,
                        'excluded': ['credentials', 'pairings', 'machineConfiguration', 'runtime'],
                        'liveSources': [a['id'] for a in state['assets'] if a.get('kind') == 'live']}
            with tempfile.TemporaryFile() as output:
                with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED) as archive:
                    archive.writestr('manifest.json', encoded(manifest))
                    for name, data in payload.items():
                        archive.writestr(name, data)
                    for ident, path in paths.items():
                        archive.write(path, 'media/' + ident)
                output.seek(0, 2)
                size = output.tell()
                output.seek(0)
                yield output, size, manifest

    def stage(self, source):
        folder = Path(tempfile.mkdtemp(dir=self.staging))
        try:
            with zipfile.ZipFile(source) as archive:
                entries = archive.infolist()
                names = [item.filename for item in entries]
                if len(entries) > MAX_FILES or len(set(names)) != len(names) or sum(i.file_size for i in entries) > MAX_PACKAGE + MAX_METADATA:
                    raise GatewayError('Archivio duplicato o troppo grande.', 400)
                for item in entries:
                    if item.filename not in {'manifest.json', 'project.json', 'prompt.json'} and not re.fullmatch(r'media/[a-f0-9]{64}', item.filename):
                        raise GatewayError('File non consentito nel pacchetto.', 400)
                    mode = item.external_attr >> 16
                    if item.flag_bits & 1 or item.is_dir() or stat.S_ISLNK(mode) or item.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                        raise GatewayError('Tipo di archivio non consentito.', 400)
                    if item.filename.endswith('.json') and item.file_size > MAX_METADATA:
                        raise GatewayError('Metadati troppo grandi.', 413)
                if not {'manifest.json', 'project.json', 'prompt.json'}.issubset(names):
                    raise GatewayError('Pacchetto incompleto.', 400)
                manifest = decoded(archive.read('manifest.json'))
                if manifest.get('format') != FORMAT or manifest.get('version') != 1 or not re.fullmatch(r'[a-f0-9]{32}', str(manifest.get('id', ''))):
                    raise GatewayError('Formato SHOW PACKAGE non supportato.', 400)
                files = manifest.get('files')
                if not isinstance(files, dict) or set(files) != set(names) - {'manifest.json'}:
                    raise GatewayError('Manifest non coerente con i file.', 400)
                for item in entries:
                    if item.filename == 'manifest.json':
                        continue
                    expected = files[item.filename]
                    if not isinstance(expected, dict) or item.file_size != expected.get('size') or not HEX.fullmatch(str(expected.get('sha256', ''))):
                        raise GatewayError('Dimensione o hash non valido.', 400)
                    dest = folder / item.filename
                    dest.parent.mkdir(exist_ok=True)
                    with archive.open(item) as data, dest.open('wb') as output:
                        shutil.copyfileobj(data, output, 1024**2)
                    if sha_file(dest) != expected['sha256']:
                        raise GatewayError('SHA-256 del pacchetto non corrispondente.', 400)
                if (folder / 'project.json').stat().st_size > 2 * 1024**2:
                    raise GatewayError('Il progetto supera il limite dei metadati della console.', 413)
                state = decoded((folder / 'project.json').read_text(encoding='utf-8'))
                if portable(state) != state:
                    raise GatewayError('Il progetto contiene campi riservati alle credenziali.', 400)
                validate_project(state, self.validator)
                prompt = decoded((folder / 'prompt.json').read_text(encoding='utf-8'))
                if set(prompt) != {'title', 'text', 'settings'} or not isinstance(prompt['title'], str) or len(prompt['title']) > 120:
                    raise GatewayError('Copione del pacchetto non valido.', 400)
                if manifest.get('title') != prompt['title']:
                    raise GatewayError('Il titolo del manifest non corrisponde allo spettacolo.', 400)
                parse_script(prompt['text'])
                if _clean_settings(prompt['settings']) != prompt['settings']:
                    raise GatewayError('Impostazioni Prompt non valide.', 400)
                required = {a['fileId'] for a in state['assets'] if a.get('kind') in {'image', 'video'}}
                if {n[6:] for n in files if n.startswith('media/')} != required:
                    raise GatewayError('Libreria media incompleta o estranea al progetto.', 400)
                for asset in state['assets']:
                    if asset.get('kind') not in {'image', 'video'}:
                        continue
                    ident = asset['fileId']
                    info = files['media/' + ident]
                    if info['sha256'] != ident or info.get('mime') not in MIMES or (asset.get('sha256') and asset['sha256'] != ident) or asset.get('size') != info['size']:
                        raise GatewayError('Riferimento media incoerente.', 400)
                result = {'ticket': secrets.token_hex(24), 'id': manifest['id'], 'title': str(manifest.get('title', ''))[:120],
                          'screens': len(state['screens']), 'assets': len(state['assets']), 'mediaFiles': len(required),
                          'cues': len(parse_script(prompt['text'])['cues']), 'bytes': sum(i['size'] for i in files.values()),
                          'warnings': ['Le sorgenti live richiedono la rete e la sorgente originale.'] if any(a.get('kind') == 'live' for a in state['assets']) else [],
                          'expires': time.time() + 1800}
                baseline = self.status()
                result.update({key: baseline[key] for key in ('revision', 'promptVersion')})
                with self.lock:
                    self._expire()
                    if len(self.pending) >= 3:
                        raise GatewayError('Completa o annulla le importazioni già in anteprima.', 409)
                    self.pending[result['ticket']] = (folder, manifest, state, prompt, result)
                return result
        except Exception:
            self.remove_stage(folder)
            raise

    def _expire(self):
        for ticket, value in list(self.pending.items()):
            if value[4]['expires'] <= time.time():
                self.remove_stage(value[0])
                del self.pending[ticket]

    def activate(self, ticket, revision, prompt_version):
        with self.lock, self.server.prompt.lock, self.db_lock:
            self._expire()
            if ticket not in self.pending:
                raise GatewayError('Anteprima non disponibile o scaduta.', 410)
            folder, manifest, state, prompt, summary = self.pending[ticket]
            with database(self.root / 'controller.sqlite3') as conn:
                current = conn.execute('SELECT version FROM state WHERE id=1').fetchone()[0]
                current_prompt = conn.execute('SELECT version FROM prompt_project WHERE id=1').fetchone()[0]
                if current != revision or current_prompt != prompt_version:
                    raise GatewayError('Il progetto è cambiato: aggiorna l’anteprima prima di attivare.', 409)
            # Snapshot content only; identity and pairing tables stay on this machine.
            with database(self.root / 'controller.sqlite3') as conn:
                has_project = bool(conn.execute('SELECT payload FROM state WHERE id=1').fetchone()[0])
            if has_project:
                with self.export() as (backup, _, _):
                    temporary = self.root / '.show-previous.tmp'
                    with temporary.open('wb') as output:
                        shutil.copyfileobj(backup, output)
                    os.replace(temporary, self.root / 'show-previous.show.zip')
            now = time.time()
            parsed = parse_script(prompt['text'])
            with database(self.root / 'controller.sqlite3') as conn:
                for name, info in manifest['files'].items():
                    if not name.startswith('media/'):
                        continue
                    ident = name[6:]
                    target = self.root / 'assets' / ident
                    if not target.exists() or sha_file(target) != ident:
                        os.replace(folder / name, target)
                    conn.execute('INSERT OR REPLACE INTO asset_files VALUES(?,?,?,?)',
                                 (ident, info['mime'], Path(str(info.get('name', ident))).name[:240], info['size']))
                conn.execute('UPDATE state SET version=version+1,payload=? WHERE id=1', (json.dumps(state),))
                conn.execute('UPDATE prompt_project SET version=version+1,title=?,script=?,settings=?,updated=? WHERE id=1',
                             (prompt['title'], json.dumps(parsed), json.dumps(prompt['settings']), now))
                runtime = dict(anchor=parsed['cues'][0]['id'], offsetVh=0.0, rate=0.0, playing=False, blackout=False,
                               message='', activeRole='PRIMARY', source='SHOW PACKAGE', updated=now)
                conn.execute('UPDATE prompt_runtime SET seq=seq+1,payload=?,updated=? WHERE id=1', (json.dumps(runtime), now))
                conn.execute('INSERT OR REPLACE INTO show_active VALUES(1,?,?,?)', (manifest['id'], summary['title'], now))
            del self.pending[ticket]
            self.remove_stage(folder)
            return {'ok': True, 'revision': current + 1, 'promptVersion': current_prompt + 1, **self.status()}


def handle_show(h, path):
    if not path.startswith('/api/show/'):
        return False
    if not h.authorized():
        return True
    packages = h.server.shows
    try:
        if path == '/api/show/status' and h.command in ('GET', 'HEAD'):
            h.reply(packages.status())
        elif path == '/api/show/export' and h.command in ('GET', 'HEAD'):
            with packages.export() as (stream, size, _):
                h.send_response(200)
                h.send_header('Content-Type', 'application/zip')
                h.send_header('Content-Length', str(size))
                h.send_header('Cache-Control', 'no-store')
                h.send_header('Content-Disposition', 'attachment; filename="DisplayControl.show.zip"')
                h.end_headers()
                if h.command != 'HEAD':
                    shutil.copyfileobj(stream, h.wfile, 1024**2)
        elif path == '/api/show/stage' and h.command == 'POST':
            size = int(h.headers.get('Content-Length', '0'))
            if not 0 < size <= MAX_PACKAGE + MAX_METADATA:
                raise GatewayError('SHOW PACKAGE vuoto o oltre 2 GiB.', 413)
            with tempfile.TemporaryFile() as source:
                remaining = size
                while remaining:
                    chunk = h.rfile.read(min(1024**2, remaining))
                    if not chunk:
                        raise GatewayError('Upload del pacchetto interrotto.', 400)
                    source.write(chunk)
                    remaining -= len(chunk)
                source.seek(0)
                h.reply(packages.stage(source), 201)
        elif path == '/api/show/activate' and h.command == 'POST':
            body = h.body_json()
            if body is not None:
                h.reply(packages.activate(str(body.get('ticket', '')), body.get('revision'), body.get('promptVersion')))
        elif path == '/api/show/discard' and h.command == 'POST':
            body = h.body_json()
            if body is not None:
                with packages.lock:
                    item = packages.pending.pop(str(body.get('ticket', '')), None)
                    if item:
                        packages.remove_stage(item[0])
                h.reply({'ok': True})
        elif path == '/api/show/rollback' and h.command == 'POST':
            body = h.body_json()
            if body is not None:
                previous = packages.root / 'show-previous.show.zip'
                if not previous.is_file():
                    raise GatewayError('Nessuno spettacolo precedente disponibile.', 409)
                with previous.open('rb') as source:
                    preview = packages.stage(source)
                h.reply(packages.activate(preview['ticket'], body.get('revision'), body.get('promptVersion')))
        else:
            h.reply({'error': 'Endpoint SHOW PACKAGE non trovato.'}, 404)
    except GatewayError as exc:
        h.reply({'error': str(exc)}, exc.status)
    except (ValueError, TypeError, KeyError, AttributeError, zipfile.BadZipFile, UnicodeError):
        h.reply({'error': 'SHOW PACKAGE non valido o danneggiato.'}, 400)
    except OSError:
        h.reply({'error': 'Impossibile leggere o salvare il pacchetto. Verifica spazio e permessi.'}, 500)
    return True
