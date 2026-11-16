"""Carisma Prompt: local teleprompter engine, pairing, OSC control and hot-backup status.

Standard library only. Designed for trusted LAN operation. Script and runtime are
stored on the Carisma server; prompt players cache the last complete project and
continue local scrolling if the server becomes temporarily unreachable.
"""
from __future__ import annotations
import base64
import hashlib
import io
import json
import math
import os
import re
import secrets
import socket
import sqlite3
import struct
import threading
import time
import zipfile
from xml.etree import ElementTree as ET
from urllib.parse import parse_qs, urlsplit
from ndi.gateway import GatewayError
from storage import database

LOCK = threading.RLock()
ID = re.compile(r'^[A-Za-z0-9_-]{1,80}$')
ROLE = {'PRIMARY', 'BACKUP'}
MAX_IMPORT = 8 * 1024 * 1024
FONT_KEYS = {'classic', 'wide', 'serif'}
SIZE_KEYS = {'medium', 'large', 'xlarge'}
THEME_KEYS = {'white', 'amber', 'inverse'}

DEFAULT_SCRIPT = """[[CUE: START]]
Benvenuti al Teatro Carisma.

Questo e il gobbo elettronico Carisma Prompt.

[[CUE: DEMO]]
Il copione e memorizzato localmente sui player.
La regia invia soltanto comandi di posizione e velocita.
"""

DEFAULT_SETTINGS = {
    'font': 'classic',
    'size': 'large',
    'theme': 'white',
    'readingLine': True,
}


