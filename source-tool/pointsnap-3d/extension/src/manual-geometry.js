/* Pure geometry. Units: metres/radians; CVAT Euler XYZ, z up. Never modifies its inputs. */
(function (root) {
  'use strict';
  const wrap = a => Math.atan2(Math.sin(a), Math.cos(a));
  const add = (a, b) => a.map((v, i) => v + b[i]);
  const sub = (a, b) => a.map((v, i) => v - b[i]);
  function matrix(rotation) {
    const [x, y, z] = rotation, a = Math.cos(x), b = Math.sin(x), c = Math.cos(y),
      d = Math.sin(y), e = Math.cos(z), f = Math.sin(z);
    return [[c*e,-c*f,d],[a*f+b*e*d,a*e-b*f*d,-b*c],[b*f-a*e*d,b*e+a*f*d,a*c]];
  }
  const mul = (m, p) => m.map(row => row.reduce((s, v, i) => s + v*p[i], 0));
  const world = (box, p) => add(box.center, mul(matrix(box.rotation), p));
  function local(box, p) {
    const m = matrix(box.rotation), q = sub(p, box.center);
    return [0,1,2].map(i => m.reduce((s, row, j) => s + row[i]*q[j], 0));
  }
  const signs = [[1,1,-1],[-1,1,-1],[-1,-1,-1],[1,-1,-1],[1,1,1],[-1,1,1],[-1,-1,1],[1,-1,1]];
  const corners = box => signs.map(s => world(box, s.map((v, i) => v*box.dims[i]/2)));
  const edges = [[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]];
  const faces = {front:[0,3,7,4],back:[1,2,6,5],left:[0,1,5,4],right:[2,3,7,6],bottom:[0,1,2,3],top:[4,5,6,7]};
  function project(point, camera, rect) {
    if (!camera?.matrixWorldInverse?.elements || !camera?.projectionMatrix?.elements) return null;
    const transform = (m, v) => [0,1,2,3].map(i => m[i]*v[0]+m[i+4]*v[1]+m[i+8]*v[2]+m[i+12]*v[3]);
    const v = transform(camera.projectionMatrix.elements, transform(camera.matrixWorldInverse.elements, [...point,1]));
    if (!v.every(Number.isFinite) || Math.abs(v[3]) < 1e-10 || camera.isPerspectiveCamera && v[3] <= 0) return null;
    const n = v.slice(0,3).map(x => x/v[3]);
    if (n[2] < -1 || n[2] > 1) return null;
    return [(n[0]+1)*rect.width/2, (1-n[1])*rect.height/2];
  }
  function valid(box) {
    return !!box && ['center','dims','rotation'].every(k => Array.isArray(box[k]) && box[k].length===3 && box[k].every(Number.isFinite)) && box.dims.every(v => v>0);
  }
  function reference(guide) {
    if (!valid(guide?.baseline) || guide.evidence !== 'measured') return null;
    const b = JSON.parse(JSON.stringify(guide.baseline)), r = guide.reference || {};
    let changed = false;
    if (Number.isFinite(r.bottom_z)) { b.center[2] = r.bottom_z+b.dims[2]/2; changed=true; }
    if (Number.isFinite(r.yaw)) { b.rotation[2]=r.yaw; changed=true; }
    if (r.dims?.length===3) { b.dims=[...r.dims]; changed=true; }
    return changed ? b : null;
  }
  function metrics(box, baseline, guide) {
    const base = valid(baseline) ? baseline : box, r=guide?.reference || {}, points=guide?.points || [];
    const qs = points.map(p => local(box,p)), half=box.dims.map(v=>v/2);
    const gaps = qs.length ? [0,1,2].map(i => [half[i]-Math.max(...qs.map(p=>p[i])), half[i]+Math.min(...qs.map(p=>p[i]))]) : null;
    return {delta:sub(box.center,base.center).map(v=>v*100),
      deltaDims:sub(box.dims,base.dims).map(v=>v*100),
      deltaRotation:sub(box.rotation,base.rotation).map(v=>wrap(v)*180/Math.PI),
      bottom:Math.min(...corners(box).map(p=>p[2])),
      groundGap:Number.isFinite(r.ground_z)? Math.min(...corners(box).map(p=>p[2]-groundHeight(p,guide))):null,
      yawGap:Number.isFinite(r.yaw)?wrap(box.rotation[2]-r.yaw)*180/Math.PI:null, gaps};
  }
  function groundHeight(point,guide){
    const r=guide?.reference || {},b=guide?.baseline;
    if(!Number.isFinite(r.ground_z))return null;
    if(!valid(b))return r.ground_z;
    const along=(point[0]-b.center[0])*Math.cos(b.rotation[2])+(point[1]-b.center[1])*Math.sin(b.rotation[2]);
    return r.ground_z+along*Math.tan((r.pitch_deg || 0)*Math.PI/180);
  }
  const api={wrap,add,sub,matrix,mul,world,local,corners,edges,faces,project,valid,reference,metrics,groundHeight};
  if (typeof module!=='undefined' && module.exports) module.exports=api;
  else root.PointSnapGeometry=api;
})(globalThis);
