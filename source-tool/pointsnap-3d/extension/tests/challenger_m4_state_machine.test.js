'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const core = require('../src/core.js');

// Helper to instantiate Extension content.js in a mock VM context
function createExtensionPanel(transport) {
  const source = fs.readFileSync(path.join(__dirname, '../src/content.js'), 'utf8');
  const domEvents = new Map();
  const document = {
    querySelector() { return null; },
    getElementById() { return null; },
    createElement() {
      return {
        style: {},
        classList: { add() {}, remove() {} },
        setAttribute() {},
        getAttribute() { return null; },
        appendChild() {},
      };
    },
  };
  const window = {
    addEventListener(evt, handler) { domEvents.set(evt, handler); },
  };
  const context = {
    PointSnapCore: core,
    PointSnapCvat: { goToFrame() {} },
    PointSnapCvatApi: {},
    PointSnapTransport: transport,
    location: { href: 'http://localhost:8080/tasks/1/jobs/2', pathname: '/tasks/1/jobs/2', origin: 'http://localhost:8080' },
    document,
    window,
    performance: { now() { return Date.now(); } },
    setInterval() {},
    clearInterval() {},
    setTimeout(fn) { return fn ? fn() : 1; },
    clearTimeout() {},
    Map,
    Set,
    URL,
    Date,
    Math,
    console,
  };
  vm.createContext(context);
  // Inject hook to expose internal functions for challenger testing
  const patched = source.replace(
    '  loadSettings().then',
    '  root.testHarness = { S, loadRepairProposal, renderRepairSection, applyRepair, rollbackRepair, onClick, setNotice };\n  loadSettings().then'
  );
  vm.runInContext(patched, context);
  return { ...context.testHarness, context };
}

// Helper to instantiate Web UI app.js in a mock VM context
function createWebUI(fetchImpl) {
  const els = new Map();
  function makeEl(id = '') {
    return {
      id,
      value: '',
      textContent: '',
      innerHTML: '',
      style: {},
      children: [],
      attrs: {},
      dataset: {},
      disabled: false,
      classList: {
        _classes: new Set(),
        add(c) { this._classes.add(c); },
        remove(c) { this._classes.delete(c); },
        toggle(c) { if (this._classes.has(c)) this._classes.delete(c); else this._classes.add(c); },
        contains(c) { return this._classes.has(c); },
      },
      setAttribute(k, v) { this.attrs[k] = v; },
      getAttribute(k) { return this.attrs[k] ?? null; },
      removeAttribute(k) { delete this.attrs[k]; },
      addEventListener() {},
      focus() {},
      appendChild(child) { this.children.push(child); },
      remove() {},
      querySelector() { return makeEl(); },
      querySelectorAll() { return []; },
      getContext() {
        return {
          clearRect() {},
          beginPath() {},
          stroke() {},
          fill() {},
          arc() {},
          rect() {},
          moveTo() {},
          lineTo() {},
          save() {},
          restore() {},
          setLineDash() {},
        };
      },
    };
  }

  const document = {
    getElementById(id) {
      if (!els.has(id)) els.set(id, makeEl(id));
      return els.get(id);
    },
    createElement() { return makeEl(); },
    querySelectorAll() { return []; },
    querySelector() { return null; },
    addEventListener() {},
    documentElement: makeEl(),
    activeElement: null,
  };

  const source = fs.readFileSync(path.join(__dirname, '../../pointsnap/web/static/app.js'), 'utf8');
  const exports = [
    'state',
    'openApplyRepairModal',
    'handleConfirmApplyRepair',
    'handleRollbackRepair',
    'fetchFindingRepair',
    'updateRepairCard',
    'renderDetailDrawer',
    'clearDetailDrawer',
    'closeModal',
    'openModal',
  ];

  let currentTime = 10000;
  const DateMock = {
    now() { return currentTime; },
    _setTime(t) { currentTime = t; },
    _advance(dt) { currentTime += dt; },
  };

  const context = {
    document,
    fetch: fetchImpl,
    console,
    getComputedStyle: () => ({ getPropertyValue: (k) => k }),
    URLSearchParams,
    URL,
    Map,
    Set,
    Date: DateMock,
    Math,
    localStorage: { getItem() { return null; }, setItem() {} },
    sessionStorage: { getItem() { return null; }, setItem() {} },
    window: { location: { search: '', hash: '' }, matchMedia: () => ({ matches: false }), addEventListener() {} },
    setTimeout(fn) { if (fn) fn(); return 1; },
    clearTimeout() {},
    setInterval() { return 1; },
    clearInterval() {},
  };

  vm.createContext(context);
  const patched = source.replace(/\}\)\(\);\s*$/, `globalThis.api = { ${exports.join(', ')} }; })();`);
  vm.runInContext(patched, context);
  return { ...context.api, els, document, DateMock };
}

