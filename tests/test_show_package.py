"""Portable show integrity, transactional activation and local identity boundaries."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
import zipfile

from ndi.gateway import GatewayError
from physical_players import init_players
from prompt_module import PromptStore
from server import valid_state
from show_package import ShowPackages, encoded
from storage import database

ROOT = Path(__file__).resolve().parents[1]


class ShowPackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'assets').mkdir()
        self.state = json.loads((ROOT / 'example_project.json').read_text(encoding='utf-8'))
        self.media = b'synthetic media bytes for archive integrity'
        self.ident = hashlib.sha256(self.media).hexdigest()
        (self.root / 'assets' / self.ident).write_bytes(self.media)
        self.state['assets'].append({'id': 'local-image', 'kind': 'image', 'title': 'Local image',
                                     'fileId': self.ident, 'sha256': self.ident,
                                     'size': len(self.media), 'mime': 'image/png'})
        with database(self.root / 'controller.sqlite3') as conn:
            conn.execute('CREATE TABLE state(id INTEGER PRIMARY KEY,version INTEGER,payload TEXT)')
            conn.execute('INSERT INTO state VALUES(1,1,?)', (json.dumps(self.state),))
            conn.execute('CREATE TABLE asset_files(id TEXT PRIMARY KEY,mime TEXT,name TEXT,size INTEGER)')
            conn.execute('INSERT INTO asset_files VALUES(?,?,?,?)', (self.ident, 'image/png', 'demo.png', len(self.media)))
        init_players(self.root)
        prompt = PromptStore(self.root)
        prompt.save_project('Rehearsal', '[[CUE: START]]\nFirst line\n[[CUE: END]]\nLast line',
                            {'font': 'classic', 'size': 'large', 'theme': 'white', 'readingLine': True})
        self.server = SimpleNamespace(data_dir=self.root, prompt=prompt)
        self.packages = ShowPackages(self.server, valid_state, threading.RLock())

    def tearDown(self):
        self.tmp.cleanup()

    def archive(self):
        with self.packages.export() as (stream, size, manifest):
            raw = stream.read()
        self.assertEqual(size, len(raw))
        return raw

    def rewrite(self, raw, changes):
        with zipfile.ZipFile(io.BytesIO(raw)) as source:
            files = {name: source.read(name) for name in source.namelist()}
        changes(files)
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as archive:
            for name, data in files.items():
                archive.writestr(name, data)
        return output.getvalue()

    def stage(self, raw):
        return self.packages.stage(io.BytesIO(raw))

    def activate(self, preview):
        with database(self.root / 'controller.sqlite3') as conn:
            revision = conn.execute('SELECT version FROM state').fetchone()[0]
        return self.packages.activate(preview['ticket'], revision, self.server.prompt.project()['version'])

    def test_round_trip_preserves_content_and_local_pairing_stops_runtime(self):
        code = self.server.prompt.issue_controller_code('Local controller')['code']
        controller = self.server.prompt.pair_controller(code, 'Local controller')
        raw = self.archive()
        preview = self.stage(raw)
        self.assertEqual(preview['mediaFiles'], 1)
        self.assertEqual(preview['cues'], 2)
        self.server.prompt.command('play')
        result = self.activate(preview)
        self.assertEqual(result['active']['id'], preview['id'])
        self.assertFalse(self.server.prompt.runtime()['playing'])
        self.assertEqual(self.server.prompt.project()['title'], 'Rehearsal')
        self.assertEqual(self.server.prompt.controller_for_token(controller['token'])['name'], 'Local controller')
        self.assertEqual((self.root / 'assets' / self.ident).read_bytes(), self.media)
        self.assertTrue(result['rollbackAvailable'])
        with self.assertRaises(GatewayError):
            self.activate(preview)

    def test_export_omits_machine_secrets_pairing_and_history(self):
        (self.root / 'access.key').write_text('private-administrator-key')
        self.state['site']['password'] = 'private-password'
        with database(self.root / 'controller.sqlite3') as conn:
            conn.execute('UPDATE state SET payload=?', (json.dumps(self.state),))
        raw = self.archive()
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            self.assertEqual(set(archive.namelist()), {'manifest.json', 'project.json', 'prompt.json', 'media/' + self.ident})
            state = json.loads(archive.read('project.json'))
            self.assertEqual(state['events'], [])
            self.assertNotIn('password', state['site'])
        self.assertNotIn(b'private-administrator-key', raw)
        self.assertNotIn(b'private-password', raw)

    def test_missing_or_corrupt_media_blocks_export(self):
        path = self.root / 'assets' / self.ident
        path.write_bytes(b'corrupt')
        with self.assertRaises(GatewayError):
            self.archive()
        path.unlink()
        with self.assertRaises(GatewayError):
            self.archive()

    def test_hash_mismatch_blocks_import_without_changing_project(self):
        raw = self.rewrite(self.archive(), lambda files: files.update({'media/' + self.ident: b'x' * len(self.media)}))
        with self.assertRaises(GatewayError):
            self.stage(raw)
        self.assertEqual(self.server.prompt.project()['title'], 'Rehearsal')
        self.assertFalse(any(self.packages.staging.iterdir()))

    def test_traversal_and_extra_credentials_file_rejected(self):
        for name in ('../outside', 'access.key', 'media/../outside', '/project.json', 'C:/project.json'):
            with self.subTest(name=name):
                raw = self.rewrite(self.archive(), lambda files: files.update({name: b'bad'}))
                with self.assertRaises(GatewayError):
                    self.stage(raw)

    def test_revision_conflict_retains_preview_and_project(self):
        preview = self.stage(self.archive())
        with self.assertRaises(GatewayError) as error:
            self.packages.activate(preview['ticket'], 999, self.server.prompt.project()['version'])
        self.assertEqual(error.exception.status, 409)
        self.assertIn(preview['ticket'], self.packages.pending)
        self.assertEqual(self.server.prompt.project()['title'], 'Rehearsal')

    def test_prompt_revision_conflict_rejected(self):
        preview = self.stage(self.archive())
        with self.assertRaises(GatewayError):
            self.packages.activate(preview['ticket'], 1, 999)

    def test_rollback_archive_restores_previous_show(self):
        preview = self.stage(self.archive())
        self.server.prompt.save_project('Changed show', 'A different script', {})
        self.activate(preview)
        self.assertEqual(self.server.prompt.project()['title'], 'Rehearsal')
        with (self.root / 'show-previous.show.zip').open('rb') as source:
            restore = self.packages.stage(source)
        self.activate(restore)
        self.assertEqual(self.server.prompt.project()['title'], 'Changed show')

    def test_expired_preview_is_deleted(self):
        preview = self.stage(self.archive())
        self.packages.pending[preview['ticket']][4]['expires'] = 0
        with self.assertRaises(GatewayError) as error:
            self.activate(preview)
        self.assertEqual(error.exception.status, 410)
        self.assertFalse(any(self.packages.staging.iterdir()))

    def test_unknown_format_and_missing_media_rejected(self):
        def alter(files):
            manifest = json.loads(files['manifest.json'])
            manifest['version'] = 999
            files['manifest.json'] = encoded(manifest)
        with self.assertRaises(GatewayError):
            self.stage(self.rewrite(self.archive(), alter))
        with self.assertRaises(GatewayError):
            self.stage(self.rewrite(self.archive(), lambda files: files.pop('media/' + self.ident)))

    def test_invalid_references_block_export(self):
        self.state['screens'][0]['base'] = {'type': 'asset', 'id': 'missing'}
        with database(self.root / 'controller.sqlite3') as conn:
            conn.execute('UPDATE state SET payload=?', (json.dumps(self.state),))
        with self.assertRaises(GatewayError):
            self.archive()

    def test_authenticated_live_urls_not_exported(self):
        self.state['assets'][-1].update(kind='live', url='https://example.test/video?token=private')
        with database(self.root / 'controller.sqlite3') as conn:
            conn.execute('UPDATE state SET payload=?', (json.dumps(self.state),))
        with self.assertRaises(GatewayError):
            self.archive()

    def test_restart_discards_staged_uploads(self):
        self.stage(self.archive())
        other = ShowPackages(self.server, valid_state, threading.RLock())
        self.assertFalse(other.pending)
        self.assertFalse(any(other.staging.iterdir()))

    def test_controller_history_stays_bounded_for_checkpoint_size(self):
        code = self.server.prompt.issue_controller_code('Bounded history')['code']
        identity = self.server.prompt.pair_controller(code, 'Bounded history')
        controller = self.server.prompt.controller_for_token(identity['token'])
        with database(self.root / 'controller.sqlite3') as conn:
            conn.executemany('INSERT INTO prompt_controller_requests VALUES(?,?,?,?,?)',
                             [(controller['id'], f'{i:032x}', 'old', '{}', time.time()) for i in range(16385)])
        self.server.prompt.controller_command(controller, {'command': 'pause', 'requestId': 'f' * 32})
        with database(self.root / 'controller.sqlite3') as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM prompt_controller_requests').fetchone()[0], 16384)
            conn.executemany('INSERT INTO prompt_controller_requests VALUES(?,?,?,?,?)',
                             [(controller['id'], f'{i:032x}', 'legacy', '{}', time.time()) for i in range(20000, 20010)])
        PromptStore(self.root)
        with database(self.root / 'controller.sqlite3') as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM prompt_controller_requests').fetchone()[0], 16384)


if __name__ == '__main__':
    unittest.main()
