'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const G=require('../src/manual-geometry.js');
const box={center:[10,3,2],dims:[4,2,2],rotation:[0,0,Math.PI/2]};
const near=(a,b)=>a.forEach((v,i)=>assert.ok(Math.abs(v-b[i])<1e-9,`${a} != ${b}`));
test('CVAT XYZ Euler transforms preserve roll, pitch, yaw and invert exactly',()=>{
  near(G.world(box,[2,0,0]),[10,5,2]);
  for(const r of [[.2,-.6,1.8],[-1.2,.4,-3.1],[0,0,0]]){
    const b={...box,rotation:r};near(G.local(b,G.world(b,[.7,-.3,1.4])),[.7,-.3,1.4]);
  }
});
test('all corners, dimensions and tilt metrics come from geometry without modifying inputs',()=>{
  const b={...box,rotation:[.1,-.2,.3]},before=JSON.stringify(b),corners=G.corners(b);
  assert.equal(corners.length,8);assert.equal(G.edges.length,12);
  const m=G.metrics(b,b,null);near(m.delta,[0,0,0]);near(m.deltaRotation,[0,0,0]);
  assert.equal(m.groundGap,null);assert.equal(m.gaps,null);assert.equal(JSON.stringify(b),before);
  assert.ok(m.bottom<1);
});
test('projection follows camera matrices, viewport resize and rejects invalid/behind points',()=>{
  const identity=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1];
  const camera={matrixWorldInverse:{elements:identity},projectionMatrix:{elements:identity}};
  near(G.project([0,0,0],camera,{width:400,height:200}),[200,100]);
  near(G.project([.5,.5,0],camera,{width:800,height:400}),[600,100]);
  const zoom=[...identity];zoom[0]=2;camera.projectionMatrix.elements=zoom;
  near(G.project([.5,0,0],camera,{width:400,height:200}),[400,100]);
  assert.equal(G.project([0,0,2],camera,{width:400,height:200}),null);
  assert.equal(G.project([NaN,0,0],camera,{width:400,height:200}),null);
});
test('references affect only evidenced components and never straighten tilt or snap a box',()=>{
  const baseline={...box,rotation:[.15,-.2,.3]},guide={baseline,evidence:'measured',reference:{bottom_z:-1}};
  const before=JSON.stringify(guide);const r=G.reference(guide);
  near(r.rotation,baseline.rotation);near(r.center,[10,3,0]);
  assert.equal(JSON.stringify(guide),before);
  assert.equal(G.reference({...guide,evidence:'insufficient'}),null);
  assert.equal(G.reference({...guide,reference:{}}),null);
});
test('signed clearances include protruding points and angle wrap is continuous',()=>{
  const b={center:[0,0,0],dims:[4,2,2],rotation:[0,0,0]};
  const m=G.metrics(b,b,{points:[[2.3,0,0],[-1,0,0]],reference:{yaw:Math.PI-.01}});
  assert.ok(Math.abs(m.gaps[0][0]+.3)<1e-9);
  assert.ok(Math.abs(G.wrap(-Math.PI+.01-(Math.PI-.01))-.02)<1e-9);
});
test('invalid geometry cannot produce an apparently valid guide',()=>{
  assert.equal(G.valid({...box,dims:[0,2,2]}),false);
  assert.equal(G.valid({...box,center:[Infinity,1,1]}),false);
  assert.equal(G.valid({...box,rotation:[NaN,0,0]}),false);
});
test('ground clearance follows the measured road slope rather than a flat height',()=>{
  const b={center:[0,0,1],dims:[4,2,2],rotation:[0,0,0]};
  const guide={baseline:b,reference:{ground_z:0,pitch_deg:Math.atan(.1)*180/Math.PI}};
  assert.ok(Math.abs(G.groundHeight([2,0,0],guide)-.2)<1e-9);
  assert.ok(Math.abs(G.metrics(b,b,guide).groundGap+.2)<1e-9);
});