function clickBtn(ext, action, datasetExtra = {}) {
  const btn = { dataset: { action, ...datasetExtra }, disabled: false };
  ext.onClick({ target: { closest: () => btn } });
}

test('Web repair: zero confidence and zero delta cannot open Apply', () => {
  const web = createWebUI();
  const f = { track_id: 101, frame: 1 };
  const rep = { confidence: 0, applicable: false, delta_center: [0, 0, 0], delta_dims: [0, 0, 0], delta_yaw: 0 };
  web.state.currentDetail = f;
  web.state.currentRepair = rep;
  web.updateRepairCard(f, rep);
  assert.equal(web.document.getElementById('repair-confidence-badge').textContent, '0% tin cậy');
  assert.equal(web.document.getElementById('btn-open-apply-repair').disabled, true);
  web.openApplyRepairModal();
  assert.equal(web.document.getElementById('modal-confirm-repair').classList.contains('open'), false);
});

test('Web repair: failed rollback retains history and original project scope', async () => {
  let body;
  const web = createWebUI(async (url, opts) => {
    body = JSON.parse(opts.body);
    return { ok: false, status: 502, json: async () => ({ detail: 'CVAT offline' }) };
  });
  web.state.currentSlug = 'other-project';
  web.state.historyStack.push({ history_id: 'saved', slug: 'original-project', job_id: 4, track_id: 101 });
  await web.handleRollbackRepair();
  assert.equal(body.slug, 'original-project');
  assert.equal(web.state.historyStack.length, 1);
  assert.equal(web.state.isApplyingRepair, false);
});

test('Web repair: unverified response never marks a finding repaired', async () => {
  const web = createWebUI(async () => ({ ok: true, status: 200, json: async () => ({ history_id: 'unverified' }) }));
  const f = { track_id: 101, frame: 1 };
  web.state.currentDetail = f;
  web.state.currentRun = { job_id: 4 };
  web.state.currentRepair = { confidence: .9, delta_center: [0, 0, -.2] };
  await web.handleConfirmApplyRepair();
  assert.equal(web.state.appliedFindings.has(f), false);
  assert.equal(web.state.historyStack.length, 0);
});

test('Web repair: confirmation uses current CVAT coordinates instead of zero or stale preview sizes', () => {
  const web = createWebUI();
  web.state.currentDetail = { track_id: 101, frame: 1 };
  web.state.previewData = { box: { length: 99, width: 99, height: 99 } };
  web.state.currentRepair = { confidence: .9, applicable: true, delta_center: [0, 0, -.2],
    delta_dims: [-1, 0, 0], delta_yaw: Math.PI / 2,
    original_cuboid: { center: [10, 5, 1.5], dims: [4, 2, 2], yaw: Math.PI / 4 },
    repaired_cuboid: { center: [10, 5, 1.3], dims: [3, 2, 2], yaw: 3 * Math.PI / 4 } };
  web.openApplyRepairModal();
  const rows = web.document.getElementById('modal-repair-table-body').children;
  assert.ok(rows[0].innerHTML.includes('1.50 m') && rows[0].innerHTML.includes('1.30 m'));
  assert.ok(rows[1].innerHTML.includes('45.0°') && rows[1].innerHTML.includes('135.0°'));
  assert.ok(rows[2].innerHTML.includes('[4.00, 2.00, 2.00]') && rows[2].innerHTML.includes('[3.00, 2.00, 2.00]'));
});

