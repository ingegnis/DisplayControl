"""Real HTTP tests, scoped device credentials, pairing and gateway fMP4."""
import base64
import concurrent.futures
import copy
import hashlib
import json
from pathlib import Path
import socket
import sqlite3
from storage import database
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
class PhysicalPlayerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='carisma-physical-');self.data=Path(self.tmp.name)
        with socket.socket() as s:s.bind(('127.0.0.1',0));self.port=s.getsockname()[1]
        self.process=subprocess.Popen([sys.executable,str(ROOT/'server.py'),'--port',str(self.port),'--data-dir',str(self.data)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        self.admin=''
        for _ in range(100):
            try:
                if self.call('/api/info')[0]==200:break
            except OSError:time.sleep(.1)
        else:raise RuntimeError('Server test non avviato')
        self.admin=(self.data/'access.key').read_text().strip()
        self.project=json.loads((ROOT/'example_project.json').read_text())
        self.project['schedules']=[]
        self.sid=self.project['screens'][0]['id']
        self.publish(self.project)
    def tearDown(self):
        # Stop encoders before Windows hard-kills the server.
        _,status=self.jsoncall('/api/ndi/status')
        for stream in status.get('streams',[]):
            self.call('/api/ndi/stop','POST',{'id':stream['id']})
        self.process.terminate()
        try:self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=5)
        self.tmp.cleanup()
    def call(self,path,method='GET',body=None,player=None,admin=True,headers=None):
        hs=dict(headers or {})
        if admin:hs['X-Control-Token']=self.admin
        if player is not None:hs['X-Player-Token']=player
        if isinstance(body,dict):body=json.dumps(body).encode();hs['Content-Type']='application/json'
        req=urllib.request.Request('http://127.0.0.1:%d%s'%(self.port,path),data=body,method=method,headers=hs)
        try:
            with urllib.request.urlopen(req,timeout=8) as r:return r.status,r.read()
        except urllib.error.HTTPError as e:
            with e:
                return e.code,e.read()
    def jsoncall(self,*a,**k):
        status,data=self.call(*a,**k);return status,json.loads(data)
    def publish(self,p):
        _,s=self.jsoncall('/api/state');status,_=self.call('/api/state','PUT',{'revision':s['revision'],'state':p});self.assertEqual(status,200)
    def code(self,sid=None):
        status,r=self.jsoncall('/api/devices/pair-code','POST',{'screenId':sid or self.sid});self.assertEqual(status,200);return r['code']
    def pair(self,sid=None):
        status,r=self.jsoncall('/api/player/pair','POST',{'code':self.code(sid),'name':'TV test'},admin=False);self.assertEqual(status,201);return r['token']
    def test_public_shell_and_connection_page(self):
        for p in ['/players.html','/connect.html','/player.html','/physical_boot.js']:
            self.assertEqual(self.call(p,admin=False)[0],200)
    def test_admin_required_for_pair_code_and_list(self):
        for p in ['/api/devices/list','/api/devices/pair-code','/api/devices/revoke']:
            self.assertEqual(self.call(p,'GET' if p.endswith('list') else 'POST',{} if not p.endswith('list') else None,admin=False)[0],401)
    def test_code_one_use_and_hashed_storage(self):
        code=self.code();status,r=self.jsoncall('/api/player/pair','POST',{'code':code},admin=False);self.assertEqual(status,201)
        self.assertEqual(self.call('/api/player/pair','POST',{'code':code},admin=False)[0],401)
        with database(self.data/'controller.sqlite3') as c:
            rows=c.execute('SELECT token_hash FROM devices').fetchall()
        self.assertEqual(rows[0][0],hashlib.sha256(r['token'].encode()).hexdigest())
    def test_expired_code_rejected(self):
        code=self.code()
        with database(self.data/'controller.sqlite3') as c:c.execute('UPDATE pairing SET expires=0')
        self.assertEqual(self.call('/api/player/pair','POST',{'code':code},admin=False)[0],401)
    def test_new_code_invalidates_old_code(self):
        a=self.code();b=self.code();self.assertNotEqual(a,b)
        self.assertEqual(self.call('/api/player/pair','POST',{'code':a},admin=False)[0],401)
        self.assertEqual(self.call('/api/player/pair','POST',{'code':b},admin=False)[0],201)
    def test_concurrent_claim_single_winner(self):
        code=self.code()
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            statuses=list(pool.map(lambda _:self.call('/api/player/pair','POST',{'code':code},admin=False)[0],range(2)))
        self.assertEqual(sorted(statuses),[201,401])
    def test_player_cannot_admin_or_other_screen(self):
        t=self.pair()
        for path,method,body in [('/api/state','GET',None),('/api/state','PUT',{}),('/api/devices/list','GET',None),('/api/ndi/stop','POST',{'id':'a'})]:
            self.assertEqual(self.call(path,method,body,player=t,admin=False)[0],401)
        self.assertEqual(self.call('/api/player/heartbeat','POST',{'screenId':'camerini'},player=t,admin=False)[0],403)
        self.assertEqual(self.call('/api/player/ndi/stop','POST',{'id':'a'},player=t,admin=False)[0],403)
    def test_state_scoped_to_assigned_contents(self):
        t=self.pair();status,r=self.jsoncall('/api/player/state',player=t,admin=False);self.assertEqual(status,200)
        self.assertEqual([x['id'] for x in r['state']['screens']],[self.sid])
        self.assertNotIn('diretta',[a['id'] for a in r['state']['assets']]);self.assertEqual(r['state']['events'],[])
    def test_admin_secret_not_accepted_as_player(self):
        self.assertEqual(self.call('/api/player/state',player=self.admin,admin=False)[0],401)
    def test_pair_replaces_previous_token(self):
        old=self.pair();new=self.pair()
        self.assertEqual(self.call('/api/player/state',player=old,admin=False)[0],401)
        self.assertEqual(self.call('/api/player/state',player=new,admin=False)[0],200)
    def test_revoke_removes_access_and_heartbeat(self):
        t=self.pair();self.call('/api/player/heartbeat','POST',{'screenId':self.sid,'cacheCount':2},player=t,admin=False)
        self.assertEqual(self.call('/api/devices/revoke','POST',{'screenId':self.sid})[0],200)
        self.assertEqual(self.call('/api/player/state',player=t,admin=False)[0],401)
        self.assertNotIn(self.sid,self.jsoncall('/api/runtime')[1]['players'])
    def test_heartbeat_bounded_and_visible(self):
        t=self.pair();self.assertEqual(self.call('/api/player/heartbeat','POST',{'screenId':self.sid,'cacheCount':'bad','revision':10**100,'title':'x'*500},player=t,admin=False)[0],200)
        p=self.jsoncall('/api/runtime')[1]['players'][self.sid];self.assertEqual(p['kind'],'physical');self.assertEqual(len(p['title']),200);self.assertEqual(p['cacheCount'],0)
    def test_deleted_screen_blocks_player(self):
        t=self.pair();self.project['screens']=self.project['screens'][1:];self.publish(self.project)
        self.assertEqual(self.call('/api/player/state',player=t,admin=False)[0],410)
    def test_scope_asset_and_hash_download(self):
        data=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2nAAAAABJRU5ErkJggg==')
        _,a=self.jsoncall('/api/assets','POST',data,headers={'Content-Type':'image/png'})
        t=self.pair();path='/api/player/assets/'+a['fileId'];self.assertEqual(self.call(path,player=t,admin=False)[0],403)
        self.project['assets'].append(dict(id='localimg',kind='image',title='Local',**a));self.project['screens'][0]['override']={'type':'asset','id':'localimg'};self.publish(self.project)
        status,received=self.call(path,player=t,admin=False);self.assertEqual(status,200);self.assertEqual(received,data)
    def test_ndi_cannot_start_unassigned_source(self):
        t=self.pair();self.assertEqual(self.call('/api/player/ndi/start','POST',{'test':True},player=t,admin=False)[0],403)
    def test_rate_limit(self):
        codes=[self.call('/api/player/pair','POST',{'code':'00000000'},admin=False)[0] for _ in range(11)]
        self.assertEqual(codes[-1],429)
    def test_real_ffmpeg_scoped_segments(self):
        import shutil
        if not shutil.which('ffmpeg'):self.skipTest('FFmpeg non installato')
        self.project['assets'].append(dict(id='test-live',kind='live',title='NON NDI',protocol='ndi-test',sourceName='',profile='light'))
        self.project['screens'][0]['override']={'type':'asset','id':'test-live'};self.publish(self.project)
        t=self.pair();status,stream=self.jsoncall('/api/player/ndi/start','POST',{'test':True,'profile':'light'},player=t,admin=False);self.assertEqual(status,200)
        for _ in range(35):
            status,m=self.jsoncall('/api/player/ndi/manifest/'+stream['id'],player=t,admin=False)
            self.assertEqual(status,200)
            if m.get('ready'):break
            time.sleep(.2)
        self.assertTrue(m.get('ready'))
        for url in [m['init'],m['segments'][-1]['url']]:
            status,b=self.call(url.replace('/api/ndi/','/api/player/ndi/'),player=t,admin=False);self.assertEqual(status,200);self.assertGreater(len(b),100)
        self.project['screens'][0]['override']={'type':'asset','id':'benvenuto'};self.publish(self.project)
        self.assertEqual(self.call('/api/player/ndi/manifest/'+stream['id'],player=t,admin=False)[0],403)
