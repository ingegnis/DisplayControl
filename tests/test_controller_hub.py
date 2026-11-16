"""Recorded-format synthetic HID frames, fake USB transport and real scoped HTTP.
No test in this module claims an attached physical controller.
"""
import json
from pathlib import Path
import struct
import tempfile
import time
import unittest
import importlib.util
from unittest.mock import patch
from controller_devices import PROFILES, identify, Decoder, Device, neo_image_reports, icon_bytes
from controller_service import ControllerHub, Session, singleton
from akp03e_controller import save_config

P = {p.key:p for p in PROFILES}
def akp(action, state=0):
    frame=bytearray(64);frame[:3]=b'ACK';frame[9]=action;frame[10]=state;return frame
def neo(*keys):return bytes([1,0,10,0])+bytes(int(i in keys) for i in range(10))
def contour(ring=0,jog=0,buttons=0):return struct.pack('<bBBH',ring,jog,0,buttons)


class ProtocolTests(unittest.TestCase):
    def test_only_exact_supported_ids_and_interfaces_are_claimed(self):
        for p in PROFILES:
            self.assertEqual(identify(dict(vendor_id=p.vid,product_id=p.pid,interface_number=0)),p)
        self.assertIsNone(identify(dict(vendor_id=0x046d,product_id=0xc31c)))
        self.assertIsNone(identify(dict(vendor_id=0x0b00,product_id=0x1001,interface_number=1)))
        self.assertIsNone(identify(dict(vendor_id=0x0300,product_id=0x3002,usage_page=1)))
        self.assertIsNone(identify(dict(vendor_id=0x0300,product_id=0x1001)))

    def test_msd_discrete_events_do_not_require_a_release_byte(self):
        decoder=Decoder(P['msd-two'])
        self.assertEqual(decoder.feed(akp(1,1)),[('toggle',None)])
        self.assertEqual(decoder.feed(akp(0x91)),[('speed_delta',.015)])
        self.assertEqual(decoder.feed(akp(0x35)),[('stop',None)])
        self.assertEqual(decoder.feed(akp(0x31)),[('take_toggle',None)])
        self.assertEqual(decoder.feed(akp(0)),[])
        self.assertEqual(decoder.feed(b'bad'),[])
        invalid=akp(1);invalid[:3]=b'CRT';self.assertEqual(decoder.feed(invalid),[])

    def test_ajazz_release_and_encoder_mapping_remain_compatible(self):
        d=Decoder(P['akp03e'])
        self.assertEqual(d.feed(akp(1,1)),[])
        self.assertEqual(d.feed(akp(1,0)),[('toggle',None)])
        self.assertEqual(d.feed(akp(0x50)),[('jog',-.08)])

    def test_neo_edges_held_keys_and_touch_keys(self):
        d=Decoder(P['neo']);self.assertEqual(d.feed(neo(0)),[])
        self.assertEqual(d.feed(neo()),[])
        self.assertEqual(d.feed(neo(0,7,9)),[('toggle',None),('speed_delta',.015),('jog',.08)])
        self.assertEqual(d.feed(neo(0,7,9)),[])
        self.assertEqual(d.feed(bytes(14)),[])
        self.assertEqual(d.feed(b'bad'),[])

    def test_contour_ring_signed_speed_center_stop_and_initial_arming(self):
        d=Decoder(P['shuttlexpress'])
        self.assertEqual(d.feed(contour(5)),[])
        self.assertEqual(d.feed(contour(6)),[])
        self.assertEqual(d.feed(contour()),[('stop',None)])
        self.assertEqual(d.feed(contour(-3)),[('speed',-.07)])
        self.assertEqual(d.feed(contour(7)),[('speed',.4)])
        self.assertEqual(d.feed(contour()),[('stop',None)])
        self.assertEqual(d.feed(contour(8)),[])

    def test_contour_jog_wrap_both_directions_and_all_button_edges(self):
        d=Decoder(P['shuttlexpress']);d.feed(contour(jog=255))
        self.assertEqual(d.feed(contour(jog=0,buttons=0x30)),[('jog',.08),('toggle',None),('cue_prev',None)])
        self.assertEqual(d.feed(contour(jog=255)),[('jog',-.08)])
        self.assertEqual(d.feed(contour(jog=100)),[])  # Counter discontinuity.
        d=Decoder(P['shuttlepro-v2']);d.feed(contour())
        self.assertEqual(d.feed(contour(buttons=3)),[('toggle',None),('cue_prev',None)])
        self.assertEqual(d.feed(contour(buttons=(1<<12)|(1<<13)|(1<<14))),
                         [('speed_delta',-.015),('speed_delta',.015),('take_backup',None)])

    def test_contour_center_overrides_combined_report_jog_and_button(self):
        d=Decoder(P['shuttlexpress']);d.feed(contour());d.feed(contour(3))
        self.assertEqual(d.feed(contour(0,1,0x10)),[('stop',None)])

    def test_neo_packets_boundary_headers_padding_and_content(self):
        data=b'j'*2050;reports=list(neo_image_reports(7,data))
        self.assertEqual([len(p) for p in reports],[1024]*3)
        self.assertEqual(struct.unpack('<BBBBHH',reports[0][:8]),(2,7,7,0,1016,0))
        self.assertEqual(struct.unpack('<BBBBHH',reports[-1][:8]),(2,7,7,1,18,2))
        self.assertEqual(b''.join(r[8:8+struct.unpack_from('<H',r,4)[0]] for r in reports),data)
        for key in (-1,8):
            with self.assertRaises(ValueError):list(neo_image_reports(key,data))


