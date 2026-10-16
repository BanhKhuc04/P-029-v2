/* CVAT 2.77.1 adapter. Isolate private camera access and fail closed on incompatible canvases. */
(function(root){
  'use strict';
  function sameOrigin(a,b){
    try {
      const key=value=>{const u=new URL(value);const host=['localhost','127.0.0.1','[::1]'].includes(u.hostname)?'localhost':u.hostname;
        return `${u.protocol}//${host}:${u.port || (u.protocol==='https:'?443:80)}`;};
      return key(a)===key(b);
    }catch(_){return false;}
  }
  function inspect(store) {
    const a=store?.getState?.()?.annotation, canvas=a?.canvas?.instance;
    if (!canvas?.html || !a.job?.instance || a.player?.frame?.fetching) return null;
    const dom=canvas.html(), views=canvas.view?.views;
    if (!views || !['perspective','top','side','front'].every(k =>
      dom[k]?.getDrawnObjects && views[k]?.renderer?.domElement===dom[k] &&
      views[k]?.camera?.projectionMatrix?.elements?.length===16 && views[k]?.camera?.matrixWorldInverse?.elements?.length===16)) return null;
    return {annotation:a,canvas,dom,views,frame:a.player.frame.number,jobId:a.job.instance.id,job:a.job.instance};
  }
  function record(context, identity=null) {
    const records=context.dom.perspective.getDrawnObjects();
    const id=context.annotation.annotations.activatedStateID;
    const found=records.filter(r => identity ?
      r.state?.serverID===identity.server_id && r.state?.objectType===identity.kind : r.state?.clientID===id);
    return found.length===1 ? found[0]:null;
  }
  function readBox(record, frame) {
    const m=record?.cuboid?.perspective, s=record?.state;
    if (!m || !s || s.outside || s.shapeType!=='cuboid') return null;
    const box={center:[m.position.x,m.position.y,m.position.z],dims:[m.scale.x,m.scale.y,m.scale.z],
      rotation:[m.rotation.x,m.rotation.y,m.rotation.z],frame,label:s.label.name,
      track_id:s.objectType==='track'?s.serverID:null,source_id:s.objectType==='shape'?s.serverID:null,
      attrs:{...(s.attributes || {}),occluded:!!s.occluded},keyframe:!!s.keyframe,outside:!!s.outside};
    return root.PointSnapGeometry.valid(box)?box:null;
  }
  function normalizeExport(data, labels) {
    const result=[], byId=new Map(labels.map(l=>[l.id,l]));
    const convert=(shape,owner=null,inherited={})=>{
      if (shape.type!=='cuboid' || !shape.points?.slice(0,9).every(Number.isFinite)) return;
      const label=byId.get(owner?.label_id ?? shape.label_id); if (!label) throw Error('Missing label');
      const attrs={...inherited};
      for (const a of shape.attributes || []) attrs[label.attributes.find(s=>s.id===a.spec_id)?.name || String(a.spec_id)]=a.value;
      attrs.occluded=!!shape.occluded;
      result.push({center:shape.points.slice(0,3),rotation:shape.points.slice(3,6),dims:shape.points.slice(6,9),
        frame:shape.frame,label:label.name,track_id:owner?.id ?? null,source_id:owner?null:shape.id ?? null,
        attrs,outside:!!shape.outside,keyframe:true});
      return attrs;
    };
    for (const s of data.shapes || []) convert(s);
    for (const t of data.tracks || []) {
      const label=byId.get(t.label_id); if(!label) throw Error('Missing label');
      let attrs={}; for(const a of t.attributes || []) attrs[label.attributes.find(s=>s.id===a.spec_id)?.name || String(a.spec_id)]=a.value;
      for(const s of [...t.shapes].sort((a,b)=>a.frame-b.frame)) attrs=convert(s,t,attrs) || attrs;
    }
    return result;
  }
  async function draft(context, box) {
    const exported=await context.job.annotations.export();
    let normalized=normalizeExport(exported,context.job.labels);
    const current=await context.job.annotations.get(context.frame,false,[]);
    // Replace current-frame keyframes with all actual interpolated states, without active filters.
    normalized=normalized.filter(b=>b.frame!==context.frame);
    for(const s of current) {
      if(s.shapeType!=='cuboid') continue;
      const label=s.label, attrs={occluded:!!s.occluded};
      for(const [id,value] of Object.entries(s.attributes || {})) attrs[label.attributes.find(a=>String(a.id)===id)?.name || id]=value;
      normalized.push({center:s.points.slice(0,3),rotation:s.points.slice(3,6),dims:s.points.slice(6,9),
        frame:context.frame,label:label.name,track_id:s.objectType==='track'?s.serverID:null,
        source_id:s.objectType==='shape'?s.serverID:null,attrs,outside:!!s.outside,keyframe:!!s.keyframe});
    }
    // Use the actual mesh, including the final mouse movement before Redux updates.
    const same=b=>b.frame===box.frame && (box.track_id!=null?b.track_id===box.track_id:b.track_id==null && b.source_id===box.source_id);
    const selected=normalized.find(same);
    const actual={...box,attrs:selected?.attrs || box.attrs};
    normalized=normalized.filter(b=>!same(b));
    normalized.push(actual);
    return {box:actual,context:normalized,context_complete:true};
  }
  const api={inspect,record,readBox,normalizeExport,draft,sameOrigin};
  if(typeof module!=='undefined'&&module.exports) module.exports=api; else root.PointSnapCvatCompat=api;
})(globalThis);