def digest(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _db(path):
    return database(path)


def _clean_settings(value):
    value = value if isinstance(value, dict) else {}
    return {
        'font': value.get('font') if value.get('font') in FONT_KEYS else 'classic',
        'size': value.get('size') if value.get('size') in SIZE_KEYS else 'large',
        'theme': value.get('theme') if value.get('theme') in THEME_KEYS else 'white',
        'readingLine': bool(value.get('readingLine', True)),
    }


def parse_script(text: str):
    if not isinstance(text, str):
        raise GatewayError('Copione non valido.', 400)
    text = text.replace('\r\n', '\n').replace('\r', '\n').replace('\x00', '')
    if len(text) > 1_000_000:
        raise GatewayError('Copione troppo lungo.', 413)
    raw_lines = text.split('\n')
    lines = []
    cues = []
    pending = []
    for raw in raw_lines:
        m = re.match(r'^\s*\[\[\s*CUE\s*:\s*(.+?)\s*\]\]\s*$', raw, re.I)
        if m:
            title = re.sub(r'\s+', ' ', m.group(1).strip())[:120]
            if title:
                pending.append(title)
            continue
        # Preserve deliberate blank lines but avoid unlimited runs.
        if raw.strip() == '' and lines and lines[-1]['text'] == '':
            continue
        line = {'id': f'l{len(lines)+1}', 'text': raw.rstrip()[:4000]}
        lines.append(line)
        if pending:
            for title in pending:
                cid = re.sub(r'[^A-Za-z0-9_-]+', '-', title).strip('-').lower()[:60] or f'cue-{len(cues)+1}'
                base = cid; n = 2
                used = {c['id'] for c in cues}
                while cid in used:
                    cid = f'{base}-{n}'; n += 1
                cues.append({'id': cid, 'title': title, 'lineId': line['id'], 'lineIndex': len(lines)-1})
            pending = []
    if not lines:
        lines = [{'id': 'l1', 'text': ''}]
    if not cues or cues[0]['lineIndex'] != 0:
        cues.insert(0, {'id': 'start', 'title': 'START', 'lineId': lines[0]['id'], 'lineIndex': 0})
    return {'text': text, 'lines': lines, 'cues': cues}


def docx_to_text(raw: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(raw), 'r') as z:
            xml = z.read('word/document.xml')
    except (zipfile.BadZipFile, KeyError, OSError) as exc:
        raise GatewayError('DOCX non valido: ' + str(exc), 400)
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise GatewayError('XML DOCX non valido: ' + str(exc), 400)
    ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    paras = []
    for p in root.iter(ns + 'p'):
        chunks = []
        for node in p.iter():
            if node.tag == ns + 't' and node.text:
                chunks.append(node.text)
            elif node.tag == ns + 'tab':
                chunks.append('\t')
            elif node.tag == ns + 'br':
                chunks.append('\n')
        paras.append(''.join(chunks))
    return '\n\n'.join(paras)


class PromptStore:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.db_path = data_dir / 'controller.sqlite3'
        self.lock = threading.RLock()
        self.status = {}
        self.controller_status = {}
        self.last_osc = None
        self._init()

    def _init(self):
        project = parse_script(DEFAULT_SCRIPT)
        now = time.time()
        runtime = dict(seq=0, anchor='start', offsetVh=0.0, rate=0.0, playing=False,
                       blackout=False, message='', activeRole='PRIMARY', source='INIT', updated=now)
        with _db(self.db_path) as c:
            c.execute('''CREATE TABLE IF NOT EXISTS prompt_project(
                id INTEGER PRIMARY KEY CHECK(id=1), version INTEGER NOT NULL,
                title TEXT NOT NULL, script TEXT NOT NULL, settings TEXT NOT NULL, updated REAL NOT NULL)''')
            c.execute('''CREATE TABLE IF NOT EXISTS prompt_runtime(
                id INTEGER PRIMARY KEY CHECK(id=1), seq INTEGER NOT NULL, payload TEXT NOT NULL, updated REAL NOT NULL)''')
            c.execute('''CREATE TABLE IF NOT EXISTS prompt_pairing(
                code_hash TEXT PRIMARY KEY, station TEXT NOT NULL, role TEXT NOT NULL, expires REAL NOT NULL)''')
            c.execute('''CREATE TABLE IF NOT EXISTS prompt_devices(
                slot TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL, station TEXT NOT NULL,
                role TEXT NOT NULL, name TEXT NOT NULL, paired REAL NOT NULL)''')
            c.execute('''CREATE TABLE IF NOT EXISTS prompt_controller_pairing(
                code_hash TEXT PRIMARY KEY, expires REAL NOT NULL, name TEXT NOT NULL)''')
            c.execute('''CREATE TABLE IF NOT EXISTS prompt_controllers(
                id TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL, name TEXT NOT NULL, paired REAL NOT NULL)''')
            c.execute('''CREATE TABLE IF NOT EXISTS prompt_controller_requests(
                controller TEXT NOT NULL, request_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
                response TEXT NOT NULL, created REAL NOT NULL, PRIMARY KEY(controller,request_id))''')
            c.execute('INSERT OR IGNORE INTO prompt_project VALUES(1,1,?,?,?,?)',
                      ('Demo Carisma Prompt', json.dumps(project, ensure_ascii=False),
                       json.dumps(DEFAULT_SETTINGS), now))
            c.execute('INSERT OR IGNORE INTO prompt_runtime VALUES(1,?,?,?)',
                      (0, json.dumps(runtime), now))

    def project(self):
        with _db(self.db_path) as c:
            row = c.execute('SELECT version,title,script,settings,updated FROM prompt_project WHERE id=1').fetchone()
        return {'version': row[0], 'title': row[1], 'script': json.loads(row[2]),
                'settings': json.loads(row[3]), 'updated': row[4]}

    def runtime(self, now=None):
        now = time.time() if now is None else now
        with _db(self.db_path) as c:
            row = c.execute('SELECT seq,payload FROM prompt_runtime WHERE id=1').fetchone()
        rt = json.loads(row[1]); rt['seq'] = row[0]; rt.setdefault('activeRole', 'PRIMARY')
        if rt.get('playing'):
            dt = max(0.0, min(3600.0, now - float(rt.get('updated', now))))
            rt['offsetVh'] = max(0.0, float(rt.get('offsetVh', 0)) + float(rt.get('rate', 0))*dt)
        rt['serverTime'] = now
        return rt

    def _write_runtime(self, rt, source, connection=None):
        now = time.time()
        seq = int(rt.get('seq', 0)) + 1
        rt = dict(rt)
        rt.update(seq=seq, source=str(source)[:80], updated=now)
        if connection is not None:
            connection.execute('UPDATE prompt_runtime SET seq=?,payload=?,updated=? WHERE id=1',
                               (seq, json.dumps(rt), now))
            return dict(rt, serverTime=now)
        with _db(self.db_path) as c:
            c.execute('UPDATE prompt_runtime SET seq=?,payload=?,updated=? WHERE id=1',
                      (seq, json.dumps(rt), now))
        return self.runtime(now)

    def save_project(self, title, text, settings, expected=None):
        parsed = parse_script(text)
        clean = _clean_settings(settings)
        title = re.sub(r'\s+', ' ', str(title or 'Copione')).strip()[:120] or 'Copione'
        now = time.time()
        with self.lock, _db(self.db_path) as c:
            row = c.execute('SELECT version FROM prompt_project WHERE id=1').fetchone()
            version = int(row[0])
            if expected is not None and int(expected) != version:
                raise GatewayError('Il copione e cambiato. Ricarica prima di salvare.', 409)
            version += 1
            c.execute('UPDATE prompt_project SET version=?,title=?,script=?,settings=?,updated=? WHERE id=1',
                      (version, title, json.dumps(parsed, ensure_ascii=False), json.dumps(clean), now))
            rt = dict(seq=0, anchor=parsed['cues'][0]['id'], offsetVh=0.0, rate=0.0, playing=False,
                      blackout=False, message='', activeRole='PRIMARY', source='PROJECT', updated=now)
            c.execute('UPDATE prompt_runtime SET seq=seq+1,payload=?,updated=? WHERE id=1',
                      (json.dumps(rt), now))
        return self.project()

    def command(self, command, value=None, source='REGIA', connection=None):
        with self.lock:
            rt = self.runtime()
            proj = self.project()
            cmd = str(command or '').lower()
            if cmd == 'play':
                rt['playing'] = True
                if abs(float(rt.get('rate',0))) < .0001: rt['rate'] = .11
            elif cmd == 'pause': rt['playing'] = False
            elif cmd == 'toggle':
                rt['playing'] = not bool(rt.get('playing'))
                if rt['playing'] and abs(float(rt.get('rate',0))) < .0001: rt['rate'] = .11
            elif cmd == 'stop': rt.update(playing=False, rate=0.0)
            elif cmd == 'speed':
                try: rate = float(value)
                except (TypeError, ValueError): raise GatewayError('Velocita non valida.', 400)
                if not math.isfinite(rate): raise GatewayError('Velocita non valida.', 400)
                rt['rate'] = max(-0.8, min(0.8, rate)); rt['playing'] = abs(rt['rate']) > 0.0001
            elif cmd == 'speed_delta':
                try: delta = float(value)
                except (TypeError, ValueError): raise GatewayError('Variazione velocita non valida.', 400)
                if not math.isfinite(delta): raise GatewayError('Variazione velocita non valida.', 400)
                rt['rate'] = max(-0.8, min(0.8, float(rt.get('rate', 0))+delta))
                rt['playing'] = abs(rt['rate']) > 0.0001
            elif cmd == 'jog':
                try: delta = float(value)
                except (TypeError, ValueError): raise GatewayError('Jog non valido.', 400)
                if not math.isfinite(delta): raise GatewayError('Jog non valido.', 400)
                rt['offsetVh'] = max(0.0, float(rt.get('offsetVh', 0))+max(-5.0, min(5.0, delta)))
                rt['playing'] = False
            elif cmd == 'top':
                rt.update(anchor=proj['script']['cues'][0]['id'], offsetVh=0.0, playing=False)
            elif cmd in ('cue', 'goto'):
                cue = str(value or '')
                if cue not in {x['id'] for x in proj['script']['cues']}:
                    raise GatewayError('Cue non trovato.', 404)
                rt.update(anchor=cue, offsetVh=0.0)
            elif cmd in ('cue_next', 'cue_prev'):
                cues = proj['script']['cues']; ids = [x['id'] for x in cues]
                try: idx = ids.index(rt.get('anchor'))
                except ValueError: idx = 0
                idx = min(len(ids)-1, idx+1) if cmd == 'cue_next' else max(0, idx-1)
                rt.update(anchor=ids[idx], offsetVh=0.0)
            elif cmd in ('take', 'take_role'):
                role = str(value or '').upper()
                if role not in ROLE: raise GatewayError('Ruolo TAKE non valido.', 400)
                rt['activeRole'] = role
            elif cmd == 'take_primary': rt['activeRole'] = 'PRIMARY'
            elif cmd == 'take_backup': rt['activeRole'] = 'BACKUP'
            elif cmd == 'take_toggle': rt['activeRole'] = 'BACKUP' if str(rt.get('activeRole','PRIMARY')).upper() == 'PRIMARY' else 'PRIMARY'
            elif cmd == 'blackout':
                rt['blackout'] = bool(value) if value is not None else not bool(rt.get('blackout'))
            elif cmd == 'message': rt['message'] = str(value or '')[:240]
            elif cmd == 'message_clear': rt['message'] = ''
            else: raise GatewayError('Comando Prompt non riconosciuto.', 400)
            return self._write_runtime(rt, source, connection)

    def controller_command(self, ctl, body):
        request_id = body.get('requestId')
        if request_id is None:  # Older controller clients remain compatible.
            return self.command(body['command'], body.get('value'), source='USB:'+ctl['id'])
        if not isinstance(request_id, str) or not re.fullmatch(r'[a-f0-9]{32}', request_id):
            raise GatewayError('ID richiesta controller non valido.', 400)
        fingerprint = digest(json.dumps([body['command'], body.get('value')], sort_keys=True, allow_nan=False))
        with self.lock, _db(self.db_path) as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT fingerprint,response FROM prompt_controller_requests WHERE controller=? AND request_id=?',
                            (ctl['id'], request_id)).fetchone()
            if row:
                if row[0] != fingerprint: raise GatewayError('ID richiesta riutilizzato con altro comando.', 409)
                return json.loads(row[1])
            response = self.command(body['command'], body.get('value'), source='USB:'+ctl['id'], connection=c)
            c.execute('DELETE FROM prompt_controller_requests WHERE created<?', (time.time()-86400,))
            c.execute('INSERT INTO prompt_controller_requests VALUES(?,?,?,?,?)',
                      (ctl['id'], request_id, fingerprint, json.dumps(response), time.time()))
            return response

    def issue_code(self, station, role):
        station = re.sub(r'[^A-Za-z0-9_-]+', '-', str(station or 'palco')).strip('-')[:60] or 'palco'
        role = str(role or '').upper()
        if role not in ROLE: raise GatewayError('Ruolo player non valido.', 400)
        code = ''.join(str(secrets.randbelow(10)) for _ in range(8)); now = time.time()
        with self.lock, _db(self.db_path) as c:
            c.execute('DELETE FROM prompt_pairing WHERE (station=? AND role=?) OR expires<=?', (station, role, now))
            c.execute('INSERT INTO prompt_pairing VALUES(?,?,?,?)', (digest(code), station, role, now+600))
        return {'code': code, 'station': station, 'role': role, 'expiresAt': now+600}

    def pair(self, code, name):
        code = str(code or '').replace(' ', '').replace('-', '')
        if not re.fullmatch(r'\d{8}', code): raise GatewayError('Codice non valido o scaduto.', 401)
        now = time.time()
        with self.lock, _db(self.db_path) as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT station,role,expires FROM prompt_pairing WHERE code_hash=?', (digest(code),)).fetchone()
            if not row or row[2] <= now: raise GatewayError('Codice non valido o scaduto.', 401)
            station, role = row[0], row[1]; slot = f'{station}:{role}'
            token = secrets.token_urlsafe(32)
            c.execute('DELETE FROM prompt_pairing WHERE station=? AND role=?', (station, role))
            c.execute('INSERT OR REPLACE INTO prompt_devices VALUES(?,?,?,?,?,?)',
                      (slot, digest(token), station, role, str(name or slot)[:100], now))
        self.status.pop(slot, None)
        return {'token': token, 'slot': slot, 'station': station, 'role': role, 'name': str(name or slot)[:100]}

    def device_for_token(self, token):
        if not 20 <= len(token or '') <= 128: raise GatewayError('Player Prompt non abbinato.', 401)
        with _db(self.db_path) as c:
            row = c.execute('SELECT slot,station,role,name FROM prompt_devices WHERE token_hash=?', (digest(token),)).fetchone()
        if not row: raise GatewayError('Abbinamento Prompt revocato o non valido.', 401)
        return {'slot': row[0], 'station': row[1], 'role': row[2], 'name': row[3]}

    def heartbeat(self, dev, body):
        item = {
            'lastSeen': time.time(), 'station': dev['station'], 'role': dev['role'], 'name': dev['name'],
            'seq': int(body.get('seq', 0) or 0), 'projectVersion': int(body.get('projectVersion', 0) or 0),
            'anchor': str(body.get('anchor', ''))[:80], 'offsetVh': float(body.get('offsetVh', 0) or 0),
            'online': bool(body.get('online', True)), 'fps': float(body.get('fps', 0) or 0),
            'message': str(body.get('message', ''))[:200]
        }
        with self.lock: self.status[dev['slot']] = item
        return item

    def issue_controller_code(self, name='AKP03E'):
        name = re.sub(r'\s+', ' ', str(name or 'AKP03E')).strip()[:100] or 'AKP03E'
        code = ''.join(str(secrets.randbelow(10)) for _ in range(8)); now = time.time()
        with self.lock, _db(self.db_path) as c:
            c.execute('DELETE FROM prompt_controller_pairing WHERE expires<=?', (now,))
            c.execute('DELETE FROM prompt_controller_pairing')
            c.execute('INSERT INTO prompt_controller_pairing VALUES(?,?,?)', (digest(code), now+600, name))
        return {'code': code, 'expiresAt': now+600, 'name': name}

    def pair_controller(self, code, name='AKP03E'):
        code = str(code or '').replace(' ', '').replace('-', '')
        if not re.fullmatch(r'\d{8}', code): raise GatewayError('Codice controller non valido o scaduto.', 401)
        now = time.time()
        with self.lock, _db(self.db_path) as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT expires,name FROM prompt_controller_pairing WHERE code_hash=?', (digest(code),)).fetchone()
            if not row or row[0] <= now: raise GatewayError('Codice controller non valido o scaduto.', 401)
            controller_id = 'akp03e-' + secrets.token_hex(6)
            token = secrets.token_urlsafe(32)
            ctl_name = re.sub(r'\s+', ' ', str(name or row[1] or 'AKP03E')).strip()[:100] or 'AKP03E'
            c.execute('DELETE FROM prompt_controller_pairing')
            c.execute('INSERT INTO prompt_controllers VALUES(?,?,?,?)', (controller_id, digest(token), ctl_name, now))
        self.controller_status.pop(controller_id, None)
        return {'token': token, 'id': controller_id, 'name': ctl_name}

    def controller_for_token(self, token):
        if not 20 <= len(token or '') <= 128: raise GatewayError('Controller Prompt non abbinato.', 401)
        with _db(self.db_path) as c:
            row = c.execute('SELECT id,name,paired FROM prompt_controllers WHERE token_hash=?', (digest(token),)).fetchone()
        if not row: raise GatewayError('Controller Prompt revocato o non valido.', 401)
        return {'id': row[0], 'name': row[1], 'paired': row[2]}

    def controller_heartbeat(self, ctl, body):
        item = {
            'lastSeen': time.time(), 'name': ctl['name'],
            'usbConnected': bool(body.get('usbConnected', False)),
            'vid': str(body.get('vid', ''))[:16], 'pid': str(body.get('pid', ''))[:16],
            'lastEvent': str(body.get('lastEvent', ''))[:160],
            'version': str(body.get('version', ''))[:40],
            'devices': [{'model':str(d.get('model',''))[:40], 'name':str(d.get('name',''))[:80], 'vid':str(d.get('vid',''))[:4], 'pid':str(d.get('pid',''))[:4]} for d in (body.get('devices') if isinstance(body.get('devices'),list) else [])[:8] if isinstance(d,dict)],
            'droppedEvents': max(0,min(1000000,int(body.get('droppedEvents',0) or 0))),
        }
        with self.lock: self.controller_status[ctl['id']] = item
        return item

    def controllers(self):
        now = time.time()
        with _db(self.db_path) as c:
            rows = c.execute('SELECT id,name,paired FROM prompt_controllers ORDER BY paired DESC').fetchall()
        out=[]
        for row in rows:
            st=self.controller_status.get(row[0]); online=bool(st and now-st['lastSeen'] < 4.0)
            out.append({'id':row[0],'name':row[1],'paired':row[2],'online':online,'status':st})
        return out

    def revoke_controller(self, controller_id):
        with self.lock, _db(self.db_path) as c:
            c.execute('DELETE FROM prompt_controllers WHERE id=?', (str(controller_id),))
        self.controller_status.pop(str(controller_id), None)
        return {'ok': True}

    def devices(self):
        now = time.time()
        with _db(self.db_path) as c:
            rows = c.execute('SELECT slot,station,role,name,paired FROM prompt_devices ORDER BY station,role DESC').fetchall()
        out=[]
        for row in rows:
            s = self.status.get(row[0]); online = bool(s and now-s['lastSeen'] < 2.5)
            out.append({'slot':row[0],'station':row[1],'role':row[2],'name':row[3],'paired':row[4],
                        'online':online,'status':s})
        return out

    def revoke(self, slot):
        with self.lock, _db(self.db_path) as c:
            c.execute('DELETE FROM prompt_devices WHERE slot=?', (slot,))
        self.status.pop(slot, None)
        return {'ok': True}

    def admin_state(self):
        project = self.project(); rt = self.runtime(); devices = self.devices()
        primary = next((x for x in devices if x['role']=='PRIMARY'), None)
        backup = next((x for x in devices if x['role']=='BACKUP'), None)
        ready = bool(backup and backup['online'] and backup.get('status',{}).get('projectVersion') == project['version'])
        sync_delta = None
        if primary and backup and primary.get('status') and backup.get('status'):
            try: sync_delta = round(abs(float(primary['status']['offsetVh'])-float(backup['status']['offsetVh'])), 3)
            except Exception: pass
        return {'project':project,'runtime':rt,'devices':devices,'controllers':self.controllers(),
                'backupReady':ready,'syncDeltaVh':sync_delta,'lastOsc':self.last_osc}


