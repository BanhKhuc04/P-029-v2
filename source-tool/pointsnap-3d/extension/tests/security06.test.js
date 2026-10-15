'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
function background(fetch) {
  const noop={addListener(){}};const id='a'.repeat(32);
  const context={URL,Set,AbortSignal,fetch,btoa,Uint8Array,chrome:{runtime:{id,getURL:()=>`chrome-extension://${id}/`,onMessage:noop,onInstalled:noop},
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

test('camera route is read-only and rejects traversal, arbitrary endpoints and query smuggling',()=>{
  const b=background(),p=`/api/projects/a/scans/${run}/findings/0/camera`;
  assert.ok(b.requestRoute('GET',p,undefined,sender));
  for(const path of [p+'?full=1',p.replace('/0/','/%30/'),p.replace('/camera','/preview')])
    assert.equal(b.requestRoute('GET',path,undefined,sender),null);
  assert.equal(b.requestRoute('PUT',p,{verdict:'ok'},sender),null);
});

test('rules catalog is readable from a job without widening project or query access',()=>{
  const b=background();
  assert.ok(b.requestRoute('GET','/api/rules',undefined,sender));
  assert.equal(b.requestRoute('GET','/api/rules?token=x',undefined,sender),null);
  assert.equal(b.requestRoute('PUT','/api/rules',{},sender),null);
});

test('camera image cannot be fetched from another job or absent finding',async()=>{
  for(const data of [{job_id:99,findings:[{}]},{job_id:2,findings:[]}]) {
    const calls=[];
    const b=background(async(u,opts)=>{calls.push(u);return{ok:true,status:200,json:async()=>u.endsWith('/api/projects/a')?{cvat_url:'http://localhost:8080'}:data};});
    const r=await b.callPointSnap({method:'GET',path:`/api/projects/a/scans/${run}/findings/0/camera`},sender);
    assert.equal(r.ok,false);assert.equal(calls.length,2);
  }
});

test('camera returns bounded JPEG data, refuses executable content and redirects',async()=>{
  for(const mime of ['image/jpeg','image/svg+xml']) {
    const calls=[];
    const b=background(async(u,opts)=>{
      calls.push(opts);
      if(!u.endsWith('/camera'))return{ok:true,status:200,json:async()=>u.endsWith('/api/projects/a')?{cvat_url:'http://localhost:8080'}:{job_id:2,findings:[{}]}};
      return{ok:true,status:200,headers:{get:k=>k==='Content-Type'?mime:k==='X-Camera-Channel'?'CAM_FRONT':null},
             arrayBuffer:async()=>new Uint8Array([255,216,255,217]).buffer};
    });
    const r=await b.callPointSnap({method:'GET',path:`/api/projects/a/scans/${run}/findings/0/camera`},sender);
    assert.equal(r.ok,mime==='image/jpeg');
    if(r.ok)assert.equal(r.data.image_url,'data:image/jpeg;base64,/9j/2Q==');
    assert.ok(calls.every(c=>c.redirect==='error'&&c.method==='GET'));
  }
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

test('F14: repair, apply-repair and rollback routes are whitelisted for sender job',()=>{
  const b=background();
  // Valid GET repair with and without query params
  assert.ok(b.requestRoute('GET','/api/jobs/2/tracks/101/repair?frame=0&rule=floating',undefined,sender));
  assert.ok(b.requestRoute('GET','/api/jobs/2/tracks/101/repair',undefined,sender));
  assert.ok(b.requestRoute('GET','/api/jobs/2/tracks/101/repair?frame=5&rule=fit.outside&slug=demo_proj',undefined,sender));

  // Valid POST apply-repair
  const applyBody={frame:0,repair:{delta_center:[0,0,-0.2],confidence:0.95},client_track_etag:'etag123',slug:'demo_proj'};
  assert.ok(b.requestRoute('POST','/api/jobs/2/tracks/101/apply-repair',applyBody,sender));
  assert.ok(b.requestRoute('POST','/api/jobs/2/tracks/101/apply-repair',{frame:0,repair:{}},sender));

  // Valid POST rollback
  assert.ok(b.requestRoute('POST','/api/jobs/2/tracks/101/rollback',{history_id:'7f9b8c0a-1e2d-4b5c-8f9a-0e1d2c3b4a5f',slug:'demo_proj'},sender));
  assert.ok(b.requestRoute('POST','/api/jobs/2/tracks/101/rollback',{history_id:'snap_101_0'},sender));
});

test('F14: cross-job repair, apply-repair, and rollback are rejected',()=>{
  const b=background();
  // Sender is in job 2; target is job 3 or 99
  assert.equal(b.requestRoute('GET','/api/jobs/3/tracks/101/repair?frame=0',undefined,sender),null);
  assert.equal(b.requestRoute('POST','/api/jobs/3/tracks/101/apply-repair',{frame:0,repair:{}},sender),null);
  assert.equal(b.requestRoute('POST','/api/jobs/99/tracks/101/rollback',{history_id:'snap-1'},sender),null);
});

test('F14: parameter smuggling, traversal, and invalid body schemas are rejected on repair routes',()=>{
  const b=background();
  // Traversal and malformed paths
  assert.equal(b.requestRoute('GET','/api/jobs/2/tracks/../admin/repair',undefined,sender),null);
  assert.equal(b.requestRoute('GET','/api/jobs/2/tracks/%2e%2e/repair',undefined,sender),null);
  assert.equal(b.requestRoute('POST','/api/jobs/2/tracks/101/rollback',{history_id:'../../etc/passwd'},sender),null);

  // Query smuggling on repair
  assert.equal(b.requestRoute('GET','/api/jobs/2/tracks/101/repair?evil=1',undefined,sender),null);
  assert.equal(b.requestRoute('GET','/api/jobs/2/tracks/101/repair?frame=0&frame=1',undefined,sender),null);
  assert.equal(b.requestRoute('GET','/api/jobs/2/tracks/101/repair?frame=-1',undefined,sender),null);

  // Query strings on POST apply-repair / rollback
  assert.equal(b.requestRoute('POST','/api/jobs/2/tracks/101/apply-repair?x=1',{frame:0,repair:{}},sender),null);
  assert.equal(b.requestRoute('POST','/api/jobs/2/tracks/101/rollback?x=1',{history_id:'snap-1'},sender),null);

  // Body schema violations on apply-repair
  assert.equal(b.requestRoute('POST','/api/jobs/2/tracks/101/apply-repair',{frame:0,repair:{},secret_token:'LEAK'},sender),null);
  assert.equal(b.requestRoute('POST','/api/jobs/2/tracks/101/apply-repair',{frame:'zero',repair:{}},sender),null);
  assert.equal(b.requestRoute('POST','/api/jobs/2/tracks/101/apply-repair',{frame:-1,repair:{}},sender),null);
  assert.equal(b.requestRoute('POST','/api/jobs/2/tracks/101/apply-repair',{frame:0},sender),null);
  assert.equal(b.requestRoute('POST','/api/jobs/2/tracks/101/apply-repair',null,sender),null);

  // Body schema violations on rollback
  assert.equal(b.requestRoute('POST','/api/jobs/2/tracks/101/rollback',{},sender),null);
  assert.equal(b.requestRoute('POST','/api/jobs/2/tracks/101/rollback',{history_id:123},sender),null);
  assert.equal(b.requestRoute('POST','/api/jobs/2/tracks/101/rollback',{history_id:'snap-1',unwanted:true},sender),null);
});

test('F14: callPointSnap executes repair routes successfully',async()=>{
  const calls=[];
  const b=background(async(u,opts)=>{
    calls.push({u,opts});
    return {ok:true,status:200,json:async()=>({status:'ok'})};
  });

  const r1=await b.callPointSnap({method:'GET',path:'/api/jobs/2/tracks/101/repair?frame=0&rule=floating'},sender);
  assert.equal(r1.ok,true);

  const r2=await b.callPointSnap({method:'POST',path:'/api/jobs/2/tracks/101/apply-repair',body:{frame:0,repair:{}}},sender);
  assert.equal(r2.ok,true);

  const r3=await b.callPointSnap({method:'POST',path:'/api/jobs/2/tracks/101/rollback',body:{history_id:'snap-1'}},sender);
  assert.equal(r3.ok,true);

  assert.equal(calls.length,3);
});

