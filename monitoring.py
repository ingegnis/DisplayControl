"""On-demand player thumbnails. Last image only, in memory; no cloud or encoders.

Only admin sessions can request/read monitoring. Player credentials can upload
only their assigned screen through the existing restricted API.
"""
from __future__ import annotations
import base64
import binascii
from collections import deque
import hashlib
import math
import re
import threading
import time
from urllib.parse import parse_qs, urlsplit
from ndi.gateway import GatewayError

ID = re.compile(r'^[A-Za-z0-9_-]{1,120}$')
VIEWER = re.compile(r'^[A-Za-z0-9_-]{8,80}$')
MAX_JPEG = 64 * 1024
INTERVALS = (1, 2, 5)


def jpeg_size(data):
    """Read bounded JPEG SOF dimensions, not an image decoder."""
    if not data.startswith(b'\xff\xd8') or not data.endswith(b'\xff\xd9'):
        raise GatewayError('Miniatura JPEG non valida.', 400)
    pos = 2
    while pos + 4 < len(data):
        if data[pos] != 0xff:
            raise GatewayError('Intestazione JPEG non valida.', 400)
        while pos < len(data) and data[pos] == 0xff:
            pos += 1
        if pos >= len(data):
            break
        mark = data[pos]; pos += 1
        if mark in (0xd8, 0xd9) or 0xd0 <= mark <= 0xd7:
            continue
        length = int.from_bytes(data[pos:pos+2], 'big')
        if length < 2 or pos + length > len(data):
            break
        if mark in (0xc0, 0xc1, 0xc2):
            if length < 8:
                break
            height = int.from_bytes(data[pos+3:pos+5], 'big')
            width = int.from_bytes(data[pos+5:pos+7], 'big')
            if 0 < width <= 480 and 0 < height <= 270:
                return width, height
            raise GatewayError('Miniatura oltre 480x270.', 400)
        if mark == 0xda:
            break
        pos += length
    raise GatewayError('Dimensioni JPEG non valide.', 400)


def number(value, low=0, high=86400):
    try:
        value = float(value)
        return max(low, min(high, value)) if math.isfinite(value) else None
    except (TypeError, ValueError, OverflowError):
        return None


