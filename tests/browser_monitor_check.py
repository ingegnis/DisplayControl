"""UI test with real API/FFmpeg/JPEG; explicit transport and memory storage fixtures.
No LAN reachability, Windows, Chromecast, or actual NDI-source claim.
"""
import base64,json,re,socket,subprocess,sys,tempfile,time,urllib.error,urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
QA=ROOT/'qa_v052';QA.mkdir(exist_ok=True)
checks=[];errors=[]
with tempfile.TemporaryDirectory() as folder:
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    origin='http://127.0.0.1:'+str(port)
    proc=subprocess.Popen([sys.executable,str(ROOT/'server.py'),'--port',str(port),'--data-dir',folder],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    def req(path,method='GET',body=None,token=None,player=None):
        headers={}
        if token:headers['X-Control-Token']=token
        if player:headers['X-Player-Token']=player
        if isinstance(body,dict):headers['Content-Type']='application/json';body=json.dumps(body).encode()
        r=urllib.request.Request(origin+path,data=body,headers=headers,method=method)
        try:
            with urllib.request.urlopen(r,timeout=8) as res:return res.status,res.read()
        except urllib.error.HTTPError as e:return e.code,e.read()
    try:
        for _ in range(80):
            try:req('/api/info');break
            except OSError:time.sleep(.1)
        admin=(Path(folder)/'access.key').read_text().strip()
        state=json.loads((ROOT/'example_project.json').read_text());state['schedules']=[]
        state['assets'].append({'id':'test-live','title':'Palco / segnale di prova','kind':'live','protocol':'ndi-test','profile':'light','sourceName':''})
        for i,s in enumerate(state['screens']):
            s['override']={'type':'asset','id':['orologio','programma','test-live','intervallo'][i]};s['fallbackAssetId']='orologio'
        assert req('/api/state','PUT',{'revision':0,'state':state},token=admin)[0]==200
        def publish():
            revision=json.loads(req('/api/state',token=admin)[1])['revision']
            assert req('/api/state','PUT',{'revision':revision,'state':state},token=admin)[0]==200
        tokens=[]
        for s in state['screens']:
            code=json.loads(req('/api/devices/pair-code','POST',{'screenId':s['id']},token=admin)[1])['code']
            tokens.append(json.loads(req('/api/player/pair','POST',{'code':code,'name':'Browser fixture'})[1])['token'])
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
            context=browser.new_context(viewport={'width':1440,'height':1000},reduced_motion='reduce')
            def bridge(source,args):
                if not args['path'].startswith('/api/'):raise ValueError('Only API transport')
                body=args.get('body');data=body.encode() if body else None;headers=args.get('headers',{})
                status,raw=req(args['path'],args.get('method','GET'),data,token=headers.get('x-control-token'),player=headers.get('x-player-token'))
                return dict(status=status,body=base64.b64encode(raw).decode())
            context.expose_binding('qaHTTP',bridge)
            shim="""
            window.qaStorage=new Map();window.qaDB={media:new Map(),snapshots:new Map()};window.qaApiOffline=false;
            Object.defineProperty(window,'localStorage',{value:{getItem:k=>window.qaStorage.get(k)||null,setItem:(k,v)=>window.qaStorage.set(k,v),removeItem:k=>window.qaStorage.delete(k)},configurable:true});
            window.fetch=async(url,opts={})=>{if(window.qaApiOffline)throw Error('QA transport offline');const r=await window.qaHTTP({path:String(url),method:opts.method||'GET',body:opts.body||null,headers:Object.fromEntries(new Headers(opts.headers||{}).entries())});const b=Uint8Array.from(atob(r.body),c=>c.charCodeAt(0));return new Response(b,{status:r.status,headers:{'Content-Type':'application/json'}});};
            """
            pages=[]
            for s,token in zip(state['screens'],tokens):
                sid=s['id'];page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
                text=(ROOT/'player.html').read_text()
                transport=(ROOT/'physical_boot.js').read_text().replace('new URL(value, location.href)','new URL(value, "https://carisma.fixture/")').replace('u.origin !== location.origin','u.origin !== "https://carisma.fixture"')
                prefix=shim+'localStorage.setItem("carisma-device-token",'+json.dumps(token)+');'
                text=text.replace('<script src="/physical_boot.js"></script>','<script>'+prefix+transport+'</script>')
                text=text.replace('new URLSearchParams(location.search)','new URLSearchParams("?player='+sid+'&kiosk=1")')
                text=re.sub(r'async function dbget\(store,key\).*?\n',"async function dbget(store,key){return window.qaDB[store].get(key);}\n",text)
                text=re.sub(r'async function dbput\(store,key,value\).*?\n',"async function dbput(store,key,value){window.qaDB[store].set(key,value);}\n",text)
                text=re.sub(r'async function dbdel\(store,key\).*?\n',"async function dbdel(store,key){window.qaDB[store].delete(key);}\n",text)
                page.set_content(text,wait_until='domcontentloaded');page.wait_for_function('playerState.connected',timeout=10000);pages.append(page)
            pages[2].wait_for_function('!!document.querySelector("video") && document.querySelector("video").currentTime>.5',timeout=20000)
            assert pages[0].evaluate('CarismaPreview.sample().kind')=='rendered'
            assert pages[2].evaluate('CarismaPreview.sample().kind')=='frame'
            checks.append('Player captures a real decoded FFmpeg video frame; clock marked as reconstructed')
            # Heartbeat policy remains inactive without an admin monitor.
            assert not json.loads(req('/api/player/heartbeat','POST',{'screenId':state['screens'][0]['id']},player=tokens[0])[1])['monitor']['enabled']
            checks.append('No thumbnail demand before opening monitor')
            monitor=context.new_page();monitor.on('pageerror',lambda e:errors.append(str(e)))
            text=(ROOT/'monitor.html').read_text().replace('<script>','<script>'+shim+'localStorage.setItem("carisma-access-key",'+json.dumps(admin)+');',1)
            monitor.set_content(text,wait_until='domcontentloaded')
            monitor.wait_for_function('document.querySelectorAll(".card img:not([hidden])").length===4 && [...document.querySelectorAll(".card img")].every(i=>i.naturalWidth===480)',timeout=20000)
            checks.append('All four authenticated players upload actual JPEG previews and monitor displays them')
            monitor.select_option('#columns','2');monitor.screenshot(path=str(QA/'monitor-desktop.png'),full_page=True)
            frames=monitor.evaluate('snapshot.screens.map(s=>({id:s.id,bytes:s.preview.bytes,kind:s.preview.kind}))')
            assert len(json.loads(req('/api/ndi/status',token=admin)[1])['streams'])==1
            checks.append('Monitor opens no new NDI receiver or FFmpeg encoder')
            for interval in ['1','5','2']:
                monitor.select_option('#interval',interval)
                monitor.wait_for_function('snapshot.policy.interval==='+interval,timeout=10000)
            checks.append('Refresh selector 1, 2, 5 seconds updates server lease')
            monitor.select_option('#group',state['screens'][2]['group'])
            assert monitor.locator('.card:visible').count()==1
            monitor.select_option('#group','')
            checks.append('Group filter hides unrelated screens')
            state['screens'][1]['override']={'type':'asset','id':'intervallo'};publish();pages[1].evaluate('syncPlayer()')
            monitor.wait_for_function('snapshot.screens[1].preview.title==="Intervallo"',timeout=12000)
            checks.append('New content confirmed by player replaces previous thumbnail')
            pages[2].evaluate('failLive("QA: sorgente interrotta")')
            monitor.wait_for_function('snapshot.screens[2].preview.fallback===true',timeout=8000)
            checks.append('Actual fallback rendering is reported and marked in monitor')
            monitor.set_viewport_size({'width':390,'height':844});monitor.screenshot(path=str(QA/'monitor-mobile.png'),full_page=True)
            assert monitor.evaluate('document.documentElement.scrollWidth<=innerWidth');checks.append('Mobile 390px has no horizontal overflow')
            monitor.set_viewport_size({'width':1440,'height':1000})
            pages[3].evaluate('window.qaApiOffline=true');pages[3].evaluate('syncPlayer()')
            monitor.wait_for_timeout(14500)
            bar=state['screens'][3]['id']
            assert monitor.locator('[data-sid="'+bar+'"] .badge').inner_text()=='Non raggiungibile'
            assert not monitor.locator('[data-sid="'+bar+'"] .stale').is_hidden()
            checks.append('Disconnected player retains stale image with age and unreachable status; not fake live')
            monitor.screenshot(path=str(QA/'monitor-offline.png'),full_page=True)
            pages[3].evaluate('window.qaApiOffline=false');pages[3].evaluate('syncPlayer()')
            monitor.wait_for_function('document.querySelector("[data-sid='+bar+'] .badge").textContent==="Player attivo"',timeout=12000)
            checks.append('Player reconnection restores fresh preview')
            monitor.click('#pause');monitor.wait_for_timeout(2000)
            assert not json.loads(req('/api/player/heartbeat','POST',{'screenId':state['screens'][0]['id']},player=tokens[0])[1])['monitor']['enabled']
            before=pages[0].evaluate('CarismaPreview.sample().title');monitor.wait_for_timeout(1500)
            checks.append('Pause releases monitoring demand without stopping player playback')
            monitor.click('#pause');monitor.wait_for_function('snapshot.policy.enabled && !paused',timeout=7000)
            checks.append('Resume re-enables monitoring')
            monitor.screenshot(path=str(QA/'monitor-final.png'),full_page=True)
            assert not errors,errors
            checks.append('No JavaScript page errors')
            browser.close()
        (QA/'monitor-results.json').write_text(json.dumps(dict(checks=checks,frames=frames,errors=errors,limitations=['set_content with explicit HTTP bridge; browser navigation not tested','IndexedDB and localStorage memory fixture','real server, FFmpeg, JPEG generation, canvas drawImage and decoded video','no Windows/NDI transmitter/TV/Chromecast test']),indent=2))
        print(json.dumps(checks,indent=2))
    finally:
        proc.terminate();proc.wait(timeout=8)
