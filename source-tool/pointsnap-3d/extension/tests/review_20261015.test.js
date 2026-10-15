'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const core = require('../src/core.js');
const engine = require('../src/ghost-engine.js');

test('P1-1 matches the original finding index after filtering', () => {
  assert.deepEqual(core.matchFindings([{index: 4, frame: 1, label: 'car', message: 'm', track_id: 7}],
    {frame: 1, label: 'car', value: 'm', kind: 'track', objectId: 7}), [4]);
});

test('P2-8 yaw-only snap preserves dimensions and stays OFF_TARGET', () => {
  const current = {center: [4, 0, 1], dims: [4, 2, 2], yaw: 0};
  const target = {center: [0, 0, 1], dims: [5, 3, 2], yaw: 0};
  const result = engine.evaluateMagnetSnap(current, target);
  assert.deepEqual(result.box.dims, current.dims);
  assert.equal(result.snapped, false);
  assert.equal(result.rotationSnapped, true);
  assert.equal(result.residuals.statusText, 'OFF_TARGET');
  assert.equal(engine.computeSpatialResiduals(current, target).isSnapped, false);
});

function browserHook() {
  const listeners = {};
  const documentListeners = {};
  const messages = [];
  const window = {addEventListener(type, fn) {listeners[type] = fn;}, dispatchEvent() {},
    postMessage(message) {messages.push(message);}, PointSnapGhostEngine: engine};
  const document = {readyState: 'complete', querySelector() {return null;},
    addEventListener(type, fn) {documentListeners[type] = fn;}};
  const context = {window, document, PointSnapGhostEngine: engine, Date};
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/cvat-3d-hook.js'), 'utf8'), context);
  return {hook: context.PointSnap3DHook, listeners, documentListeners, messages, window};
}

test('P1-2 unavailable is explicit, active box bridge computes real residuals', () => {
  const b = browserHook();
  assert.ok(b.messages.some(m => m.type === 'POINTSNAP_3D_UNAVAILABLE'));
  const box = {center: [0, 0, 2], dims: [4, 2, 2], yaw: 0, roll: .1, pitch: .2};
  b.listeners.message({source: b.window, data: {type: 'POINTSNAP_SET_ACTIVE_BOX', detail: {box}}});
  b.listeners.message({source: b.window, data: {type: 'POINTSNAP_SET_GHOST_TARGET', detail: {ghostTarget: {...box, center: [0, 0, 1]}}}});
  assert.equal(b.hook.getActiveBox().roll, .1);
  assert.ok(b.messages.some(m => m.type === 'POINTSNAP_3D_TELEMETRY' && m.detail.residuals.deltaZ_cm === 100));
  // No native canvas writer: browser gestures must not pretend to apply geometry.
  assert.equal(b.hook.handleHotkey({code: 'KeyL'}), false);
});

test('P1-2 pointer listeners cover canvases mounted after initialization', () => {
  const b = browserHook();
  assert.equal(typeof b.documentListeners.pointerdown, 'function');
  assert.equal(typeof b.documentListeners.pointermove, 'function');
  assert.equal(typeof b.documentListeners.pointerup, 'function');
});

test('P3-6 foreign window cannot change active geometry', () => {
  const b = browserHook();
  b.listeners.message({source: {}, data: {type: 'POINTSNAP_SET_GHOST_TARGET', detail: {ghostTarget: {center: [9,9,9]}}}});
  assert.equal(b.hook.getGhostTarget(), null);
});

test('P1-2 content sends saved CVAT geometry including tilt to MAIN world', async () => {
  const messages = [];
  const listeners = {};
  const window = {addEventListener(type, fn) {listeners[type] = fn;}, postMessage(m) {messages.push(m);}};
  const context = {PointSnapCore: core, PointSnapCvat: {},
    PointSnapCvatApi: {annotations: async () => ({tracks: [{id: 7, shapes: [
      {frame: 1, points: [1, 2, 3, .1, -.2, .3, 4, 2, 2]}]}]})},
    window, document: {}, location: {href: '', pathname: ''}, setInterval() {}, setTimeout() {}, clearInterval() {}, clearTimeout() {}};
  vm.createContext(context);
  let source = fs.readFileSync(path.join(__dirname, '../src/content.js'), 'utf8');
  source = source.replace('  root.PointSnapPanel = {', '  root.testBridge = dispatchActiveBox;\n  root.PointSnapPanel = {');
  vm.runInContext(source, context);
  const state = context.PointSnapPanel.state;
  state.job = {jobId: 1}; state.frame = 1;
  state.active = {flag: 'm', label: 'car', clientId: 3};
  state.flags = [{frame: 1, value: 'm', label: 'car', kind: 'track', objectId: 7}];
  await context.testBridge();
  const sent = messages.find(m => m.type === 'POINTSNAP_SET_ACTIVE_BOX');
  assert.deepEqual(JSON.parse(JSON.stringify(sent.detail.box)),
    {center: [1,2,3], dims: [4,2,2], roll: .1, pitch: -.2, yaw: .3});
  listeners.message({source: {}, data: {type: 'POINTSNAP_3D_TELEMETRY', detail: {fake: true}}});
  assert.equal(state.telemetry, undefined);
});
