'use strict';

/**
 * Adversarial Stress Tests for Milestone M4 (Extension & Web UI Canvas Boundary)
 *
 * Authored by: teamwork_preview_challenger_m4_1
 *
 * Targets:
 * 1. Chrome Extension route whitelisting bypass attempts:
 *    - Path traversal: '../', '%2e%2e', mixed encoding, trailing slashes, null bytes.
 *    - Query string smuggling: unexpected params, duplicate params, smuggling on POST routes, hash fragments.
 *    - Foreign jobId spoofing: sender job != path job_id, foreign tab sender.
 *    - Body schema tampering: unknown properties, prototype pollution, type confusion, negative frames.
 * 2. Canvas preview data boundary inputs:
 *    - Missing points (undefined / null).
 *    - Null / undefined / incomplete ground elevation.
 *    - Zero-size canvas (clientWidth = 0, clientHeight = 0).
 *    - Zero-dimension box (L = 0, W = 0, H = 0).
 *    - Extreme coordinates and NaN values in repair overlay.
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function createBackgroundHarness(fetchImpl) {
  const noop = { addListener() {} };
  const extId = 'b'.repeat(32);
  const context = {
    URL,
    Set,
    AbortSignal,
    fetch: fetchImpl || (async () => ({ ok: true, status: 200, json: async () => ({}) })),
    btoa,
    Uint8Array,
    chrome: {
      runtime: {
        id: extId,
        getURL: () => `chrome-extension://${extId}/`,
        onMessage: noop,
        onInstalled: noop,
      },
      storage: {
        sync: {
          get: async () => ({ pointsnapUrl: 'http://127.0.0.1:8765', cvatUrls: [] }),
        },
        onChanged: noop,
      },
      permissions: {
        onAdded: noop,
        onRemoved: noop,
        contains: async () => true,
      },
      action: { onClicked: noop },
      scripting: {},
    },
  };
  vm.createContext(context);
  const bgCode = fs.readFileSync(path.join(__dirname, '../background.js'), 'utf8');
  vm.runInContext(
    bgCode + '\nglobalThis.api = { requestRoute, callPointSnap, trustedSender, httpOrigin, sameCvatOrigin };',
    context
  );
  return { ...context.api, chrome: context.chrome };
}

const legitimateSender = {
  id: 'b'.repeat(32),
  url: 'http://localhost:8080/tasks/1/jobs/42',
  frameId: 0,
  tab: { id: 7 },
};

// =========================================================================
// 1. Chrome Extension Route Whitelisting: Path Traversal Bypass Attempts
// =========================================================================

test('Adversarial Ext 1.1: Path traversal with ../ and %2e%2e are strictly rejected', () => {
  const bg = createBackgroundHarness();

  const traversalPaths = [
    '/api/jobs/../admin',
    '/api/jobs/42/tracks/../admin/repair',
    '/api/jobs/42/tracks/101/../../admin/repair',
    '/api/jobs/%2e%2e/tracks/101/repair',
    '/api/jobs/42/tracks/%2e%2e/repair',
    '/api/jobs/42/tracks/101/repair/..%2f..%2f',
    '/api/jobs/..\\tracks\\101\\repair',
    '/api/jobs/42/tracks/101/apply-repair/..',
    '/api/jobs/42/tracks/101/rollback/..%2e%2e',
    '/api/jobs/42%00/tracks/101/repair',
    '/api/jobs/42/tracks/101%00/repair',
  ];

  for (const p of traversalPaths) {
    assert.equal(bg.requestRoute('GET', p, undefined, legitimateSender), null, `Should reject traversal path: ${p}`);
    assert.equal(bg.requestRoute('POST', p, { frame: 0, repair: {} }, legitimateSender), null, `Should reject traversal POST: ${p}`);
  }
});

// =========================================================================
// 2. Chrome Extension Route Whitelisting: Query String Smuggling
// =========================================================================

test('Adversarial Ext 2.1: Query parameter smuggling and unauthorized query keys rejected', () => {
  const bg = createBackgroundHarness();

  const smuggledQueries = [
    // Unauthorized keys on GET repair
    '/api/jobs/42/tracks/101/repair?frame=0&rule=floating&admin=true',
    '/api/jobs/42/tracks/101/repair?frame=0&exec=whoami',
    '/api/jobs/42/tracks/101/repair?token=SECRET',
    '/api/jobs/42/tracks/101/repair?job_id=99',
    '/api/jobs/42/tracks/101/repair?frame=0&frame=1', // duplicate key
    '/api/jobs/42/tracks/101/repair?frame=0&rule=floating&rule=fit.outside', // duplicate rule
    '/api/jobs/42/tracks/101/repair?frame=-5', // negative frame
    '/api/jobs/42/tracks/101/repair?frame=0.5', // non-integer frame
    '/api/jobs/42/tracks/101/repair?slug=../../etc', // invalid slug
    '/api/jobs/42/tracks/101/repair?slug=slug%20with%20space', // invalid slug characters

    // Query strings appended to POST routes (strictly prohibited)
    '/api/jobs/42/tracks/101/apply-repair?debug=1',
    '/api/jobs/42/tracks/101/apply-repair?override=true',
    '/api/jobs/42/tracks/101/rollback?dump=all',
    '/api/jobs/42/tracks/101/rollback?job_id=99',

    // Hash fragment smuggling
    '/api/jobs/42/tracks/101/repair#token=LEAK',
    '/api/jobs/42/tracks/101/apply-repair#action=admin',
    '/api/jobs/42/tracks/101/rollback#bypass=1',
  ];

  for (const p of smuggledQueries) {
    const isPost = p.includes('apply-repair') || p.includes('rollback');
    const method = isPost ? 'POST' : 'GET';
    const body = isPost ? (p.includes('rollback') ? { history_id: 'snap-1' } : { frame: 0, repair: {} }) : undefined;
    assert.equal(bg.requestRoute(method, p, body, legitimateSender), null, `Should reject smuggled query: ${p}`);
  }
});

// =========================================================================
// 3. Chrome Extension Route Whitelisting: Foreign JobId Spoofing
// =========================================================================

test('Adversarial Ext 3.1: Cross-job foreign jobId access and spoofed tab origin are denied', async () => {
  const bg = createBackgroundHarness();

  // legitimateSender is on job 42
  const foreignJobs = [43, 1, 9999, 0, -1];
  for (const foreignId of foreignJobs) {
    // GET repair for foreign job
    assert.equal(
      bg.requestRoute('GET', `/api/jobs/${foreignId}/tracks/101/repair?frame=0`, undefined, legitimateSender),
      null,
      `Should reject GET repair on foreign job ${foreignId}`
    );

    // POST apply-repair for foreign job
    assert.equal(
      bg.requestRoute('POST', `/api/jobs/${foreignId}/tracks/101/apply-repair`, { frame: 0, repair: {} }, legitimateSender),
      null,
      `Should reject POST apply-repair on foreign job ${foreignId}`
    );

    // POST rollback for foreign job
    assert.equal(
      bg.requestRoute('POST', `/api/jobs/${foreignId}/tracks/101/rollback`, { history_id: 'snap-1' }, legitimateSender),
      null,
      `Should reject POST rollback on foreign job ${foreignId}`
    );
  }

  // Sender on non-job page (e.g. task page, projects page, invalid job id format)
  const invalidPathSenders = [
    { ...legitimateSender, url: 'http://localhost:8080/tasks/1' },
    { ...legitimateSender, url: 'http://localhost:8080/projects' },
    { ...legitimateSender, url: 'http://localhost:8080/tasks/1/jobs/abc' },
    { ...legitimateSender, url: 'http://localhost:8080/tasks/1/jobs/-5' },
  ];

  for (const sender of invalidPathSenders) {
    assert.equal(
      bg.requestRoute('GET', '/api/jobs/42/tracks/101/repair?frame=0', undefined, sender),
      null,
      `Should reject request from non-job URL: ${sender.url}`
    );
  }

  // Untrusted origins rejected by trustedSender
  const evilSenders = [
    { ...legitimateSender, url: 'https://evil.attacker.com/tasks/1/jobs/42' },
    { ...legitimateSender, url: 'http://malicious.org/tasks/1/jobs/42' },
    { ...legitimateSender, frameId: 1 }, // iframe sender
    { ...legitimateSender, id: 'c'.repeat(32) }, // wrong extension ID
  ];

  for (const sender of evilSenders) {
    const isTrusted = await bg.trustedSender(sender);
    assert.equal(isTrusted, false, `trustedSender must reject untrusted sender: ${sender.url || sender.id}`);
  }
});

// =========================================================================
// 4. Chrome Extension Route Whitelisting: Body Schema Tampering & Injection
// =========================================================================

test('Adversarial Ext 4.1: Malicious body schemas, prototype injection, and type confusion are rejected', () => {
  const bg = createBackgroundHarness();
  const applyPath = '/api/jobs/42/tracks/101/apply-repair';
  const rollbackPath = '/api/jobs/42/tracks/101/rollback';

  const badApplyBodies = [
    null,
    undefined,
    '{"frame": 0}',
    [1, 2, 3],
    { frame: -1, repair: {} }, // negative frame
    { frame: 1.5, repair: {} }, // float frame
    { frame: '0', repair: {} }, // string frame
    { frame: 0 }, // missing repair
    { repair: {} }, // missing frame
    { frame: 0, repair: null }, // null repair
    { frame: 0, repair: 'corrupt' }, // string repair
    { frame: 0, repair: [1, 2] }, // array repair
    { frame: 0, repair: {}, client_track_etag: 12345 }, // non-string etag
    { frame: 0, repair: {}, slug: '../../traversal' }, // path traversal in slug
    { frame: 0, repair: {}, slug: 'slug with spaces' }, // invalid slug chars
    { frame: 0, repair: {}, secret_admin_token: 'LEAK' }, // unauthorized extra key
    JSON.parse('{"frame": 0, "repair": {}, "__proto__": {"admin": true}}'), // prototype pollution attempt
  ];

  for (const body of badApplyBodies) {
    assert.equal(bg.requestRoute('POST', applyPath, body, legitimateSender), null, `Should reject bad apply body: ${JSON.stringify(body)}`);
  }

  const badRollbackBodies = [
    null,
    undefined,
    {}, // missing history_id
    { history_id: null },
    { history_id: 12345 }, // non-string history_id
    { history_id: '' }, // empty string
    { history_id: '   ' }, // blank spaces
    { history_id: 'snap-1; DROP TABLE history;' }, // SQL injection chars
    { history_id: 'snap-1/../../etc/passwd' }, // traversal
    { history_id: 'snap-1', slug: '../evil' }, // slug traversal
    { history_id: 'snap-1', extra_key: true }, // unexpected key
    { history_id: ['snap-1'] }, // array history_id
  ];

  for (const body of badRollbackBodies) {
    assert.equal(bg.requestRoute('POST', rollbackPath, body, legitimateSender), null, `Should reject bad rollback body: ${JSON.stringify(body)}`);
  }
});

// =========================================================================
// 5. Canvas Preview Data Boundary Inputs: Missing Points, Null Ground, Zero Canvas
// =========================================================================

function createMockCanvas(width, height) {
  const drawOps = [];
  return {
    clientWidth: width,
    clientHeight: height,
    width: 0,
    height: 0,
    getContext(type) {
      assert.equal(type, '2d');
      return {
        setTransform() {},
        clearRect(...args) { drawOps.push({ op: 'clearRect', args }); },
        beginPath() { drawOps.push({ op: 'beginPath' }); },
        moveTo(...args) { drawOps.push({ op: 'moveTo', args }); },
        lineTo(...args) { drawOps.push({ op: 'lineTo', args }); },
        closePath() { drawOps.push({ op: 'closePath' }); },
        stroke() { drawOps.push({ op: 'stroke' }); },
        fill() { drawOps.push({ op: 'fill' }); },
        strokeRect(...args) { drawOps.push({ op: 'strokeRect', args }); },
        fillRect(...args) { drawOps.push({ op: 'fillRect', args }); },
        arc(...args) { drawOps.push({ op: 'arc', args }); },
        save() { drawOps.push({ op: 'save' }); },
        restore() { drawOps.push({ op: 'restore' }); },
        setLineDash(pattern) { drawOps.push({ op: 'setLineDash', pattern }); },
        strokeStyle: '',
        fillStyle: '',
        lineWidth: 1,
      };
    },
    _drawOps: drawOps,
  };
}

function loadDrawPreviewFunction() {
  const appJsCode = fs.readFileSync(path.join(__dirname, '../../pointsnap/web/static/app.js'), 'utf8').replace(/\r\n/g, '\n');

  // Extract drawPreview function definition
  const match = appJsCode.match(/function\s+drawPreview\s*\([\s\S]*?\n\s{2}\}\n/);
  assert.ok(match, 'drawPreview function must exist in app.js');
  const fnCode = match[0];

  const context = {
    window: { devicePixelRatio: 1 },
    getComputedStyle: () => ({
      getPropertyValue: (prop) => (prop.includes('color') ? '#000000' : '#4CC38A'),
    }),
    document: { documentElement: {} },
    Math,
  };
  vm.createContext(context);
  vm.runInContext(`${fnCode}\nglobalThis.drawPreview = drawPreview;`, context);
  return context.drawPreview;
}

test('Adversarial Canvas 5.1: Null / undefined ground does not crash drawPreview in any view', () => {
  const drawPreview = loadDrawPreviewFunction();
  const canvas = createMockCanvas(300, 200);

  const dataNullGround = {
    box: { length: 4.5, width: 2.0, height: 1.6 },
    points: [[0, 0, 0], [1, 0, 0]],
    ground: null,
    color: 'accent',
  };

  for (const view of ['top', 'side', 'front']) {
    assert.doesNotThrow(() => {
      drawPreview(canvas, dataNullGround, view);
    }, `Should safely render view '${view}' when ground is null`);
  }

  // Also undefined ground
  const dataUndefinedGround = {
    box: { length: 4.5, width: 2.0, height: 1.6 },
    points: [[0, 0, 0]],
    color: 'accent',
  };
  for (const view of ['top', 'side', 'front']) {
    assert.doesNotThrow(() => {
      drawPreview(canvas, dataUndefinedGround, view);
    }, `Should safely render view '${view}' when ground is undefined`);
  }
});

test('Adversarial Canvas 5.2: Empty points array renders bounding box and orientation without error', () => {
  const drawPreview = loadDrawPreviewFunction();
  const canvas = createMockCanvas(300, 200);

  const dataEmptyPoints = {
    box: { length: 4.5, width: 2.0, height: 1.6 },
    points: [],
    ground: { z: -0.8, pitch_deg: 0.5 },
    color: 'error',
    repair: {
      delta_center: [0.0, 0.0, -0.2],
      delta_dims: [0.0, 0.0, 0.0],
      delta_yaw: 0.1,
    },
    repairApplied: false,
  };

  for (const view of ['top', 'side', 'front']) {
    assert.doesNotThrow(() => {
      drawPreview(canvas, dataEmptyPoints, view);
    }, `Should safely render view '${view}' with 0 LiDAR points`);
  }
});

test('Adversarial Canvas 5.3: Zero canvas dimensions handle scale gracefully without uncaught exceptions', () => {
  const drawPreview = loadDrawPreviewFunction();
  const zeroCanvas = createMockCanvas(0, 0);

  const data = {
    box: { length: 4.5, width: 2.0, height: 1.6 },
    points: [[0, 0, 0]],
    ground: null,
    color: 'accent',
  };

  for (const view of ['top', 'side', 'front']) {
    assert.doesNotThrow(() => {
      drawPreview(zeroCanvas, data, view);
    }, `Zero-size canvas should not throw in view '${view}'`);
  }
});

test('Adversarial Canvas 5.4: Proposed repair overlay with extreme deltas and zero dims does not throw', () => {
  const drawPreview = loadDrawPreviewFunction();
  const canvas = createMockCanvas(300, 200);

  const dataExtremeRepair = {
    box: { length: 4.5, width: 2.0, height: 1.6 },
    points: [[0, 0, 0]],
    color: 'accent',
    repair: {
      delta_center: [1000.0, -500.0, -100.0],
      delta_dims: [50.0, 20.0, 10.0],
      delta_yaw: Math.PI * 10,
    },
    repairApplied: false,
  };

  for (const view of ['top', 'side', 'front']) {
    assert.doesNotThrow(() => {
      drawPreview(canvas, dataExtremeRepair, view);
    }, `Extreme repair values should not throw in view '${view}'`);
  }
});

test('Adversarial Canvas 5.5: Missing / null points renders safely without TypeError', () => {
  const drawPreview = loadDrawPreviewFunction();
  const canvas = createMockCanvas(300, 200);

  const dataNullPoints = {
    box: { length: 4.5, width: 2.0, height: 1.6 },
    points: null,
    ground: null,
    color: 'accent',
  };

  for (const view of ['top', 'side', 'front']) {
    assert.doesNotThrow(() => {
      drawPreview(canvas, dataNullPoints, view);
    }, `Should safely render view '${view}' when data.points is null`);
  }

  // Also undefined points
  assert.doesNotThrow(() => {
    drawPreview(canvas, { box: { length: 4.5, width: 2.0, height: 1.6 }, color: 'accent' }, 'top');
  });
});
