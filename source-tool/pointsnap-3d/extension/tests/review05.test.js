'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const core = require('../src/core.js');

function web(fetch, confirm = () => false) {
  const els = new Map();
  function el(id='') {
    return {id, value:'', textContent:'', innerHTML:'', style:{}, children:[], attrs:{}, disabled:false,
      classList:{add(){},remove(){},toggle(){}}, setAttribute(k,v){this.attrs[k]=v;},
      getAttribute(k){return this.attrs[k] ?? 'true';}, removeAttribute(k){delete this.attrs[k];}, addEventListener(){}, focus(){},
      appendChild(child){this.children.push(child);}, remove(){}, querySelector(){return el();},
      querySelectorAll(){return [];}, getContext(){return {clearRect(){}};}};
  }
  const document={getElementById(id){if(!els.has(id))els.set(id,el(id)); return els.get(id);},
    createElement(){return el();}, querySelectorAll(){return [];}, querySelector(){return null;},
    addEventListener(){}, documentElement:el(), activeElement:null};
  const source=fs.readFileSync(path.join(__dirname,'../../pointsnap/web/static/app.js'),'utf8');
  const exports=['state','populateGuidelineForm','handleSaveGuideline','loadRunDetails','markReview','loadLatestRun','showEmptyResults','setGuidelineMode','safeHttpLink','renderHistoryRuns','handleResetGuideline','findingFixTip','handleSaveConnectionSettings','drawPreview'];
  const context={document,fetch, console, getComputedStyle:()=>({getPropertyValue:(k)=>k}), URLSearchParams, URL, Map, Set, Date, Math,
    localStorage:{getItem(){return null;},setItem(){}},sessionStorage:{getItem(){return null;},setItem(){}},
    window:{location:{search:'',hash:''},matchMedia(){return {matches:false};},addEventListener(){}},
    setTimeout(){return 1;},clearTimeout(){},setInterval(){return 1;},clearInterval(){},confirm};
  vm.createContext(context);
  vm.runInContext(source.replace(/\}\)\(\);\s*$/,`globalThis.api={${exports.join(',')}};})();`),context);
  return {...context.api,els,document};
}

test('identity matching cannot review another same-label box',()=>{
  const findings=[{frame:0,label:'car',message:'same',track_id:7},{frame:0,label:'car',message:'same',track_id:8}];
  assert.deepEqual(core.matchFindings(findings,{frame:0,label:'car',value:'same',kind:'track',objectId:8}),[1]);
  assert.deepEqual(core.matchFindings(findings,{frame:0,label:'car',value:'same',kind:'track',objectId:99}),[]);
});
test('outside shapes cannot become navigable flags',()=>{
  const specs=new Map([[1,{name:'car',specId:2}]]);
  assert.equal(core.collectFlags({shapes:[{id:1,type:'cuboid',outside:true,label_id:1,frame:0,attributes:[{spec_id:2,value:'[Lỗi] same'}]}]},specs).length,0);
});
test('mutable flags carry through keyframes and explicit reset stops carry',()=>{
  const specs=new Map([[1,{name:'car',specId:2}]]);
  const shape=(frame,attributes)=>({frame,type:'cuboid',outside:false,attributes});
  const flags=core.collectFlags({tracks:[{id:7,label_id:1,shapes:[shape(2,[{spec_id:2,value:''}]),shape(1,[]),shape(0,[{spec_id:2,value:'[Lỗi] same'}])]}]},specs);
  assert.deepEqual(flags.map(f=>f.frame),[0,1]);
});
test('manual ranges form reflects actual schema',()=>{
  const w=web();
  w.populateGuidelineForm({size:{manual_ranges:{bus:{length:[9,18],width:[2,3],height:[2,4]}}}});
  assert.ok(w.document.getElementById('size-classes-table-body').children[0]?.innerHTML.includes('bus'));
});
test('default form can save without adding unsupported schema keys',async()=>{
  const cfg={size:{class_range:{stats:{}},manual_ranges:{bus:{length:[9,18],width:[2,3],height:[2,4]}}},floating:{},gate:{}};
  let posted;
  const w=web(async(url,opts)=>{if(opts){posted=JSON.parse(opts.body);return {ok:true,json:async()=>({})};}return {ok:true,json:async()=>({config:cfg,yaml:'valid'})};});
  w.state.currentSlug='a';w.state.currentGuideline=cfg;w.populateGuidelineForm(cfg);
  await w.handleSaveGuideline();
  assert.ok(posted.config.size.manual_ranges.bus);
  assert.equal(posted.config.size.class_range.manual_ranges,undefined);
});
test('zero threshold is preserved rather than replaced with default',async()=>{
  let posted;
  const cfg={size:{manual_ranges:{}},floating:{warning_m:0,error_m:.22,single_warning_m:0,single_error_m:.3}};
  const w=web(async(url,opts)=>{if(opts){posted=JSON.parse(opts.body);return {ok:true,json:async()=>({})};}return {ok:true,json:async()=>({config:cfg,yaml:''})};});
  w.state.currentSlug='a';w.state.currentGuideline=cfg;w.populateGuidelineForm(cfg);
  await w.handleSaveGuideline();
  assert.equal(posted.config.floating.warning_m,0);
});
test('review completion cannot alter a newly selected run',async()=>{
  let resolve;
  const w=web(()=>new Promise(r=>{resolve=r;}));
  const f={};const a={run_id:'a',findings:[f],reviews:{}}; const b={run_id:'b',findings:[{}],reviews:{}};
  w.state.currentSlug='a';w.state.currentRun=a;w.state.currentDetail=f;
  const pending=w.markReview('fp');w.state.currentSlug='b';w.state.currentRun=b;
  resolve({ok:true,json:async()=>({reviews:{'0':'fp'}})}); await pending;
  assert.deepEqual(b.reviews,{});
});
test('old project response cannot replace the newly selected project run',async()=>{
  let resolve;
  const w=web(()=>new Promise(r=>{resolve=r;}));
  w.state.currentSlug='a';const pending=w.loadRunDetails('old');
  const b={run_id:'b',findings:[]};w.state.currentSlug='b';w.state.currentRun=b;
  resolve({ok:true,json:async()=>({run_id:'old',status:'done',findings:[],summary:{}})});await pending;
  assert.equal(w.state.currentRun,b);
});
test('old connection save cannot reload the new project form',async()=>{
  let resolve;
  const calls=[];
  const w=web(url=>{calls.push(url);return new Promise(r=>{resolve=r;});});
  w.state.currentSlug='a';
  const pending=w.handleSaveConnectionSettings();
  w.state.currentSlug='b';w.state.projectEpoch++;
  w.document.getElementById('conn-cvat-token').value='new-project-draft';
  resolve({ok:true});await pending;
  assert.deepEqual(calls,['/api/projects/a']);
  assert.equal(w.document.getElementById('conn-cvat-token').value,'new-project-draft');
});

