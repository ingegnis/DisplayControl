"""Lease fencing and real three-process Core failover, without physical hardware."""
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from coordinator import Authority, LEASE_SECONDS, OscRelay
from ndi.gateway import GatewayError
from storage import database, transaction_hooks

ROOT = Path(__file__).resolve().parents[1]
KEY = 'synthetic-cluster-test-key-not-a-deployed-secret'


class AuthorityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'authority.json'
        self.config = {'key': KEY, 'nodes': {'a': 'http://127.0.0.1:1', 'b': 'http://127.0.0.1:2'}, 'initialPrimary': 'a'}
        self.authority = Authority(self.config, self.path)

    def tearDown(self):
        self.temp.cleanup()

    def lease(self, node, checkpoint=0, ready=False, boot='one'):
        return self.authority.lease({'node': node, 'checkpoint': checkpoint, 'ready': ready, 'boot': boot})

    def test_only_initial_core_can_bootstrap(self):
        self.assertFalse(self.authority.status()['nodes']['b']['reachable'])
        self.assertIsNone(self.lease('b')['active'])
        self.assertEqual(self.lease('a')['active'], 'a')
        self.assertEqual(self.lease('b')['ttl'], 0)

    def test_live_lease_cannot_be_preempted(self):
        self.lease('a')
        self.assertEqual(self.lease('b', 100, True)['active'], 'a')

    def test_stale_replica_never_promoted(self):
        self.lease('a')
        self.authority.committed = 4
        self.authority.deadline = 0
        self.authority.nodes['a']['seen'] = 0
        self.assertEqual(self.lease('b', 3, True)['ttl'], 0)
        self.assertEqual(self.lease('b', 4, True)['active'], 'b')

    def test_restart_waits_out_preexisting_grants(self):
        self.lease('a')
        other = Authority(self.config, self.path)
        self.assertGreater(other.recover_until, time.monotonic())
        self.assertEqual(other.lease({'node': 'a', 'checkpoint': 0, 'ready': True})['ttl'], 0)

    def test_new_process_cannot_inherit_unexpired_grant(self):
        self.lease('a', boot='first-process')
        self.assertEqual(self.lease('a', boot='new-process')['ttl'], 0)

    def test_missing_coordinator_history_cannot_bootstrap_existing_cores(self):
        with self.assertRaises(ValueError):
            self.lease('a', 25, True)
        self.assertTrue(self.authority.status()['needsRecovery'])
        self.assertIsNone(self.authority.route())

    def test_osc_relay_enforces_namespace_sender_and_active_lease(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as destination, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            destination.bind(('127.0.0.1', 0))
            destination.settimeout(.3)
            self.authority.config['oscPorts'] = {'a': destination.getsockname()[1]}
            self.lease('a')
            relay = OscRelay(self.authority, '127.0.0.1', 0, ['127.0.0.1'])
            relay.thread.start()
            def osc_string(value):
                raw = value.encode() + b'\0'
                return raw + b'\0' * (-len(raw) % 4)
            target = relay.socket.getsockname()
            message = osc_string('/carisma/prompt/message') + osc_string(',s') + osc_string('synthetic relay test')
            try:
                sender.sendto(message, target)
                self.assertEqual(destination.recvfrom(16384)[0], message)
                for raw in (osc_string('/other') + osc_string(','),):
                    sender.sendto(raw, target)
                    with self.assertRaises(socket.timeout):
                        destination.recvfrom(16384)
                relay.allow = {'192.0.2.1'}
                sender.sendto(message, target)
                with self.assertRaises(socket.timeout):
                    destination.recvfrom(16384)
                relay.allow = {'127.0.0.1'}
                self.authority.deadline = 0
                sender.sendto(message, target)
                with self.assertRaises(socket.timeout):
                    destination.recvfrom(16384)
            finally:
                relay.close()


class CommitFenceTests(unittest.TestCase):
    def test_expired_lease_rolls_back_before_commit(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'test.sqlite3'
            with database(path) as conn:
                conn.execute('CREATE TABLE writes(value TEXT)')
            def expired():
                raise GatewayError('Expired synthetic lease.', 503)
            transaction_hooks(path, expired, lambda: self.fail('Uncommitted write was replicated.'))
            with self.assertRaises(GatewayError):
                with database(path) as conn:
                    conn.execute("INSERT INTO writes VALUES('must roll back')")
            with database(path) as conn:
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM writes').fetchone()[0], 0)


class ClusterProcessTests(unittest.TestCase):
    def test_replication_failover_recovery_and_witness_loss(self):
        with tempfile.TemporaryDirectory(prefix='displaycontrol-cluster-test-') as temporary:
            folder = Path(temporary)
            holders = [socket.socket() for _ in range(3)]
            for holder in holders:
                holder.bind(('127.0.0.1', 0))
            ports = [holder.getsockname()[1] for holder in holders]
            for holder in holders:
                holder.close()
            nodes = {'a': f'http://127.0.0.1:{ports[0]}', 'b': f'http://127.0.0.1:{ports[1]}'}
            origin = f'http://127.0.0.1:{ports[2]}'
            processes = {}
            common = {'key': KEY, 'nodes': nodes, 'coordinator': origin, 'initialPrimary': 'a'}
            for node in ('a', 'b', 'coordinator'):
                (folder / (node + '.json')).write_text(json.dumps(dict(common, node=node)))

            def start(node):
                if node == 'coordinator':
                    command = [sys.executable, str(ROOT / 'coordinator.py'), '--config', str(folder / 'coordinator.json'),
                               '--data-dir', str(folder / 'coordinator'), '--port', str(ports[2])]
                else:
                    command = [sys.executable, str(ROOT / 'server.py'), '--cluster-config', str(folder / (node + '.json')),
                               '--data-dir', str(folder / node), '--port', str(ports[0 if node == 'a' else 1]), '--prompt-osc-port', '0']
                processes[node] = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            def request(path, body=None, token=None, base=origin, private=False, method=None, extra=None):
                headers = dict(extra or {})
                if private:
                    headers['X-Cluster-Key'] = KEY
                if token:
                    headers['X-Control-Token'] = token
                if isinstance(body, dict):
                    body = json.dumps(body).encode()
                    headers['Content-Type'] = 'application/json'
                req = urllib.request.Request(base + path, data=body, headers=headers, method=method)
                try:
                    with urllib.request.urlopen(req, timeout=8) as response:
                        raw = response.read()
                        return response.status, json.loads(raw) if 'application/json' in response.headers.get('Content-Type', '') else raw
                except urllib.error.HTTPError as exc:
                    raw = exc.read()
                    exc.close()
                    return exc.code, json.loads(raw)

            def wait(check, timeout=18):
                deadline = time.monotonic() + timeout
                last = None
                while time.monotonic() < deadline:
                    try:
                        last = check()
                        if last:
                            return last
                    except (OSError, ValueError, KeyError):
                        pass
                    time.sleep(.1)
                self.fail('Cluster condition timed out; process exits: ' + str({key: value.poll() for key, value in processes.items()}))

            try:
                for node in ('coordinator', 'a', 'b'):
                    start(node)
                wait(lambda: request('/cluster/status', private=True)[1].get('active') == 'a')
                admin = (folder / 'a/access.key').read_text().strip()
                state = json.loads((ROOT / 'example_project.json').read_text(encoding='utf-8'))
                self.assertEqual(request('/api/state', {'revision': 0, 'state': state}, admin, method='PUT')[0], 200)
                self.assertEqual(request('/api/state', {'revision': 1, 'state': state}, admin, base=nodes['b'], method='PUT')[0], 503)
                code = request('/api/prompt/controller/pair-code', {'name': 'Synthetic USB service'}, admin)[1]['code']
                token = request('/api/prompt/controller/pair', {'code': code, 'name': 'Synthetic USB service'})[1]['token']
                headers = {'X-Prompt-Controller-Token': token}
                command = {'command': 'jog', 'value': .25, 'requestId': 'e' * 32}
                before = request('/api/prompt/controller/command', command, extra=headers)
                self.assertEqual(before[0], 200)
                committed = request('/cluster/status', private=True)[1]['committed']
                wait(lambda: request('/api/cluster/health', base=nodes['b'], private=True)[1].get('checkpoint', 0) >= committed)
                self.assertEqual((folder / 'b/access.key').read_text().strip(), admin)

                processes['a'].terminate()
                processes['a'].wait(timeout=5)
                self.assertEqual(request('/')[0], 200)
                wait(lambda: request('/cluster/status', private=True)[1].get('active') == 'b')
                self.assertEqual(request('/api/state', token=admin)[1]['state']['site']['name'], state['site']['name'])
                replay = request('/api/prompt/controller/command', command, extra=headers)
                self.assertEqual(replay, before)
                self.assertEqual(request('/api/prompt/command', {'command': 'message', 'value': 'After failover'}, admin)[0], 200)

                start('a')
                committed = request('/cluster/status', private=True)[1]['committed']
                wait(lambda: request('/api/cluster/health', base=nodes['a'], private=True)[1].get('checkpoint', 0) >= committed)
                self.assertEqual(request('/cluster/status', private=True)[1]['active'], 'b')
                self.assertEqual(request('/api/prompt/state', token=admin, base=nodes['a'])[1]['runtime']['message'], 'After failover')

                processes['coordinator'].terminate()
                processes['coordinator'].wait(timeout=5)
                time.sleep(LEASE_SECONDS + .5)
                self.assertEqual(request('/api/prompt/command', {'command': 'play'}, admin, base=nodes['b'])[0], 503)
                start('coordinator')
                wait(lambda: request('/cluster/status', private=True)[1].get('active') == 'b', timeout=20)
                self.assertEqual(request('/api/prompt/state', token=admin)[1]['runtime']['message'], 'After failover')
            finally:
                for proc in processes.values():
                    if proc.poll() is None:
                        proc.terminate()
                for proc in processes.values():
                    proc.wait(timeout=8)


if __name__ == '__main__':
    unittest.main()
