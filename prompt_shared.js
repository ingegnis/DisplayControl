/* Shared Prompt layout/timeline: offsetVh and rate use a fixed 1280x720 page.
 */
(() => {
  'use strict';
  const WIDTH=1280,HEIGHT=720,READING=HEIGHT*.38;
  class Timeline {
    constructor(clock=()=>performance.now()){this.clock=clock;this.runtime=null;this.received=0;this.sampleTime=0;}
    receive(runtime,sentAt=this.clock()){
      const now=this.clock(),seq=Number(runtime?.seq);
      if(!runtime||!Number.isFinite(seq)||!Number.isFinite(Number(runtime.offsetVh)))return false;
      if(this.runtime&&seq<Number(this.runtime.seq))return false;
      if(this.runtime&&seq===Number(this.runtime.seq)){
        // Keep the monotonic timeline across duplicate polls and outages.
        return true;
      }
      this.runtime={...runtime};this.received=now;
      if(runtime.playing)this.runtime.offsetVh=Number(runtime.offsetVh)+(Number(runtime.rate)||0)*Math.min(.5,Math.max(0,now-sentAt)/2000);
      return true;
    }
    offset(){if(!this.runtime)return 0;return Math.max(0,Number(this.runtime.offsetVh)+(this.runtime.playing?(Number(this.runtime.rate)||0)*(this.clock()-this.received)/1000:0));}
    snapshot(){return this.runtime?{...this.runtime,offsetVh:this.offset()}:null;}
    restore(runtime,cachedAt){if(!runtime)return;const age=Math.max(0,Math.min(3600,(Date.now()-Number(cachedAt||Date.now()))/1000));this.receive({...runtime,offsetVh:Number(runtime.offsetVh)+(runtime.playing?(Number(runtime.rate)||0)*age:0)});}
  }
  class Viewport {
    constructor(host,script,reading,message,blackout){
      this.host=host;this.script=script;this.reading=reading;this.message=message;this.blackout=blackout;this.lines=new Map();
      this.stage=document.createElement('div');this.stage.className='prompt-stage';
      this.stage.style.cssText='position:absolute;width:1280px;height:720px;left:50%;top:50%;transform-origin:center;overflow:hidden;';
      host.style.overflow='hidden';host.append(this.stage);
      for(const el of [script,reading,message,blackout])if(el)this.stage.append(el);
      script.style.cssText='position:absolute;left:115.2px;right:115.2px;top:0;padding-top:273.6px;padding-bottom:504px;line-height:1.33;font-weight:600;letter-spacing:.01em;will-change:transform;';
      if(reading)reading.style.cssText='position:absolute;left:51.2px;right:51.2px;top:273.6px;height:2px;background:#de5e37;z-index:5;';
      if(message)message.style.cssText='position:absolute;left:89.6px;right:89.6px;top:36px;padding:12px 24px;background:#ba4a29;color:white;border-radius:7px;z-index:80;text-align:center;font:700 21.6px Arial,sans-serif;display:none;';
      if(blackout)blackout.style.cssText='position:absolute;inset:0;background:black;z-index:100;display:none;';
      new ResizeObserver(()=>this.fit()).observe(host);this.fit();
    }
    fit(){const scale=Math.min(this.host.clientWidth/WIDTH,this.host.clientHeight/HEIGHT);this.stage.style.transform=`translate(-50%,-50%) scale(${scale})`;this.scale=scale;}
    settings(settings={}){
      const fonts={classic:'Arial,"Liberation Sans",sans-serif',wide:'Verdana,"DejaVu Sans",sans-serif',serif:'Georgia,"Liberation Serif",serif'};
      const sizes={medium:32.4,large:41.04,xlarge:50.4},themes={white:['#000','#f4f4f0'],amber:['#050403','#ffc56b'],inverse:['#f1f0e9','#111']};
      const theme=themes[settings.theme]||themes.white;this.stage.style.background=theme[0];this.stage.style.color=theme[1];
      this.script.style.fontFamily=fonts[settings.font]||fonts.classic;this.script.style.fontSize=(sizes[settings.size]||sizes.large)+'px';
      if(this.reading)this.reading.style.display=settings.readingLine===false?'none':'block';
    }
    render(project){
      this.project=project;this.settings(project.settings);this.script.replaceChildren();this.lines.clear();
      for(const line of project.script.lines){
        const el=document.createElement('div');el.className='prompt-logical-line'+(!line.text?' blank':'');el.dataset.lineId=line.id;
        el.style.cssText='min-height:'+(line.text?'1.33em':'.75em')+';margin:0 0 '+(line.text?'.45em':'0')+';white-space:pre-wrap;overflow-wrap:anywhere;';
        el.textContent=line.text||'\u00a0';this.script.append(el);this.lines.set(line.id,el);
      }
    }
    target(anchor,offset){
      const cues=this.project?.script.cues||[],cue=cues.find(c=>c.id===anchor)||cues[0],line=cue&&this.lines.get(cue.lineId);
      const base=line?Math.max(0,line.offsetTop-READING):0,max=Math.max(0,this.script.scrollHeight-HEIGHT*.62);
      return Math.max(0,Math.min(max,base+Math.max(0,offset)*HEIGHT));
    }
    draw(runtime,offset){
      if(!runtime||!this.project)return 0;
      const target=this.target(runtime.anchor,offset);this.script.style.transform=`translate3d(0,${-target}px,0)`;
      if(this.blackout)this.blackout.style.display=runtime.blackout?'block':'none';
      if(this.message){this.message.textContent=runtime.message||'';this.message.style.display=runtime.message?'block':'none';}
      return target;
    }
  }
  window.PromptShared={Timeline,Viewport,WIDTH,HEIGHT,READING};
})();
