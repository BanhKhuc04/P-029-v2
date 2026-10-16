/* ISOLATED-world controller: scoped guide requests, read-only draft checks, no annotation writes. */
(function(root){
  'use strict';
  const session=Date.now().toString(36)+Math.random().toString(36).slice(2);
  let sequence=0;
  const invalidatedRuns=new Set();
  const runKey=c=>`${c.slug}:${c.run.run_id}`;
  let current=null,token=0,selected=null,pending=false,guide=null,error='',status='';
  let options={enabled:true,reference:true,rulers:true,points:true};
  const post=(type,detail)=>window.postMessage({type,detail},location.origin);
  const esc=s=>String(s || '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function refresh(){root.PointSnapPanel?.render();}
  function publish(kind,state=null,revision=0){
    const c=current;if(!c || selected==null)return;
    c.request('POST','/api/extension/events',{slug:c.slug,run_id:c.run.run_id,job_id:c.jobId,cvat_url:location.origin,
      finding_index:selected,kind,state,revision,session,sequence:++sequence});
  }
  function clear(){token++;current=null;selected=null;guide=null;pending=false;error='';post('POINTSNAP_MANUAL_CLEAR',{});}
  function activate(next){
    const key=`${next.jobId}:${next.frame}:${next.run?.run_id}:${next.indices.join(',')}`;
    if(current?.key===key)return;
    clear();current={...next,key};selected=next.indices[0];load();
  }
  async function load(){
    if(!current || selected==null)return;
    if(invalidatedRuns.has(runKey(current))){pending=false;guide=null;error='Vừa Save · quét lại để cập nhật ID và hướng dẫn.';refresh();return;}
    const id=++token,c=current;guide=null;pending=true;error='';post('POINTSNAP_MANUAL_CLEAR',{});
    const path=`/api/projects/${c.slug}/scans/${c.run.run_id}/findings/${selected}`;
    const res=await c.request('GET',`${path}/guide`);
    if(id!==token || current!==c)return;
    pending=false;
    if(res.ok && res.data?.schema_version===1){guide=res.data;current.path=path;post('POINTSNAP_MANUAL_GUIDE',{guide,token:id,select:true});}
    else error=res.error || 'Chưa có hướng dẫn · tọa độ/thước vẫn dùng được.';
    publish('selected');refresh();
  }
  function select(index){if(current?.indices.includes(index)){selected=index;load();refresh();}}
  function toggle(key){if(!(key in options))return;options[key]=!options[key];post('POINTSNAP_MANUAL_OPTIONS',options);refresh();}
  function controls(){return `<div class="manual-controls" style="display:flex;gap:5px;flex-wrap:wrap;padding:8px 0">${
    [['enabled','Đo trực tiếp'],['reference','Khung'],['rulers','Thước'],['points','Điểm']].map(([k,label])=>`<button class="btn small" data-action="manual-toggle" data-k="${k}" aria-pressed="${options[k]}" title="Bật/tắt ${label}">${options[k]?'●':'○'} ${label}</button>`).join('')}</div>`;}
  function card(){
    if(!current)return '';
    const short={floating:'↕ Cao độ',size:'↔ Kích thước',heading:'⤾ Hướng',fit:'▧ Vị trí'};
    const chips=current.indices.map(i=>{const rule=current.run.findings[i]?.rule || '';return `<button class="btn small ${i===selected?'chosen':''}" data-action="manual-rule" data-n="${i}" aria-pressed="${i===selected}" title="${esc(root.PointSnapCore.RULE_LABEL[rule] || rule)}">${esc(short[rule.split('.')[0]] || rule)}</button>`;}).join('');
    return `<div class="repair-box"><div style="display:flex;flex-wrap:wrap;gap:5px">${chips}</div><p class="small">${esc(pending?'Đang lấy số đo tham chiếu…':error || guide?.instruction || 'Chọn lỗi · kéo sửa bằng CVAT.')}</p><div class="small muted">${esc(status || 'Tâm/kích thước/góc hiện trên canvas · Save/Undo của CVAT')}</div></div>`;
  }
  window.addEventListener('message',async event=>{
    if(event.source!==window || event.origin!==location.origin)return;
    const {type,detail}=event.data || {};
    if(type==='POINTSNAP_MANUAL_EDITING' && detail?.token===token){publish('evaluated','insufficient');return;}
    if(type==='POINTSNAP_MANUAL_ACCEPTED' && detail?.token===token){publish('evaluated',detail.result.state,detail.result.revision);return;}
    if(type==='POINTSNAP_MANUAL_CONTEXT' && current && (current.jobId!==detail?.jobId || current.frame!==detail?.frame)){
      clear();return;
    }
    if(type==='POINTSNAP_MANUAL_INVALIDATE'){
      if(current)invalidatedRuns.add(runKey(current));publish('saved','stale');token++;guide=null;pending=false;error=detail?.message || 'Quét lại để cập nhật lỗi.';refresh();return;
    }
    if(type==='POINTSNAP_MANUAL_STATUS'){
      status=detail?.message || '';
      if(detail?.supported && guide)post('POINTSNAP_MANUAL_GUIDE',{guide,token,select:true});
      refresh();
    }
    if(type!=='POINTSNAP_MANUAL_DRAFT' || !current?.path || detail?.token!==token)return;
    const c=current,t=token,revision=detail.payload?.revision;
    const res=await c.request('POST',`${c.path}/evaluate`,detail.payload);
    if(c!==current || t!==token)return;
    const result=res.ok?res.data:{revision,state:'insufficient',message:res.error || 'Mất kết nối; vẫn có thể sửa tay.'};
    post('POINTSNAP_MANUAL_RESULT',{token:t,result});

  });
  root.PointSnapManualController={activate,clear,select,toggle,controls,card,getRule:()=>current?.run?.findings?.[selected]?.rule};
})(globalThis);
