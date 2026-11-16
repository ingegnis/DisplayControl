"""Independent HID adapters. Protocol references are listed in CONTROLLERS.md.

Enumeration never claims arbitrary keyboards. No browser focus or keyboard hooks.
"""
from __future__ import annotations
from dataclasses import dataclass
import io
import struct
import time
from pathlib import Path
from akp03e_controller import (HidDevice, parse_report, image_announce, image_chunk,
                              packet, BUTTON_CODES, KNOB_PRESS_CODES, KNOB_TURN_CODES)


@dataclass(frozen=True)
class Profile:
    key: str
    name: str
    vid: int
    pid: int
    protocol: str
    display_keys: int = 0
    rotation: int = 0


PROFILES = (
    Profile('akp03e', 'AJAZZ AKP03E', 0x0300, 0x3002, 'akp3', 6, 270),
    Profile('akp03e-v2', 'AJAZZ AKP03E (protocollo 2)', 0x0300, 0x1002, 'akp2', 6),
    Profile('msd-two', 'Mars Gaming MSD-TWO', 0x0B00, 0x1001, 'akp2', 6),
    Profile('shuttlexpress', 'Contour ShuttleXpress', 0x0B33, 0x0020, 'contour'),
    Profile('shuttlepro-v2', 'Contour ShuttlePRO v2', 0x0B33, 0x0030, 'contour'),
    Profile('neo', 'Elgato Stream Deck Neo', 0x0FD9, 0x009A, 'neo', 8, 180),
)
BY_USB = {(p.vid, p.pid): p for p in PROFILES}
RATES = (0, .02, .04, .07, .11, .17, .25, .4)
BUTTON_COMMANDS = ('toggle', 'cue_prev', 'cue_next', 'blackout', 'top',
                   'take_toggle', 'message_clear', 'stop', 'take_toggle')


def identify(info):
    profile = BY_USB.get((info.get('vendor_id'), info.get('product_id')))
    if profile is None:
        return None
    interface = info.get('interface_number', -1)
    page = info.get('usage_page', 0)
    if profile.protocol.startswith('akp'):
        return profile if interface in (None, -1, 0) and page in (None, 0, 0xFFA0) else None
    if profile.protocol == 'contour':
        return profile if page in (None, 0, 0x0C) else None
    return profile if interface in (None, -1, 0) else None


def common_event(event):
    if not event:
        return []
    kind, index, value = event
    if kind == 'button' and value == 0 and 0 <= index < len(BUTTON_COMMANDS):
        return [(BUTTON_COMMANDS[index], None)]
    if kind == 'knob' and value == 1 and 0 <= index < 3:
        return [(("toggle", "stop", "take_toggle")[index], None)]
    if kind == 'turn' and value in (-1, 1):
        if index == 0: return [('speed_delta', .015 * value)]
        if index == 1: return [('jog', .08 * value)]
        if index == 2: return [('cue_next' if value > 0 else 'cue_prev', None)]
    return []


class Decoder:
    def __init__(self, profile):
        self.profile = profile
        self.previous = None
        self.ring_armed = False

    def feed(self, data):
        data = bytes(data)
        if self.profile.protocol.startswith('akp') and not data.startswith(b'ACK'):
            return []
        if self.profile.protocol == 'akp3':
            return common_event(parse_report(data))
        if self.profile.protocol == 'akp2':
            if len(data) < 10: return []
            action = data[9]
            # Protocol 2 sends discrete clicks, not key-up/key-down pairs.
            if action in BUTTON_CODES: return common_event(('button', BUTTON_CODES[action], 0))
            if action in KNOB_PRESS_CODES: return common_event(('knob', KNOB_PRESS_CODES[action], 1))
            if action in KNOB_TURN_CODES:
                index, direction = KNOB_TURN_CODES[action]
                return common_event(('turn', index, direction))
            return []
        if self.profile.protocol == 'neo':
            if len(data) != 14 or data[0] != 1 or data[1] != 0 or any(v > 1 for v in data[4:]): return []
            states = tuple(data[4:14])
            old, self.previous = self.previous, states
            if old is None: return []  # Held keys at connection are not commands.
            commands = [(c, None) for c in BUTTON_COMMANDS[:6]] + [
                ('speed_delta', -.015), ('speed_delta', .015), ('jog', -.08), ('jog', .08)]
            return [commands[i] for i in range(10) if states[i] and not old[i]]
        if self.profile.protocol == 'contour':
            # hidapi omits the zero report ID on unnumbered 5-byte reports.
            if len(data) != 5: return []
            ring = struct.unpack('b', data[:1])[0]
            if not -7 <= ring <= 7: return []
            mask = int.from_bytes(data[3:5], 'little')
            old, self.previous = self.previous, (ring, data[1], mask)
            if old is None:
                self.ring_armed = ring == 0
                return []
            result = []
            if ring == 0: self.ring_armed = True
            if ring != old[0] and self.ring_armed:
                result.append(('speed', RATES[abs(ring)] * (1 if ring >= 0 else -1)))
            steps = ((data[1] - old[1] + 128) % 256) - 128
            if 0 < abs(steps) <= 32: result.append(('jog', .08 * steps))
            bits = range(4, 9) if self.profile.key == 'shuttlexpress' else range(15)
            pro_extra = [('play',None),('pause',None),('stop',None),
                         ('speed_delta',-.015),('speed_delta',.015),('take_backup',None)]
            for index, bit in enumerate(bits):
                if mask & (1 << bit) and not old[2] & (1 << bit):
                    if index < 9: result.append((BUTTON_COMMANDS[index], None))
                    else: result.append(pro_extra[index-9])
            # A centered ring and explicit STOP take precedence in combined reports.
            if ('speed', 0) in result: return [('stop', None)]
            if ('stop', None) in result: return [('stop', None)]
            return result
        return []