test('empty results clear the previous detail and review state',()=>{
  const w=web();w.state.currentRun={run_id:'old'};w.state.currentDetail={};w.showEmptyResults();
  assert.equal(w.state.currentRun,null);assert.equal(w.state.currentDetail,null);
});
test('changing guideline mode with unsaved edits can be cancelled',()=>{
  const w=web();w.state.guidelineDirty=true;w.state.guidelineMode='form';w.setGuidelineMode('yaml');
  assert.equal(w.state.guidelineMode,'form');
});

function panel(transport) {
  const source=fs.readFileSync(path.join(__dirname,'../src/content.js'),'utf8');
  const context={PointSnapCore:core,PointSnapCvat:{},PointSnapCvatApi:{},PointSnapTransport:transport,
    location:{href:'http://localhost:8080/',pathname:'/',origin:'http://localhost:8080'},
    document:{querySelector(){return null;}},window:{addEventListener(){}},
    performance:{now(){return 0;}},setInterval(){},clearInterval(){},setTimeout(){},Map,Set,URL};
  vm.createContext(context);
  vm.runInContext(source.replace('  loadSettings().then', '  root.testPanel={S,pickFor,reviewState,review,startScan,showCamera};\n  loadSettings().then'),context);
  return {...context.testPanel,cvat:context.PointSnapCvat};
}
test('focus distinguishes same-frame objects and refuses an ambiguous legacy command',()=>{
  const p=panel();p.S.flags=[{frame:0,label:'car',value:'same',kind:'track',objectId:7},{frame:0,label:'car',value:'same',kind:'track',objectId:8}];
  assert.equal(p.pickFor(0,{label:'car',message:'same',track_id:8}),1);
  assert.equal(p.pickFor(0,{label:'car',message:'same'}),-1);
  assert.equal(p.pickFor(0,{label:'car',message:'same',track_id:99}),-1);
});
test('an ambiguous DOM selection cannot submit reviews',()=>{
  const p=panel();p.S.ps.run={findings:[{frame:0,label:'car',message:'same',track_id:7}]};
  assert.equal(p.reviewState({frame:0,label:'car',value:'same',ambiguous:true}),null);
});
test('extension review in flight cannot overwrite a new job run',async()=>{
  let resolve;const p=panel(()=>new Promise(r=>{resolve=r;}));
  p.S.ps.project={slug:'a'};p.S.ps.run={run_id:'old',findings:[{frame:0,label:'car',message:'same',track_id:7}]};
  const pending=p.review({frame:0,label:'car',value:'same',kind:'track',objectId:7},'fp');
  const next={run_id:'next',reviews:{}};p.S.sid++;p.S.ps.run=next;
  resolve({ok:true,data:{reviews:{'0':'fp'}}});await pending;
  assert.deepEqual(next.reviews,{});
});
test('extension scan response after a route change cannot attach to the new job',async()=>{
  let resolve;const p=panel(()=>new Promise(r=>{resolve=r;}));
  p.S.job={jobId:1};p.S.ps.project={slug:'a'};
  const pending=p.startScan(false);p.S.sid++;p.S.job={jobId:2};p.S.ps={active:null};
  resolve({ok:true,data:{run_id:'old'}});await pending;
  assert.equal(p.S.ps.active,null);
});

