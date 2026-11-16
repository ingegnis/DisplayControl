import json
import socket
import tempfile
import time
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch
from akp03e_controller import CarismaApi, ControllerService, HidDevice, save_config, load_config
from test_akp03e_controller import FakeApi, FakeDevice
from prompt_module import PromptStore, PromptOscServer


class DeliveryTests(unittest.TestCase):
    def api(self):
        return CarismaApi({'servers':['http://a','http://b'],'token':'x'*32,'serverTokens':{'http://b':'b'*32},'oscTargets':['127.0.0.1:9000']})

    def test_timeout_does_not_replay_relative_command(self):
        api=self.api()
        with patch.object(api,'_request',side_effect=TimeoutError),patch.object(api,'_osc_fallback') as osc:
            with self.assertRaisesRegex(RuntimeError,'incerto'):api.command('toggle')
            osc.assert_not_called()

    def test_absolute_command_can_failover_with_dedicated_token(self):
        api=self.api()
        with patch.object(api,'_request',side_effect=[TimeoutError(),{'playing':False}]) as req:
            self.assertEqual(api.command('stop')[1],'HTTP')
            self.assertEqual(req.call_args.kwargs['token'],'b'*32)
            self.assertEqual(req.call_args_list[0].args[2]['requestId'],req.call_args_list[1].args[2]['requestId'])

    def test_revocation_does_not_bypass_auth_through_osc(self):
        for code in (400,401,403,409,500):
            api=self.api()
            with patch.object(api,'_request',side_effect=urllib.error.HTTPError('http://a',code,'rejected',{},None)),patch.object(api,'_osc_fallback') as osc:
                with self.assertRaisesRegex(RuntimeError,'rifiuta'):api.command('pause')
                osc.assert_not_called()

    def test_connection_refused_allows_real_udp_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            store=PromptStore(Path(d));listener=PromptOscServer(store,bind='127.0.0.1',port=0)
            # Reserve a real OSC port; zero disables production OSC.
            with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as reserve:
                reserve.bind(('127.0.0.1',0));port=reserve.getsockname()[1]
            listener.port=port;listener.start()
            try:
                api=self.api();api.config['oscTargets']=['127.0.0.1:'+str(port)]
                with patch.object(api,'_request',side_effect=urllib.error.URLError(ConnectionRefusedError())):
                    self.assertEqual(api.command('speed',.2)[1],'OSC-INVIATO-NON-CONFERMATO')
                deadline=time.monotonic()+2
                while time.monotonic()<deadline and not store.runtime()['playing']:time.sleep(.02)
                self.assertAlmostEqual(store.runtime()['rate'],.2,places=5)
            finally:listener.close()


class QueueAndUsbTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.cfg=self.root/'config.json';save_config(self.cfg,{'token':'x'*32})
        self.api=FakeApi();self.dev=FakeDevice();self.s=ControllerService(self.cfg,self.dev,self.api)
        self.s.connected=True
    def tearDown(self):self.tmp.cleanup()

    def test_expired_and_disconnected_events_never_replay(self):
        self.s.events.put((time.monotonic()-2,('turn',0,1)));self.s.process_event()
        self.s.enqueue(('turn',0,1));self.s.lose_usb('unplug');self.s.connected=True;self.s.process_event()
        self.assertEqual(self.api.commands,[]);self.assertEqual(self.s.dropped_events,2)

    def test_stop_overtakes_encoder_burst(self):
        for _ in range(40):self.s.enqueue(('turn',0,1))
        self.s.enqueue(('knob',1,1));self.s.process_event()
        self.assertEqual(self.api.commands,[('stop',None)]);self.assertTrue(self.s.events.empty())

    def test_communication_failure_discards_pending_events(self):
        self.s.enqueue(('button',0,0));self.s.enqueue(('turn',0,1))
        with patch.object(self.api,'command',side_effect=TimeoutError):self.s.process_event()
        self.assertTrue(self.s.events.empty())

    def test_partial_open_failure_closes_device(self):
        self.dev.open=lambda: {'product_string':'test'}
        with patch.object(self.dev,'set_key_jpeg',side_effect=OSError('USB gone')),patch.object(self.dev,'close') as close:
            self.assertFalse(self.s.connect_usb());close.assert_called_once();self.assertFalse(self.s.connected)

    def test_short_write_detected(self):
        dev=HidDevice();dev.dev=type('Device',(),{'write':lambda _,data:2})()
        with self.assertRaises(OSError):dev.write(b'123')

    def test_config_replacement_leaves_no_partial_file(self):
        save_config(self.cfg,{'token':'new'});self.assertEqual(load_config(self.cfg),{'token':'new'})
        self.assertEqual(list(self.root.glob('*.tmp')),[])


class DeduplicationTests(unittest.TestCase):
    def test_atomic_replay_survives_store_restart_and_rejects_conflict(self):
        with tempfile.TemporaryDirectory() as d:
            store=PromptStore(Path(d));ctl=store.pair_controller(store.issue_controller_code()['code'])
            body={'command':'toggle','requestId':'a'*32}
            first=store.controller_command(ctl,body);self.assertTrue(first['playing'])
            restarted=PromptStore(Path(d));second=restarted.controller_command(ctl,body)
            self.assertEqual(first,second);self.assertTrue(restarted.runtime()['playing'])
            from ndi.gateway import GatewayError
            with self.assertRaises(GatewayError):restarted.controller_command(ctl,dict(body,command='stop'))

    def test_non_finite_motion_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            store=PromptStore(Path(d));initial=store.runtime()['seq']
            for cmd in ['speed','speed_delta','jog']:
                for value in [float('nan'),float('inf'),-float('inf')]:
                    with self.assertRaises(Exception):store.command(cmd,value)
            self.assertEqual(store.runtime()['seq'],initial)