def neo_image_reports(key, jpeg):
    if not 0 <= key < 8 or not jpeg or len(jpeg) > 65535: raise ValueError('Immagine Neo non valida')
    for page, offset in enumerate(range(0, len(jpeg), 1016)):
        chunk = jpeg[offset:offset+1016]
        header = struct.pack('<BBBBHH', 2, 7, key, int(offset+len(chunk) == len(jpeg)), len(chunk), page)
        yield (header + chunk).ljust(1024, b'\0')


class Device(HidDevice):
    """One exact enumerated path; never opens another matching device by accident."""
    def __init__(self, profile, info, hid_module, config):
        super().__init__(config.get('brightness', 65))
        self.profile, self.info, self.config = profile, info, config
        self.hid = hid_module
        self.path = info['path']
        self.decoder = Decoder(profile)
        self.icons = {}

    def enumerate(self):
        return [self.info]

    def open(self):
        try:
            if self.profile.protocol == 'akp3':
                # Preserve the established AKP03E double-open handshake, but bind
                # both opens to this exact path rather than the first USB match.
                return super().open()
            self.dev = self._open_path(self.path)
            if self.profile.protocol.startswith('akp'):
                self.write(packet(b'DIS\0\0'))
                self.set_brightness(self.brightness)
            elif self.profile.protocol == 'neo':
                self.write(bytes([2]).ljust(1024, b'\0'))
                feature = bytes([3, 8, self.brightness]).ljust(33, b'\0')
                if self.dev.send_feature_report(feature) != len(feature): raise OSError('Feature Neo incompleta')
            return self.info
        except Exception:
            self.close()
            raise

    def commands(self):
        data = self.read(1)
        return self.decoder.feed(data) if data else []

    def keep_alive(self):
        if self.profile.protocol.startswith('akp'): super().keep_alive()

    def set_key_jpeg(self, key, jpeg):
        if not 0 <= key < self.profile.display_keys or not jpeg or len(jpeg) > 65535:
            raise ValueError('Tasto o immagine non validi')
        if self.profile.protocol == 'neo':
            for report in neo_image_reports(key, jpeg): self.write(report)
        elif self.profile.protocol == 'akp2':
            # Explicit image length excludes padding used to clear the staging tail.
            self.write(image_announce(key, len(jpeg)))
            data = jpeg.ljust(8192, b'\0')
            for pos in range(0, len(data), 1024): self.write(image_chunk(data[pos:pos+1024]))
            self.write(packet(b'STP'))
        else:
            super().set_key_jpeg(key, jpeg)

    def update_icons(self, state):
        if not self.profile.display_keys: return
        rt = state.get('runtime', {})
        active = rt.get('activeRole', 'PRIMARY')
        names = ['pause' if rt.get('playing') else 'play', 'cue_prev', 'cue_next',
                 'black_on' if rt.get('blackout') else 'black', 'top',
                 'take_a' if active == 'BACKUP' else ('take_b' if state.get('backupReady') else 'backup_nr')]
        if self.profile.protocol == 'neo': names += ['speed_down', 'speed_up']
        for key, name in enumerate(names):
            if self.icons.get(key) == name: continue
            self.set_key_jpeg(key, icon_bytes(self.profile, name, self.config))
            self.icons[key] = name


_ICON_CACHE = {}
def icon_bytes(profile, name, config):
    root = Path(__file__).resolve().parent / 'controller_assets' / 'akp03e'
    rotation = int(config.get('iconRotation', profile.rotation)) if profile.protocol == 'akp3' else profile.rotation
    if rotation not in (0, 90, 180, 270): raise ValueError('Rotazione LCD non valida')
    if profile.protocol != 'neo': return (root / f'rot{rotation}' / (name+'.jpg')).read_bytes()
    cache_key = (name, rotation)
    if cache_key not in _ICON_CACHE:
        from PIL import Image, ImageDraw
        if name in ('speed_down', 'speed_up'):
            image = Image.new('RGB', (96, 96), '#172b27')
            draw = ImageDraw.Draw(image)
            draw.text((8, 28), 'SPEED', fill='white', font_size=19)
            draw.text((32, 49), '-' if name == 'speed_down' else '+', fill='#ffb270', font_size=32)
        else:
            with Image.open(root / 'rot0' / (name+'.jpg')) as original:
                image = original.convert('RGB').resize((96, 96))
        image = image.rotate(rotation)
        out = io.BytesIO();image.save(out, format='JPEG', quality=90)
        _ICON_CACHE[cache_key] = out.getvalue()
    return _ICON_CACHE[cache_key]
