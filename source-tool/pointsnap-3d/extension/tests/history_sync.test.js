'use strict';
// Extension: sửa / hoàn tác box ở web (history_rev) hiện ngay trên thẻ đề xuất sửa trong CVAT, không cần F5.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const core = require('../src/core.js');

function panel() {
  const source = fs.readFileSync(path.join(__dirname, '../src/content.js'), 'utf8');
  const context = {
    PointSnapCore: core, PointSnapCvat: {}, PointSnapCvatApi: {}, PointSnapTransport: async () => ({ ok: false }),
    location: { href: 'http://localhost:8080/', pathname: '/', origin: 'http://localhost:8080' },
    document: { querySelector() { return null; } }, window: { addEventListener() {} },
    performance: { now() { return 0; } }, setInterval() {}, clearInterval() {}, setTimeout() {}, Map, Set, URL,
  };
  vm.createContext(context);
  vm.runInContext(source.replace('  loadSettings().then',
    '  root.testPanel={S,applyHistoryEvent,renderRepairSection};\n  loadSettings().then'), context);
  return context.testPanel;
}

test('web apply on the open card shows applied state with rollback', () => {
  const p = panel();
  p.S.job = { jobId: 2 };
  Object.assign(p.S.repair, { trackId: 12, frame: 18, applied: false, historyId: null, confirming: true });
  p.applyHistoryEvent({ action: 'apply', job_id: 2, track_id: 12, frame: 18, history_id: 'h1', rev: 3 });
  assert.equal(p.S.repair.applied, true);
  assert.equal(p.S.repair.historyId, 'h1');
  assert.equal(p.S.repair.confirming, false);
  p.applyHistoryEvent({ action: 'rollback', job_id: 2, track_id: 12, frame: 18, history_id: 'h1', rev: 4 });
  assert.equal(p.S.repair.applied, false);
  assert.equal(p.S.repair.historyId, null);
});

test('events of another job are ignored', () => {
  const p = panel();
  p.S.job = { jobId: 2 };
  Object.assign(p.S.repair, { trackId: 12, frame: 18, applied: false, historyId: null });
  p.applyHistoryEvent({ action: 'apply', job_id: 7, track_id: 12, frame: 18, history_id: 'x', rev: 1 });
  assert.equal(p.S.repair.applied, false);
});

test('a web apply on another box is remembered when that card opens later', () => {
  const p = panel();
  p.S.job = { jobId: 2 };
  p.S.ps.online = true;
  Object.assign(p.S.repair, { trackId: 5, frame: 1 });
  p.applyHistoryEvent({ action: 'apply', job_id: 2, track_id: 12, frame: 18, history_id: 'h9', rev: 1 });
  assert.equal(p.S.repair.applied, false, 'thẻ đang mở là box khác');
  p.renderRepairSection({ frame: 18, items: [{ rule: 'floating' }] }, 12);
  assert.equal(p.S.repair.trackId, 12);
  assert.equal(p.S.repair.applied, true);
  assert.equal(p.S.repair.historyId, 'h9');
});

test('rollback of an unrelated snapshot does not clear a newer apply', () => {
  const p = panel();
  p.S.job = { jobId: 2 };
  Object.assign(p.S.repair, { trackId: 12, frame: 18, applied: true, historyId: 'new' });
  p.applyHistoryEvent({ action: 'rollback', job_id: 2, track_id: 12, frame: 18, history_id: 'old', rev: 5 });
  assert.equal(p.S.repair.applied, true);
  assert.equal(p.S.repair.historyId, 'new');
});
