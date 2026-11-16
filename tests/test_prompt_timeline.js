'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const ctx=vm.createContext({window:{}});vm.runInContext(fs.readFileSync(__dirname+'/../prompt_shared.js','utf8'),ctx);
const {Timeline,WIDTH,HEIGHT}=ctx.window.PromptShared;
let now=0;const t=new Timeline(()=>now);
assert(t.receive({seq:10,offsetVh:.5,playing:true,rate:.1},0));now=1000;assert.equal(t.offset(),.6);
// Duplicated polls, stale samples, delayed replies and a restarted server cannot rewind.
assert(t.receive({seq:10,offsetVh:.1,playing:true,rate:.1},1000));assert.equal(t.offset(),.6);
assert.equal(t.receive({seq:9,offsetVh:0,playing:false,rate:0},0),false);
now=21000;assert.equal(t.offset(),2.6);assert(t.receive({seq:10,offsetVh:2.6,playing:true,rate:.1},21000));assert.equal(t.offset(),2.6);
assert(t.receive({seq:11,offsetVh:2.6,playing:false,rate:.1},21000));now=31000;assert.equal(t.offset(),2.6);
assert(t.receive({seq:12,offsetVh:0,playing:false,rate:0},31000));assert.equal(t.offset(),0);
const p=new Timeline(()=>now);p.receive({seq:12,offsetVh:0,playing:false,rate:0});assert.equal(p.offset(),t.offset());
assert.equal(WIDTH,1280);assert.equal(HEIGHT,720);
for(const page of ['prompt.html','prompt_player.html']){
  const html=fs.readFileSync(__dirname+'/../'+page,'utf8');assert(html.includes('prompt_shared.js'));assert(html.includes('new PromptShared.Viewport'));assert(html.includes('new PromptShared.Timeline'));
}
console.log('Prompt timeline: offline continuity, same-sequence reconnect, stale response rejection, STOP and shared layout passed.');