# ---- OSC 1.0 minimal codec -------------------------------------------------
def _osc_pad4(n): return (n + 3) & ~3

def _osc_string(data, pos):
    end = data.find(b'\0', pos)
    if end < 0: raise ValueError('OSC string')
    value = data[pos:end].decode('utf-8', 'replace')
    return value, _osc_pad4(end+1)


def parse_osc_packet(data):
    if not data or len(data) > 65535: raise ValueError('OSC packet')
    if data.startswith(b'#bundle\0'):
        if len(data) < 16: raise ValueError('OSC bundle')
        pos = 16; out=[]
        while pos+4 <= len(data):
            size = struct.unpack('>i', data[pos:pos+4])[0]; pos += 4
            if size <= 0 or pos+size > len(data): raise ValueError('OSC bundle item')
            out.extend(parse_osc_packet(data[pos:pos+size])); pos += size
        return out
    addr, pos = _osc_string(data, 0)
    tags, pos = _osc_string(data, pos)
    if not addr.startswith('/') or not tags.startswith(','): raise ValueError('OSC header')
    args=[]
    for tag in tags[1:]:
        if tag == 'i': args.append(struct.unpack('>i', data[pos:pos+4])[0]); pos += 4
        elif tag == 'f': args.append(struct.unpack('>f', data[pos:pos+4])[0]); pos += 4
        elif tag == 's': v,pos = _osc_string(data,pos); args.append(v)
        elif tag == 'T': args.append(True)
        elif tag == 'F': args.append(False)
        else: raise ValueError('OSC type '+tag)
    return [(addr,args)]