class MonitorStore:
    def __init__(self, clock=time.monotonic, wall=time.time):
        self.clock, self.wall = clock, wall
        self.lock = threading.RLock()
        self.viewers, self.frames, self.accepted = {}, {}, {}
        self.traffic = deque(maxlen=20000)
        self.seq = 0

    def policy(self):
        with self.lock:
            now = self.clock()
            self.viewers = {k: v for k, v in self.viewers.items() if v[1] > now}
            if not self.viewers:
                return dict(enabled=False, interval=5, leaseSeconds=0)
            return dict(enabled=True, interval=min(v[0] for v in self.viewers.values()),
                        leaseSeconds=round(max(v[1] for v in self.viewers.values())-now, 2))

    def watch(self, viewer, interval):
        if not isinstance(viewer, str) or not VIEWER.fullmatch(viewer) or interval not in INTERVALS:
            raise GatewayError('Sessione monitor o intervallo non valido.', 400)
        with self.lock:
            self.policy()
            if viewer not in self.viewers and len(self.viewers) >= 32:
                raise GatewayError('Troppe sessioni monitor.', 429)
            self.viewers[viewer] = (interval, self.clock()+max(12, interval*3))
        return self.policy()

    def stop(self, viewer):
        with self.lock:
            self.viewers.pop(viewer, None)
        return self.policy()

    def remove(self, sid):
        with self.lock:
            self.frames.pop(sid, None)
            self.accepted.pop(sid, None)

    def receive(self, sid, body):
        if not isinstance(sid, str) or not ID.fullmatch(sid):
            raise GatewayError('Schermo non valido.', 400)
        with self.lock:
            policy = self.policy()
            if not policy['enabled']:
                return dict(ok=True, stored=False, monitor=policy)
            now = self.clock()
            if now - self.accepted.get(sid, -1e20) < .65:
                raise GatewayError('Miniature troppo frequenti.', 429)
            encoded = body.get('jpeg', '')
            if not isinstance(encoded, str) or len(encoded) > ((MAX_JPEG+2)//3)*4:
                raise GatewayError('Miniatura troppo grande.', 413)
            raw = b''; width = height = 0
            if encoded:
                try:
                    raw = base64.b64decode(encoded, validate=True)
                except (ValueError, binascii.Error):
                    raise GatewayError('Miniatura non valida.', 400)
                if len(raw) > MAX_JPEG:
                    raise GatewayError('Miniatura troppo grande.', 413)
                width, height = jpeg_size(raw)
            kind = body.get('kind', 'unavailable')
            if kind not in ('frame', 'rendered', 'black', 'unavailable'):
                raise GatewayError('Tipo miniatura non valido.', 400)
            if kind != 'unavailable' and not raw:
                raise GatewayError('Miniatura mancante.', 400)
            self.seq += 1
            self.frames[sid] = dict(
                seq=self.seq, receivedAt=self.wall(), kind=kind, jpeg=raw,
                hash=hashlib.sha256(raw).hexdigest() if raw else '', bytes=len(raw),
                width=width, height=height,
                title=str(body.get('title', ''))[:200], assetId=str(body.get('assetId', ''))[:120],
                assetKind=str(body.get('assetKind', ''))[:30], message=str(body.get('message', ''))[:300],
                error=str(body.get('error', ''))[:240], revision=number(body.get('revision'), 0, 2147483647),
                fallback=bool(body.get('fallback')), offlineTest=bool(body.get('offlineTest')),
                mediaTime=number(body.get('mediaTime')), bufferSeconds=number(body.get('bufferSeconds')),
                paused=bool(body.get('paused')), hidden=bool(body.get('hidden')))
            self.accepted[sid] = now
            # Bounded by normal project limit, also under direct authenticated calls.
            while len(self.frames) > 200:
                self.remove(min(self.frames, key=lambda k: self.frames[k]['seq']))
            self.traffic.append((now, len(encoded)))
            return dict(ok=True, stored=True, monitor=policy)

    def frame(self, sid):
        with self.lock:
            item = self.frames.get(sid)
            if not item or not item['jpeg']:
                raise GatewayError('Nessuna miniatura dal player.', 404)
            return item['jpeg'], item['hash']

    def overview(self, state, revision, heartbeats):
        with self.lock:
            now = self.wall()
            ids = {x['id'] for x in (state or {}).get('screens', [])}
            for sid in set(self.frames)-ids:
                self.remove(sid)
            screens = []
            for s in (state or {}).get('screens', []):
                sid = s['id']; hb = heartbeats.get(sid)
                frame = self.frames.get(sid)
                meta = {k: v for k, v in frame.items() if k != 'jpeg'} if frame else None
                screens.append(dict(id=sid, name=s.get('name', sid), group=s.get('group', ''),
                    location=s.get('location', ''), heartbeat=hb, preview=meta))
            cutoff = self.clock()-60
            while self.traffic and self.traffic[0][0] < cutoff:
                self.traffic.popleft()
            return dict(serverTime=now, revision=revision, screens=screens, policy=self.policy(),
                        uploadedBase64BytesLastMinute=sum(x[1] for x in self.traffic),
                        note='Anteprime dal software player; non verificano accensione o immagine fisica del TV.')


def store(h):
    return h.server.monitor


def handle_monitor(h, path, heartbeats, heartbeat_lock):
    if path != '/api/preview' and not path.startswith('/api/monitor'):
        return False
    if not h.authorized():
        return True
    try:
        from physical_players import read_state, subset
        revision, state = read_state(h)
        if path == '/api/preview' and h.command == 'POST':
            body = h.body_json()
            if body is not None:
                sid = body.get('screenId', '')
                subset(state, sid)
                h.reply(store(h).receive(sid, body))
        elif path == '/api/monitor' and h.command in ('GET', 'HEAD'):
            query = parse_qs(urlsplit(h.path).query)
            try:
                interval = int(query.get('interval', ['2'])[0])
            except ValueError:
                raise GatewayError('Intervallo non valido.', 400)
            store(h).watch(query.get('viewer', [''])[0], interval)
            with heartbeat_lock:
                beats = dict(heartbeats)
            h.reply(store(h).overview(state, revision, beats))
        elif path == '/api/monitor/stop' and h.command == 'POST':
            body = h.body_json()
            if body is not None:
                h.reply(dict(ok=True, monitor=store(h).stop(str(body.get('viewer', '')))))
        elif path.startswith('/api/monitor/frame/') and h.command in ('GET', 'HEAD'):
            sid = path.rsplit('/', 1)[-1]
            subset(state, sid)
            raw, digest = store(h).frame(sid)
            h.send_data(200, raw, 'image/jpeg', {'ETag': '"'+digest+'"'})
        else:
            h.reply({'error': 'Endpoint monitor non trovato.'}, 404)
    except GatewayError as exc:
        h.reply({'error': str(exc)}, exc.status)
    return True
