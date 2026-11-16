'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync(__dirname+'/../index.html','utf8');
const js=html.slice(html.indexOf('function livePlaybackPolicy'),html.indexOf('class CarismaLiveClient'));
const context=vm.createContext({});vm.runInContext(js,context);
let checks=0;
function check(test){test();checks++;}
const policy=context.livePlaybackPolicy,position=context.livePosition;
check(()=>assert.equal(policy().targetBufferSeconds,2));
check(()=>assert.equal(policy().pollMs,500));
const reactive=policy({mode:'responsive',targetBufferSeconds:.75,maxBufferSeconds:1.8,pollMs:100,initialSegments:3});
check(()=>assert.equal(reactive.mode,'responsive'));
check(()=>assert.equal(reactive.pollMs,100));
check(()=>assert.equal(policy({targetBufferSeconds:-3}).targetBufferSeconds,2));
check(()=>assert.equal(policy({pollMs:0}).pollMs,500));
check(()=>assert.equal(policy({maxBufferSeconds:0}).maxBufferSeconds,5));
check(()=>assert.equal(position(1,4,0,false,false,reactive).time,3.25));
check(()=>assert.equal(position(1,4,3.4,true,false,reactive).seek,false));
check(()=>assert.equal(position(1,4,1.1,true,false,reactive).seek,true));
check(()=>assert.equal(position(1,4,3.4,true,true,reactive).seek,true));
check(()=>assert.equal(position(4,4.3,0,false,false,reactive).time,4.02));
check(()=>assert.equal(position(4,5,5.5,true,false,reactive).seek,true));
check(()=>assert.equal(position(4,5,3.5,true,false,reactive).seek,true));
for(const file of ['demo_compatta.html','player.html','android-player/assets/player.html']){
 const t=fs.readFileSync(__dirname+'/../'+file,'utf8');
 check(()=>assert.equal(t.slice(t.indexOf('function livePlaybackPolicy'),t.indexOf('// Extra handlers')),html.slice(html.indexOf('function livePlaybackPolicy'),html.indexOf('// Extra handlers'))));
}
console.log(checks+' JS latency/recovery checks passed.');
