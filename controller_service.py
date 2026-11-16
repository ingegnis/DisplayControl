#!/usr/bin/env python3
"""Background USB controller hub. One scoped pairing, all supported surfaces."""
from __future__ import annotations
import argparse
from dataclasses import dataclass, field
from pathlib import Path
import queue
import threading
import time
import uuid
from akp03e_controller import CarismaApi, DEFAULT_CONFIG, load_config, interactive_setup
from controller_devices import Device, PROFILES, identify

VERSION = '0.11.0-alpha'


@dataclass
class Session:
    device: object
    generation: str = field(default_factory=lambda: uuid.uuid4().hex)
    attached: float = field(default_factory=time.monotonic)
    last_keep: float = 0
    last_buttons: dict = field(default_factory=dict)


def singleton(config_path):
    """An OS-released file lock; no reserved TCP/UDP ports or stale PID files."""
    import os
    path = Path(config_path).resolve()
    handle = path.with_name(path.name+'.controller.lock').open('a+b')
    try:
        if handle.seek(0, 2) == 0:handle.write(b'0');handle.flush()
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        handle.close()
        raise RuntimeError('Configurazione già utilizzata da un altro servizio controller, o file non accessibile.') from exc
    return handle


class ControllerHub:
    def __init__(self, config_path=DEFAULT_CONFIG, hid_module=None, api=None, factory=Device):
        self.config_path = Path(config_path)
        self.config = load_config(config_path)
        if hid_module is None:
            try: import hid as hid_module
            except ImportError as exc: raise RuntimeError('Esegui Installa_Controller_Windows.bat oppure python3 setup_controllers.py') from exc
        self.hid = hid_module
        self.api = api or CarismaApi(self.config)
        self.factory = factory
        self.sessions = {}
        self.lock = threading.RLock()
        self.events = queue.Queue(maxsize=64)
        self.stop = threading.Event()
        self.state = {}
        self.last_event = 'In attesa di un controller USB'
        self.dropped = 0
        self.worker = None
        self.telemetry = None
        self.retry_after = {}

    def discard(self):
        while True:
            try:self.events.get_nowait();self.dropped += 1
            except queue.Empty:return

    def remove(self, path, reason='USB scollegato'):
        with self.lock:session = self.sessions.pop(path, None)
        if session:
            try:session.device.close()
            finally:self.last_event = session.device.profile.name+': '+reason

    def scan(self):
        # Keep healthy handles if enumeration fails.
        found = {}
        for info in self.hid.enumerate():
            profile = identify(info)
            if profile and info.get('path') is not None and len(found) < 8:
                found.setdefault(info['path'], (profile, info))
        with self.lock:existing = set(self.sessions)
        for path in existing - found.keys(): self.remove(path)
        for path, (profile, info) in found.items():
            if path in self.sessions or time.monotonic() < self.retry_after.get(path, 0): continue
            device = self.factory(profile, info, self.hid, self.config)
            try:
                device.open()
                with self.lock:self.sessions[path] = Session(device)
                self.last_event = profile.name+' collegato'
                self.retry_after.pop(path, None)
            except Exception as exc:
                device.close()
                self.retry_after[path] = time.monotonic()+2
                self.last_event = profile.name+': apertura non riuscita ('+type(exc).__name__+')'
        self.retry_after = {p:t for p,t in self.retry_after.items() if p in found}

    def submit(self, session, command, value=None):
        now = time.monotonic()
        if now-session.attached < .2: return
        if command in {'toggle','blackout','take_toggle'}:
            if now-session.last_buttons.get(command, 0) < .1: return
            session.last_buttons[command] = now
        if command == 'stop' or (command == 'speed' and value == 0): self.discard()
        item = (now, session.generation, command, value)
        try:self.events.put_nowait(item)
        except queue.Full:
            self.discard()
            self.events.put_nowait(item)

    def poll_devices(self):
        with self.lock:sessions = list(self.sessions.items())
        for path, session in sessions:
            try:
                # Seed held keys during connection grace.
                decoder = getattr(session.device, 'decoder', None)
                if time.monotonic()-session.attached >= .2 and decoder and decoder.profile.protocol == 'neo' and decoder.previous is None:
                    decoder.previous = (0,)*10
                for command, value in session.device.commands(): self.submit(session, command, value)
                if time.monotonic()-session.last_keep > 4:
                    session.device.keep_alive();session.last_keep = time.monotonic()
                session.device.update_icons(self.state)
            except Exception as exc:
                self.remove(path, 'errore HID/LCD ('+type(exc).__name__+')')
                self.retry_after[path] = time.monotonic()+2

    def dispatch_one(self):
        try:created, generation, command, value = self.events.get_nowait()
        except queue.Empty:return
        with self.lock:
            session = next((s for s in self.sessions.values() if s.generation == generation), None)
        if not session or time.monotonic()-created > .75:
            self.dropped += 1
            return
        try:
            result, transport = self.api.command(command, value)
            self.last_event = f'{session.device.profile.name}: {command} / {transport}'
            if isinstance(result, dict):self.state = {**self.state, 'runtime':result}
        except Exception as exc:
            self.last_event = str(exc)[:160]
            self.discard()

    def status(self):
        with self.lock:sessions = list(self.sessions.values())
        return {'usbConnected':bool(sessions), 'version':VERSION, 'lastEvent':self.last_event,
                'droppedEvents':self.dropped, 'devices':[
                    {'model':s.device.profile.key,'name':s.device.profile.name,
                     'vid':f'{s.device.profile.vid:04x}','pid':f'{s.device.profile.pid:04x}'} for s in sessions]}

    def network_loop(self):
        while not self.stop.is_set():
            self.dispatch_one()
            self.stop.wait(.01)

    def telemetry_loop(self):
        next_state = next_hb = 0
        while not self.stop.is_set():
            now = time.monotonic()
            if now >= next_state:
                try:self.state = self.api.state()
                except Exception:self.last_event = 'Core non raggiungibile; i comandi scaduti non vengono ripetuti'
                next_state = time.monotonic()+.45
            if now >= next_hb:
                try:self.api.heartbeat(self.status())
                except Exception:pass
                next_hb = time.monotonic()+1.5
            self.stop.wait(.01)

    def run(self):
        if not self.config.get('token') and not self.config.get('serverTokens'):
            raise RuntimeError('Genera un codice nella regia Prompt e avvia Configura_Controller_Windows.bat / --setup')
        guard = singleton(self.config_path)
        self.worker = threading.Thread(target=self.network_loop, name='controller-network', daemon=True)
        self.worker.start()
        self.telemetry = threading.Thread(target=self.telemetry_loop, name='controller-status', daemon=True)
        self.telemetry.start()
        next_scan = 0
        print('DisplayControl / Controller USB', VERSION, flush=True)
        print('Riconoscimento automatico; Prompt può restare in secondo piano. CTRL+C per arrestare.', flush=True)
        try:
            while not self.stop.is_set():
                if time.monotonic() >= next_scan:
                    try:self.scan()
                    except Exception as exc:self.last_event = 'Enumerazione USB non riuscita ('+type(exc).__name__+')'
                    next_scan = time.monotonic()+1
                self.poll_devices()
                self.stop.wait(.005)
        except KeyboardInterrupt:pass
        finally:
            self.stop.set()
            self.worker.join(timeout=5)
            self.telemetry.join(timeout=5)
            for path in list(self.sessions):self.remove(path, 'servizio arrestato')
            guard.close()