def osc_to_command(address, args):
    base = '/carisma/prompt'
    if not address.startswith(base): return None
    tail = address[len(base):] or '/'
    direct = {
        '/play': ('play', None), '/pause': ('pause', None), '/toggle': ('toggle', None), '/stop': ('stop', None),
        '/cue/next': ('cue_next', None), '/cue/prev': ('cue_prev', None), '/top': ('top', None),
        '/message/clear': ('message_clear', None), '/take/primary': ('take_primary', None), '/take/backup': ('take_backup', None), '/take/toggle': ('take_toggle', None),
    }
    if tail in direct: return direct[tail]
    if tail.startswith('/cue/') and len(tail) > 5: return ('cue', tail[5:])
    if tail == '/cue' and args: return ('cue', args[0])
    if tail == '/speed' and args: return ('speed', args[0])
    if tail == '/speed/delta' and args: return ('speed_delta', args[0])
    if tail == '/jog' and args: return ('jog', args[0])
    if tail == '/blackout': return ('blackout', args[0] if args else None)
    if tail == '/message' and args: return ('message', args[0])
    if tail == '/take' and args: return ('take', args[0])
    return None


class PromptOscServer:
    def __init__(self, store: PromptStore, bind='0.0.0.0', port=9000, allow=''):
        self.store=store; self.bind=bind; self.port=int(port); self.allow={x.strip() for x in str(allow).split(',') if x.strip()}
        self.stop_event=threading.Event(); self.thread=None; self.sock=None; self.error=''
    def start(self):
        try:
            sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            sock.bind((self.bind,self.port)); sock.settimeout(.5); self.sock=sock
        except OSError as exc:
            self.error=str(exc); return False
        self.thread=threading.Thread(target=self._run,name='carisma-prompt-osc',daemon=True); self.thread.start(); return True
    def _run(self):
        while not self.stop_event.is_set():
            try: data,addr=self.sock.recvfrom(65535)
            except socket.timeout: continue
            except OSError: break
            ip=addr[0]
            if self.allow and ip not in self.allow: continue
            try:
                messages=parse_osc_packet(data)
                for address,args in messages:
                    mapped=osc_to_command(address,args)
                    if mapped:
                        rt=self.store.command(mapped[0],mapped[1],source='OSC:'+ip)
                        self.store.last_osc={'at':time.time(),'ip':ip,'address':address,'args':args[:4],'seq':rt['seq']}
            except Exception as exc:
                self.store.last_osc={'at':time.time(),'ip':ip,'error':str(exc)[:180]}
    def status(self):
        return {'enabled':bool(self.sock),'bind':self.bind,'port':self.port,'allow':sorted(self.allow),'error':self.error,
                'last':self.store.last_osc}
    def close(self):
        self.stop_event.set()
        if self.sock:
            try:self.sock.close()
            except OSError:pass
        if self.thread: self.thread.join(timeout=1)


