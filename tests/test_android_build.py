import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import xml.etree.ElementTree as ET
import build_android as b

class AndroidBuildUtilitiesTests(unittest.TestCase):
    def test_zip_traversal_refused(self):
        for name in ['../outside','/absolute','x\\..\\outside','C:/outside']:
            with tempfile.TemporaryDirectory() as d:
                z=Path(d)/'x.zip'
                with zipfile.ZipFile(z,'w') as f:f.writestr(name,'bad')
                with self.assertRaises(ValueError):b.safe_extract(z,Path(d)/'target')
    def test_zip_safe_content(self):
        with tempfile.TemporaryDirectory() as d:
            z=Path(d)/'x.zip'
            with zipfile.ZipFile(z,'w') as f:f.writestr('cmdline-tools/bin/test','valid')
            b.safe_extract(z,Path(d)/'target')
            self.assertEqual((Path(d)/'target/cmdline-tools/bin/test').read_text(),'valid')
    def test_verified_cache_never_downloads(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'sdk.zip';p.write_bytes(b'cache');sha=hashlib.sha256(b'cache').hexdigest()
            with patch('urllib.request.urlopen',side_effect=AssertionError('network')):b.fetch_checked('https://invalid',p,sha)
    def test_bad_checksum_refused(self):
        import io
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'sdk.zip'
            with patch('urllib.request.urlopen',return_value=io.BytesIO(b'incorrect')):
                with self.assertRaises(ValueError):b.fetch_checked('https://invalid',p,'0'*64)
            self.assertFalse(p.exists());self.assertFalse(p.with_suffix('.zip.part').exists())
    def test_manifest_tv_and_no_privileged_permissions(self):
        m=ET.parse(b.SOURCE/'AndroidManifest.xml').getroot();a='{http://schemas.android.com/apk/res/android}'
        permissions={x.get(a+'name') for x in m.findall('uses-permission')}
        self.assertEqual(permissions,{'android.permission.INTERNET','android.permission.ACCESS_NETWORK_STATE'})
        categories={x.get(a+'name') for x in m.findall('.//category')}
        self.assertIn('android.intent.category.LEANBACK_LAUNCHER',categories)
        self.assertEqual(m.find('application').get(a+'allowBackup'),'false')
    def test_packaged_shell_is_current(self):
        for name in ['player.html','physical_boot.js','favicon.svg']:
            self.assertEqual((b.ROOT/name).read_bytes(),(b.SOURCE/'assets'/name).read_bytes())
    def test_sdk_hashes_pinned(self):
        for name,sha in b.DOWNLOADS.values():self.assertRegex(sha,r'^[a-f0-9]{64}$');self.assertTrue(name.endswith('.zip'))
