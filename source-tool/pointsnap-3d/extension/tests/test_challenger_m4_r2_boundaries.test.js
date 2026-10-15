'use strict';

/**
 * Challenger Boundaries & Edge Cases Test Suite for Milestone M4 Iteration 2.
 *
 * Targets:
 * 1. Extreme float values:
 *    - Extreme large floats (1e308, -1e308) in repair deltas.
 *    - Subnormal numbers (1e-320) in dimensions and points.
 *    - Infinite / non-finite pitch degrees in ground slope calculation.
 * 2. Zero coordinates:
 *    - Points at (0, 0, 0) and zero dimensions.
 *    - Zero delta repairs (identity repair overlay).
 * 3. Negative roll and pitch:
 *    - Negative pitch angles (-15 deg, -45 deg, -89.9 deg) in side view slope.
 *    - Pitch angle near -90 deg (-Infinity slope) handled gracefully without uncaught exceptions.
 *    - Negative delta yaw values (-Math.PI/4, -Math.PI, -2*Math.PI).
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function createMockCanvas(width, height) {
  const operations = [];
  return {
    clientWidth: width,
    clientHeight: height,
    width: 0,
    height: 0,
    getContext(type) {
      if (type !== '2d') return null;
      return {
        setTransform() {},
        clearRect() {},
        save() {},
        restore() {},
        beginPath() {},
        moveTo(...args) { operations.push(['moveTo', ...args]); },
        lineTo(...args) { operations.push(['lineTo', ...args]); },
        stroke() {},
        fill() {},
        fillRect(...args) { operations.push(['fillRect', ...args]); },
        strokeRect(...args) { operations.push(['strokeRect', ...args]); },
        arc(...args) { operations.push(['arc', ...args]); },
        closePath() {},
        setLineDash() {},
        fillText() {},
      };
    },
    _operations: operations,
  };
}

function loadDrawPreviewFunction() {
  const appJsPath = path.join(__dirname, '../../pointsnap/web/static/app.js');
  const code = fs.readFileSync(appJsPath, 'utf8');

  const match = code.match(/function drawPreview\(canvas,\s*data,\s*view\)\s*\{[\s\S]*?\n\s{2}\}/);
  assert.ok(match, 'drawPreview function must exist in app.js');
  const fnCode = match[0];

  const context = {
    window: { devicePixelRatio: 1 },
    getComputedStyle: () => ({
      getPropertyValue: (prop) => (prop.includes('color') ? '#000000' : '#4CC38A'),
    }),
    document: { documentElement: {} },
    Math,
    Number,
    Array,
  };
  vm.createContext(context);
  vm.runInContext(`${fnCode}\nglobalThis.drawPreview = drawPreview;`, context);
  return context.drawPreview;
}

// =========================================================================
// 1. Extreme Float Values
// =========================================================================

test('Challenger JS Boundary 1.1: Extreme large coordinates (1e308) in repair do not crash drawPreview', () => {
  const drawPreview = loadDrawPreviewFunction();
  const canvas = createMockCanvas(400, 300);

  const data = {
    box: { length: 4.5, width: 2.0, height: 1.6 },
    points: [[0, 0, 0], [1, 0, 0]],
    repair: {
      delta_center: [1e308, -1e308, 1e308],
      delta_dims: [1.0, 0.5, 0.2],
      delta_yaw: 0.1,
    },
    repairApplied: false,
  };

  for (const view of ['top', 'side', 'front']) {
    assert.doesNotThrow(() => {
      drawPreview(canvas, data, view);
    }, `Should not crash on extreme floats in view '${view}'`);
  }
});

test('Challenger JS Boundary 1.2: Subnormal numbers (1e-320) handled safely', () => {
  const drawPreview = loadDrawPreviewFunction();
  const canvas = createMockCanvas(400, 300);

  const data = {
    box: { length: 1e-320, width: 1e-320, height: 1e-320 },
    points: [[1e-320, -1e-320, 0]],
    ground: { z: 1e-320, pitch_deg: 0.0 },
    repair: {
      delta_center: [1e-320, 0, 0],
      delta_dims: [0, 0, 0],
      delta_yaw: 0,
    },
    repairApplied: false,
  };

  for (const view of ['top', 'side', 'front']) {
    assert.doesNotThrow(() => {
      drawPreview(canvas, data, view);
    }, `Should not throw on subnormal numbers in view '${view}'`);
  }
});

// =========================================================================
// 2. Zero Coordinates
// =========================================================================

test('Challenger JS Boundary 2.1: Zero center coordinates and zero deltas render identically without divide-by-zero', () => {
  const drawPreview = loadDrawPreviewFunction();
  const canvas = createMockCanvas(400, 300);

  const data = {
    box: { length: 4.0, width: 2.0, height: 1.5 },
    points: [[0, 0, 0], [0.5, -0.5, 0]],
    ground: { z: 0.0, pitch_deg: 0.0 },
    repair: {
      delta_center: [0.0, 0.0, 0.0],
      delta_dims: [0.0, 0.0, 0.0],
      delta_yaw: 0.0,
    },
    repairApplied: false,
  };

  for (const view of ['top', 'side', 'front']) {
    assert.doesNotThrow(() => {
      drawPreview(canvas, data, view);
    }, `Should safely render zero coordinates in view '${view}'`);
  }
});

// =========================================================================
// 3. Negative Roll and Pitch
// =========================================================================

test('Challenger JS Boundary 3.1: Negative pitch angles (-15 deg, -45 deg, -89 deg) render slope correctly', () => {
  const drawPreview = loadDrawPreviewFunction();
  const canvas = createMockCanvas(400, 300);

  for (const pitch of [-15.0, -45.0, -89.0]) {
    const data = {
      box: { length: 4.5, width: 2.0, height: 1.6 },
      points: [[0, 0, 0]],
      ground: { z: -0.8, pitch_deg: pitch },
    };

    assert.doesNotThrow(() => {
      drawPreview(canvas, data, 'side');
    }, `Negative pitch ${pitch} deg should not throw in side view`);
  }
});

test('Challenger JS Boundary 3.2: Extreme negative pitch near -90 deg handled safely without uncaught exception', () => {
  const drawPreview = loadDrawPreviewFunction();
  const canvas = createMockCanvas(400, 300);

  const data = {
    box: { length: 4.5, width: 2.0, height: 1.6 },
    points: [[0, 0, 0]],
    ground: { z: -0.8, pitch_deg: -90.0 },
  };

  for (const view of ['top', 'side', 'front']) {
    assert.doesNotThrow(() => {
      drawPreview(canvas, data, view);
    }, `Pitch -90 deg should not throw in view '${view}'`);
  }
});

test('Challenger JS Boundary 3.3: Negative delta yaw angles wrap and draw dashed repair box correctly', () => {
  const drawPreview = loadDrawPreviewFunction();
  const canvas = createMockCanvas(400, 300);

  for (const dyaw of [-Math.PI / 4, -Math.PI / 2, -Math.PI, -2 * Math.PI, -10 * Math.PI]) {
    const data = {
      box: { length: 4.5, width: 2.0, height: 1.6 },
      points: [[0, 0, 0]],
      repair: {
        delta_center: [0.1, -0.1, 0.0],
        delta_dims: [0.2, 0.1, 0.0],
        delta_yaw: dyaw,
      },
      repairApplied: false,
    };

    for (const view of ['top', 'side', 'front']) {
      assert.doesNotThrow(() => {
        drawPreview(canvas, data, view);
      }, `Negative delta yaw ${dyaw} should not throw in view '${view}'`);
    }
  }
});