// =========================================================================
// Extension Tests
// =========================================================================

test('Challenger Ext 1: 2-step confirmation toggles and cancellation cycle', () => {
  const ext = createExtensionPanel();
  const S = ext.S;
  S.job = { jobId: 2 };
  S.ps.online = true;

  const flag = { frame: 0, items: [{ rule: 'floating' }] };
  const trackId = 101;

  // Initial state
  S.repair.data = { delta_center: [0, 0, -0.25], delta_yaw: 0, delta_dims: [0, 0, 0], confidence: 0.95 };
  S.repair.trackId = trackId;
  S.repair.frame = 0;
  S.repair.loading = false;
  S.repair.confirming = false;
  S.repair.applying = false;

  const htmlBefore = ext.renderRepairSection(flag, trackId);
  assert.ok(htmlBefore.includes('data-action="repair-apply-start"'), 'Should show initial 1-click apply button');
  assert.equal(htmlBefore.includes('data-action="repair-apply-confirm"'), false, 'Should not show confirm button yet');

  // Step 1: Click "Áp dụng sửa"
  clickBtn(ext, 'repair-apply-start');
  assert.equal(S.repair.confirming, true, 'Confirming state must be true');

  const htmlConfirm = ext.renderRepairSection(flag, trackId);
  assert.ok(htmlConfirm.includes('data-action="repair-apply-confirm"'), 'Should render confirmation action buttons');
  assert.ok(htmlConfirm.includes('data-action="repair-apply-cancel"'), 'Should render cancel button');
  assert.ok(htmlConfirm.includes('Xác nhận áp dụng'), 'Should have Vietnamese label');

  // Step 2: Click "Hủy"
  clickBtn(ext, 'repair-apply-cancel');
  assert.equal(S.repair.confirming, false, 'Confirming state must return to false upon cancel');

  const htmlAfterCancel = ext.renderRepairSection(flag, trackId);
  assert.ok(htmlAfterCancel.includes('data-action="repair-apply-start"'), 'Should return to initial 1-click button');

  // Stress-test: 50 consecutive start-cancel cycles
  for (let i = 0; i < 50; i++) {
    clickBtn(ext, 'repair-apply-start');
    assert.equal(S.repair.confirming, true);
    clickBtn(ext, 'repair-apply-cancel');
    assert.equal(S.repair.confirming, false);
  }
  assert.equal(S.repair.applying, false);
  assert.equal(S.repair.applied, false);
});

