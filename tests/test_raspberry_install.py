"""Installer boundaries and persisted configuration using disposable homes only."""
import importlib.util
import json
from pathlib import Path, PurePosixPath
import tempfile
import types
import unittest
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('rpi_install', ROOT / 'raspberry/install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)
spec = importlib.util.spec_from_file_location('rpi_kiosk', ROOT / 'raspberry/kiosk.py')
kiosk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kiosk)


class RaspberryInstallerTests(unittest.TestCase):
    def test_screen_blanking_uses_official_tool_and_preserves_user_backup(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(installer.shutil, 'which', return_value='/usr/bin/raspi-config'), \
             patch.object(installer.subprocess, 'run', return_value=types.SimpleNamespace(stdout='1\n')) as command:
            home = Path(directory)
            original = home / '.config/labwc/autostart'
            original.parent.mkdir(parents=True)
            original.write_text('existing startup\nswayidle example &\n')
            installer.disable_screen_blanking(home)
            self.assertEqual(command.call_args_list[0].args[0], ['sudo', '/usr/bin/raspi-config', 'nonint', 'do_blanking', '1'])
            self.assertEqual(command.call_args_list[1].args[0], ['sudo', '/usr/bin/raspi-config', 'nonint', 'get_blanking'])
            backups = list((home / '.local/state/displaycontrol-screen-backups').glob('*/labwc-autostart'))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(), original.read_text())

    def test_screen_blanking_failure_is_reported(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(installer.shutil, 'which', return_value='/usr/bin/raspi-config'), \
             patch.object(installer.subprocess, 'run', return_value=types.SimpleNamespace(stdout='0\n')):
            with self.assertRaisesRegex(ValueError, 'did not confirm'):
                installer.disable_screen_blanking(Path(directory))

    def test_missing_os_tool_does_not_write_or_claim_success(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(installer.shutil, 'which', return_value=None), \
             patch.object(installer.subprocess, 'run') as command:
            home = Path(directory)
            with self.assertRaisesRegex(ValueError, 'raspi-config missing'):
                installer.disable_screen_blanking(home)
            self.assertEqual(list(home.iterdir()), [])
            command.assert_not_called()

    def test_bad_origins_rejected_before_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            for value in ('http://user:pass@host', 'http://host/api', 'http://host?q=x', 'http://host\n', 'file:///etc/passwd', 'http://host:wrong'):
                with self.assertRaises(ValueError):
                    installer.install(home, ROOT, value, 'prompt', 8877, '/usr/bin/chromium')
            self.assertEqual(list(home.iterdir()), [])

    def test_install_preserves_pairing_and_cache_on_update(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(installer.subprocess, 'run') as command:
            home = Path(directory)
            result = installer.install(home, ROOT, 'http://regia:8787', 'prompt', 8877, '/usr/bin/chromium')
            base = Path(result['directory'])
            config = base / 'data/station.json'
            data = json.loads(config.read_text())
            data['token'] = 'synthetic-test-token'
            config.write_text(json.dumps(data))
            cache = base / 'data/browser/Default/cache-test'
            cache.parent.mkdir(parents=True)
            cache.write_bytes(b'synthetic-cache')
            labwc = home / '.config/labwc/autostart'
            labwc.write_text('existing-desktop-command &\n' + labwc.read_text())
            installer.install(home, ROOT, 'http://regia:8787', 'prompt', 8877, '/usr/bin/chromium')
            self.assertEqual(json.loads(config.read_text())['token'], 'synthetic-test-token')
            self.assertEqual(cache.read_bytes(), b'synthetic-cache')
            self.assertEqual(labwc.read_text().count(installer.BEGIN), 1)
            self.assertIn('existing-desktop-command &', labwc.read_text())
            self.assertTrue(list((base / 'backups').iterdir()))
            self.assertIn('enable', str(command.call_args_list[-1]))
            runtime = Path(json.loads((base / 'installation.json').read_text())['release'])
            for name in installer.FILES:
                self.assertEqual((runtime / name).read_bytes(), (ROOT / name).read_bytes())

    def test_dry_run_does_not_create_files_or_run_commands(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(installer.subprocess, 'run') as command:
            home = Path(directory)
            installer.install(home, ROOT, 'http://regia:8787', 'signage', 8877, '/usr/bin/chromium', False)
            self.assertEqual(list(home.iterdir()), [])
            command.assert_not_called()

    def test_reconfiguration_cannot_silently_reuse_pairing_or_change_origin(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(installer.subprocess, 'run'):
            home = Path(directory)
            installer.install(home, ROOT, 'http://regia:8787', 'prompt', 8877, '/usr/bin/chromium')
            for server, mode, port in [('http://other:8787', 'prompt', 8877), ('http://regia:8787', 'signage', 8877), ('http://regia:8787', 'prompt', 8888)]:
                with self.assertRaises(ValueError):
                    installer.install(home, ROOT, server, mode, port, '/usr/bin/chromium')

    def test_unmanaged_startup_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            unit = home / '.config/systemd/user/displaycontrol-station.service'
            unit.parent.mkdir(parents=True)
            unit.write_text('unrelated service')
            with self.assertRaises(ValueError):
                installer.install(home, ROOT, 'http://regia', 'prompt', 8877, '/bin/true')
            self.assertEqual(unit.read_text(), 'unrelated service')

    def test_malformed_autostart_block_is_rejected(self):
        with self.assertRaises(ValueError):
            installer.managed_block(installer.BEGIN, 'command')

    def test_browser_profile_and_security_flags(self):
        args = kiosk.browser_args('/usr/bin/chromium', PurePosixPath('/home/kiosk/my data'), 'http://127.0.0.1:8877/')
        self.assertIn('--user-data-dir=/home/kiosk/my data/browser', args)
        self.assertIn('--kiosk', args)
        self.assertNotIn('--no-sandbox', args)
        self.assertNotIn('--disable-web-security', args)

    def test_generated_commands_quote_spaces_and_percent(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(installer.subprocess, 'run'):
            home = Path(directory) / 'home space%'
            home.mkdir()
            result = installer.install(home, ROOT, 'http://regia', 'prompt', 8877, '/usr/bin/chromium')
            launcher = (Path(result['directory']) / 'launch-kiosk.sh').read_text()
            self.assertIn("'", launcher)
            self.assertIn('%%', (home / '.config/systemd/user/displaycontrol-station.service').read_text())

    def test_browser_crash_restarts_and_shutdown_terminates_owned_process_group(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'data'
            fake_lock = types.SimpleNamespace(flock=Mock(), LOCK_EX=1, LOCK_NB=2)
            callbacks = {}
            first, second = Mock(pid=101), Mock(pid=102)
            first.poll.return_value = 1
            second.poll.return_value = None
            sleeps = []
            def tick(seconds):
                sleeps.append(seconds)
                if len(sleeps) >= 3:
                    callbacks[kiosk.signal.SIGTERM]()
            with patch.dict('sys.modules', {'fcntl': fake_lock}), patch.dict(kiosk.os.environ, {'DISPLAY': ':0'}), \
                 patch.object(kiosk.signal, 'signal', side_effect=lambda sig, fn: callbacks.update({sig: fn})), \
                 patch.object(kiosk, 'ready', return_value=True), patch.object(kiosk.time, 'sleep', side_effect=tick), \
                 patch.object(kiosk.subprocess, 'Popen', side_effect=[first, second]) as start, \
                 patch.object(kiosk.os, 'killpg', create=True) as kill:
                self.assertEqual(kiosk.run(state, '/usr/bin/chromium', 'http://127.0.0.1:8877/'), 0)
                self.assertEqual(start.call_count, 2)
                kill.assert_called_once_with(102, kiosk.signal.SIGTERM)
                self.assertTrue(start.call_args.kwargs['start_new_session'])
                self.assertFalse((state / 'kiosk-status.json').exists())

    def test_corrupt_manifest_blocks_installation(self):
        with tempfile.TemporaryDirectory() as directory:
            source, home = Path(directory) / 'source', Path(directory) / 'home'
            source.mkdir()
            home.mkdir()
            for name in installer.FILES:
                target = source / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / name).read_bytes())
            (source / 'raspberry/SHA256.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                installer.install(home, source, 'http://regia', 'prompt', 8877, '/bin/true')
            self.assertEqual(list(home.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
