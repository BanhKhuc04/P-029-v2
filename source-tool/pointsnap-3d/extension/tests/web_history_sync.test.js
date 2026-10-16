'use strict';
// Web (/app): sự kiện sửa / hoàn tác box từ extension (history_rev) cập nhật trang không cần F5;
// Guideline luôn lưu luật track = false và chặn ngưỡng không hợp lệ.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function web(fetchImpl) {
  const els = new Map();
  const el = (id = '') => ({
    id, value: '', textContent: '', innerHTML: '', style: {}, children: [], attrs: {}, dataset: {}, disabled: false, hidden: false,
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    setAttribute(k, v) { this.attrs[k] = String(v); }, getAttribute(k) { return this.attrs[k] ?? null; },
    removeAttribute(k) { delete this.attrs[k]; }, addEventListener() {}, focus() {}, appendChild(c) { this.children.push(c); },
    remove() {}, querySelector() { return el(); }, querySelectorAll() { return []; }, getContext() { return { clearRect() {} }; },
  });
  const document = {
    getElementById(id) { if (!els.has(id)) els.set(id, el(id)); return els.get(id); },
    createElement() { return el(); }, querySelectorAll() { return []; }, querySelector() { return null; },
    addEventListener() {}, documentElement: el(), activeElement: null, hidden: false,
  };
  const toasts = [];
  const source = fs.readFileSync(path.join(__dirname, '../../pointsnap/web/static/app.js'), 'utf8');
  const names = ['state', 'applyHistoryEvent', 'handleSaveGuideline', 'populateGuidelineForm', 'validateGuidelineForm',
    'renderRuleToggles', 'updateRuleCounts', 'updateCvatButton'];
  const context = {
    document, fetch: fetchImpl || (async () => ({ ok: false, json: async () => ({}) })), console,
    getComputedStyle: () => ({ getPropertyValue: () => '' }), URLSearchParams, URL, Map, Set, Date, Math, Number,
    localStorage: { getItem() { return null; }, setItem() {} }, sessionStorage: { getItem() { return null; }, setItem() {} },
    window: { location: { search: '', hash: '' }, matchMedia() { return { matches: false }; }, addEventListener() {} },
    setTimeout() { return 1; }, clearTimeout() {}, setInterval() { return 1; }, clearInterval() {}, confirm: () => true,
  };
  vm.createContext(context);
  vm.runInContext(source.replace(/\}\)\(\);\s*$/, `globalThis.api={${names.join(',')}};})();`), context);
  // Ghi lại toast để kiểm tra thông báo cho người dùng.
  const container = document.getElementById('toast-container');
  container.appendChild = (t) => toasts.push(t.textContent);
  return { ...context.api, document, toasts };
}

function runWith(findings) {
  return { run_id: 'r1', job_id: 2, findings, reviews: {}, summary: {} };
}

test('extension apply marks the matching finding repaired and offers rollback on the web', () => {
  const w = web();
  const f = { rule: 'floating', severity: 'error', frame: 18, track_id: 12, label: 'car' };
  const other = { rule: 'floating', severity: 'error', frame: 19, track_id: 12, label: 'car' };
  const run = runWith([f, other]);
  w.state.currentRun = run;
  w.state.currentSlug = 'demo';
  w.applyHistoryEvent(run, { action: 'apply', job_id: 2, track_id: 12, frame: 18, history_id: 'h1', slug: 'demo', rev: 3 });
  assert.equal(w.state.appliedFindings.has(f), true);
  assert.equal(w.state.appliedFindings.has(other), false);
  assert.equal(w.state.historyStack.length, 1);
  assert.equal(w.state.historyStack[0].history_id, 'h1');
  assert.equal(w.state.historyStack[0].slug, 'demo');
  assert.match(w.toasts[0], /vừa được sửa từ CVAT/);
});

