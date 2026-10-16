/* SVG overlays projected with CVAT's own cameras. No scene or annotation writes. */
(function(root){
  'use strict';
  const G=root.PointSnapGeometry, layers=new Map();
  const names={perspective:'3D',top:'Nhìn trên',side:'Bên hông',front:'Phía trước'};
  let hud=null, lastKey='', latency=[],inputLatency=[],lastInputAt=null;
  const signed=(v,d=1)=>Number.isFinite(v)?`${v>0?'+':''}${v.toFixed(d)}`:'—';
  const safe=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function element(tag){return document.createElementNS('http://www.w3.org/2000/svg',tag);}
  function mount(view,canvas) {
    let l=layers.get(view);
    if(l?.canvas===canvas && l.svg.isConnected) return l;
    l?.svg.remove();
    const svg=element('svg'); svg.dataset.pointsnapView=view;
    svg.style.cssText='position:fixed;pointer-events:none;z-index:1001;overflow:hidden;font:12px system-ui;';
    svg.setAttribute('aria-hidden','true'); document.body.appendChild(svg);
    l={svg,canvas}; layers.set(view,l); return l;
  }
  function clear(){for(const l of layers.values()) l.svg.remove();layers.clear();hud?.remove();hud=null;lastKey='';}
  function render({context,box,baseline,guide,options,evaluation,dragging,sampledAt,inputAt}) {
    if(!G.valid(box) || !options.enabled){clear();return;}
    const started=performance.now();
    // Read all layout before writing any SVG, avoiding four forced layout passes per frame.
    const rectangles=Object.fromEntries(Object.entries(context.views).map(([k,v])=>[k,v.renderer.domElement.getBoundingClientRect()]));
    const key=JSON.stringify([box,baseline,guide?.rule,guide?.identity,guide?.reference,guide?.points?.length,guide?.face,
      options,evaluation,dragging,...Object.entries(context.views).map(([k,v])=>[...v.camera.projectionMatrix.elements,...v.camera.matrixWorldInverse.elements,
        rectangles[k].left,rectangles[k].top,rectangles[k].width,rectangles[k].height])]);
    if(key===lastKey) return; lastKey=key;
    const measured=guide?.evidence==='measured', ref=options.reference?G.reference(guide):null;
    const m=G.metrics(box,baseline,guide), cs=G.corners(box);
    for(const [view,v] of Object.entries(context.views)) {
      const canvas=v.renderer.domElement, rect=rectangles[view], {svg}=mount(view,canvas);
      svg.dataset.rule=guide?.rule || '';svg.dataset.frame=String(context.frame);
      svg.style.left=`${rect.left}px`;svg.style.top=`${rect.top}px`;svg.style.width=`${rect.width}px`;svg.style.height=`${rect.height}px`;
      svg.style.display=rect.width>0&&rect.height>0?'block':'none';
      svg.setAttribute('viewBox',`0 0 ${rect.width} ${rect.height}`);
      const p=q=>G.project(q,v.camera,rect), draw=[];
      const line=(a,b,color='#60a5fa',dash='',width=1.4)=>{
        const x=p(a),y=p(b);if(!x||!y)return;
        draw.push(`<path d="M${x.join(',')}L${y.join(',')}" stroke="${color}" stroke-width="${width}" fill="none"${dash?` stroke-dasharray="${dash}"`:''}/>`);
      };
      const text=(q,t,color='#e2e8f0')=>{const x=p(q);if(x)draw.push(`<text x="${x[0]+5}" y="${x[1]-7}" fill="${color}" stroke="#0f172a" stroke-width="3" paint-order="stroke">${safe(t)}</text>`);};
      const mesh=(b,color,dash)=>{const c=G.corners(b);for(const [a,d] of G.edges)line(c[a],c[d],color,dash);};
      if(guide?.missing && options.reference && guide.baseline) mesh(guide.baseline,'#fbbf24','6 4');
      if(ref) mesh(ref,'#38bdf8','6 4');
      const faceNames={'đầu':'front','trước':'front','đuôi':'back','sau':'back','trái':'left','phải':'right'};
      const face=G.faces[faceNames[guide?.face] || guide?.face];
      const highlight=indices=>{const qs=indices.map(i=>p(cs[i]));if(qs.every(Boolean))draw.push(`<polygon points="${qs.map(q=>q.join(',')).join(' ')}" fill="#f87171" fill-opacity=".15" stroke="#f87171" stroke-width="1.7"/>`);};
      if(measured && m.gaps && guide.rule==='fit.outside') {
        m.gaps.forEach((pair,i)=>pair.forEach((gap,j)=>{if(gap<-.05)highlight(G.faces[[['front','back'],['left','right'],['top','bottom']][i][j]]);}));
      } else if(measured && m.gaps && guide.rule==='fit.loose') {
        m.gaps.forEach((pair,i)=>pair.forEach((gap,j)=>{if(gap>(guide.thresholds?.clearance_m || .4))highlight(G.faces[[['front','back'],['left','right'],['top','bottom']][i][j]]);}));
      } else if(measured && face) highlight(face);
      const ranges=guide?.reference?.ranges || {};
      ['length','width','height'].forEach((dim,i)=>{
        const range=ranges[dim], rd=guide?.reference?.dims?.[i];
        const tolerance=guide?.thresholds?.dims_m?.[i] ?? .1;
        if(range && (box.dims[i]<range[0]||box.dims[i]>range[1]) || Number.isFinite(rd)&&Math.abs(box.dims[i]-rd)>tolerance) {
          highlight(G.faces[['front','left','top'][i]]);highlight(G.faces[['back','right','bottom'][i]]);
        }
      });
      if(options.rulers) {
        [[1,0,0],[0,1,0],[0,0,1]].forEach((axis,i)=>{
          const a=axis.map((n,j)=>n?-box.dims[j]/2:-box.dims[j]/2), b=[...a];b[i]=box.dims[i]/2;
          const wa=G.world(box,a),wb=G.world(box,b),qa=p(wa),qb=p(wb);
          if(qa&&qb&&Math.hypot(qa[0]-qb[0],qa[1]-qb[1])>25){
            line(wa,wb,['#fb7185','#4ade80','#60a5fa'][i]);text(wa.map((x,j)=>(x+wb[j])/2),`${['D','R','C'][i]} ${box.dims[i].toFixed(2)}m`);
          }
        });
        if(Number.isFinite(guide?.reference?.ground_z)) {
          const anchor=guide.baseline, ground=guide.reference.ground_z, pitch=(guide.reference.pitch_deg || 0)*Math.PI/180;
          const groundPoint=(x,y)=>{
            const yaw=anchor.rotation[2];return [anchor.center[0]+x*Math.cos(yaw)-y*Math.sin(yaw),anchor.center[1]+x*Math.sin(yaw)+y*Math.cos(yaw),ground+x*Math.tan(pitch)];
          };
          const half=anchor.dims[0]/2+1;
          line(groundPoint(-half,0),groundPoint(half,0),'#a3e635','5 3',2);
          const bottom=cs.reduce((a,b)=>a[2]-G.groundHeight(a,guide)<b[2]-G.groundHeight(b,guide)?a:b);
          const onGround=[bottom[0],bottom[1],G.groundHeight(bottom,guide)];
          line(bottom,onGround,'#fbbf24','',2);text(onGround,`${signed(m.groundGap*100)} cm`,'#fbbf24');
          if(ref) {
            const target=ref.center[2]-ref.dims[2]/2, band=guide.thresholds?.distance_m || 0;
            for(const dz of [-band,band])line(groundPoint(-half,0).map((x,i)=>i===2?x+target-ground+dz:x),groundPoint(half,0).map((x,i)=>i===2?x+target-ground+dz:x),'#38bdf8','2 4');
          }
        }
      }
      if(guide?.rule?.startsWith('heading.')) {
        const o=[...box.center];o[2]+=box.dims[2]/2+.1;const radius=Math.max(box.dims[0]/2,.7);
        const tip=yaw=>[o[0]+radius*Math.cos(yaw),o[1]+radius*Math.sin(yaw),o[2]];
        line(o,tip(box.rotation[2]),'#fb7185','',2);text(tip(box.rotation[2]),'Hướng box','#fb7185');
        if(Number.isFinite(guide.reference?.yaw)) {
          const target=guide.reference.yaw,delta=G.wrap(target-box.rotation[2]);line(o,tip(target),'#38bdf8','5 3',2);
          let prev=tip(box.rotation[2]);for(let i=1;i<=24;i++){const next=tip(box.rotation[2]+delta*i/24);line(prev,next,'#fbbf24');prev=next;}
          text(tip(box.rotation[2]+delta/2),`${signed(-m.yawGap)}°`,'#fbbf24');
        }
      }
      if(options.points && measured && guide.points?.length) {
        const paths=['',''];const stride=Math.max(1,Math.ceil(guide.points.length/300));
        for(let i=0;i<guide.points.length;i+=stride){const q=guide.points[i],s=p(q);if(!s)continue;
          const local=G.local(box,q),outside=local.some((x,j)=>Math.abs(x)>box.dims[j]/2+.05);
          paths[outside?1:0]+=`M${s[0].toFixed(1)},${s[1].toFixed(1)}h.1`;
        }
        paths.forEach((path,i)=>draw.push(`<path d="${path}" stroke="${i?'#f87171':'#67e8f9'}" stroke-width="3" stroke-linecap="round" fill="none"/>`));
      }
      const preferred=guide?.preferred_view===view;
      draw.push(`<rect x="2" y="2" width="${Math.max(0,rect.width-4)}" height="${Math.max(0,rect.height-4)}" rx="3" stroke="${preferred?'#38bdf8':'transparent'}" fill="none" stroke-width="2"/>`);
      draw.push(`<text x="10" y="20" fill="#bae6fd" stroke="#0f172a" stroke-width="3" paint-order="stroke">${names[view]} · ${view==='top'?'Dài / Rộng':view==='side'?'Dài / Cao':view==='front'?'Rộng / Cao':'X / Y / Z'}</text>`);
      svg.innerHTML=draw.join('');
    }
    if(!hud){hud=document.createElement('div');hud.id='pointsnap-manual-hud';hud.style.cssText='position:fixed;z-index:1002;pointer-events:none;background:#0f172aee;color:#e2e8f0;border:1px solid #475569;border-radius:7px;padding:9px 12px;font:12px/1.65 system-ui;max-width:390px;';document.body.appendChild(hud);}
    const rect=rectangles.perspective;hud.style.left=`${Math.max(rect.left+10,rect.right-380)}px`;hud.style.top=`${Math.max(5,rect.top+28)}px`;
    const state=dragging?'dragging':evaluation?.state || 'insufficient';
    const status=state==='cleared'?'Hết lỗi đang xét · chưa Save':state==='remaining'?'Còn lỗi đang xét':state==='checking'?'Đang kiểm lại…':dragging?'Đang kéo · số đo tham khảo':'Số đo tham khảo';
    const color=state==='cleared'?'#4ade80':state==='remaining'?'#f87171':'#fbbf24';
    const gaps=m.gaps?m.gaps.map((v,i)=>`${['D','R','C'][i]} ${signed(v[0]*100)}/${signed(v[1]*100)}`).join(' · '):'';
    hud.innerHTML=`<strong style="color:${color}">${status}</strong><br>`+
      `Tâm X/Y/Z: ${box.center.map(v=>v.toFixed(3)).join(' / ')} m<br>`+
      `D/R/C: ${box.dims.map(v=>v.toFixed(2)).join(' / ')} m · Yaw ${signed(box.rotation[2]*180/Math.PI)}°<br>`+
      `Δ vị trí: ${m.delta.map(v=>signed(v)).join(' / ')} cm<br>`+
      `Δ D/R/C: ${m.deltaDims.map(v=>signed(v)).join(' / ')} cm · Δ góc ${m.deltaRotation.map(v=>signed(v)).join(' / ')}°<br>`+
      `Roll/Pitch: ${box.rotation.slice(0,2).map(v=>signed(v*180/Math.PI)).join(' / ')}°`+
      (gaps?`<br>Dư/hụt hai mặt: ${gaps} cm`:'')+
      (evaluation?.message?`<br>${safe(evaluation.message)}`:'')+
      `<br><span style="color:#94a3b8">${safe(guide?.instruction || 'Sửa bằng công cụ CVAT · Save để lưu · Undo để hoàn tác.')}</span>`;
    latency.push(performance.now()-(sampledAt || started));if(latency.length>1000)latency.shift();
    if(dragging && Number.isFinite(inputAt) && inputAt!==lastInputAt){inputLatency.push(performance.now()-inputAt);lastInputAt=inputAt;if(inputLatency.length>1000)inputLatency.shift();}
  }
  function performanceStats(){const p95=a=>{const s=[...a].sort((a,b)=>a-b);return s.length?s[Math.min(s.length-1,Math.floor(s.length*.95))]:null;};return {samples:latency.length,render_p95_ms:p95(latency),input_samples:inputLatency.length,input_to_overlay_p95_ms:p95(inputLatency)};}
  root.PointSnapManualOverlay={render,clear,performanceStats};
})(globalThis);
