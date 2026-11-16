"""Device pairing and restricted player API. Standard library, no cloud.

HTTP on a trusted LAN only. Pairing codes are one-use, expire after 10 minutes,
are stored hashed and rate limited. Player secrets never authorize controller API.
Revocation stops synchronization/live, not content already cached offline.
"""
from __future__ import annotations
import hashlib
import json
import re
import secrets
import sqlite3
import threading
import time
from collections import defaultdict, deque
from ndi.gateway import GatewayError
from monitoring import store
from storage import database

LOCK = threading.RLock()
ATTEMPTS = defaultdict(deque)
ID = re.compile(r'^[A-Za-z0-9_-]{1,120}$')
HEX = re.compile(r'^[a-f0-9]{64}$')


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def init_players(folder):
    with database(folder / 'controller.sqlite3') as c:
        c.execute('CREATE TABLE IF NOT EXISTS pairing(code_hash TEXT PRIMARY KEY,screen_id TEXT,expires REAL)')
        c.execute('CREATE TABLE IF NOT EXISTS devices(screen_id TEXT PRIMARY KEY,token_hash TEXT UNIQUE,name TEXT,paired REAL)')


def read_state(h):
    with h.db() as c:
        row = c.execute('SELECT version,payload FROM state WHERE id=1').fetchone()
    return row[0], json.loads(row[1]) if row[1] else None


def subset(state, sid):
    """Keep only the screen and all assets required for its current/scheduled plan."""
    if not state:
        raise GatewayError('Apri la console e crea prima lo schermo.', 409)
    screen = next((x for x in state['screens'] if x['id'] == sid), None)
    if screen is None:
        raise GatewayError('Schermo eliminato dal progetto.', 410)
    schedules = [dict(x, screenIds=[sid]) for x in state['schedules'] if sid in x.get('screenIds', [])]
    refs = [screen.get('base'), screen.get('override')] + [x.get('content') for x in schedules]
    aids, pids = {screen.get('fallbackAssetId')}, set()
    for ref in refs:
        if isinstance(ref, dict):
            if ref.get('type') == 'asset': aids.add(ref.get('id'))
            if ref.get('type') == 'playlist': pids.add(ref.get('id'))
    playlists = [x for x in state['playlists'] if x['id'] in pids]
    for pl in playlists:
        aids.update(x.get('assetId') for x in pl.get('items', []))
    # Same fallback as the existing player when an explicit fallback is absent.
    poster = next((a for a in state['assets'] if a.get('kind') == 'poster'), None)
    if poster: aids.add(poster['id'])
    return dict(schemaVersion=1, site=state['site'], screens=[screen],
                assets=[a for a in state['assets'] if a['id'] in aids],
                playlists=playlists, schedules=schedules, events=[])


def specs(s):
    return {(('TEST LOCALE / NON NDI' if a.get('protocol') == 'ndi-test' else str(a.get('sourceName', '')).strip()),
             a.get('profile', 'light'), a.get('protocol') == 'ndi-test')
            for a in s['assets'] if a.get('kind') == 'live' and a.get('protocol') in ('ndi', 'ndi-test')}


def clean_heartbeat(body):
    def bounded(name):
        try: return max(0, min(2147483647, int(body.get(name, 0))))
        except (ValueError, TypeError, OverflowError): return 0
    return dict(lastSeen=time.time(), title=str(body.get('title', ''))[:200],
                cacheCount=bounded('cacheCount'), revision=bounded('revision'),
                offlineTest=bool(body.get('offlineTest')), message=str(body.get('message', ''))[:300],
                kind='physical')


def handle_players(h, path, heartbeats, heartbeat_lock):
    if not path.startswith(('/api/player/', '/api/devices/')):
        return False
    try:
        _handle(h, path, heartbeats, heartbeat_lock)
    except GatewayError as e:
        h.reply({'error': str(e)}, e.status)
    except (ValueError, TypeError, KeyError, OverflowError):
        h.reply({'error': 'Richiesta player non valida.'}, 400)
    return True