test('Challenger Ext 2: Concurrency lock on applyRepair prevents duplicate in-flight requests', async () => {
  let requestCount = 0;
  let finishRequest;
  const transport = async (method, path, body) => {
    requestCount++;
    return new Promise((resolve) => {
      finishRequest = resolve;
    });
  };

  const ext = createExtensionPanel(transport);
  const S = ext.S;
  S.job = { jobId: 2 };
  S.ps.online = true;
  S.repair.data = { delta_center: [0, 0, -0.2], confidence: 0.95 };
  S.repair.trackId = 101;
  S.repair.frame = 1;
  S.repair.confirming = true; // Confirmation modal opened

  // First call to applyRepair()
  const p1 = ext.applyRepair();
  assert.equal(S.repair.applying, true, 'applying flag must be true during in-flight call');
  assert.equal(requestCount, 1, 'First request sent');

  // Concurrent calls while in-flight
  const p2 = ext.applyRepair();
  const p3 = ext.applyRepair();
  assert.equal(requestCount, 1, 'Duplicate calls while in-flight must be ignored');

  // Verify UI renders disabled buttons during applying
  const htmlApplying = ext.renderRepairSection({ frame: 1, items: [{ rule: 'floating' }] }, 101);
  assert.ok(htmlApplying.includes('disabled'), 'Buttons must be disabled while applying');

  // Resolve transport
  finishRequest({ ok: true, data: { history_id: 'snap-1234-abcd', new_scan_verdict: 'NOT_RUN', sync_status: 'verified', track_etag: 'new-etag' } });
  await p1;
  await p2;
  await p3;

  assert.equal(S.repair.applying, false, 'applying flag must reset to false');
  assert.equal(S.repair.applied, true, 'applied flag must be true');
  assert.equal(S.repair.historyId, 'snap-1234-abcd');
  assert.equal(S.repair.verdict, 'NOT_RUN');
  assert.equal(requestCount, 1, 'Total requests must strictly equal 1');
});

test('Challenger Ext 3: Multiple rapid switches between findings drop stale in-flight responses', async () => {
  let resolveProposalA;
  let resolveProposalB;

  const transport = async (method, path) => {
    if (path.includes('tracks/101/repair')) {
      return new Promise((r) => { resolveProposalA = r; });
    }
    if (path.includes('tracks/102/repair')) {
      return new Promise((r) => { resolveProposalB = r; });
    }
    return { ok: false };
  };

  const ext = createExtensionPanel(transport);
  const S = ext.S;
  S.job = { jobId: 2 };
  S.ps.online = true;

  const flagA = { frame: 0, items: [{ rule: 'floating' }] };
  const flagB = { frame: 4, items: [{ rule: 'fit.outside' }] };

  // 1. User selects Finding A (track 101, frame 0)
  ext.renderRepairSection(flagA, 101);
  assert.equal(S.repair.trackId, 101);
  assert.equal(S.repair.frame, 0);
  assert.equal(S.repair.loading, true);

  // 2. User quickly navigates to Finding B (track 102, frame 4) before A resolves
  ext.renderRepairSection(flagB, 102);
  assert.equal(S.repair.trackId, 102);
  assert.equal(S.repair.frame, 4);
  assert.equal(S.repair.loading, true);

  // 3. Stale Finding A response resolves now
  resolveProposalA({
    ok: true,
    data: {
      repair: { delta_center: [0, 0, -0.99], reason: 'Old proposal for A' },
      track_etag: 'etag_A',
    },
  });
  // Yield microtasks
  await new Promise((r) => setTimeout(r, 10));

  // Assert S.repair was NOT corrupted by stale Finding A response
  assert.equal(S.repair.trackId, 102);
  assert.equal(S.repair.frame, 4);
  assert.equal(S.repair.data, null, 'Stale A data must be discarded');

  // 4. Finding B response resolves
  resolveProposalB({
    ok: true,
    data: {
      repair: { delta_center: [0.1, 0.2, 0.0], reason: 'Fresh proposal for B' },
      track_etag: 'etag_B',
    },
  });
  await new Promise((r) => setTimeout(r, 10));

  assert.equal(S.repair.data?.reason, 'Fresh proposal for B');
  assert.equal(S.repair.trackEtag, 'etag_B');
  assert.equal(S.repair.loading, false);
});

