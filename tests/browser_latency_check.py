"""Measure browser queue and startup on a local test generator, NOT NDI E2E.
The browser uses an explicit HTTP transport bridge, no navigation/storage claims.
Run separately in responsive/stable modes for comparable buffering measurements.
"""
import argparse,base64,json,socket,statistics,subprocess,sys,tempfile,time,urllib.error,urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
QA=ROOT/'qa_v051';QA.mkdir(exist_ok=True)
p=argparse.ArgumentParser();p.add_argument('--mode',choices=['responsive','stable'],default='responsive');args=p.parse_args()
with tempfile.TemporaryDirectory() as folder:
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    origin='http://127.0.0.1:'+str(port)
    proc=subprocess.Popen([sys.executable,str(ROOT/'server.py'),'--port',str(port),'--data-dir',folder,'--live-mode',args.mode],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    def req(path,method='GET',body=None):
        headers={'X-Control-Token':token} if 'token' in locals() else {}
        if isinstance(body,str):headers['Content-Type']='application/json';body=body.encode()
        # Load the token after server startup.
        if (Path(folder)/'access.key').exists():headers['X-Control-Token']=(Path(folder)/'access.key').read_text().strip()
        r=urllib.request.Request(origin+path,data=body,headers=headers,method=method)
        try:
            with urllib.request.urlopen(r,timeout=8) as response:return response.status,response.read()
        except urllib.error.HTTPError as e:
            with e:
                return e.code,e.read()
    try:
        for _ in range(80):
            try:req('/api/info');break
            except OSError:time.sleep(.1)
        checks=[];errors=[];navigation='not attempted'
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
            context=browser.new_context(viewport={'width':960,'height':640})
            probe=context.new_page()
            try:
                probe.goto(origin,wait_until='domcontentloaded',timeout=5000)
                navigation='HTTP navigation loaded: '+str(probe.url)
            except Exception as e:navigation=str(e).splitlines()[0]
            probe.close()
            def bridge(source,request):
                status,raw=req(request['path'],request.get('method','GET'),request.get('body'))
                return {'status':status,'body':base64.b64encode(raw).decode()}
            context.expose_binding('qaHTTP',bridge)
            text=(ROOT/'index.html').read_text()
            js=text[text.index('function livePlaybackPolicy'):text.index('// Extra handlers')]
            page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            shim='''
             window.statuses=[];window.clientErrors=[];window.blockMediaUntil=0;
             async function api(path,opts={}){
              if(Date.now()<window.blockMediaUntil&&String(path).includes('/manifest/')){
               await new Promise(r=>setTimeout(r,window.blockMediaUntil-Date.now()));
              }
              const r=await qaHTTP({path,method:opts.method||'GET',body:opts.body||null});
              const bytes=Uint8Array.from(atob(r.body),c=>c.charCodeAt(0));
              if(r.status>=400)throw Error('HTTP '+r.status);
              return new Response(bytes,{status:r.status});
             }
             async function apiJSON(path,opts={}){return (await api(path,opts)).json();}
            '''
            page.set_content('<html><body style="background:#15251e;color:white"><h1>Carisma / '+args.mode+'</h1><video id="v" style="width:640px" muted playsinline></video><p id="label"></p><script>'+shim+js+'''
             window.v=document.querySelector('video');window.client=new CarismaLiveClient(v,{protocol:'ndi-test',profile:'light'}, {
              status:s=>{document.querySelector('#label').textContent=s;statuses.push(s);},error:e=>clientErrors.push(e)
             });
             client.start();
             </script></body></html>''',wait_until='domcontentloaded')
            started=time.monotonic()
            page.wait_for_function('v.currentTime>0 && v.readyState>=3 && !v.paused',timeout=20000)
            startup=time.monotonic()-started
            samples=[]
            for _ in range(50):
                page.wait_for_timeout(200)
                samples.append(page.evaluate('''()=>({time:v.currentTime,buffer:v.buffered.length?v.buffered.end(v.buffered.length-1)-v.currentTime:0,ready:v.readyState,paused:v.paused,catchups:client.catchups,frames:v.getVideoPlaybackQuality?.().totalVideoFrames||0,dropped:v.getVideoPlaybackQuality?.().droppedVideoFrames||0})'''))
            assert samples[-1]['time']>samples[0]['time']+8,samples
            assert samples[-1]['frames']>samples[0]['frames']
            assert not page.evaluate('clientErrors'),page.evaluate('clientErrors')
            checks.append('MediaSource displays actual FFmpeg H264/AAC; time and decoded frames advance')
            assert all(s['ready']>=3 and not s['paused'] for s in samples),samples
            checks.append('No starvation observed during 50 periodic samples')
            if args.mode=='responsive':
                assert statistics.mean(s['buffer'] for s in samples)<1.2,samples
                checks.append('Mean player queue below 1.2 seconds in this fixture')
                # Stall manifest delivery only.
                before=page.evaluate('v.currentTime');page.evaluate('blockMediaUntil=Date.now()+5000')
                page.wait_for_timeout(6500)
                page.wait_for_function('v.readyState>=3 && v.buffered.length>0 && v.currentTime>0 && v.buffered.end(v.buffered.length-1)-v.currentTime<1.3',timeout=8000)
                checks.append('After a 5-second manifest stall, skips stale segments and returns near live edge')
                # Invoke the live button's recovery method.
                page.evaluate('v.pause();client.goLive()')
                page.wait_for_function('!v.paused && v.readyState>=3',timeout=5000)
                checks.append('Torna alla diretta resumes paused playback')
            page.screenshot(path=str(QA/('latency-'+args.mode+'.png')))
            assert not errors,errors
            result={'mode':args.mode,'firstPlaybackSeconds':round(startup,3),'samples':len(samples),
                    'meanPlayerQueueSeconds':round(statistics.mean(s['buffer'] for s in samples),3),
                    'minPlayerQueueSeconds':round(min(s['buffer'] for s in samples),3),
                    'maxPlayerQueueSeconds':round(max(s['buffer'] for s in samples),3),
                    'decodedFramesDuringSampling':samples[-1]['frames']-samples[0]['frames'],
                    'droppedFramesDuringSampling':samples[-1]['dropped']-samples[0]['dropped'],
                    'checks':checks,'navigationProbe':navigation,
                    'limitations':['test generator, not NDI sender','queue measurement, not glass-to-glass latency','set_content plus HTTP transport bridge','no durable storage or Chromecast test','short-run Chromium/Linux, not 24/7 performance'],
                    'rawSamples':samples}
            (QA/('latency-'+args.mode+'.json')).write_text(json.dumps(result,indent=2))
            print(json.dumps({k:v for k,v in result.items() if k!='rawSamples'},indent=2))
            page.evaluate('client.stop()');browser.close()
    finally:
        proc.terminate()
        try:proc.wait(timeout=8)
        except subprocess.TimeoutExpired:proc.kill();proc.wait()