test('camera response cannot attach to a new run',async()=>{
  let resolve;const p=panel(()=>new Promise(r=>{resolve=r;}));
  const flag={frame:0,label:'car',value:'same',kind:'track',objectId:7};
  p.S.frame=0;p.S.flags=[flag];p.S.ps.project={slug:'a'};
  p.S.ps.run={run_id:'old',findings:[{frame:0,label:'car',message:'same',track_id:7}]};
  const pending=p.showCamera(flag);p.S.sid++;p.S.ps.run={run_id:'next'};
  resolve({ok:true,data:{image_url:'data:image/jpeg;base64,/9j/2Q==',channel:'CAM_FRONT'}});
  await pending;assert.equal(p.S.camera,null);
});

test('security: executable and credential links are not shown',()=>{
  const w=web();for(const value of ['javascript:alert(1)','data:text/html,x','http://u:SECRET@localhost/'])assert.equal(w.safeHttpLink(value),'');
  assert.equal(w.safeHttpLink('http://localhost:8080/tasks/1/jobs/2?frame=0'),'http://localhost:8080/tasks/1/jobs/2?frame=0');
});
test('security: persisted history fields and attributes are escaped',()=>{
  const w=web(),payload='<img src=x onerror=alert(1)>';
  w.renderHistoryRuns([{run_id:'" onmouseover="x',job_id:payload,started_at:payload,status:'done',summary:{num_errors:payload,num_warnings:0}}]);
  const html=w.document.getElementById('history-table-body').children[0].innerHTML;
  assert.ok(!html.includes('<img'));assert.ok(html.includes('&lt;img'));assert.ok(!html.includes('data-id="" onmouseover'));
});

test('confirmed reset discards dirty draft and reloads the saved default',async()=>{
  const w=web(async()=>({ok:true,json:async()=>({config:{size:{manual_ranges:{}},gate:{max_errors:0}},yaml:'default'})}),()=>true);
  w.state.currentSlug='a';w.state.currentGuideline={gate:{max_errors:5}};w.state.guidelineDirty=true;
  await w.handleResetGuideline();assert.equal(w.state.guidelineDirty,false);assert.equal(w.state.currentGuideline.gate.max_errors,0);
});

test('floating sunk-box advice matches the extension and moves the box upwards',()=>{
  const w=web();assert.match(w.findingFixTip({rule:'floating',message:'Đáy box nằm dưới mặt đất 31 cm (lún)'}),/^Nâng/);
  assert.match(w.findingFixTip({rule:'floating',message:'Đáy box cách mặt đất 18 cm (lơ lửng)'}),/^Hạ/);
});
test('results view without a project shows only the empty state, not a gate verdict',async()=>{
  const html=fs.readFileSync(path.join(__dirname,'../../pointsnap/web/static/index.html'),'utf8');
  assert.match(html,/id="results-content-box" style="display: none;/);
  const w=web(async()=>{throw new Error('no fetch without a project');});
  w.state.currentSlug=null;
  await w.loadLatestRun();
  assert.equal(w.document.getElementById('results-content-box').style.display,'none');
  assert.equal(w.document.getElementById('results-empty-state').style.display,'block');
});
test('preview marks the box front with a red arrow and draws the measured ground along the slope',()=>{
  const w=web();
  const calls=[];
  const ctx=new Proxy({},{get:(t,k)=>k in t?t[k]:(...a)=>calls.push([k,...a]),
    set:(t,k,v)=>{t[k]=v;calls.push(['set',k,v]);return true;}});
  const canvas={clientWidth:200,clientHeight:100,getContext:()=>ctx};
  const data={box:{length:4,width:2,height:1.6},points:[],color:'warn',ground:{z:-0.8,pitch_deg:10}};
  w.drawPreview(canvas,data,'side');
  assert.ok(calls.some(c=>c[0]==='set'&&c[1]==='fillStyle'&&c[2]==='--error'),'red arrow');
  const line=calls.filter(c=>c[0]==='moveTo'||c[0]==='lineTo');
  const [, x0, y0]=line[0], [, x1, y1]=line[1];
  assert.ok(x1>x0&&y1<y0,'ground rises toward the box front on canvas');
  calls.length=0;
  w.drawPreview(canvas,{...data,ground:null},'top');
  assert.ok(!calls.some(c=>c[0]==='setLineDash'),'no ground line without a measured ground');
});