test('Challenger Ext 4: Rollback concurrency and state restoration', async () => {
  let rollbackCalls = 0;
  let finishRollback;
  const transport = async (method, path, body) => {
    if (path.includes('rollback')) {
      rollbackCalls++;
      return new Promise((resolve) => { finishRollback = resolve; });
    }
    return { ok: false };
  };

  const ext = createExtensionPanel(transport);
  const S = ext.S;
  S.job = { jobId: 2 };
  S.ps.online = true;
  S.repair.trackId = 101;
  S.repair.frame = 2;
  S.repair.applied = true;
  S.repair.historyId = 'snap-to-rollback';

  // Trigger rollback
  const r1 = ext.rollbackRepair();
  assert.equal(S.repair.rollingBack, true);
  assert.equal(rollbackCalls, 1);

  // Duplicate click while rolling back
  const r2 = ext.rollbackRepair();
  assert.equal(rollbackCalls, 1, 'Duplicate rollback calls must be blocked');

  // Resolve rollback
  finishRollback({ ok: true, data: { status: 'ok', sync_status: 'verified' } });
  await r1;
  await r2;

  assert.equal(S.repair.rollingBack, false);
  assert.equal(S.repair.applied, false);
  assert.equal(S.repair.historyId, null);
  assert.equal(rollbackCalls, 1);
});

// =========================================================================
// Web UI Tests
// =========================================================================

test('Challenger Web 1: 500ms debounce on openApplyRepairModal rejects rapid clicks', () => {
  const web = createWebUI();
  const f = { track_id: 101, frame: 2, severity: 'error', rule: 'floating' };
  const rep = { delta_center: [0, 0, -0.25], delta_dims: [0, 0, 0], delta_yaw: 0, confidence: 0.95 };

  web.state.currentDetail = f;
  web.state.currentRepair = rep;
  web.state.currentRun = { job_id: 4 };

  const modal = web.document.getElementById('modal-confirm-repair');

  // t = 10000: Click 1
  web.DateMock._setTime(10000);
  web.openApplyRepairModal();
  assert.equal(modal.style.display, 'flex', 'Modal opened on click 1');

  // Reset modal display to check if subsequent rapid calls open it
  modal.style.display = 'none';

  // Rapid clicks at t = 10100, 10200, 10300, 10450 (< 500ms debounce)
  for (const t of [10100, 10200, 10300, 10450]) {
    web.DateMock._setTime(t);
    web.openApplyRepairModal();
    assert.equal(modal.style.display, 'none', `Click at t=${t} must be debounced`);
  }

  // Click at t = 10501 (> 500ms)
  web.DateMock._setTime(10501);
  web.openApplyRepairModal();
  assert.equal(modal.style.display, 'flex', 'Click after 500ms must be accepted');
});

test('Challenger Web 2: Concurrency lock on handleConfirmApplyRepair blocks duplicate in-flight submissions', async () => {
  let postCount = 0;
  let finishFetch;
  const fetchMock = async (url, opts) => {
    if (url.includes('apply-repair')) {
      postCount++;
      return new Promise((resolve) => { finishFetch = resolve; });
    }
    return { ok: true, json: async () => ({}) };
  };

  const web = createWebUI(fetchMock);
  const f = { track_id: 101, frame: 2, severity: 'error', rule: 'floating' };
  const rep = { delta_center: [0, 0, -0.25], delta_dims: [0, 0, 0], delta_yaw: 0, confidence: 0.95 };

  web.state.currentDetail = f;
  web.state.currentRepair = rep;
  web.state.currentRun = { job_id: 4 };

  // First call
  const p1 = web.handleConfirmApplyRepair();
  assert.equal(web.state.isApplyingRepair, true);
  assert.equal(postCount, 1);

  // Rapid duplicate calls (simulating rapid user clicks on confirmation button)
  const p2 = web.handleConfirmApplyRepair();
  const p3 = web.handleConfirmApplyRepair();
  assert.equal(postCount, 1, 'Duplicate calls must be blocked by isApplyingRepair lock');

  // Resolve HTTP POST
  finishFetch({
    ok: true,
    status: 200,
    json: async () => ({ status: 'ok', history_id: 'snap-uuid-1', new_scan_verdict: 'NOT_RUN', sync_status: 'verified', track_etag: 'new-etag' }),
  });

  await p1;
  await p2;
  await p3;

  assert.equal(web.state.isApplyingRepair, false);
  assert.equal(postCount, 1);
  assert.equal(web.state.historyStack.length, 1);
  assert.equal(web.state.historyStack[0].history_id, 'snap-uuid-1');
  assert.ok(web.state.appliedFindings.has(f));
  assert.equal(f.repaired, true);
});