def diagnose(config_path, seconds, list_only=False):
    import hid
    found = [(identify(i),i) for i in hid.enumerate() if identify(i)]
    print('Controller riconosciuti:', len(found))
    for profile, _ in found: print(' -', profile.name, f'{profile.vid:04x}:{profile.pid:04x}')
    if list_only:return 0
    if not found:return 2
    handles = []
    try:
        for profile, info in found:
            device = Device(profile, info, hid, load_config(config_path));handles.append(device);device.open()
        print('Diagnosi locale: nessun comando viene inviato al server.')
        until = time.monotonic()+seconds
        while time.monotonic() < until:
            for device in handles:
                for command in device.commands():print(device.profile.name, command, flush=True)
            time.sleep(.01)
    finally:
        for device in handles:device.close()
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description='DisplayControl: controller USB automatici, indipendenti dal browser')
    parser.add_argument('--config', default=str(DEFAULT_CONFIG))
    parser.add_argument('--setup', action='store_true')
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--diagnose', action='store_true')
    parser.add_argument('--diagnose-seconds', '--seconds', type=int, default=15)
    args = parser.parse_args(argv)
    if args.setup:interactive_setup(Path(args.config));return 0
    if args.list or args.diagnose:return diagnose(args.config, max(2,min(60,args.diagnose_seconds)), args.list)
    ControllerHub(args.config).run()
    return 0

if __name__ == '__main__':raise SystemExit(main())