def _handle(h, path, heartbeats, heartbeat_lock):
    now = time.time()
    if path == '/api/player/pair' and h.command == 'POST':
        ip = h.client_address[0]
        with LOCK:
            # Discard old buckets; never accumulate arbitrary clients indefinitely.
            for k in list(ATTEMPTS):
                while ATTEMPTS[k] and now - ATTEMPTS[k][0] >= 60: ATTEMPTS[k].popleft()
                if not ATTEMPTS[k]: del ATTEMPTS[k]
            if len(ATTEMPTS[ip]) >= 10:
                raise GatewayError('Troppi tentativi: riprova tra un minuto.', 429)
            ATTEMPTS[ip].append(now)
        body = h.body_json()
        if body is None: return
        code = str(body.get('code', '')).replace(' ', '').replace('-', '')
        if not re.fullmatch(r'\d{8}', code):
            raise GatewayError('Codice non valido o scaduto.', 401)
        with LOCK, h.db() as c:
            c.execute('BEGIN IMMEDIATE')
            found = c.execute('SELECT screen_id,expires FROM pairing WHERE code_hash=?', (digest(code),)).fetchone()
            if not found or found[1] <= now:
                raise GatewayError('Codice non valido o scaduto.', 401)
            sid = found[0]
            _, state = read_state(h)
            scoped = subset(state, sid)
            token = secrets.token_urlsafe(32)
            name = str(body.get('name') or scoped['screens'][0]['name'])[:100]
            c.execute('DELETE FROM pairing WHERE screen_id=?', (sid,))
            c.execute('INSERT OR REPLACE INTO devices(screen_id,token_hash,name,paired) VALUES(?,?,?,?)',
                      (sid, digest(token), name, now))
        store(h).remove(sid)
        return h.reply(dict(screenId=sid, token=token, name=name, version='0.5.0-alpha'), 201)

    if path.startswith('/api/devices/'):
        if not h.authorized(): return
        if path == '/api/devices/list' and h.command in ('GET', 'HEAD'):
            with h.db() as c:
                rows = c.execute('SELECT screen_id,name,paired FROM devices').fetchall()
            return h.reply({'devices': [dict(screenId=x[0],name=x[1],paired=x[2]) for x in rows]})
        if h.command != 'POST': raise GatewayError('Metodo non consentito.', 405)
        body = h.body_json()
        if body is None: return
        sid = body.get('screenId', '')
        if not isinstance(sid, str) or not ID.fullmatch(sid):
            raise GatewayError('ID schermo non valido.', 400)
        if path == '/api/devices/pair-code':
            _, state = read_state(h)
            subset(state, sid)
            code = ''.join(str(secrets.randbelow(10)) for _ in range(8))
            with LOCK, h.db() as c:
                c.execute('DELETE FROM pairing WHERE screen_id=? OR expires<=?', (sid, now))
                c.execute('INSERT INTO pairing VALUES(?,?,?)', (digest(code), sid, now+600))
            return h.reply(dict(code=code, screenId=sid, expiresAt=now+600))
        if path == '/api/devices/revoke':
            with LOCK, h.db() as c:
                c.execute('DELETE FROM devices WHERE screen_id=?', (sid,))
                c.execute('DELETE FROM pairing WHERE screen_id=?', (sid,))
            with heartbeat_lock: heartbeats.pop(sid, None)
            store(h).remove(sid)
            return h.reply({'ok': True})
        raise GatewayError('Endpoint non trovato.', 404)

    supplied = h.headers.get('X-Player-Token', '')
    if not 20 <= len(supplied) <= 128:
        raise GatewayError('Player non abbinato.', 401)
    with h.db() as c:
        dev = c.execute('SELECT screen_id FROM devices WHERE token_hash=?', (digest(supplied),)).fetchone()
    if not dev: raise GatewayError('Abbinamento revocato o non valido.', 401)
    sid = dev[0]
    revision, state = read_state(h)
    scoped = subset(state, sid)
    if path == '/api/player/state' and h.command in ('GET','HEAD'):
        return h.reply(dict(revision=revision,state=scoped))
    if path == '/api/player/heartbeat' and h.command == 'POST':
        body = h.body_json()
        if body is None: return
        if body.get('screenId') != sid: raise GatewayError('Player diverso.', 403)
        with heartbeat_lock: heartbeats[sid] = clean_heartbeat(body)
        return h.reply({'ok': True, 'monitor': store(h).policy()})
    if path == '/api/player/preview' and h.command == 'POST':
        body = h.body_json()
        if body is None: return
        if body.get('screenId') != sid: raise GatewayError('Player diverso.', 403)
        return h.reply(store(h).receive(sid, body))
    if path.startswith('/api/player/assets/') and h.command in ('GET', 'HEAD'):
        fid = path.rsplit('/',1)[-1]
        permitted = {a.get('fileId') for a in scoped['assets'] if a.get('kind') in ('image','video')}
        if not HEX.fullmatch(fid) or fid not in permitted: raise GatewayError('File non assegnato.', 403)
        fp = h.server.data_dir / 'assets' / fid
        with h.db() as c:
            row = c.execute('SELECT mime FROM asset_files WHERE id=?',(fid,)).fetchone()
        if not row or not fp.is_file(): raise GatewayError('File mancante.',404)
        h.send_response(200)
        h.send_header('Content-Type',row[0]); h.send_header('Content-Length',str(fp.stat().st_size))
        h.send_header('Cache-Control','no-store'); h.send_header('X-Content-Type-Options','nosniff')
        h.end_headers()
        if h.command != 'HEAD':
            try:
                with fp.open('rb') as f:
                    while chunk := f.read(1024*256): h.wfile.write(chunk)
            except (BrokenPipeError, ConnectionResetError): pass
        return
    if path == '/api/player/ndi/start' and h.command == 'POST':
        body=h.body_json()
        if body is None: return
        test=body.get('test') is True
        spec=('TEST LOCALE / NON NDI' if test else str(body.get('sourceName','')).strip(),body.get('profile','light'),test)
        if spec not in specs(scoped): raise GatewayError('Sorgente non assegnata al player.',403)
        return h.reply(h.server.gateway.start(body))
    if path.startswith(('/api/player/ndi/manifest/','/api/player/ndi/media/')) and h.command in ('GET','HEAD'):
        parts=path.split('/')
        if len(parts) not in (6,8): raise GatewayError('Percorso non valido.',400)
        stream=h.server.gateway.get(parts[5])
        if (stream.name,stream.profile,stream.test) not in specs(scoped):
            raise GatewayError('Flusso non assegnato.',403)
        if parts[4]=='manifest' and len(parts)==6:
            return h.reply(stream.manifest())
        if parts[4]=='media' and len(parts)==8:
            return h.send_data(200,h.server.gateway.media(parts[5],parts[6],parts[7]),'video/mp4')
    raise GatewayError('Endpoint non consentito al player.',403)