test('Challenger Web 3: Race condition check when switching findings while fetchFindingRepair is in flight', async () => {
  let resolveA;
  let resolveB;

  const fetchMock = async (url) => {
    if (url.includes('findings/0/repair')) {
      return new Promise((r) => { resolveA = r; });
    }
    if (url.includes('findings/1/repair')) {
      return new Promise((r) => { resolveB = r; });
    }
    return { ok: false };
  };

  const web = createWebUI(fetchMock);
  web.state.currentSlug = 'test-proj';
  web.state.currentRun = { run_id: 'run-1' };

  const findingA = { track_id: 101, frame: 0, rule: 'floating' };
  const findingB = { track_id: 102, frame: 3, rule: 'heading.flip' };

  // Select A
  web.state.currentDetail = findingA;
  const pA = web.fetchFindingRepair(findingA, 0);

  // Switch to B before A completes
  web.state.currentDetail = findingB;
  const pB = web.fetchFindingRepair(findingB, 1);

  // A arrives now (slow response)
  resolveA({
    ok: true,
    json: async () => ({
      repair: { delta_center: [0, 0, -0.3], reason: 'Proposal for A' },
      track_etag: 'etag_A',
    }),
  });
  await pA;

  // Verify A does not overwrite current state
  assert.equal(web.state.currentRepair, null, 'Stale A repair proposal must NOT be set in state');
  assert.equal(web.state.currentTrackEtag, null);

  // B arrives
  resolveB({
    ok: true,
    json: async () => ({
      repair: { delta_yaw: 3.1415, reason: 'Proposal for B' },
      track_etag: 'etag_B',
    }),
  });
  await pB;

  // Verify B is properly set
  assert.equal(web.state.currentRepair?.reason, 'Proposal for B');
  assert.equal(web.state.currentTrackEtag, 'etag_B');
});

test('Challenger Web 4: Strict LIFO rollback order under multiple sequential applies', async () => {
  const rollbackCalls = [];
  const fetchMock = async (url, opts) => {
    if (url.includes('rollback')) {
      const body = JSON.parse(opts.body);
      rollbackCalls.push({ url, body });
      return { ok: true, status: 200, json: async () => ({ status: 'ok', sync_status: 'verified' }) };
    }
    return { ok: false };
  };

  const web = createWebUI(fetchMock);
  web.state.currentSlug = 'test-proj';

  const f1 = { track_id: 101, frame: 1, severity: 'error', severity_label: 'Lỗi' };
  const f2 = { track_id: 101, frame: 2, severity: 'warning', severity_label: 'Cảnh báo' };
  const f3 = { track_id: 105, frame: 0, severity: 'error', severity_label: 'Lỗi' };

  // Simulate 3 applies in order: f1 -> f2 -> f3
  web.state.historyStack.push({ history_id: 'snap-1', job_id: 4, track_id: 101, frame: 1, finding: f1 });
  web.state.appliedFindings.add(f1);
  f1.repaired = true;

  web.state.historyStack.push({ history_id: 'snap-2', job_id: 4, track_id: 101, frame: 2, finding: f2 });
  web.state.appliedFindings.add(f2);
  f2.repaired = true;

  web.state.historyStack.push({ history_id: 'snap-3', job_id: 4, track_id: 105, frame: 0, finding: f3 });
  web.state.appliedFindings.add(f3);
  f3.repaired = true;

  assert.equal(web.state.historyStack.length, 3);

  // Rollback 1: Must pop snap-3
  web.state.currentDetail = f3;
  await web.handleRollbackRepair();
  assert.equal(rollbackCalls.length, 1);
  assert.equal(rollbackCalls[0].body.history_id, 'snap-3');
  assert.equal(rollbackCalls[0].url, '/api/jobs/4/tracks/105/rollback');
  assert.equal(f3.repaired, false);
  assert.equal(web.state.appliedFindings.has(f3), false);

  // Rollback 2: Must pop snap-2
  web.state.currentDetail = f2;
  await web.handleRollbackRepair();
  assert.equal(rollbackCalls.length, 2);
  assert.equal(rollbackCalls[1].body.history_id, 'snap-2');
  assert.equal(rollbackCalls[1].url, '/api/jobs/4/tracks/101/rollback');
  assert.equal(f2.repaired, false);
  assert.equal(web.state.appliedFindings.has(f2), false);

  // Rollback 3: Must pop snap-1
  web.state.currentDetail = f1;
  await web.handleRollbackRepair();
  assert.equal(rollbackCalls.length, 3);
  assert.equal(rollbackCalls[2].body.history_id, 'snap-1');
  assert.equal(rollbackCalls[2].url, '/api/jobs/4/tracks/101/rollback');
  assert.equal(f1.repaired, false);
  assert.equal(web.state.appliedFindings.has(f1), false);

  // Stack is now empty
  assert.equal(web.state.historyStack.length, 0);

  // Rollback 4: On empty stack, must do nothing gracefully
  await web.handleRollbackRepair();
  assert.equal(rollbackCalls.length, 3, 'No additional network request on empty stack');
});

