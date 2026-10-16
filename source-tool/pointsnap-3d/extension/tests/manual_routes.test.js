'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
function background(fetchImpl){
  const registered=[],noop={addListener(){}};
  const chrome={runtime:{id:'a'.repeat(32),getURL:()=>`chrome-extension://${'a'.repeat(32)}/`,onMessage:noop,onInstalled:noop},
    storage:{sync:{get:async()=>({pointsnapUrl:'http://127.0.0.1:8765',cvatUrls:['https://cvat.example']})},onChanged:noop},
    permissions:{contains:async()=>true,onAdded:noop,onRemoved:noop},scripting:{getRegisteredContentScripts:async()=>[],
      unregisterContentScripts:async()=>{},registerContentScripts:async scripts=>registered.push(...scripts)}};
  const ctx={chrome,URL,AbortSignal,fetch:fetchImpl || (async()=>({ok:true,status:200,json:async()=>({})})),btoa,Uint8Array,console};
  vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(__dirname,'../background.js'),'utf8')+'\nglobalThis.api={requestRoute,callPointSnap,syncContentScripts};',ctx);
  return {...ctx.api,registered};
}
const sender={id:'a'.repeat(32),url:'http://localhost:8080/tasks/1/jobs/2',frameId:0,tab:{id:1}};
const base='/api/projects/p/scans/20261015-120000-job2/findings/0';
const body={box:{frame:0},context:[],context_complete:true,revision:1};
test('guide/evaluate are scoped and legacy geometry writes are never forwarded',()=>{
  const b=background();assert.ok(b.requestRoute('GET',base+'/guide',undefined,sender));
  assert.ok(b.requestRoute('POST',base+'/evaluate',body,sender));
  for(const [method,url,payload] of [['POST',base+'/guide',body],['GET',base+'/evaluate',undefined],
    ['POST',base+'/evaluate?evil=1',body],['POST',base+'/evaluate',{...body,secret:'no'}],
    ['POST','/api/jobs/2/tracks/7/apply-repair',{frame:0,repair:{}}],['POST','/api/jobs/2/tracks/7/rollback',{history_id:'old'}]])
    assert.equal(b.requestRoute(method,url,payload,sender),null,url);
});
test('another CVAT/job/run cannot access a finding guide or evaluate its draft',async()=>{
  for(const variant of ['origin','job','index']){
    let forwarded=0;
    const b=background(async url=>({ok:true,status:200,json:async()=>url.endsWith('/api/projects/p')?
      {cvat_url:variant==='origin'?'http://other':'http://localhost:8080'}:url.endsWith('/guide')||url.endsWith('/evaluate')?
      (forwarded++,{}):{job_id:variant==='job'?9:2,findings:variant==='index'?[]:[{}]}}));
    const result=await b.callPointSnap({method:'POST',path:base+'/evaluate',body},sender);
    assert.equal(result.ok,false);assert.equal(forwarded,0);
  }
});
test('evaluate forwards the unsaved draft using POST, rather than returning a cached run',async()=>{
  const calls=[];
  const b=background(async(url,opts)=>{calls.push([url,opts]);return {ok:true,status:200,json:async()=>
    url.endsWith('/api/projects/p')?{cvat_url:'http://localhost:8080'}:url.endsWith('/evaluate')?{state:'remaining',revision:1}:{job_id:2,findings:[{}]}};});
  const result=await b.callPointSnap({method:'POST',path:base+'/evaluate',body},sender);
  assert.equal(result.data.state,'remaining');assert.equal(calls.at(-1)[1].method,'POST');
  assert.equal(JSON.parse(calls.at(-1)[1].body).revision,1);
});
test('granted custom CVAT origins register exactly the same MAIN/isolated files as localhost',async()=>{
  const b=background();await b.syncContentScripts();
  const manifest=JSON.parse(fs.readFileSync(path.join(__dirname,'../manifest.json'),'utf8'));
  const main=b.registered.find(s=>s.world==='MAIN');
  assert.deepEqual([...main.js],manifest.content_scripts.find(s=>s.world==='MAIN').js);
  const panel=b.registered.find(s=>s.id==='pointsnap-panel');
  assert.deepEqual([...panel.js],manifest.content_scripts.at(-1).js);
  assert.deepEqual([...main.matches],['https://cvat.example/*']);
});
