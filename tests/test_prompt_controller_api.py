import json,socket,subprocess,sys,tempfile,time,unittest,urllib.error,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class ControllerApiTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory(prefix='prompt-akp-http-');cls.data=Path(cls.tmp.name)
  with socket.socket() as s:s.bind(('127.0.0.1',0));cls.port=s.getsockname()[1]
  cls.proc=subprocess.Popen([sys.executable,str(ROOT/'server.py'),'--port',str(cls.port),'--data-dir',str(cls.data),'--prompt-osc-port','0'],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
  for _ in range(120):
   try:urllib.request.urlopen(f'http://127.0.0.1:{cls.port}/api/info',timeout=.2);break
   except Exception:time.sleep(.05)
  cls.admin=(cls.data/'access.key').read_text().strip()
 @classmethod
 def tearDownClass(cls):
  cls.proc.terminate();cls.proc.wait(timeout=5);cls.proc.stderr.close();cls.tmp.cleanup()
 @classmethod
 def call(cls,path,method='GET',body=None,admin=False,controller=None):
  h={}
  if admin:h['X-Control-Token']=cls.admin
  if controller:h['X-Prompt-Controller-Token']=controller
  if isinstance(body,dict):body=json.dumps(body).encode();h['Content-Type']='application/json'
  req=urllib.request.Request(f'http://127.0.0.1:{cls.port}{path}',data=body,headers=h,method=method)
  try:
   with urllib.request.urlopen(req,timeout=3) as r:return r.status,json.loads(r.read() or b'{}')
  except urllib.error.HTTPError as e:return e.code,json.loads(e.read() or b'{}')
 def test_pair_scoped_commands_and_take(self):
  st,c=self.call('/api/prompt/controller/pair-code','POST',{'name':'AKP03E'},admin=True);self.assertEqual(st,200)
  st,p=self.call('/api/prompt/controller/pair','POST',{'code':c['code'],'name':'AKP03E Regia'});self.assertEqual(st,201);token=p['token']
  self.assertEqual(self.call('/api/prompt/state',controller=token)[0],401)
  self.assertEqual(self.call('/api/prompt/controller/state',controller=token)[0],200)
  st,r=self.call('/api/prompt/controller/command','POST',{'command':'take_backup'},controller=token);self.assertEqual(st,200);self.assertEqual(r['activeRole'],'BACKUP')
  st,r=self.call('/api/prompt/controller/command','POST',{'command':'message','value':'NO'},controller=token);self.assertEqual(st,403)
  st,r=self.call('/api/prompt/controller/heartbeat','POST',{'usbConnected':True,'vid':'0300','pid':'3002','lastEvent':'cue_next','version':'0.8'},controller=token);self.assertEqual(st,200)
  st,a=self.call('/api/prompt/state',admin=True);self.assertTrue(a['controllers'][0]['online']);self.assertTrue(a['controllers'][0]['status']['usbConnected'])
 def test_osc_take_mapping_via_unit_import(self):
  from prompt_module import osc_to_command
  self.assertEqual(osc_to_command('/carisma/prompt/take/backup',[]),('take_backup',None))
  self.assertEqual(osc_to_command('/carisma/prompt/take',['PRIMARY']),('take','PRIMARY'))

 def test_expiry_single_use_and_revocation(self):
  from storage import database
  _,code=self.call('/api/prompt/controller/pair-code','POST',{},admin=True)
  with database(self.data/'controller.sqlite3') as c:c.execute('UPDATE prompt_controller_pairing SET expires=0')
  self.assertEqual(self.call('/api/prompt/controller/pair','POST',{'code':code['code']})[0],401)
  _,code=self.call('/api/prompt/controller/pair-code','POST',{},admin=True)
  status,ctl=self.call('/api/prompt/controller/pair','POST',{'code':code['code']});self.assertEqual(status,201)
  self.assertEqual(self.call('/api/prompt/controller/pair','POST',{'code':code['code']})[0],401)
  self.assertEqual(self.call('/api/prompt/controller/revoke','POST',{'id':ctl['id']},admin=True)[0],200)
  self.assertEqual(self.call('/api/prompt/controller/state',controller=ctl['token'])[0],401)

 def test_concurrent_duplicate_request_executes_once(self):
  import concurrent.futures
  _,code=self.call('/api/prompt/controller/pair-code','POST',{},admin=True)
  _,ctl=self.call('/api/prompt/controller/pair','POST',{'code':code['code']})
  body={'command':'toggle','requestId':'f'*32}
  with concurrent.futures.ThreadPoolExecutor(4) as pool:
   replies=list(pool.map(lambda _:self.call('/api/prompt/controller/command','POST',body,controller=ctl['token']),range(4)))
  self.assertTrue(all(r[0]==200 for r in replies));self.assertTrue(all(r[1]==replies[0][1] for r in replies))
  self.assertEqual(self.call('/api/prompt/controller/command','POST',dict(body,command='stop'),controller=ctl['token'])[0],409)

if __name__=='__main__':unittest.main()