test('Challenger Web 5: Detail drawer isolation if selection switches while apply is in flight', async () => {
  let resolveApply;
  const fetchMock = async (url) => {
    if (url.includes('apply-repair')) {
      return new Promise((r) => { resolveApply = r; });
    }
    return { ok: true, json: async () => ({}) };
  };

  const web = createWebUI(fetchMock);
  web.state.currentSlug = 'test-proj';
  web.state.currentRun = { job_id: 4 };

  const findingA = { track_id: 101, frame: 1, severity: 'error', severity_label: 'Lỗi' };
  const findingB = { track_id: 102, frame: 5, severity: 'warning', severity_label: 'Cảnh báo' };

  web.state.currentDetail = findingA;
  web.state.currentRepair = { delta_center: [0, 0, -0.2], reason: 'Proposal A' };

  // Trigger apply for A
  const pApply = web.handleConfirmApplyRepair();
  assert.equal(web.state.isApplyingRepair, true);

  // User closes modal and switches detail drawer to finding B while A is in flight
  web.closeModal('modal-confirm-repair');
  web.renderDetailDrawer(findingB);
  assert.equal(web.state.currentDetail, findingB);

  const badgeEl = web.document.getElementById('detail-sev-badge');
  assert.equal(badgeEl.textContent, 'Cảnh báo', 'Drawer should display finding B severity');

  // Now apply for A resolves
  resolveApply({
    ok: true,
    status: 200,
    json: async () => ({ status: 'ok', history_id: 'snap-A', new_scan_verdict: 'NOT_RUN', sync_status: 'verified', track_etag: 'new-etag' }),
  });
  await pApply;

  // Verify: Finding A is recorded as repaired in historyStack and appliedFindings
  assert.equal(findingA.repaired, true);
  assert.ok(web.state.appliedFindings.has(findingA));

  // Critical check: Finding B was NOT repaired. Did finding B's badge get overwritten with 'PASS (ĐÃ SỬA)'?
  // If lines 1717-1729 lack `if (state.currentDetail === f)`, badgeEl will show 'PASS (ĐÃ SỬA)' incorrectly!
  const isBadgeCorrupted = (badgeEl.textContent !== 'Cảnh báo');
  assert.equal(
    isBadgeCorrupted,
    false,
    `Finding B badge was corrupted to "${badgeEl.textContent}" because apply response lacked currentDetail check!`
  );
});

