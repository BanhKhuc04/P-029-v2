'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');

test('an existing ServerID filter must not be mistaken for the PointSnap filter',async()=>{
  let opened=0,selected=0,submitted=0;
  const recent={click(){},getClientRects(){return [{}];}};
  const modal={querySelector(){return recent;}};
  const button={classList:{contains(){return true;}},click(){opened++;}};
  const item={textContent:'pointsnap_error is not empty',click(){selected++;}};
  const menu={querySelectorAll(){return [item];}};
  const submit={disabled:false,click(){submitted++;}};
  const document={querySelector(selector){
    if(selector==='.cvat-annotation-header-filters-button')return button;
    if(selector==='.cvat-filters-modal-visible')return modal;
    if(selector.startsWith('.cvat-recently-used-filters-dropdown'))return menu;
    if(selector==='.cvat-filters-modal-submit-button')return submit;
    return null;
  }};
  const context={document,performance:{now:()=>0},setTimeout,Date};
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../src/cvat-dom.js'),'utf8'),context);
  const result=await context.PointSnapCvat.applyRecentFilter('pointsnap_error');
  assert.equal(result.ok,true);
  assert.equal(opened,1);assert.equal(selected,1);assert.equal(submitted,1);
});
