"""Repair logic tests; native Windows installers are NOT run by this suite."""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import zipfile

import diagnose_ndi as diag
import setup_ndi as setup


class DiagnosticTests(unittest.TestCase):
    def test_codec_names_not_descriptions(self):
        text = ' V....D h264_wrong Description mentioning libx264\n A..... aac_wrong Description aac \n'
        self.assertNotIn('libx264', diag.encoder_names(text))
        self.assertNotIn('aac', diag.encoder_names(text))

    def test_codec_names_valid(self):
        self.assertEqual(diag.encoder_names(' V....D libx264 H264\n A..... aac AAC\n'), {'libx264', 'aac'})

    def test_missing_ffmpeg(self):
        self.assertFalse(diag.probe_ffmpeg('')['available'])

    def test_encoder_process_failure(self):
        process = subprocess.CompletedProcess([], 2, ' V....D libx264 H264\n A..... aac AAC\n', 'failed')
        with patch.object(diag.subprocess, 'run', return_value=process):
            self.assertFalse(diag.probe_ffmpeg('missing-exe')['available'])

    def test_timeout_is_reported(self):
        with patch.object(diag.subprocess, 'run', side_effect=subprocess.TimeoutExpired('ffmpeg', 20)):
            self.assertFalse(diag.probe_ffmpeg('ffmpeg')['available'])

    def test_no_ndi_source_is_not_install_failure(self):
        runtime = MagicMock()
        runtime.status.return_value = {'available': True, 'version': 'TEST-NOT-REAL', 'error': ''}
        runtime.path = '/fake/ndi'
        runtime.sources.return_value = []
        with patch.object(diag, 'Runtime', return_value=runtime), patch.object(diag.time, 'sleep'):
            report = diag.probe_ndi(Path('.'), seconds=.001)
        self.assertTrue(report['available'])
        self.assertEqual(report['discovery'], 'OK')
        self.assertEqual(report['sources'], [])
        runtime.close.assert_called_once()

    @unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg not installed in the test environment')
    def test_real_one_second_conversion(self):
        report = diag.probe_ffmpeg(shutil.which('ffmpeg'), smoke=True)
        self.assertTrue(report['available'], report['error'])
        self.assertEqual(report['smoke_test'], 'OK')


class FileSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def archive(self, names):
        path = self.root / 'test.zip'
        with zipfile.ZipFile(path, 'w') as z:
            for name, content in names:
                z.writestr(name, content)
        return path

    def test_hash_parsing(self):
        value = 'ab' * 32
        self.assertEqual(setup.parse_sha256(value + '  file.zip\n'), value)
        for text in ['too-short', value + ' ' + value, 'abc' * 30]:
            with self.assertRaises(setup.SetupError):
                setup.parse_sha256(text)

    def test_safe_extract_valid(self):
        path = self.archive([('ffmpeg-x/bin/ffmpeg.exe', b'PE-TEST-ONLY'), ('ffmpeg-x/LICENSE', b'test licence')])
        setup.safe_extract(path, self.root / 'out')
        self.assertEqual((self.root / 'out/ffmpeg-x/LICENSE').read_bytes(), b'test licence')

    def test_zip_traversal(self):
        for name in ['../escape.exe', '/absolute.exe', 'C:/evil.exe', 'dir/../../bad', 'dir\\..\\bad', 'dir./bad']:
            with self.subTest(name=name):
                path = self.archive([(name, b'x')])
                with self.assertRaises(setup.SetupError):
                    setup.safe_extract(path, self.root / 'out')
        self.assertFalse((self.root.parent / 'escape.exe').exists())

    def test_duplicate_case_insensitive_paths(self):
        path = self.archive([('bin/ffmpeg.exe', b'x'), ('BIN/FFMPEG.EXE', b'y')])
        with self.assertRaises(setup.SetupError):
            setup.safe_extract(path, self.root / 'out')

    def test_symlink_rejected(self):
        info = zipfile.ZipInfo('a-link')
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        path = self.archive([(info, '../outside')])
        with self.assertRaises(setup.SetupError):
            setup.safe_extract(path, self.root / 'out')

    def test_size_limit(self):
        path = self.archive([('normal', b'12345')])
        with patch.object(setup, 'MAX_UNPACKED', 4), self.assertRaises(setup.SetupError):
            setup.safe_extract(path, self.root / 'out')

    def test_non_https_rejected(self):
        with self.assertRaises(setup.SetupError):
            setup.download('http://example.com/x', self.root / 'x')

    def test_http_redirect_rejected(self):
        redirect = setup.HTTPSOnlyRedirect()
        with self.assertRaises(setup.SetupError):
            redirect.redirect_request(None, None, 302, '', {}, 'http://example.com')

    def test_cache_reuse_no_network(self):
        cache = self.root / 'cache'
        cache.mkdir()
        archive = cache / 'ffmpeg-release-essentials.zip'
        archive.write_bytes(b'fixture')
        (cache / 'ffmpeg-release-essentials.zip.sha256').write_text(hashlib.sha256(b'fixture').hexdigest())
        with patch.object(setup, 'download', side_effect=AssertionError('network forbidden')):
            self.assertEqual(setup.verified_ffmpeg_archive(cache), archive)

    def test_hash_mismatch_stops_installation(self):
        def fake_download(url, destination, **kw):
            destination.write_bytes(b'wrong archive') if url.endswith('.zip') else destination.write_text('0' * 64)
        with patch.object(setup, 'download', side_effect=fake_download), self.assertRaises(setup.SetupError):
            setup.verified_ffmpeg_archive(self.root / 'cache')

    def test_settings_are_portable_and_preserve_data(self):
        exe = self.root / 'bin/ffmpeg/bin/ffmpeg.exe'
        exe.parent.mkdir(parents=True)
        exe.write_bytes(b'fixture')
        data = self.root / 'data'
        data.mkdir()
        (data / 'database.sqlite').write_bytes(b'leave me alone')
        setup.save_settings(self.root, ffmpeg=str(exe))
        value = setup.read_settings(self.root)
        self.assertEqual(value['ffmpeg'], str(Path('bin/ffmpeg/bin/ffmpeg.exe')))
        with patch.dict(os.environ, {}, clear=True):
            setup.apply_settings(self.root)
            self.assertEqual(os.environ['CARISMA_FFMPEG'], str(exe))
        self.assertEqual((data / 'database.sqlite').read_bytes(), b'leave me alone')

    def test_install_staged_and_preserves_previous_build(self):
        target = self.root / 'bin/ffmpeg'
        target.mkdir(parents=True)
        (target / 'old-license').write_text('old')
        archive = self.archive([('ffmpeg-x/bin/ffmpeg.exe', b'new'), ('ffmpeg-x/LICENSE', b'new licence')])
        with patch.object(setup, 'verified_ffmpeg_archive', return_value=archive), \
             patch.object(setup, 'probe_ffmpeg', return_value={'available': True}):
            result = setup.install_ffmpeg(self.root)
        self.assertEqual(Path(result).read_bytes(), b'new')
        self.assertEqual((target / 'LICENSE').read_bytes(), b'new licence')
        self.assertEqual(len(list((self.root / 'bin').glob('ffmpeg.backup-*'))), 1)

    def test_failed_new_build_leaves_existing_untouched(self):
        target = self.root / 'bin/ffmpeg'
        target.mkdir(parents=True)
        (target / 'do-not-remove').write_bytes(b'old')
        archive = self.archive([('ffmpeg-x/bin/ffmpeg.exe', b'new')])
        with patch.object(setup, 'verified_ffmpeg_archive', return_value=archive), \
             patch.object(setup, 'probe_ffmpeg', return_value={'available': False, 'error': 'unsupported CPU'}), \
             self.assertRaises(setup.SetupError):
            setup.install_ffmpeg(self.root)
        self.assertEqual((target / 'do-not-remove').read_bytes(), b'old')


class RepairLogicTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.ff = {'available': True, 'path': '/fake/ffmpeg'}
        self.ndi = {'available': True, 'version': 'fake-only', 'path': '/fake/ndi', 'error': ''}

    def exercise(self, ff_available):
        with patch.object(setup, 'find_working_ffmpeg', return_value=self.ff if ff_available else {'available': False}), \
             patch.object(setup, 'probe_ndi', return_value=self.ndi), \
             patch.object(setup, 'probe_ffmpeg', return_value=self.ff), \
             patch.object(setup, 'install_ffmpeg', return_value='/fake/ffmpeg') as ff_install, \
             patch.object(setup, 'install_ndi') as ndi_install, \
             patch.object(setup, 'check', return_value={'dependencies_ok': True}), \
             patch.object(setup, 'print_report'), patch.object(setup, 'say'):
            setup.repair(self.root)
            self.assertEqual(ff_install.call_count, 0 if ff_available else 1)
            ndi_install.assert_not_called()

    def test_all_present_never_installs(self):
        self.exercise(True)

    def test_user_case_installs_only_ffmpeg(self):
        self.exercise(False)

    def test_absent_ndi_installs_then_rechecks(self):
        with patch.object(setup, 'find_working_ffmpeg', return_value=self.ff), \
             patch.object(setup, 'probe_ndi', side_effect=[{'available': False, 'error': 'missing'}, self.ndi]), \
             patch.object(setup, 'install_ndi') as install, \
             patch.object(setup, 'check', return_value={'dependencies_ok': True}), \
             patch.object(setup, 'print_report'), patch.object(setup, 'say'):
            setup.repair(self.root)
            install.assert_called_once_with(self.root)

    def test_final_failure_not_reported_success(self):
        with patch.object(setup, 'find_working_ffmpeg', return_value=self.ff), \
             patch.object(setup, 'probe_ndi', return_value=self.ndi), \
             patch.object(setup, 'check', return_value={'dependencies_ok': False}), \
             patch.object(setup, 'print_report'), patch.object(setup, 'say'), \
             self.assertRaises(setup.SetupError):
            setup.repair(self.root)


if __name__ == '__main__':
    unittest.main()
