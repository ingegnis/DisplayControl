import base64
import copy
import json
import struct
import unittest
import zlib
from branding import valid_branding, identity
from server import valid_state
from pathlib import Path

def png(width=2,height=2):
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,6,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+b'\x14\x6e\xf0\xff'*width)*height))+chunk(b'IEND',b'')

class BrandingTests(unittest.TestCase):
    def test_embedded_png_theme_export_roundtrip(self):
        site={'name':'Associazione Test','branding':{'logo':'data:image/png;base64,'+base64.b64encode(png()).decode(),'theme':{'accent':'#1260ab','sidebar':'#12283e'}}}
        self.assertTrue(valid_branding(site));self.assertEqual(identity(json.loads(json.dumps(site))),site)
        project=json.loads((Path(__file__).resolve().parents[1]/'example_project.json').read_text(encoding='utf-8'))
        project['site']=site;self.assertTrue(valid_state(project))

    def test_remote_svg_oversize_and_css_injection_rejected(self):
        for logo in ['https://outside/logo.png','data:image/svg+xml,<svg/>','data:image/png;base64,'+'a'*180000,'data:image/png;base64,'+base64.b64encode(png(321,1)).decode()]:
            self.assertFalse(valid_branding({'branding':{'logo':logo}}))
        self.assertFalse(valid_branding({'branding':{'theme':{'accent':'red;url(https://outside)','sidebar':'#112233'}}}))

    def test_corrupt_image_rejected_without_exposing_project(self):
        raw=bytearray(png());raw[29]^=1
        self.assertFalse(valid_branding({'branding':{'logo':'data:image/png;base64,'+base64.b64encode(raw).decode()}}))
        self.assertEqual(set(identity({'name':'Test','password':'secret'})),{'name','branding'})
