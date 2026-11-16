import json, tempfile, unittest
from pathlib import Path
from akp03e_controller import packet,image_announce,image_chunk,parse_report,osc_message,command_to_osc,ControllerService

class FakeDevice:
    def __init__(self):self.images=[];self.brightness=65
    def set_key_jpeg(self,k,data):self.images.append((k,len(data)))
    def keep_alive(self):pass
    def close(self):pass

class FakeApi:
    def __init__(self):
        self.commands=[]
        self.state_value={'runtime':{'playing':False,'blackout':False,'activeRole':'PRIMARY'},'backupReady':True,'devices':[{'role':'PRIMARY','online':True},{'role':'BACKUP','online':True}]}
    def command(self,c,v=None):self.commands.append((c,v));return ({'playing':c=='toggle','blackout':False,'activeRole':'PRIMARY'},'HTTP')
    def state(self):return self.state_value
    def heartbeat(self,p):return True

class ProtocolTests(unittest.TestCase):
    def test_packets(self):
        self.assertEqual(len(packet(b'DIS\0\0')),1025)
        self.assertEqual(packet(b'DIS\0\0')[1:6],b'CRT\0\0')
        self.assertEqual(len(image_announce(0,3000)),1025)
        self.assertEqual(len(image_chunk(b'x'*1024)),1025)
    def test_report_mapping(self):
        b=bytearray(512);b[0]=1;b[9]=0x91;b[10]=0
        self.assertEqual(parse_report(bytes(b)),('turn',0,1))
        b[9]=0x50;self.assertEqual(parse_report(bytes(b)),('turn',1,-1))
        b[9]=0x33;b[10]=1;self.assertEqual(parse_report(bytes(b)),('knob',0,1))
        b[9]=0x06;b[10]=0;self.assertEqual(parse_report(bytes(b)),('button',5,0))
    def test_osc_fallback_encoding(self):
        self.assertTrue(command_to_osc('take_backup').startswith(b'/carisma/prompt/take/backup'))
        self.assertTrue(command_to_osc('speed',.1).startswith(b'/carisma/prompt/speed'))
        self.assertIsNone(command_to_osc('message','x'))

class MappingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        cfg=self.root/'cfg.json';cfg.write_text(json.dumps({'token':'x'*32,'servers':['http://127.0.0.1:1'],'brightness':65,'iconRotation':270}))
        self.api=FakeApi();self.dev=FakeDevice();self.s=ControllerService(cfg,device=self.dev,api=self.api)
    def tearDown(self):self.tmp.cleanup()
    def test_encoder_mapping(self):
        self.s.handle_event(('turn',0,1));self.assertEqual(self.api.commands[-1],('speed_delta',.015))
        self.s.handle_event(('turn',1,-1));self.assertEqual(self.api.commands[-1],('jog',-.08))
        self.s.handle_event(('turn',2,1));self.assertEqual(self.api.commands[-1],('cue_next',None))
    def test_button_mapping_on_release(self):
        self.s.handle_event(('button',0,1));self.assertEqual(self.api.commands,[])
        self.s.handle_event(('button',0,0));self.assertEqual(self.api.commands[-1],('toggle',None))
        self.s.handle_event(('button',5,0));self.assertEqual(self.api.commands[-1],('take_toggle',None))
    def test_knob_press_mapping(self):
        self.s.handle_event(('knob',2,1));self.assertEqual(self.api.commands[-1],('take_toggle',None))

if __name__=='__main__':unittest.main()
