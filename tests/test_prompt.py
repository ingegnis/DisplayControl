import base64, io, json, socket, struct, subprocess, sys, tempfile, time, unittest, urllib.error, urllib.request, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
from prompt_module import PromptStore, parse_script, docx_to_text, parse_osc_packet, osc_to_command


def osc_str(s):
    b=s.encode()+b'\0'; return b+b'\0'*((-len(b))%4)
def osc_msg(addr,tags='',args=()):
    b=osc_str(addr)+osc_str(','+tags)
    for t,a in zip(tags,args):
        if t=='f': b+=struct.pack('>f',float(a))
        elif t=='i': b+=struct.pack('>i',int(a))
        elif t=='s': b+=osc_str(str(a))
    return b

class PromptUnitTests(unittest.TestCase):
    def test_script_cues_and_default(self):
        p=parse_script('[[CUE: UNO]]\nRiga uno\n\n[[CUE: DUE]]\nRiga due')
        self.assertEqual([x['id'] for x in p['cues']],['uno','due'])
        self.assertEqual(p['cues'][1]['lineIndex'],2)
        self.assertEqual(parse_script('solo testo')['cues'][0]['id'],'start')
    def test_docx_extract(self):
        xml='''<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Ciao</w:t></w:r></w:p><w:p><w:r><w:t>Mondo</w:t></w:r></w:p></w:body></w:document>'''.encode()
        bio=io.BytesIO()
        with zipfile.ZipFile(bio,'w') as z:z.writestr('word/document.xml',xml)
        self.assertEqual(docx_to_text(bio.getvalue()),'Ciao\n\nMondo')
    def test_runtime_commands_and_three_presets(self):
        with tempfile.TemporaryDirectory() as d:
            s=PromptStore(Path(d)); p=s.save_project('X','[[CUE: A]]\nuno\n[[CUE: B]]\ndue',{'font':'bad','size':'large','theme':'amber'},1)
            self.assertEqual(p['settings'],{'font':'classic','size':'large','theme':'amber','readingLine':True})
            self.assertEqual(s.command('cue','b')['anchor'],'b')
            self.assertTrue(s.command('speed',.2)['playing'])
            time.sleep(.02); self.assertGreater(s.runtime()['offsetVh'],0)
            self.assertFalse(s.command('pause')['playing'])
            self.assertTrue(s.command('blackout')['blackout'])
            self.assertEqual(s.command('message','5 minuti')['message'],'5 minuti')
    def test_pair_primary_backup_and_ready(self):
        with tempfile.TemporaryDirectory() as d:
            s=PromptStore(Path(d)); tokens={}
            for role in ('PRIMARY','BACKUP'):
                c=s.issue_code('palco',role)['code']; tokens[role]=s.pair(c,role)
                dev=s.device_for_token(tokens[role]['token']); s.heartbeat(dev,{'projectVersion':1,'seq':0,'offsetVh':1.0,'fps':60})
            a=s.admin_state(); self.assertTrue(a['backupReady']); self.assertEqual(a['syncDeltaVh'],0.0)
            s.revoke('palco:BACKUP'); self.assertFalse(s.admin_state()['backupReady'])
    def test_osc_message_and_bundle(self):
        m=osc_msg('/carisma/prompt/speed','f',(.12,)); r=parse_osc_packet(m)
        self.assertEqual(r[0][0],'/carisma/prompt/speed'); self.assertAlmostEqual(r[0][1][0],.12,places=4)
        self.assertEqual(osc_to_command('/carisma/prompt/cue/scena-2',[]),('cue','scena-2'))
        bundle=b'#bundle\0'+b'\0'*8+struct.pack('>i',len(m))+m
        self.assertEqual(len(parse_osc_packet(bundle)),1)

class PromptHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='prompt-http-');cls.data=Path(cls.tmp.name)
        with socket.socket() as s:s.bind(('127.0.0.1',0));cls.port=s.getsockname()[1]
        cls.proc=subprocess.Popen([sys.executable,str(ROOT/'server.py'),'--port',str(cls.port),'--data-dir',str(cls.data),'--prompt-osc-port','0'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(120):
            try:
                urllib.request.urlopen(f'http://127.0.0.1:{cls.port}/api/info',timeout=.2);break
            except Exception:time.sleep(.05)
        cls.admin=(cls.data/'access.key').read_text().strip()
    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate();cls.proc.wait(timeout=5);cls.tmp.cleanup()
    @classmethod
    def call(cls,path,method='GET',body=None,admin=True,prompt=None):
        hs={}
        if admin:hs['X-Control-Token']=cls.admin
        if prompt:hs['X-Prompt-Token']=prompt
        if isinstance(body,dict):body=json.dumps(body).encode();hs['Content-Type']='application/json'
        req=urllib.request.Request(f'http://127.0.0.1:{cls.port}{path}',data=body,headers=hs,method=method)
        try:
            with urllib.request.urlopen(req,timeout=5) as r:return r.status,json.loads(r.read() or b'{}') if 'json' in r.headers.get('Content-Type','') else None
        except urllib.error.HTTPError as e:return e.code,json.loads(e.read() or b'{}')
    def test_public_pages_and_admin_auth(self):
        for p in ('/prompt.html','/prompt_player.html'):
            req=urllib.request.Request(f'http://127.0.0.1:{self.port}{p}')
            with urllib.request.urlopen(req,timeout=3) as r:self.assertEqual(r.status,200)
        self.assertEqual(self.call('/api/prompt/state',admin=False)[0],401)
        self.assertEqual(self.call('/api/prompt/state')[0],200)
    def test_pair_scoped_player_and_commands(self):
        st,r=self.call('/api/prompt/pair-code','POST',{'station':'palco','role':'PRIMARY'});self.assertEqual(st,200)
        st,p=self.call('/api/prompt/pair','POST',{'code':r['code'],'name':'Gobbo A'},admin=False);self.assertEqual(st,201)
        token=p['token'];self.assertEqual(self.call('/api/prompt/player/state',admin=False,prompt=token)[0],200)
        self.assertEqual(self.call('/api/prompt/state',admin=False,prompt=token)[0],401)
        st,r=self.call('/api/prompt/command','POST',{'command':'speed','value':.1});self.assertEqual(st,200);self.assertTrue(r['playing'])
        st,r=self.call('/api/prompt/player/heartbeat','POST',{'seq':r['seq'],'projectVersion':1,'anchor':'start','offsetVh':.1,'fps':60},admin=False,prompt=token);self.assertEqual(st,200)
    def test_import_txt(self):
        data=base64.b64encode(b'[[CUE: X]]\nTest').decode()
        st,r=self.call('/api/prompt/import','POST',{'name':'x.txt','data':data});self.assertEqual(st,200);self.assertEqual(r['parsed']['cues'][0]['id'],'x')

if __name__=='__main__':unittest.main()
