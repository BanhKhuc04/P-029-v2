'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
function controller(){
  const handlers=new Map(),sent=[];
  const window={postMessage:message=>sent.push(message),addEventListener:(name,fn)=>handlers.set(name,fn)};
  const ctx={window,location:{origin:'http://localhost:8080'},PointSnapCore:{RULE_LABEL:{}},PointSnapPanel:{render(){}}};
  vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(__dirname,'../src/manual-controller.js'),'utf8'),ctx);
  return {c:ctx.PointSnapManualController,sent,message:(type,detail)=>handlers.get('message')({source:window,origin:ctx.location.origin,data:{type,detail}})};
}
const next=(id,request)=>({jobId:2,frame:0,slug:'p',run:{run_id:id,findings:[{rule:'floating'}]},indices:[0],request});
const flush=()=>new Promise(r=>setImmediate(r));
test('a late guide response never replaces the newly selected run',async()=>{
  const h=controller();let resolveA;
  h.c.activate(next('a',()=>new Promise(r=>resolveA=r)));
  h.c.activate(next('b',async()=>({ok:true,data:{schema_version:1,rule:'b'}})));await flush();
  resolveA({ok:true,data:{schema_version:1,rule:'a'}});await flush();
  assert.deepEqual(h.sent.filter(m=>m.type==='POINTSNAP_MANUAL_GUIDE').map(m=>m.detail.guide.rule),['b']);
});
test('an in-flight check is discarded when selection changes and all requests are read-only',async()=>{
  const h=controller(),calls=[];let resolve;
  const request=async(method,path,body)=>{calls.push({method,path,body});return method==='POST'?new Promise(r=>resolve=r):{ok:true,data:{schema_version:1}};};
  h.c.activate(next('a',request));await flush();
  const token=h.sent.find(m=>m.type==='POINTSNAP_MANUAL_GUIDE').detail.token;
  const pending=h.message('POINTSNAP_MANUAL_DRAFT',{token,payload:{revision:4}});
  h.c.clear();resolve({ok:true,data:{revision:4,state:'cleared'}});await pending;
  assert.equal(h.sent.some(m=>m.type==='POINTSNAP_MANUAL_RESULT'),false);
  assert.ok(calls.every(c=>c.path.endsWith('/guide')||c.path.endsWith('/evaluate')||c.path==='/api/extension/events'));
});
test('Save invalidates references and an unavailable backend never produces success',async()=>{
  const h=controller();h.c.activate(next('a',async()=>({ok:true,data:{schema_version:1}})));await flush();
  h.message('POINTSNAP_MANUAL_INVALIDATE',{message:'Quét lại sau Save'});
  assert.match(h.c.card(),/Quét lại sau Save/);
  assert.ok(!h.c.card().includes('ĐÃ GHI'));
});


test('Save blocks the same historical guide after navigating away and returning',async()=>{
  const h=controller(),calls=[];
  const request=async(method,path,body)=>{calls.push(path);return {ok:true,data:{schema_version:1}};};
  h.c.activate(next('old',request));await flush();
  h.message('POINTSNAP_MANUAL_INVALIDATE',{message:'Quét lại sau Save'});
  h.c.clear();const before=calls.filter(p=>p.endsWith('/guide')).length;
  h.c.activate(next('old',request));await flush();
  assert.equal(calls.filter(p=>p.endsWith('/guide')).length,before);
  assert.match(h.c.card(),/quét lại/i);
  h.c.activate(next('new',request));await flush();
  assert.equal(calls.filter(p=>p.endsWith('/guide')).length,before+1);
});
