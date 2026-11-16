"""Bounded organization identity stored in the existing project, without secrets."""
import base64
import re
import struct
import zlib


def valid_branding(site):
    if not isinstance(site.get('name', ''), str) or len(site.get('name', '')) > 80:
        return False
    brand = site.get('branding', {})
    if not isinstance(brand, dict): return False
    logo = brand.get('logo', '')
    if not isinstance(logo, str) or len(logo) > 180000: return False
    if logo:
        if not logo.startswith('data:image/png;base64,'): return False
        try:
            raw = base64.b64decode(logo.split(',', 1)[1], validate=True)
            if len(raw) < 45 or raw[:8] != b'\x89PNG\r\n\x1a\n' or raw[12:16] != b'IHDR': return False
            width, height = struct.unpack('>II', raw[16:24])
            if not (1 <= width <= 320 and 1 <= height <= 320): return False
            # Validate PNG chunk bounds and checksums.
            pos = 8
            while pos < len(raw):
                length = int.from_bytes(raw[pos:pos+4], 'big')
                end = pos + 12 + length
                if end > len(raw): return False
                chunk = raw[pos+4:pos+8+length]
                if zlib.crc32(chunk) != int.from_bytes(raw[pos+8+length:end], 'big'): return False
                if raw[pos+4:pos+8] == b'IEND': return length == 0 and end == len(raw) and valid_theme(brand)
                pos = end
            return False
        except (ValueError, struct.error): return False
    return valid_theme(brand)


def valid_theme(brand):
    theme = brand.get('theme')
    return theme is None or (isinstance(theme, dict) and all(
        isinstance(theme.get(k), str) and re.fullmatch(r'#[0-9a-fA-F]{6}', theme[k])
        for k in ('accent', 'sidebar')))


def identity(site):
    brand = site.get('branding', {}) if valid_branding(site) else {}
    name = site.get('name')
    return {'name': name.strip() if isinstance(name, str) and name.strip() else 'Carisma',
            'branding': {'logo': brand.get('logo', ''), 'theme': brand.get('theme')}}