class FakeHid:
    def __init__(self):self.infos=[];self.handle=FakeHandle()
    def enumerate(self):return self.infos
    def device(self):return self.handle

class FakeHandle:
    def __init__(self):self.writes=[];self.features=[];self.closed=False;self.path=None;self.reports=[];self.opens=0
    def open_path(self,path):self.path=path;self.closed=False;self.opens+=1
    def write(self,data):self.writes.append(data);return len(data)
    def send_feature_report(self,data):self.features.append(data);return len(data)
    def read(self,*args,**kwargs):return self.reports.pop(0) if self.reports else []
    def close(self):self.closed=True

class FakeApi:
    def __init__(self):self.sent=[];self.reports=[]
    def command(self,c,v):self.sent.append((c,v));return {'playing':False},'HTTP'
    def state(self):return {'runtime':{}}
    def heartbeat(self,p):self.reports.append(p);return True

class FakeDevice:
    def __init__(self,p,info,hid,config):self.profile=p;self.closed=False;self.events=[]
    def open(self):pass
    def close(self):self.closed=True
    def commands(self):r=self.events;self.events=[];return r
    def keep_alive(self):pass
    def update_icons(self,state):pass


class HubTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.cfg=Path(self.tmp.name)/'cfg.json'
        save_config(self.cfg,{'token':'t'*32,'servers':['http://127.0.0.1:1']})
        self.hid=FakeHid();self.api=FakeApi();self.hub=ControllerHub(self.cfg,self.hid,self.api,FakeDevice)
    def tearDown(self):
        for p in list(self.hub.sessions):self.hub.remove(p)
        self.tmp.cleanup()
    def plug(self,model,path):
        p=P[model];self.hid.infos.append(dict(path=path,vendor_id=p.vid,product_id=p.pid,interface_number=0));self.hub.scan()
        s=self.hub.sessions[path];s.attached-=1;return s

    def test_auto_swap_all_four_families_without_pairing_or_browser(self):
        for model in ('akp03e','shuttlexpress','msd-two','neo'):
            self.hid.infos=[];self.hub.scan()
            session=self.plug(model,model.encode())
            self.hub.submit(session,'jog',.08);self.hub.dispatch_one()
        self.assertEqual(self.api.sent,[('jog',.08)]*4)
        self.assertEqual(self.hub.config['token'],'t'*32)

    def test_unplug_and_replug_cannot_replay_old_session_queue(self):
        old=self.plug('akp03e',b'a');self.hub.submit(old,'jog',.08)
        self.hid.infos=[];self.hub.scan();self.plug('neo',b'a')
        self.hub.dispatch_one();self.assertEqual(self.api.sent,[])
        self.assertTrue(old.device.closed)

    def test_expired_events_and_stop_priority_across_devices(self):
        a=self.plug('msd-two',b'a');b=self.plug('neo',b'b')
        self.hub.events.put((time.monotonic()-1,a.generation,'jog',.08));self.hub.dispatch_one()
        for _ in range(20):self.hub.submit(a,'speed_delta',.015)
        self.hub.submit(b,'stop');self.hub.dispatch_one()
        self.assertEqual(self.api.sent,[('stop',None)]);self.assertTrue(self.hub.events.empty())

    def test_initial_grace_has_no_attach_command_and_reconnect_does_not_stop(self):
        s=self.plug('shuttlexpress',b'a');s.attached=time.monotonic()
        self.hub.submit(s,'toggle');self.hub.dispatch_one();self.assertEqual(self.api.sent,[])
        self.hub.remove(b'a');self.assertEqual(self.api.sent,[])

    def test_failed_enumeration_preserves_live_handle(self):
        s=self.plug('neo',b'a')
        with patch.object(self.hid,'enumerate',side_effect=OSError):
            with self.assertRaises(OSError):self.hub.scan()
        self.assertFalse(s.device.closed)

    def test_neo_first_press_after_connection_grace_is_not_swallowed(self):
        self.hub.factory=Device
        session=self.plug('neo',b'a');self.hid.handle.reports=[neo(0)]
        with patch.object(session.device,'update_icons'):
            self.hub.poll_devices();self.hub.dispatch_one()
        self.assertEqual(self.api.sent,[('toggle',None)])

    def test_usb_lcd_loss_removes_session_and_stale_commands(self):
        s=self.plug('neo',b'a');self.hub.submit(s,'cue_next')
        with patch.object(s.device,'update_icons',side_effect=OSError):self.hub.poll_devices()
        self.hub.dispatch_one();self.assertEqual(self.api.sent,[]);self.assertTrue(s.device.closed)

    def test_network_failure_discards_relative_backlog(self):
        s=self.plug('msd-two',b'a');self.hub.submit(s,'cue_next');self.hub.submit(s,'jog',.08)
        with patch.object(self.api,'command',side_effect=TimeoutError):self.hub.dispatch_one()
        self.assertTrue(self.hub.events.empty())

    def test_status_excludes_usb_paths_serials_and_tokens(self):
        self.plug('neo',b'SENSITIVE-PATH');status=json.dumps(self.hub.status())
        self.assertIn('Stream Deck Neo',status);self.assertNotIn('SENSITIVE',status);self.assertNotIn('t'*32,status)

    def test_slow_status_poll_does_not_block_stop_dispatch(self):
        import threading
        waiting=threading.Event();release=threading.Event();sent=threading.Event()
        session=self.plug('neo',b'a')
        def slow_state():waiting.set();release.wait(2);return {'runtime':{}}
        def command(c,v):self.api.sent.append((c,v));sent.set();return {},'HTTP'
        with patch.object(self.api,'state',side_effect=slow_state),patch.object(self.api,'command',side_effect=command):
            poll=threading.Thread(target=self.hub.telemetry_loop);worker=threading.Thread(target=self.hub.network_loop)
            poll.start();worker.start()
            try:
                self.assertTrue(waiting.wait(1));self.hub.submit(session,'stop')
                self.assertTrue(sent.wait(1));self.assertEqual(self.api.sent,[('stop',None)])
            finally:
                self.hub.stop.set();release.set();poll.join(2);worker.join(2)

    def test_singleton_prevents_two_instances_and_releases_on_close(self):
        lock=singleton(self.cfg)
        try:
            with self.assertRaises(RuntimeError):singleton(self.cfg)
        finally:lock.close()
        singleton(self.cfg).close()

    def test_protocol_writes_use_exact_path_and_no_contour_output(self):
        for name in ('msd-two','akp03e','neo','shuttlexpress'):
            h=FakeHid();d=Device(P[name],{'path':b'exact'},h,{})
            d.open();self.assertEqual(h.handle.path,b'exact')
            self.assertEqual(h.handle.opens,2 if name=='akp03e' else 1)
            if name=='shuttlexpress':self.assertEqual(h.handle.writes,[])
            elif name=='neo':
                self.assertEqual(h.handle.features[0][:3],bytes([3,8,65]))
                self.assertEqual(len(h.handle.features[0]),33)
            d.close();self.assertTrue(h.handle.closed)

    def test_msd_staging_padding_and_neo_no_crt_header(self):
        for model in ('msd-two','neo'):
            h=FakeHid();d=Device(P[model],{'path':b'x'},h,{});d.open();h.handle.writes=[]
            d.set_key_jpeg(0,b'jpeg')
            if model=='msd-two':
                self.assertEqual(len(h.handle.writes),10);self.assertTrue(h.handle.writes[0][1:].startswith(b'CRT'))
            else:self.assertEqual(h.handle.writes[0][:2],bytes([2,7]))
            d.close()

    @unittest.skipUnless(importlib.util.find_spec('PIL'), 'Pillow required for Neo image encoding')
    def test_neo_images_are_native_jpeg_dimensions(self):
        from PIL import Image
        import io
        for name in ('play','speed_up','speed_down'):
            image=Image.open(io.BytesIO(icon_bytes(P['neo'],name,{})))
            self.assertEqual(image.size,(96,96));self.assertEqual(image.format,'JPEG')


class HubHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import socket,subprocess,sys,urllib.request
        cls.tmp=tempfile.TemporaryDirectory();cls.folder=Path(cls.tmp.name)
        with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
        cls.origin=f'http://127.0.0.1:{port}'
        cls.proc=subprocess.Popen([sys.executable,str(Path(__file__).resolve().parents[1]/'server.py'),
            '--port',str(port),'--data-dir',str(cls.folder),'--prompt-osc-port','0'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(100):
            try:urllib.request.urlopen(cls.origin+'/api/info',timeout=.2).close();break
            except OSError:time.sleep(.05)
        else:cls.proc.terminate();cls.proc.wait();raise RuntimeError('Test server not ready')
        cls.admin=(cls.folder/'access.key').read_text().strip()

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate();cls.proc.wait(timeout=5);cls.tmp.cleanup()

    def admin_post(self,path,body):
        import urllib.request
        req=urllib.request.Request(self.origin+path,data=json.dumps(body).encode(),
            headers={'X-Control-Token':self.admin,'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(req,timeout=3) as response:return json.load(response)

    def test_real_http_one_pairing_four_models_and_no_prompt_page(self):
        from akp03e_controller import CarismaApi
        code=self.admin_post('/api/prompt/controller/pair-code',{'name':'Controller test'})['code']
        api=CarismaApi({'servers':[self.origin]});paired=api.pair(code,'Controller test')
        cfg=self.folder/'hub.json';save_config(cfg,{'servers':[self.origin],'token':paired['token']})
        hid=FakeHid();hub=ControllerHub(cfg,hid,api,FakeDevice)
        seq=api.state()['runtime']['seq']
        try:
            for model,report in [('akp03e',akp(1)),('msd-two',akp(1,1)),('shuttlexpress',contour(buttons=0x10)),('neo',neo(0))]:
                hid.infos=[];hub.scan()
                p=P[model];hid.infos=[dict(path=model.encode(),vendor_id=p.vid,product_id=p.pid,interface_number=0)]
                hub.scan();session=hub.sessions[model.encode()];session.attached-=1
                decoder=Decoder(p)
                if model=='shuttlexpress':decoder.feed(contour())
                if model=='neo':decoder.feed(neo())
                for command,value in decoder.feed(report):hub.submit(session,command,value)
                hub.dispatch_one();seq+=1
                self.assertEqual(api.state()['runtime']['seq'],seq)
                self.assertEqual(api.token,paired['token'])
            self.assertTrue(api.heartbeat(hub.status()))
            import urllib.request
            req=urllib.request.Request(self.origin+'/api/prompt/state',headers={'X-Control-Token':self.admin})
            with urllib.request.urlopen(req) as r:state=json.load(r)
            ctl=next(c for c in state['controllers'] if c['id']==paired['id'])
            self.assertEqual(ctl['status']['devices'][0]['model'],'neo')
            self.assertNotIn('path',json.dumps(ctl['status']))
        finally:
            for path in list(hub.sessions):hub.remove(path)

    def test_play_starts_after_stop_instead_of_zero_rate(self):
        self.admin_post('/api/prompt/command',{'command':'stop'})
        result=self.admin_post('/api/prompt/command',{'command':'play'})
        self.assertTrue(result['playing']);self.assertEqual(result['rate'],.11)
        self.admin_post('/api/prompt/command',{'command':'stop'})
