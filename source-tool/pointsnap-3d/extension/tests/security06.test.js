'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
function background(fetch) {
  const noop={addListener(){}};const id='a'.repeat(32);
  const context={URL,Set,AbortSignal,fetch,chrome:{runtime:{id,getURL:()=>`chrome-extension://${id}/`,onMessage:noop,onInstalled:noop},
    storage:{sync:{get:async()=>({pointsnapUrl:'http://127.0.0.1:8765',cvatUrls:[]})},onChanged:noop},
    permissions:{onAdded:noop,onRemoved:noop,contains:async()=>true},action:{onClicked:noop},scripting:{}}};
  vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(__dirname,'../background.js'),'utf8')+'\nglobalThis.api={requestRoute,callPointSnap,trustedSender,httpOrigin,sameCvatOrigin,syncContentScripts};',context);
  return {...context.api,chrome:context.chrome};
}
const sender={id:'a'.repeat(32),url:'http://localhost:8080/tasks/1/jobs/2',frameId:0,tab:{id:1}};
const run='20261011-123456-job2';
test('content script cannot proxy project secrets/config endpoints',()=>{
  const b=background();
  for(const [method,p] of [['PUT','/api/projects/a'],['POST','/api/projects/a/guideline/reset'],['GET','/api/projects'],['POST','/api/extension/focus'],['GET','/api/projects/a/scans']]) assert.equal(b.requestRoute(method,p,{},sender),null);
});
test('encoded path traversal and query smuggling are refused',()=>{
  const b=background();for(const p of ['/api/projects/%2e%2e/scans','/api/projects/a/scans/'+run+'#x','/api/projects/a/scans/'+run+'?x=1'])assert.equal(b.requestRoute('GET',p,undefined,sender),null);
});
test('scan is bound to sender job and minimal body',()=>{
  const b=background();assert.ok(b.requestRoute('POST','/api/projects/a/scans',{job_id:2,flag:false},sender));
  assert.equal(b.requestRoute('POST','/api/projects/a/scans',{job_id:3,flag:true},sender),null);
  assert.equal(b.requestRoute('POST','/api/projects/a/scans',{job_id:2,flag:true,cvat_token:'SECRET'},sender),null);
});
test('poll is bound to exact sender origin and job',()=>{
  const b=background();assert.ok(b.requestRoute('GET','/api/extension/poll?job_id=2&after=-1&cvat_url=http%3A%2F%2Flocalhost%3A8080',undefined,sender));
  assert.equal(b.requestRoute('GET','/api/extension/poll?job_id=3&cvat_url=http%3A%2F%2Flocalhost%3A8080',undefined,sender),null);
  assert.equal(b.requestRoute('GET','/api/extension/jobs/2?cvat_url=https%3A%2F%2Fevil.example',undefined,sender),null);
});
test('iframe/foreign extension/webpage sender is denied',async()=>{
  const b=background();assert.equal(await b.trustedSender({...sender,frameId:1}),false);
  assert.equal(await b.trustedSender({...sender,id:'b'.repeat(32)}),false);
  assert.equal(await b.trustedSender({...sender,url:'https://evil.example/'}),false);
  assert.equal(await b.trustedSender(sender),true);
});
test('own options page can only check projects',()=>{
  const b=background(),options={...sender,url:'chrome-extension://'+'a'.repeat(32)+'/options.html'};
  assert.ok(b.requestRoute('GET','/api/projects',undefined,options));
  assert.equal(b.requestRoute('PUT','/api/projects/a',{},options),null);
});
test('request cannot reach another CVAT project',async()=>{
  const calls=[];const b=background(async(u)=>{calls.push(u);return{ok:true,status:200,json:async()=>({cvat_url:'https://other.example'})};});
  const r=await b.callPointSnap({method:'POST',path:'/api/projects/a/scans',body:{job_id:2,flag:true}},sender);
  assert.equal(r.ok,false);assert.equal(calls.length,1);
});
test('review cannot reach another job run',async()=>{
  const calls=[];const b=background(async(u,opts)=>{calls.push({u,opts});return{ok:true,status:200,json:async()=>u.endsWith('/api/projects/a')?{cvat_url:'http://localhost:8080'}:{job_id:99}};});
  const r=await b.callPointSnap({method:'PUT',path:`/api/projects/a/scans/${run}/reviews/0`,body:{verdict:'fp'}},sender);
  assert.equal(r.ok,false);assert.ok(calls.every(c=>c.opts.method==='GET'&&c.opts.redirect==='error'));
});
test('valid same-job review forwards once with redirect refused',async()=>{
  const calls=[];const b=background(async(u,opts)=>{calls.push(opts);return{ok:true,status:200,json:async()=>u.endsWith('/api/projects/a')?{cvat_url:'http://127.0.0.1:8080'}:{job_id:2,reviews:{'0':'fp'}}};});
  const r=await b.callPointSnap({method:'PUT',path:`/api/projects/a/scans/${run}/reviews/0`,body:{verdict:'fp'}},sender);
  assert.equal(r.ok,true);assert.equal(calls.filter(c=>c.method==='PUT').length,1);
  assert.ok(calls.every(c=>c.redirect==='error'));
});
test('URLs reject executable schemes, credentials and path loss',()=>{
  const b=background();for(const u of ['javascript:alert(1)','file:///tmp','http://u:SECRET@localhost:8080','http://localhost:8080/proxy','http://localhost:8080?x=1'])assert.throws(()=>b.httpOrigin(u));
  assert.equal(b.sameCvatOrigin('http://localhost:8080/','http://127.0.0.1:8080'),true);
});
test('custom hosts do not reinject built-in content scripts',async()=>{
  const b=background();let scripts;
  b.chrome.storage.sync.get=async()=>({cvatUrls:['http://localhost:8080','http://127.0.0.1:8080','https://cvat.example','https://cvat.example/']});
  b.chrome.scripting.getRegisteredContentScripts=async()=>[];b.chrome.scripting.registerContentScripts=async(s)=>{scripts=s;};await b.syncContentScripts();
  assert.deepEqual(Array.from(scripts[0].matches),['https://cvat.example/*']);
});
