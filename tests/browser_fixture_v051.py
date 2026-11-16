"""UI fixtures only: browser navigation blocked by managed policy.
Uses set_content + in-memory storage and an explicit transport adapter to real
local HTTP APIs. Does NOT claim native Android/WebView, persistent IDB or LAN QA.
"""
import base64,json,re,sys,tempfile,subprocess,socket,time,urllib.request,urllib.error
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
QA=ROOT/'qa_v051';QA.mkdir(exist_ok=True)
checks=[]
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
        sid=state['screens'][0]['id'];state['screens'][0]['override']={'type':'asset','id':'orologio'};state['screens'][0]['fallbackAssetId']='orologio'
        assert req('/api/state','PUT',{'revision':0,'state':state},token=admin)[0]==200
        def publish():
            current=json.loads(req('/api/state',token=admin)[1]);assert req('/api/state','PUT',{'revision':current['revision'],'state':state},token=admin)[0]==200
        code=json.loads(req('/api/devices/pair-code','POST',{'screenId':sid},token=admin)[1])['code']
        device=json.loads(req('/api/player/pair','POST',{'code':code,'name':'Chromecast / fixture'})[1]);token=device['token']
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=__import__('os').environ.get('CARISMA_QA_CHROMIUM','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
            context=browser.new_context(viewport={'width':1280,'height':720},reduced_motion='reduce')
            def bridge(source,args):
                if not args['path'].startswith('/api/'):raise ValueError('Only API transport')
                body=args.get('body');data=body.encode() if body else None
                # Use known fixture credentials for the JS transport.
                headers=args.get('headers',{})
                status,raw=req(args['path'],args.get('method','GET'),data,token=headers.get('x-control-token'),player=headers.get('x-player-token'))
                return dict(status=status,body=base64.b64encode(raw).decode())
            context.expose_binding('qaHTTP',bridge)
            shim="""
            window.qaStorage=new Map();window.qaDB={media:new Map(),snapshots:new Map()};window.qaApiOffline=false;
            Object.defineProperty(window,'localStorage',{value:{getItem:k=>window.qaStorage.get(k)||null,setItem:(k,v)=>window.qaStorage.set(k,v),removeItem:k=>window.qaStorage.delete(k)},configurable:true});
            window.fetch=async(url,opts={})=>{if(window.qaApiOffline)throw Error('QA transport offline');const r=await window.qaHTTP({path:String(url),method:opts.method||'GET',body:opts.body||null,headers:Object.fromEntries(new Headers(opts.headers||{}).entries())});const b=Uint8Array.from(atob(r.body),c=>c.charCodeAt(0));return new Response(b,{status:r.status,headers:{'Content-Type':'application/json'}});};
            """
            errors=[]
            # Use an API-generated code in the admin fixture.
            page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            text=(ROOT/'players.html').read_text();text=text.replace("location.origin+'/connect.html'",json.dumps('http://192.168.1.20:8787/connect.html'))
            text=text.replace('<script>','<script>'+shim+'localStorage.setItem("carisma-access-key",'+json.dumps(admin)+');',1)
            page.set_content(text,wait_until='domcontentloaded');page.wait_for_function("document.querySelector('#screen').options.length===4")
            page.click('#generate');page.wait_for_function("document.querySelector('#code').textContent.length===9")
            page.screenshot(path=str(QA/'pairing-desktop.png'),full_page=True);checks.append('Console pairing: select screen, generate code from real API, list paired device')
            page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(QA/'pairing-mobile.png'),full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');checks.append('Console mobile width 390px without horizontal overflow')
            page.close()
            def player_page(snapshot=None):
                page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
                text=(ROOT/'player.html').read_text()
                transport=(ROOT/'physical_boot.js').read_text().replace('new URL(value, location.href)','new URL(value, "https://carisma.fixture/")').replace('u.origin !== location.origin','u.origin !== "https://carisma.fixture"')
                prefix=shim+'localStorage.setItem("carisma-device-token",'+json.dumps(token)+');'
                if snapshot is not None:
                    prefix+='window.qaDB.snapshots.set('+json.dumps(sid)+','+json.dumps(snapshot)+');window.qaApiOffline=true;'
                text=text.replace('<script src="/physical_boot.js"></script>','<script>'+prefix+transport+'</script>')
                text=text.replace('new URLSearchParams(location.search)','new URLSearchParams("?player='+sid+'&kiosk=1")')
                # Replace storage in fixtures only.
                text=re.sub(r'async function dbget\(store,key\).*?\n',"async function dbget(store,key){return window.qaDB[store].get(key);}\n",text)
                text=re.sub(r'async function dbput\(store,key,value\).*?\n',"async function dbput(store,key,value){window.qaDB[store].set(key,value);}\n",text)
                text=re.sub(r'async function dbdel\(store,key\).*?\n',"async function dbdel(store,key){window.qaDB[store].delete(key);}\n",text)
                page.set_content(text,wait_until='domcontentloaded');return page
            page=player_page();page.wait_for_function('playerState.connected && !!document.querySelector(".dc-time")',timeout=10000)
            page.screenshot(path=str(QA/'player-clock.png'));checks.append('Player shell renders animated clock with real scoped server state')
            page.evaluate('window.qaApiOffline=true');page.evaluate('syncPlayer()')
            state['screens'][0]['override']={'type':'asset','id':'intervallo'};publish()
            page.wait_for_timeout(700);assert page.locator('.dc-time').count()==1;checks.append('Transport outage holds old clock despite a new server assignment')
            page.evaluate('window.qaApiOffline=false');page.evaluate('syncPlayer()')
            page.wait_for_function('playerState.effectiveTitle==="Intervallo"',timeout=6000);checks.append('Transport restored applies updated content')
            # Simulate offline reopening with an injected snapshot.
            state['screens'][0]['override']={'type':'asset','id':'orologio'};publish();page.evaluate('syncPlayer()')
            page.wait_for_function('playerState.effectiveTitle==="Orologio e data"')
            saved=page.evaluate('window.qaDB.snapshots.get('+json.dumps(sid)+')')
            offline=player_page(saved);offline.wait_for_function('!!document.querySelector(".dc-time")',timeout=6000)
            assert not offline.evaluate('playerState.connected');offline.close();checks.append('Packaged shell boots from injected snapshot while API unavailable (not a persistence test)')
            # Play real server/FFmpeg fMP4 through MediaSource.
            state['assets'].append({'id':'test-live','title':'Test NON NDI','kind':'live','protocol':'ndi-test','profile':'light','sourceName':''})
            state['screens'][0]['override']={'type':'asset','id':'test-live'};publish();page.evaluate('syncPlayer()')
            page.wait_for_function('!!document.querySelector("video") && document.querySelector("video").currentTime>0.4',timeout=25000)
            initial=page.evaluate('document.querySelector("video").currentTime');page.wait_for_timeout(1200);later=page.evaluate('document.querySelector("video").currentTime');assert later>initial
            page.screenshot(path=str(QA/'player-video.png'));checks.append('Real FFmpeg H264/AAC fragments rendered by Chromium: advancing currentTime')
            second=player_page();second.wait_for_function('!!document.querySelector("video") && document.querySelector("video").currentTime>0.4',timeout=20000)
            status=json.loads(req('/api/ndi/status',token=admin)[1]);assert len(status['streams'])==1;checks.append('Two player fixtures share one actual FFmpeg encoder')
            page.evaluate('window.qaApiOffline=true');page.evaluate('syncPlayer()');page.wait_for_function('!!document.querySelector(".dc-time")',timeout=6000);checks.append('Live transport loss switches to local clock fallback')
            page.evaluate('window.qaApiOffline=false');page.evaluate('syncPlayer()');page.wait_for_function('!!document.querySelector("video") && document.querySelector("video").currentTime>0.4',timeout=22000);checks.append('Live resumes after transport reconnection')
            assert not errors,errors
            checks.append('No JavaScript page errors during completed fixtures')
            browser.close()
        (QA/'results.json').write_text(json.dumps({'checks':checks,'limitations':['set_content fixture; browser managed policy blocked navigation','in-memory storage substituted; no durable storage test','HTTP/API and FFmpeg real; transport adapter in browser','No Android runtime or native APK compilation']},indent=2))
        print(json.dumps(checks,indent=2))
    finally:
        proc.terminate();proc.wait(timeout=8)
