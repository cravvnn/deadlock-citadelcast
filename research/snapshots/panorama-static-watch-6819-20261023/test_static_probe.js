"use strict";
const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
function fixture(){
 const queue=[],logs=[],classes={},state={rootValid:true,probeValid:true,spectator:false,deletes:0};
 const root={IsValid:()=>state.rootValid,FindChildTraverse:id=>id==='spectate_bar'?bar:probe,GetParent:()=>null,BHasClass:c=>c==='TeamSpectator'&&state.spectator};
 const bar={IsValid:()=>true,BHasClass:()=>false,GetParent:()=>root};
 const probe={IsValid:()=>state.probeValid,SetHasClass:(k,v)=>classes[k]=v,DeleteAsync:()=>{state.deletes++}};
 const $={GetContextPanel:()=>root,Msg:s=>logs.push(s),Schedule:(delay,fn)=>queue.push({delay,fn})};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'panorama/scripts/citadelcast/static_probe.js'),'utf8'),{$});
 return {state,queue,logs,classes,step(n=1){for(let i=0;i<n;i++){assert.ok(queue.length);queue.shift().fn()}}};
}
test('non-spectator never shows; waiting ends after bounded 10-minute schedule',()=>{
 const f=fixture();f.step(2400);assert.notEqual(f.classes.CCStaticVisible,true);assert.equal(f.queue.length,0);assert.equal(f.state.deletes,1);assert.match(f.logs.at(-1),/waiting_limit/);
});
test('native ancestor spectator class enables a single 3s/12s fixture and deletion',()=>{
 const f=fixture();f.state.spectator=true;f.step(11);assert.notEqual(f.classes.CCStaticVisible,true);
 f.step();assert.equal(f.classes.CCStaticVisible,true);f.step(48);assert.equal(f.classes.CCStaticVisible,false);
 assert.equal(f.state.deletes,1);assert.equal(f.queue.length,0);assert.match(f.logs.at(-1),/complete_12s/);
 assert.equal(f.logs.filter(s=>s.includes('shown;')).length,1);
});
test('brief spectator state does not arm; loss after showing clears immediately',()=>{
 const f=fixture();f.state.spectator=true;f.step(8);f.state.spectator=false;f.step();f.state.spectator=true;f.step(11);assert.notEqual(f.classes.CCStaticVisible,true);f.step();f.state.spectator=false;f.step();assert.equal(f.classes.CCStaticVisible,false);assert.match(f.logs.at(-1),/context_lost/);
});
test('destroyed HUD/probe ends without any rescheduled work',()=>{
 const f=fixture();f.state.rootValid=false;f.step();assert.equal(f.queue.length,0);assert.match(f.logs.at(-1),/hud_destroyed/);
 const g=fixture();g.state.probeValid=false;g.step();assert.equal(g.queue.length,0);assert.match(g.logs.at(-1),/probe_missing/);
});
