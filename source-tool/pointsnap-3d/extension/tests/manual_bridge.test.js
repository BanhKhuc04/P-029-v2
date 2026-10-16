'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
function bridge(){
  const handlers=new Map(),frames=[],sent=[],rendered=[],timers=[];
  const events=new Map();
  const identity=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1];
  const state={clientID:8,serverID:45,objectType:'track',shapeType:'cuboid',label:{name:'car'},attributes:{},keyframe:true};
  const record={state,cuboid:{perspective:{position:{x:1,y:2,z:3},scale:{x:4,y:2,z:2},rotation:{x:.1,y:-.2,z:.3}}}};
  const dom={},views={};
  for(const k of ['perspective','top','side','front']){
    dom[k]={getDrawnObjects:()=>[record],addEventListener:(t,f)=>events.set(t,f),removeEventListener(){},
      dispatchEvent(e){if(e.type==='canvas.selected')annotation.annotations.activatedStateID=e.detail.clientID;}};
    views[k]={renderer:{domElement:dom[k]},camera:{projectionMatrix:{elements:identity},matrixWorldInverse:{elements:identity}}};
  }
  const annotation={canvas:{instance:{html:()=>dom,view:{views},focus(){} }},job:{instance:{id:2}},
    annotations:{activatedStateID:8},player:{frame:{number:0}}};
  const store={getState:()=>({annotation}),subscribe:f=>(handlers.set('store',f),()=>{})};
  const window={postMessage:(message)=>sent.push(message),addEventListener:(t,f)=>handlers.set(t,f),removeEventListener(){},
    cvatUI:{registerComponent:f=>f({store})}};
  const ctx={window,URL,location:{origin:'http://localhost:8080'},document:{addEventListener:(t,f)=>handlers.set(t,f),removeEventListener(){}},
    performance:{now:()=>0},setInterval:()=>1,clearInterval(){},setTimeout:f=>(timers.push(f),timers.length),clearTimeout(){},
    requestAnimationFrame:f=>(frames.push(f),frames.length),cancelAnimationFrame(){},
    CustomEvent:class{constructor(type,o){this.type=type;this.detail=o.detail;}},
    PointSnapManualOverlay:{render:x=>rendered.push(x),clear(){},performanceStats:()=>({})},console};
  vm.createContext(ctx);
  for(const name of ['manual-geometry.js','cvat-compat.js','cvat-3d-hook.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../src',name),'utf8'),ctx);
  const message=(type,detail)=>handlers.get('message')({source:window,origin:ctx.location.origin,data:{type,detail}});
  const sample=()=>frames.shift()();
  const guide={schema_version:1,identity:{job_id:2,frame:0,kind:'track',server_id:45,cvat_origin:ctx.location.origin},rule:'floating',evidence:'measured',reference:{bottom_z:0},baseline:{center:[1,2,3],dims:[4,2,2],rotation:[.1,-.2,.3]}};
  return {ctx,handlers,events,record,annotation,rendered,sent,message,sample,guide};
}
test('live sampling reads real mesh geometry including tilt and never changes it',()=>{
  const b=bridge(),before=JSON.stringify(b.record);b.message('POINTSNAP_MANUAL_GUIDE',{guide:b.guide,token:1});b.sample();
  const r=b.rendered.at(-1);assert.deepEqual([...r.box.rotation],[.1,-.2,.3]);assert.equal(JSON.stringify(b.record),before);
  assert.equal(b.handlers.has('keydown'),false,'no leveling shortcut');
  b.record.cuboid.perspective.position.z=.99;b.sample();
  assert.equal(b.rendered.at(-1).box.center[2],.99);assert.equal(b.record.cuboid.perspective.position.z,.99,'no snap');
});
test('stale evaluation cannot clear the current drag; frame switch drops references',()=>{
  const b=bridge();b.message('POINTSNAP_MANUAL_GUIDE',{guide:b.guide,token:1});b.sample();
  const rev=b.ctx.PointSnapManualBridge.getRevision();
  b.record.cuboid.perspective.position.z=3.2;b.sample();
  b.message('POINTSNAP_MANUAL_RESULT',{token:1,result:{revision:rev,state:'cleared'}});b.sample();
  assert.notEqual(b.rendered.at(-1).evaluation?.state,'cleared');
  b.annotation.player.frame.number=1;b.sample();assert.equal(b.rendered.at(-1).guide,null);
});
test('foreign origin or object identities never attach a guide to the selected box',()=>{
  const b=bridge();b.message('POINTSNAP_MANUAL_GUIDE',{guide:{...b.guide,identity:{...b.guide.identity,cvat_origin:'http://other'}},token:1});b.sample();
  assert.equal(b.rendered.at(-1).guide,null);
  b.message('POINTSNAP_MANUAL_GUIDE',{guide:{...b.guide,identity:{...b.guide.identity,server_id:99}},token:2});b.sample();
  assert.equal(b.rendered.at(-1).guide,null);
});
test('incompatible camera adapter fails closed without guessed scene or coordinates',()=>{
  const b=bridge();delete b.annotation.canvas.instance.view;b.sample();assert.equal(b.rendered.length,0);
});
test('native Save removes old references before CVAT can reassign server IDs',()=>{
  const b=bridge();b.message('POINTSNAP_MANUAL_GUIDE',{guide:b.guide,token:1});b.sample();
  b.annotation.annotations.saving={uploading:true};b.handlers.get('store')();b.sample();
  assert.equal(b.rendered.at(-1).guide,null);
  assert.ok(b.sent.some(m=>m.type==='POINTSNAP_MANUAL_INVALIDATE'));
});
test('loopback aliases identify the same CVAT, while different ports stay isolated',()=>{
  const b=bridge();b.message('POINTSNAP_MANUAL_GUIDE',{guide:{...b.guide,identity:{...b.guide.identity,cvat_origin:'http://127.0.0.1:8080'}},token:1});b.sample();
  assert.equal(b.rendered.at(-1).guide.rule,'floating');
  assert.equal(b.ctx.PointSnapCvatCompat.sameOrigin('http://localhost:8081','http://localhost:8080'),false);
});
