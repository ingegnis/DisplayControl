'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const ctx=vm.createContext({window:{}});vm.runInContext(fs.readFileSync(__dirname+'/../branding.js','utf8'),ctx);
const b=ctx.window.OrganizationBranding;
const pixels=[];for(let i=0;i<200;i++)pixels.push(255,255,255,255);for(let i=0;i<80;i++)pixels.push(20,110,240,255);for(let i=0;i<100;i++)pixels.push(0,0,0,0);
const theme=b.palette(pixels);assert(b.contrast(theme.accent,'#ffffff')>=4.5);assert(b.contrast(theme.sidebar,'#ffffff')>=4.5);
assert(parseInt(theme.accent.slice(5),16)>parseInt(theme.accent.slice(1,3),16));
assert.throws(()=>b.palette([0,0,0,0]));assert.equal(b.safeLogo('https://outside/logo.png'),'');assert.equal(b.safeLogo('data:image/svg+xml,<svg onload=alert(1)>'),'');
for(let n=0;n<256;n+=8){const color='#'+[n,255-n,n].map(x=>x.toString(16).padStart(2,'0')).join('');assert(b.contrast(b.readable(color),'#ffffff')>=4.5);}
console.log('Branding: palette, transparency, contrast and local-only image checks passed.');