def handle_prompt(h, path):
    if not path.startswith('/api/prompt'):
        return False
    store: PromptStore = h.server.prompt
    try:
        # Public one-use pairing endpoint.
        if path == '/api/prompt/pair' and h.command == 'POST':
            body=h.body_json()
            if body is not None: h.reply(store.pair(body.get('code'), body.get('name')), 201)
            return True
        # Public one-use controller pairing endpoint.
        if path == '/api/prompt/controller/pair' and h.command == 'POST':
            body=h.body_json()
            if body is not None: h.reply(store.pair_controller(body.get('code'), body.get('name')), 201)
            return True
        # Restricted AKP03E/controller endpoints.
        if path.startswith('/api/prompt/controller/') and path not in ('/api/prompt/controller/pair-code','/api/prompt/controller/revoke'):
            token=h.headers.get('X-Prompt-Controller-Token',''); ctl=store.controller_for_token(token)
            if path == '/api/prompt/controller/state' and h.command in ('GET','HEAD'):
                state=store.admin_state()
                h.reply({'runtime':state['runtime'],'projectVersion':state['project']['version'],
                         'backupReady':state['backupReady'],'syncDeltaVh':state['syncDeltaVh'],
                         'devices':state['devices'],'controller':ctl,'serverTime':time.time()}); return True
            if path == '/api/prompt/controller/heartbeat' and h.command == 'POST':
                body=h.body_json()
                if body is not None: h.reply({'ok':True,'status':store.controller_heartbeat(ctl,body)})
                return True
            if path == '/api/prompt/controller/command' and h.command == 'POST':
                body=h.body_json()
                if body is None:return True
                allowed={'play','pause','toggle','stop','speed','speed_delta','jog','top','cue','cue_next','cue_prev','blackout','message_clear','take','take_primary','take_backup','take_toggle'}
                cmd=str(body.get('command','')).lower()
                if cmd not in allowed: raise GatewayError('Comando controller non consentito.',403)
                h.reply(store.controller_command(ctl, dict(body, command=cmd))); return True
            raise GatewayError('Endpoint controller Prompt non trovato.',404)
        # Restricted prompt-player endpoints.
        if path.startswith('/api/prompt/player/'):
            token=h.headers.get('X-Prompt-Token',''); dev=store.device_for_token(token)
            if path == '/api/prompt/player/state' and h.command in ('GET','HEAD'):
                q=parse_qs(urlsplit(h.path).query)
                try: pv=int(q.get('projectVersion',['0'])[0])
                except ValueError: pv=0
                project=store.project(); payload=project if pv != project['version'] else None
                h.reply({'project':payload,'projectVersion':project['version'],'runtime':store.runtime(),
                         'device':dev,'serverTime':time.time()}); return True
            if path == '/api/prompt/player/heartbeat' and h.command == 'POST':
                body=h.body_json()
                if body is not None: h.reply({'ok':True,'status':store.heartbeat(dev,body)})
                return True
            raise GatewayError('Endpoint player Prompt non trovato.',404)
        # Everything below is admin/control-token protected.
        if not h.authorized(): return True
        if path == '/api/prompt/state' and h.command in ('GET','HEAD'):
            value=store.admin_state(); value['osc']=h.server.prompt_osc.status(); h.reply(value); return True
        if path == '/api/prompt/project' and h.command == 'POST':
            body=h.body_json()
            if body is not None: h.reply(store.save_project(body.get('title'),body.get('text',''),body.get('settings'),body.get('revision')))
            return True
        if path == '/api/prompt/import' and h.command == 'POST':
            body=h.body_json()
            if body is None:return True
            encoded=body.get('data',''); name=str(body.get('name','copione.txt'))[:180]
            if not isinstance(encoded,str) or len(encoded) > ((MAX_IMPORT+2)//3)*4: raise GatewayError('File troppo grande.',413)
            try: raw=base64.b64decode(encoded,validate=True)
            except Exception: raise GatewayError('File non valido.',400)
            if len(raw)>MAX_IMPORT: raise GatewayError('File troppo grande.',413)
            if name.lower().endswith('.docx'): text=docx_to_text(raw)
            else:
                try:text=raw.decode('utf-8-sig')
                except UnicodeDecodeError: text=raw.decode('cp1252','replace')
            h.reply({'name':name,'text':text,'parsed':parse_script(text)}); return True
        if path == '/api/prompt/command' and h.command == 'POST':
            body=h.body_json()
            if body is not None: h.reply(store.command(body.get('command'),body.get('value'),source=str(body.get('source','REGIA'))[:60]))
            return True
        if path == '/api/prompt/controller/pair-code' and h.command == 'POST':
            body=h.body_json()
            if body is not None: h.reply(store.issue_controller_code(body.get('name','AKP03E')))
            return True
        if path == '/api/prompt/controller/revoke' and h.command == 'POST':
            body=h.body_json()
            if body is not None: h.reply(store.revoke_controller(str(body.get('id',''))))
            return True
        if path == '/api/prompt/pair-code' and h.command == 'POST':
            body=h.body_json()
            if body is not None: h.reply(store.issue_code(body.get('station','palco'),body.get('role')))
            return True
        if path == '/api/prompt/revoke' and h.command == 'POST':
            body=h.body_json()
            if body is not None: h.reply(store.revoke(str(body.get('slot',''))))
            return True
        raise GatewayError('Endpoint Prompt non trovato.',404)
    except GatewayError as exc:
        h.reply({'error':str(exc)},exc.status)
    except (ValueError,TypeError,KeyError,OverflowError) as exc:
        h.reply({'error':'Richiesta Prompt non valida: '+str(exc)},400)
    return True
