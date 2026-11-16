/* Organization identity. Local images only; no external services or fonts. */
(() => {
  'use strict';
  const KEY='carisma-branding-v1', ORIGINAL={accent:'#b64528',sidebar:'#202b2a'};
  const originals=new WeakMap(),marks=new WeakMap();
  let current={name:'Carisma',branding:{}}, observer, scheduled=false;
  const rgb=hex=>[1,3,5].map(i=>parseInt(hex.slice(i,i+2),16));
  const hex=values=>'#'+values.map(x=>Math.round(Math.max(0,Math.min(255,x))).toString(16).padStart(2,'0')).join('');
  const mix=(a,b,t)=>hex(rgb(a).map((v,i)=>v*(1-t)+rgb(b)[i]*t));
  function luminance(color){return rgb(color).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;}).reduce((v,c,i)=>v+c*[.2126,.7152,.0722][i],0);}
  function contrast(a,b){const x=luminance(a),y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);}
  function readable(color){while(contrast(color,'#ffffff')<4.5)color=mix(color,'#000000',.07);return color;}
  function palette(pixels){
    const bins=new Map();
    for(let i=0;i<pixels.length;i+=4){
      if(pixels[i+3]<128)continue;
      const c=[pixels[i],pixels[i+1],pixels[i+2]],key=c.map(x=>Math.floor(x/32)).join(',');
      const bin=bins.get(key)||{count:0,sum:[0,0,0]};bin.count++;c.forEach((v,n)=>bin.sum[n]+=v);bins.set(key,bin);
    }
    if(!bins.size)throw Error('Il logo è completamente trasparente.');
    const colors=[...bins.values()].map(x=>({count:x.count,color:x.sum.map(v=>v/x.count)}));
    const chromatic=colors.filter(x=>Math.max(...x.color)-Math.min(...x.color)>30);
    const candidates=chromatic.length?chromatic:colors;
    candidates.sort((a,b)=>b.count*(1+(Math.max(...b.color)-Math.min(...b.color))/255)-a.count*(1+(Math.max(...a.color)-Math.min(...a.color))/255));
    const dominant=hex(candidates[0].color);
    return {accent:readable(dominant),sidebar:mix(dominant,'#101820',.82)};
  }
  function safeTheme(value){return value&&['accent','sidebar'].every(k=>/^#[0-9a-f]{6}$/i.test(value[k]||''))?{accent:readable(value.accent),sidebar:readable(value.sidebar)}:ORIGINAL;}
  function safeLogo(value){return typeof value==='string'&&value.length<=180000&&/^data:image\/png;base64,[a-z0-9+/=]+$/i.test(value)?value:'';}
  function clean(site){const b=site?.branding||{};return {name:String(site?.name||'Carisma').trim().slice(0,80)||'Carisma',branding:{logo:safeLogo(b.logo),theme:b.theme?safeTheme(b.theme):null}};}
  function text(value){return String(value).replace(/Teatro Carisma|Carisma/gi,()=>current.name);}
  function mount(){
    if(!document.body)return;
    observer?.disconnect();
    // Static interface copy only: scripts, editor fields and show contents are untouched.
    const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
    while(walker.nextNode()){
      const node=walker.currentNode;
      if(node.parentElement?.closest('script,style,textarea,pre,code,[contenteditable],#player-canvas,#previewScript,#preview-script,.preview-script,.preview-line,#script'))continue;
      if(!originals.has(node)&&/Carisma|CARISMA/.test(node.nodeValue))originals.set(node,node.nodeValue);
      if(originals.has(node))node.nodeValue=text(originals.get(node));
    }
    document.querySelectorAll('[data-organization-name]').forEach(el=>{el.textContent=current.name;});
    const brand=document.querySelector('.sidebar .brand,.top .brand,header .brand,header>b,.pairbox h1,form>h1');
    document.querySelectorAll('.organization-logo').forEach(el=>el.remove());
    const mark=brand?.querySelector('.brand-mark,.brand-icon');
    if(mark&&marks.has(mark))mark.innerHTML=marks.get(mark);
    if(brand&&current.branding.logo){
      const img=document.createElement('img');img.className='organization-logo';img.src=current.branding.logo;img.alt='Logo '+current.name;
      const target=brand.querySelector('.brand-mark,.brand-icon');
      if(target){if(!marks.has(target))marks.set(target,target.innerHTML);target.replaceChildren(img);}else{brand.prepend(img);}
    }
    if(!document.documentElement.dataset.originalTitle)document.documentElement.dataset.originalTitle=document.title;
    document.title=text(document.documentElement.dataset.originalTitle);
    const theme=safeTheme(current.branding.theme),root=document.documentElement.style;
    root.setProperty('--accent',theme.accent);root.setProperty('--accent-dark',mix(theme.accent,'#000000',.15));
    root.setProperty('--sidebar',theme.sidebar);root.setProperty('--dark',theme.sidebar);root.setProperty('--soft',mix(theme.accent,'#ffffff',.93));
    root.setProperty('--organization-sidebar',theme.sidebar);
    observer?.observe(document.body,{subtree:true,childList:true});
  }
  function apply(site,cache=true){current=clean(site);if(cache)try{localStorage.setItem(KEY,JSON.stringify(current));}catch{}mount();}
  async function logoFile(file){
    if(!file||!['image/png','image/jpeg','image/webp'].includes(file.type))throw Error('Scegli un logo PNG, JPEG o WebP.');
    if(file.size>4*1024*1024)throw Error('Logo troppo grande: massimo 4 MB.');
    const url=URL.createObjectURL(file),img=new Image();
    try{
      await new Promise((resolve,reject)=>{img.onload=resolve;img.onerror=()=>reject(Error('Immagine non leggibile.'));img.src=url;});
      if(img.naturalWidth*img.naturalHeight>24000000)throw Error('Immagine troppo grande: massimo 24 megapixel.');
      const canvas=document.createElement('canvas'),scale=Math.min(1,320/img.naturalWidth,320/img.naturalHeight);
      canvas.width=Math.max(1,Math.round(img.naturalWidth*scale));canvas.height=Math.max(1,Math.round(img.naturalHeight*scale));
      const ctx=canvas.getContext('2d',{willReadFrequently:true});ctx.drawImage(img,0,0,canvas.width,canvas.height);
      let logo=canvas.toDataURL('image/png');
      if(logo.length>180000){const copy=document.createElement('canvas');copy.width=Math.max(1,canvas.width>>1);copy.height=Math.max(1,canvas.height>>1);copy.getContext('2d').drawImage(canvas,0,0,copy.width,copy.height);logo=copy.toDataURL('image/png');}
      if(logo.length>180000)throw Error('Logo troppo complesso. Scegli una versione più semplice.');
      return {logo,theme:palette(ctx.getImageData(0,0,canvas.width,canvas.height).data)};
    }finally{URL.revokeObjectURL(url);}
  }
  function editorMarkup(){return '<section class="settings-card" style="margin-bottom:20px"><h2>Identità dell’organizzazione</h2><p>Nome, logo e colori della tua regia. Il logo compare in piccolo nell’intestazione; i contenuti e il gobbo restano liberi.</p><div class="row"><img id="organization-logo-preview" alt="Anteprima logo" style="width:80px;height:56px;object-fit:contain;background:#f2f4f1;border-radius:8px"><div class="field"><label for="organization-logo">Logo (PNG, JPEG, WebP · massimo 4 MB)</label><input type="file" id="organization-logo" accept="image/png,image/jpeg,image/webp"></div><button type="button" class="btn" id="organization-remove">Rimuovi logo</button></div><div id="organization-proposal" aria-live="polite" style="margin:14px 0"></div><div class="row"><button type="button" class="btn" id="organization-original">Tema originale</button><span id="organization-theme-status" role="status"></span></div><small>Le modifiche si applicano con «Salva impostazioni». Il logo è incluso nell’esportazione del progetto.</small></section>';}
  function bindEditor(site){
    const input=document.getElementById('organization-logo');if(!input)return null;
    let draft=JSON.parse(JSON.stringify(clean(site).branding)),proposal=null;
    const preview=document.getElementById('organization-logo-preview'),status=document.getElementById('organization-theme-status');
    function refresh(){if(draft.logo){preview.src=draft.logo;preview.hidden=false;}else{preview.removeAttribute('src');preview.hidden=true;}status.textContent=draft.theme?'Tema personalizzato selezionato':'Tema originale selezionato';}
    input.onchange=async()=>{try{
      const result=await logoFile(input.files[0]);draft.logo=result.logo;proposal=result.theme;refresh();
      const box=document.getElementById('organization-proposal');box.replaceChildren();
      const label=document.createElement('p');label.textContent='Tema suggerito dai colori del logo';box.append(label);
      for(const color of [proposal.accent,proposal.sidebar]){const chip=document.createElement('span');chip.style.cssText='display:inline-block;padding:8px 12px;margin:0 8px 8px 0;border-radius:6px;color:white;background:'+color;chip.textContent=color;box.append(chip);}
      const use=document.createElement('button');use.type='button';use.className='btn primary';use.textContent='Usa tema dal logo';use.onclick=()=>{draft.theme={...proposal};refresh();};box.append(use);
    }catch(error){document.getElementById('organization-proposal').textContent=error.message;}finally{input.value='';}};
    document.getElementById('organization-remove').onclick=()=>{draft.logo='';proposal=null;document.getElementById('organization-proposal').replaceChildren();refresh();};
    document.getElementById('organization-original').onclick=()=>{draft.theme=null;refresh();};refresh();
    return ()=>JSON.parse(JSON.stringify(draft));
  }
  window.OrganizationBranding={apply,text,palette,contrast,readable,safeLogo,logoFile,editorMarkup,bindEditor};
  if(typeof document==='undefined')return;
  document.addEventListener('DOMContentLoaded',()=>{
    const css=document.createElement('style');css.textContent='.organization-logo{display:inline-block;vertical-align:middle;object-fit:contain;width:38px;height:32px;margin-right:9px;border-radius:4px;background:#fff;padding:3px;flex-shrink:0}.brand-mark .organization-logo,.brand-icon .organization-logo{margin:0;width:100%;height:100%}.sidebar .brand>div:last-child{min-width:0}.sidebar .brand strong{display:block;white-space:normal;overflow-wrap:anywhere;font-size:14px;line-height:1.25;max-width:150px}.top .brand{max-width:55%;font-size:14px;letter-spacing:.4px}.sidebar,header.top{background:var(--organization-sidebar,var(--sidebar))}.topnav a,.topnav button{color:#fff}.btn.primary{color:#fff}';document.head.append(css);
    try{const saved=JSON.parse(localStorage.getItem(KEY)||'null');if(saved)current=clean(saved);}catch{}
    observer=new MutationObserver(records=>{if(scheduled||records.every(r=>r.target.parentElement?.closest('#status,#script,#player-canvas,.preview-script')||r.target.closest?.('#status,#script,#player-canvas,.preview-script')))return;scheduled=true;requestAnimationFrame(()=>{scheduled=false;mount();});});mount();
    // Pairing pages need the identity only, never project data or access tokens.
    if(location.protocol!=='file:'&&!window.CARISMA_PHYSICAL&&!new URLSearchParams(location.search).has('demo')){
      const update=()=>fetch('/api/branding',{cache:'no-store',signal:AbortSignal.timeout(2500)}).then(r=>r.ok?r.json():Promise.reject()).then(site=>apply(site)).catch(()=>{});
      update();setInterval(update,10000);
    }
  });
})();
