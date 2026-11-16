#!/usr/bin/env python3
"""Carisma Prompt AKP03E controller service.

Direct USB HID integration for AJAZZ AKP03E (VID 0x0300 / PID 0x3002).
No AJAZZ vendor application is required during operation. The only Python
runtime dependency is `hidapi` (import name: hid).

Commands are sent to Carisma Prompt through the scoped controller API. If all
HTTP Core endpoints are unavailable, optional OSC fallback targets can receive
critical commands while the prompt players continue their local scroll.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import queue
import socket
import struct
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

VERSION = "0.10.0-alpha"
VID = 0x0300
PID = 0x3002
USAGE_PAGE = 0xFFA0
PACKET_SIZE = 1025
INPUT_SIZE = 512
DATA_CHUNK = 1024
HEADER = b"CRT\x00\x00"

BUTTON_CODES = {0x01:0,0x02:1,0x03:2,0x04:3,0x05:4,0x06:5,0x25:6,0x30:7,0x31:8}
KNOB_TURN_CODES = {0x90:(0,-1),0x91:(0,1),0x50:(1,-1),0x51:(1,1),0x60:(2,-1),0x61:(2,1)}
KNOB_PRESS_CODES = {0x33:0,0x35:1,0x34:2}

ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "data" / "akp03e_controller.json"
ASSET_ROOT = ROOT / "controller_assets" / "akp03e"


def packet(command: bytes) -> bytes:
    out = bytearray(PACKET_SIZE)
    out[1:6] = HEADER
    out[6:6+len(command)] = command
    return bytes(out)


def image_announce(key: int, size: int) -> bytes:
    return packet(b"BAT\x00\x00" + bytes([(size >> 8) & 0xFF, size & 0xFF, key + 1]))


def image_chunk(data: bytes) -> bytes:
    out = bytearray(PACKET_SIZE)
    out[1:1+len(data)] = data
    return bytes(out)


def parse_report(data: bytes):
    if not data or len(data) < 11 or data[0] == 0:
        return None
    action, state = data[9], data[10]
    if action == 0:
        return None
    if action in BUTTON_CODES:
        return ("button", BUTTON_CODES[action], int(state))
    if action in KNOB_TURN_CODES:
        knob, direction = KNOB_TURN_CODES[action]
        return ("turn", knob, direction)
    if action in KNOB_PRESS_CODES:
        return ("knob", KNOB_PRESS_CODES[action], int(state))
    return ("unknown", int(action), int(state))


def _osc_string(value: str) -> bytes:
    b = value.encode("utf-8") + b"\0"
    return b + b"\0" * ((-len(b)) % 4)


def osc_message(address: str, value=None) -> bytes:
    if value is None:
        return _osc_string(address) + _osc_string(",")
    if isinstance(value, bool):
        return _osc_string(address) + _osc_string(",T" if value else ",F")
    if isinstance(value, (int, float)):
        return _osc_string(address) + _osc_string(",f") + struct.pack(">f", float(value))
    return _osc_string(address) + _osc_string(",s") + _osc_string(str(value))


def command_to_osc(command: str, value=None):
    base = "/carisma/prompt"
    direct = {
        "play":"/play", "pause":"/pause", "toggle":"/toggle", "stop":"/stop",
        "cue_next":"/cue/next", "cue_prev":"/cue/prev", "top":"/top",
        "message_clear":"/message/clear", "take_primary":"/take/primary",
        "take_backup":"/take/backup", "take_toggle":"/take/toggle",
    }
    if command in direct:
        return osc_message(base + direct[command])
    if command == "speed": return osc_message(base + "/speed", value)
    if command == "speed_delta": return osc_message(base + "/speed/delta", value)
    if command == "jog": return osc_message(base + "/jog", value)
    if command == "blackout": return osc_message(base + "/blackout", value) if value is not None else osc_message(base + "/blackout")
    if command == "cue": return osc_message(base + "/cue", value)
    if command == "take": return osc_message(base + "/take", value)
    return None


class HidDevice:
    def __init__(self, brightness=65):
        self.brightness = max(1, min(100, int(brightness)))
        self.dev = None
        self.lock = threading.RLock()
        self.hid = None
        self.path = None

    def _module(self):
        if self.hid is None:
            try:
                import hid
            except ImportError as exc:
                raise RuntimeError("Modulo hidapi non installato. Esegui Installa_Controller_AKP03E_Windows.bat") from exc
            self.hid = hid
        return self.hid

    def enumerate(self):
        hid = self._module()
        out = []
        for d in hid.enumerate(VID, PID):
            if d.get("usage_page") in (None, 0, USAGE_PAGE):
                out.append(d)
        return out

    def _open_path(self, path):
        hid = self._module()
        if hasattr(hid, "Device"):
            return hid.Device(path=path)
        dev = hid.device()
        dev.open_path(path)
        return dev

    def open(self):
        devices = self.enumerate()
        if not devices:
            raise RuntimeError("AJAZZ AKP03E non trovato (atteso USB 0300:3002).")
        self.path = devices[0]["path"]
        self.dev = self._open_path(self.path)
        self._init_sequence(clear=True)
        self.close()
        time.sleep(0.5)
        self.dev = self._open_path(self.path)
        self._init_sequence(clear=True)
        return devices[0]

    def close(self):
        with self.lock:
            if self.dev is not None:
                try: self.dev.close()
                except Exception: pass
                self.dev = None

    def write(self, data: bytes):
        with self.lock:
            if self.dev is None: raise RuntimeError("AKP03E non connesso")
            written = self.dev.write(data)
            if written != len(data): raise OSError('Scrittura HID incompleta')

    def read(self, timeout_ms=100):
        with self.lock:
            if self.dev is None: return None
            try:
                data = self.dev.read(INPUT_SIZE, timeout=timeout_ms)
            except TypeError:
                data = self.dev.read(INPUT_SIZE, timeout_ms)
            return bytes(data) if data else None

    def _init_sequence(self, clear=True):
        self.write(packet(b"DIS\x00\x00"))
        self.write(packet(b"LIG\x00\x00" + bytes([self.brightness])))
        if clear:
            self.write(packet(b"CLE\x00\x00\x00\xFF"))
            self.write(packet(b"STP"))

    def keep_alive(self):
        self.write(packet(b"CONNECT"))

    def set_brightness(self, value):
        self.brightness=max(1,min(100,int(value)))
        self.write(packet(b"LIG\x00\x00"+bytes([self.brightness])))

    def set_key_jpeg(self, key: int, jpeg: bytes):
        if not 0 <= key <= 5: raise ValueError("key")
        if not jpeg or len(jpeg) > 65535: raise ValueError("jpeg")
        with self.lock:
            self.write(image_announce(key, len(jpeg)))
            for pos in range(0, len(jpeg), DATA_CHUNK):
                self.write(image_chunk(jpeg[pos:pos+DATA_CHUNK]))
            self.write(packet(b"STP"))


class CarismaApi:
    def __init__(self, config):
        self.config=config
        self.servers=[x.rstrip('/') for x in config.get("servers",[]) if str(x).strip()]
        self.token=str(config.get("token",''))
        self.timeout=float(config.get("timeout",0.6))
        self.last_server=None

    def _token_for(self, server):
        return self.config.get('serverTokens', {}).get(server, self.token)

    @staticmethod
    def _request(url, method="GET", body=None, token="", timeout=1.0):
        headers={"User-Agent":"Carisma-AKP03E/"+VERSION}
        if token: headers["X-Prompt-Controller-Token"]=token
        data=None
        if body is not None:
            data=json.dumps(body,separators=(",",":"),ensure_ascii=False).encode("utf-8")
            headers["Content-Type"]="application/json"
        req=urllib.request.Request(url,data=data,headers=headers,method=method)
        with urllib.request.urlopen(req,timeout=timeout) as r:
            raw=r.read()
            return json.loads(raw or b"{}")

    def pair(self, code, name="AKP03E Regia", server=None):
        errors=[]
        for server in ([server] if server else self.servers):
            try:
                data=self._request(server+"/api/prompt/controller/pair","POST",{"code":code,"name":name},timeout=2.0)
                self.token=data["token"]; self.last_server=server
                self.config.setdefault('serverTokens', {})[server] = data['token']
                return data
            except Exception as exc: errors.append(f"{server}: {exc}")
        raise RuntimeError("Abbinamento fallito: "+" | ".join(errors))

    def state(self):
        for server in self._ordered_servers():
            try:
                data=self._request(server+"/api/prompt/controller/state",token=self._token_for(server),timeout=self.timeout)
                self.last_server=server; return data
            except Exception: continue
        raise RuntimeError("Nessun Carisma Core raggiungibile via HTTP")

    def heartbeat(self, payload):
        for server in self._ordered_servers():
            try:
                self._request(server+"/api/prompt/controller/heartbeat","POST",payload,token=self._token_for(server),timeout=self.timeout)
                self.last_server=server; return True
            except Exception: continue
        return False

    def command(self, command, value=None):
        body={"command":command, "requestId":uuid.uuid4().hex}
        if value is not None: body["value"]=value
        # Relative actions cannot be replayed after an ambiguous HTTP result.
        # Separate Core databases cannot deduplicate one another's requests.
        absolute = command in {'play','pause','stop','speed','top','cue','message_clear','take','take_primary','take_backup'} or (command == 'blackout' and value is not None)
        for server in self._ordered_servers():
            try:
                data=self._request(server+"/api/prompt/controller/command","POST",body,token=self._token_for(server),timeout=self.timeout)
                self.last_server=server; return data, "HTTP"
            except urllib.error.HTTPError as exc:
                # Rejection must not be bypassed through unauthenticated OSC.
                raise RuntimeError('Core rifiuta il comando (HTTP %s); verificare pairing e permessi.' % exc.code) from exc
            except Exception as exc:
                reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
                definitely_not_sent = isinstance(reason, (ConnectionRefusedError, socket.gaierror))
                if not absolute and not definitely_not_sent:
                    raise RuntimeError('Esito HTTP incerto: comando relativo non ritrasmesso. Verificare lo stato.') from exc
        if self._osc_fallback(command,value): return None, "OSC-INVIATO-NON-CONFERMATO"
        raise RuntimeError("Comando non consegnato: nessun Core HTTP/OSC disponibile")

    def _ordered_servers(self):
        if self.last_server in self.servers:
            return [self.last_server]+[x for x in self.servers if x!=self.last_server]
        return list(self.servers)

    def _osc_fallback(self, command, value):
        msg=command_to_osc(command,value)
        targets=self.config.get("oscTargets",[])
        if not msg or not targets: return False
        sent=False
        sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        try:
            for target in targets:
                try:
                    host,port=str(target).rsplit(':',1)
                    sock.sendto(msg,(host,int(port))); sent=True
                except Exception: pass
        finally: sock.close()
        return sent


class ControllerService:
    def __init__(self, config_path=DEFAULT_CONFIG, device=None, api=None):
        self.config_path=Path(config_path)
        self.config=load_config(self.config_path)
        self.device=device or HidDevice(self.config.get("brightness",65))
        self.api=api or CarismaApi(self.config)
        self.events=queue.Queue(maxsize=64)
        self.stop=threading.Event()
        self.reader=None
        self.usb_info={}
        self.connected=False
        self.last_event=""
        self.last_state=None
        self.last_icons={}
        self.last_action_at={}
        self.dropped_events=0

    def clear_events(self):
        while True:
            try:self.events.get_nowait();self.dropped_events+=1
            except queue.Empty:return

    def lose_usb(self, message):
        self.connected=False
        self.last_event=message[:160]
        self.clear_events()
        self.last_icons.clear()
        try:self.device.close()
        except Exception:pass

    def enqueue(self, event):
        # STOP is never left behind a burst of encoder events.
        if event == ('knob',1,1) or (event[0]=='button' and event[1]==7):
            self.clear_events()
        try:self.events.put_nowait((time.monotonic(), event))
        except queue.Full:
            self.clear_events()
            self.events.put_nowait((time.monotonic(), event))

    def process_event(self):
        try:created,event=self.events.get_nowait()
        except queue.Empty:return
        if not self.connected or time.monotonic()-created > .75:
            self.dropped_events+=1
            return
        self.handle_event(event)

    def _icon_bytes(self, name):
        rotation=int(self.config.get("iconRotation",270))
        path=ASSET_ROOT / f"rot{rotation}" / (name+".jpg")
        if not path.is_file():
            path=ASSET_ROOT / "rot270" / (name+".jpg")
        return path.read_bytes()

    def _set_icon(self,key,name):
        if self.last_icons.get(key)==name:return
        self.device.set_key_jpeg(key,self._icon_bytes(name)); self.last_icons[key]=name

    def update_icons(self, state=None, force=False):
        state=state or self.last_state or {}
        rt=state.get("runtime",{})
        devices=state.get("devices",[])
        active=str(rt.get("activeRole","PRIMARY")).upper()
        primary=next((x for x in devices if x.get("role")=="PRIMARY"),{})
        backup=next((x for x in devices if x.get("role")=="BACKUP"),{})
        mapping={
            0:"pause" if rt.get("playing") else "play",
            1:"cue_prev", 2:"cue_next",
            3:"black_on" if rt.get("blackout") else "black",
            4:"top",
        }
        if active=="BACKUP": mapping[5]="take_a" if primary.get("online") else "primary_nr"
        else: mapping[5]="take_b" if state.get("backupReady") else "backup_nr"
        if force:self.last_icons.clear()
        for key,name in mapping.items(): self._set_icon(key,name)

    def _reader_loop(self):
        while not self.stop.is_set():
            if not self.connected:
                self.stop.wait(.1); continue
            try:
                data=self.device.read(120)
                ev=parse_report(data) if data else None
                if ev:
                    self.enqueue(ev)
            except Exception as exc:
                self.lose_usb("USB perso: "+str(exc))

    def connect_usb(self):
        try:
            self.clear_events();self.last_action_at.clear()
            info=self.device.open() or {}
            self.usb_info=info; self.last_icons.clear()
            self.update_icons(force=True)
            self.connected=True
            self.last_event="AKP03E collegato"
            return True
        except Exception as exc:
            self.lose_usb(str(exc))
            return False

    def _debounced(self,key,interval=.12):
        now=time.monotonic(); last=self.last_action_at.get(key,0)
        if now-last<interval:return False
        self.last_action_at[key]=now; return True

    def handle_event(self, ev):
        kind, index, value=ev
        command=None; arg=None
        if kind=="button":
            # Display keys generate both edges; trigger on release. Side keys on
            # this firmware are commonly release-only, so any side event triggers.
            if index < 6 and value != 0:return
            if not self._debounced((kind,index),.10):return
            mapping={0:"toggle",1:"cue_prev",2:"cue_next",3:"blackout",4:"top",5:"take_toggle",6:"message_clear",7:"stop",8:"take_toggle"}
            command=mapping.get(index)
        elif kind=="knob":
            if value==0:return
            if not self._debounced((kind,index),.15):return
            command={0:"toggle",1:"stop",2:"take_toggle"}.get(index)
        elif kind=="turn":
            if index==0: command,arg="speed_delta",0.015*value
            elif index==1: command,arg="jog",0.08*value
            elif index==2: command="cue_next" if value>0 else "cue_prev"
        if not command:return
        try:
            result,transport=self.api.command(command,arg)
            self.last_event=f"{kind}{index}: {command} via {transport}"
            if result and isinstance(result,dict):
                self.last_state={**(self.last_state or {}),"runtime":result}
                try:self.update_icons(self.last_state)
                except Exception as exc:self.lose_usb('LCD/USB perso: '+str(exc))
        except Exception as exc:
            self.last_event=f"{command}: {exc}"[:160]
            self.clear_events()

    def run(self):
        if not self.config.get("token"):
            raise RuntimeError("Controller non abbinato. Esegui Configura_Controller_AKP03E_Windows.bat")
        self.reader=threading.Thread(target=self._reader_loop,name="akp03e-reader",daemon=True);self.reader.start()
        next_usb=0.;next_state=0.;next_hb=0.;next_keep=0.
        print("CARISMA / AKP03E CONTROLLER",VERSION)
        print("Server:",", ".join(self.config.get("servers",[])))
        print("CTRL+C per arrestare.\n")
        try:
            while not self.stop.is_set():
                now=time.monotonic()
                if not self.connected and now>=next_usb:
                    if self.connect_usb(): print("AKP03E collegato.",flush=True)
                    else: print("AKP03E non disponibile; nuovo tentativo tra 2 s.",flush=True)
                    next_usb=now+2.0
                self.process_event()
                if now>=next_state:
                    try:
                        self.last_state=self.api.state()
                        if self.connected:
                            try:self.update_icons(self.last_state)
                            except Exception as exc:self.lose_usb('LCD/USB perso: '+str(exc))
                    except Exception as exc:
                        self.last_event="Core non raggiungibile: "+str(exc)[:100]
                    next_state=now+.45
                if now>=next_hb:
                    self.api.heartbeat({"usbConnected":self.connected,"vid":"0300","pid":"3002","lastEvent":self.last_event,"version":VERSION})
                    next_hb=now+2.0
                if self.connected and now>=next_keep:
                    try:self.device.keep_alive()
                    except Exception as exc:self.lose_usb('USB keepalive: '+str(exc))
                    next_keep=now+4.0
                time.sleep(.02)
        except KeyboardInterrupt: pass
        finally:
            self.stop.set(); self.device.close()
            if self.reader:self.reader.join(timeout=1)


def load_config(path):
    path=Path(path)
    if not path.is_file():return {}
    try:
        data=json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data,dict) else {}
    except Exception:return {}


def save_config(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
        try:temp.chmod(0o600)
        except OSError:pass
        os.replace(temp,path)
    finally:temp.unlink(missing_ok=True)


def normalize_server(value):
    value=value.strip().rstrip('/')
    if not value.startswith(('http://','https://')):value='http://'+value
    parsed=urllib.parse.urlsplit(value)
    if parsed.scheme not in ('http','https') or not parsed.hostname:raise ValueError("Indirizzo server non valido")
    return value


def interactive_setup(path):
    cfg=load_config(path)
    print("DISPLAYCONTROL / CONFIGURAZIONE CONTROLLER USB\n")
    current=(cfg.get("servers") or ["http://127.0.0.1:8787"])[0]
    entered=input(f"Server Core, separati da virgola [{current}]: ").strip() or current
    servers=list(dict.fromkeys(normalize_server(x) for x in entered.split(',') if x.strip()))
    name=input("Nome controller [Controller regia]: ").strip() or "Controller regia"
    osc=input("Fallback OSC opzionali, es. 192.168.10.11:9000,192.168.10.12:9000 [vuoto]: ").strip()
    cfg.update({"servers":servers,"serverTokens":{},"oscTargets":[x.strip() for x in osc.split(',') if x.strip()],"brightness":65,"iconRotation":270,"timeout":0.6})
    api=CarismaApi(cfg)
    for server in servers:
        code=input(f"Codice controller a 8 cifre generato su {server}: ").strip()
        if not code:raise RuntimeError("Codice mancante")
        data=api.pair(code,name,server=server)
        cfg.setdefault('serverControllerIds',{})[server]=data['id']
    cfg["token"]=cfg['serverTokens'][servers[0]];cfg["controllerId"]=cfg['serverControllerIds'][servers[0]];cfg["name"]=name
    save_config(path,cfg)
    print("\nAbbinamento completato:",data["id"])
    print("Configurazione salvata in",path)


def diagnose(path, seconds=8):
    cfg=load_config(path);dev=HidDevice(cfg.get("brightness",65))
    print("VID:PID atteso 0300:3002")
    devices=dev.enumerate();print("Dispositivi trovati:",len(devices))
    for d in devices:print(" -",d.get("product_string"),d.get("serial_number"),"usage",hex(d.get("usage_page") or 0))
    if not devices:return 2
    info=dev.open();print("Aperto:",info.get("product_string") or "AKP03E")
    rotation=int(cfg.get("iconRotation",270));folder=ASSET_ROOT/f"rot{rotation}"
    names=["play","cue_prev","cue_next","black","top","take_b"]
    for i,n in enumerate(names):dev.set_key_jpeg(i,(folder/(n+".jpg")).read_bytes())
    print(f"Premi tasti e ruota manopole per {seconds} secondi:")
    end=time.time()+seconds
    try:
        while time.time()<end:
            raw=dev.read(200);ev=parse_report(raw) if raw else None
            if ev:print(" ",ev,flush=True)
            try:dev.keep_alive()
            except Exception:pass
    finally:dev.close()
    return 0


def main(argv=None):
    # Compatibility entry point: one hub and one lock for old and new launchers.
    from controller_service import main as unified_main
    return unified_main(argv)


if __name__=="__main__":raise SystemExit(main())