test('web ignores the echo of its own apply and rollback', () => {
  const w = web();
  const f = { rule: 'floating', severity: 'error', frame: 18, track_id: 12, label: 'car' };
  const run = runWith([f]);
  w.state.currentRun = run;
  w.state.historyStack.push({ history_id: 'mine', job_id: 2, track_id: 12, frame: 18, finding: f });
  w.state.appliedFindings.add(f);
  w.applyHistoryEvent(run, { action: 'apply', job_id: 2, track_id: 12, frame: 18, history_id: 'mine', rev: 4 });
  assert.equal(w.state.historyStack.length, 1);
  assert.equal(w.toasts.length, 0);
  // Web tự hoàn tác: đã gỡ khỏi stack và bỏ đánh dấu trước khi sự kiện tới → không thông báo nhầm.
  w.state.historyStack.pop();
  w.state.appliedFindings.delete(f);
  w.applyHistoryEvent(run, { action: 'rollback', job_id: 2, track_id: 12, frame: 18, history_id: 'mine', rev: 5 });
  assert.equal(w.toasts.length, 0);
});

test('extension rollback clears the repaired state on the web', () => {
  const w = web();
  const f = { rule: 'floating', severity: 'error', frame: 18, track_id: 12, label: 'car' };
  const run = runWith([f]);
  w.state.currentRun = run;
  w.applyHistoryEvent(run, { action: 'apply', job_id: 2, track_id: 12, frame: 18, history_id: 'h1', rev: 1 });
  w.applyHistoryEvent(run, { action: 'rollback', job_id: 2, track_id: 12, frame: 18, history_id: 'h1', rev: 2 });
  assert.equal(w.state.appliedFindings.has(f), false);
  assert.equal(w.state.historyStack.length, 0);
  assert.equal(f.repaired, false);
});

test('events for another job or a stale run are ignored', () => {
  const w = web();
  const f = { rule: 'floating', severity: 'error', frame: 18, track_id: 12 };
  const run = runWith([f]);
  w.state.currentRun = run;
  w.applyHistoryEvent(run, { action: 'apply', job_id: 9, track_id: 12, frame: 18, history_id: 'x', rev: 1 });
  w.applyHistoryEvent(runWith([f]), { action: 'apply', job_id: 2, track_id: 12, frame: 18, history_id: 'y', rev: 2 });
  assert.equal(w.state.historyStack.length, 0);
  assert.equal(w.toasts.length, 0);
});

test('guideline form always saves track rules off and rejects inverted thresholds', async () => {
  let posted = null;
  const w = web(async (url, opts) => {
    if (opts && opts.method === 'PUT') { posted = JSON.parse(opts.body); return { ok: true, json: async () => ({}) }; }
    return { ok: true, json: async () => ({ config: { rules: {}, size: { manual_ranges: {} } }, yaml: '' }) };
  });
  const cfg = { rules: { track_jump: true, floating: true }, floating: {}, gate: {}, size: { manual_ranges: {} } };
  w.state.currentSlug = 'a';
  w.state.currentGuideline = cfg;
  w.renderRuleToggles();
  w.populateGuidelineForm(cfg);
  ['rule-floating'].forEach((id) => w.document.getElementById(id).setAttribute('aria-checked', 'true'));
  await w.handleSaveGuideline();
  assert.ok(posted, 'form hợp lệ phải được lưu');
  assert.equal(posted.config.rules.track_jump, false);
  assert.equal(posted.config.rules.track_static_shift, false);
  assert.equal(posted.config.rules.floating, true);

  assert.match(w.validateGuidelineForm({ warning_m: 0.3, error_m: 0.2, single_warning_m: 0.1, single_error_m: 0.2 }, {}), /lớn hơn ngưỡng Cảnh báo/);
  assert.match(w.validateGuidelineForm({ warning_m: 0.1, error_m: 0.2, single_warning_m: 0.1, single_error_m: 0.2 },
    { van: { length: [6, 3] } }), /min lớn hơn max/);
  assert.equal(w.validateGuidelineForm({ warning_m: 0.1, error_m: 0.2, single_warning_m: 0.1, single_error_m: 0.2 },
    { van: { length: [3, 6], width: [1.5, 2.2] } }), '');
});

test('extension status chip follows the current run only', () => {
  const w = web();
  w.state.currentRun = { job_id: 2 };
  w.state.cvatLink = { online: true, jobId: 2, rev: 0, historyRev: 0 };
  w.updateCvatButton();
  assert.match(w.document.getElementById('ext-status-text').textContent, /đang mở job #2/);
  w.state.currentRun = null;
  w.updateCvatButton();
  assert.match(w.document.getElementById('ext-status-text').textContent, /chưa mở job/);
});
