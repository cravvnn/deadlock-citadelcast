"use strict";
const assert = require("node:assert/strict");
const test = require("node:test");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const {Model} = require("../scripts/recap_model.js");
const identity = {matchId:"match-fixture", playerId:"player-fixture"};
function event(id,time,kind,value=1) { return {...identity,id,time,kind,value}; }
function model(start=0) { return new Model(identity.matchId,identity.playerId,start); }
function snap(m,now) { m.confirmThrough(now); return m.snapshot(now,identity); }
test("rolling boundary excludes exactly 120s-old events and future time",()=>{
    const m=model(); m.ingest(event("old",5,"kill")); m.ingest(event("in",5.001,"kill"));
    m.ingest(event("now",125,"assist")); const p=snap(m,125);
    assert.equal(p.kills,1); assert.equal(p.assists,1); assert.equal(p.windowSeconds,120);
    assert.equal(m.snapshot(124,identity),null);
});
test("partial coverage has an honest duration; unconfirmed/stale feed suppressed",()=>{
    const m=model(100); m.ingest(event("k",120,"kill"));
    assert.equal(m.snapshot(130,identity),null);
    assert.equal(snap(m,130).windowSeconds,30); assert.equal(snap(m,130).windowComplete,false);
    assert.equal(m.snapshot(131,identity),null);
});
test("duplicate and other-player events cannot inflate stats",()=>{
    const m=model(); assert.ok(m.ingest(event("a",10,"kill")));
    assert.equal(m.ingest(event("a",10,"kill")),false);
    assert.equal(m.ingest({...event("b",11,"kill"),playerId:"other"}),false);
    assert.equal(snap(m,120).kills,1);
    assert.equal(m.snapshot(120,{...identity,matchId:"different"}),null);
});
test("earned souls are explicit income, wallet/net-worth are rejected",()=>{
    const m=model(); m.ingest(event("income",10,"soulsEarned",1500));
    assert.throws(()=>m.ingest(event("wallet",11,"wallet",800)),/unsupported/);
    assert.equal(snap(m,120).soulsEarned,1500);
    assert.throws(()=>m.ingest(event("bad",121,"kill",NaN)),/invalid/);
});
test("seek, out-of-order correction and feed gap invalidate coverage",()=>{
    const m=model(); m.ingest(event("new",20,"kill"));
    assert.equal(m.ingest(event("late",10,"assist")),false); assert.equal(snap(m,120),null);
    const n=model(); n.invalidate(); assert.equal(snap(n,120),null);
    const p=model(); p.confirmThrough(100); assert.equal(p.confirmThrough(99),false);
    assert.equal(p.snapshot(100,identity),null);
    const q=model(); q.confirmThrough(100); assert.equal(q.ingest(event("after-attestation",50,"kill")),false);
    assert.equal(q.snapshot(100,identity),null);
});
test("bounded history fails closed instead of truncating to misleading totals",()=>{
    const m=model(); for(let n=0;n<4096;n++) m.ingest(event(String(n),n/100,"kill"));
    assert.equal(m.ingest(event("overflow",50,"kill")),false); assert.equal(snap(m,120),null);
});
function ui() {
    const classes={},nodes={},jobs=[];
    const panel={SetHasClass:(k,v)=>classes[k]=v};
    const $=id=>nodes[id]||(nodes[id]={text:"",style:{}});
    $.GetContextPanel=()=>panel; $.Schedule=(delay,fn)=>jobs.push({delay,fn});
    vm.runInNewContext(fs.readFileSync(path.join(__dirname,"../panorama/scripts/citadelcast/hero_recap.js"),"utf8"),{$,isFinite});
    return {api:panel.CitadelCastRecap,classes,nodes,jobs};
}
const context={...identity,takeId:"take1",offair:true,observer:true,cameraSettled:true,mode:"turn-with-hero",now:120,playerName:"<img src=x>"};
const payload={...identity,windowSeconds:120,kills:2,assists:3,soulsEarned:3200,asOf:120};
test("native controller waits for settled observer camera and matching fresh data",()=>{
    const u=ui(); assert.equal(u.classes.Visible,false);
    assert.equal(u.api.show({...context,cameraSettled:false},payload),false);
    assert.equal(u.api.show(context,{...payload,playerId:"other"}),false);
    assert.equal(u.api.show({...context,now:122},payload),false);
    assert.equal(u.api.show({...context,matchId:undefined},{...payload,matchId:undefined}),false);
    assert.equal(u.api.show(context,{...payload,kills:1.5}),false);
    assert.equal(u.api.show(context,payload),true); assert.equal(u.nodes["#RecapPlayer"].text,context.playerName);
});
test("target/camera cancellation immediately hides; heartbeat loss expires",()=>{
    const u=ui(); u.api.show(context,payload);
    assert.equal(u.api.sync({...context,playerId:"new"}),false); assert.equal(u.classes.Visible,false);
    u.api.show(context,payload); u.jobs.at(-2).fn(); assert.equal(u.classes.Visible,false);
});
test("old scheduled fade cannot erase a newer take",()=>{
    const u=ui(); u.api.show(context,payload); const oldFade=u.jobs.at(-1).fn;
    u.api.show({...context,takeId:"take2"},payload); oldFade(); assert.equal(u.classes.Visible,true);
    u.api.sync({...context,takeId:"take2"}); u.jobs.at(-1).fn(); assert.equal(u.classes.Visible,false);
});
test("unsafe world projection hides and never clamps a misleading head label",()=>{
    const u=ui(); u.api.show(context,payload);
    assert.equal(u.api.anchor(context,{visible:true,occluded:false,x:1100,y:260,viewportWidth:1920,viewportHeight:1080}),true);
    assert.equal(u.classes.HeadAnchor,true);
    assert.equal(u.api.anchor(context,{visible:true,occluded:true,x:1100,y:260,viewportWidth:1920,viewportHeight:1080}),false);
    assert.equal(u.classes.Visible,false);
});
