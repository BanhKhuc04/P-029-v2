/*
 * Unit and Integration Tests for PointSnap 3D Live Telemetry HUD (Milestone M3)
 * Module: extension/src/telemetry-hud.js
 */

const test = require('node:test');
const assert = require('node:assert/strict');

// Mock browser DOM environment for Node.js
function setupMockDOM() {
  const elements = new Map();
  const listeners = new Map();

  class MockElement {
    constructor(tagName, id = '') {
      this.tagName = tagName.toUpperCase();
      this.id = id;
      this.className = '';
      this.style = {};
      this._innerHTML = '';
      this.textContent = '';
      this.children = [];
      this.parentElement = null;
    }

    get innerHTML() {
      return this._innerHTML;
    }

    set innerHTML(html) {
      this._innerHTML = html;
      this.children = [];
      const elRegex = /<([a-z0-9]+)([^>]*)>/gi;
      let match;
      while ((match = elRegex.exec(html)) !== null) {
        const tagName = match[1];
        if (tagName.startsWith('/')) continue;
        const attrs = match[2];
        const idMatch = attrs.match(/id=["']([^"']+)["']/i);
        const classMatch = attrs.match(/class=["']([^"']+)["']/i);
        const id = idMatch ? idMatch[1] : '';
        const className = classMatch ? classMatch[1] : '';

        const child = new MockElement(tagName, id);
        child.className = className;
        child.parentElement = this;
        this.children.push(child);
        if (id) elements.set(id, child);
      }
    }

    appendChild(child) {
      child.parentElement = this;
      this.children.push(child);
      if (child.id) elements.set(child.id, child);
      return child;
    }

    querySelector(sel) {
      if (sel.startsWith('#')) {
        const id = sel.slice(1);
        return elements.get(id) || this._findChild((c) => c.id === id);
      }
      if (sel.startsWith('.')) {
        const cls = sel.slice(1);
        return this._findChild((c) => c.className && c.className.includes(cls));
      }
      return null;
    }

    _findChild(predicate) {
      for (const child of this.children) {
        if (predicate(child)) return child;
        const sub = child._findChild(predicate);
        if (sub) return sub;
      }
      return null;
    }

    getBoundingClientRect() {
      return { width: 1024, height: 768, left: 0, top: 0, right: 1024, bottom: 768 };
    }
  }

  const mockDocument = {
    head: new MockElement('head'),
    body: new MockElement('body'),
    createElement: (tag) => {
      const el = new MockElement(tag);
      return el;
    },
    getElementById: (id) => elements.get(id) || null,
    querySelector: (sel) => {
      if (sel.includes('body')) return mockDocument.body;
      return null;
    },
  };

  const mockWindow = {
    addEventListener: (type, handler) => {
      if (!listeners.has(type)) listeners.set(type, []);
      listeners.get(type).push(handler);
    },
    dispatchEvent: (event) => {
      const handlers = listeners.get(event.type) || [];
      handlers.forEach((h) => h(event));
    },
    postMessage: (data) => {
      const handlers = listeners.get('message') || [];
      handlers.forEach((h) => h({ data }));
    },
  };

  return { mockDocument, mockWindow, elements, listeners };
}

test('1.1 formatSigned and formatAbs handle positive, negative, zero and non-finite values', () => {
  const hud = require('../src/telemetry-hud.js');

  assert.equal(hud.formatSigned(5.2, 1, ' cm'), '+5.2 cm');
  assert.equal(hud.formatSigned(-3.7, 1, '°'), '-3.7°');
  assert.equal(hud.formatSigned(0.0, 1, ' cm'), '0.0 cm');
  assert.equal(hud.formatSigned(NaN, 1, ' cm'), '--');
  assert.equal(hud.formatSigned(Infinity, 1, ' cm'), '--');
  assert.equal(hud.formatSigned(null, 1, ' cm'), '--');

  assert.equal(hud.formatAbs(-12.4, 1, ' cm'), '12.4 cm');
  assert.equal(hud.formatAbs(8.9, 1, '°'), '8.9°');
  assert.equal(hud.formatAbs(NaN, 1, ' cm'), '--');
});

test('1.2 project3DToScreen projects 3D coordinates using camera.project()', () => {
  const hud = require('../src/telemetry-hud.js');

  const mockCamera = {
    project: (vec) => {
      // Mock NDC projection: x: 0.2, y: -0.4, z: 0.5
      vec.x = 0.2;
      vec.y = -0.4;
      vec.z = 0.5;
      return vec;
    },
  };

  const mockContainer = {
    getBoundingClientRect: () => ({ width: 1000, height: 800, left: 0, top: 0 }),
  };

  // Mock global THREE.Vector3
  const origThree = global.THREE;
  global.THREE = {
    Vector3: class {
      constructor(x, y, z) {
        this.x = x;
        this.y = y;
        this.z = z;
      }
      project(cam) {
        return cam.project(this);
      }
    },
  };

  const screenPos = hud.project3DToScreen([2.0, 3.0, 1.0], mockCamera, mockContainer);
  assert.ok(screenPos);
  // screenX = (0.2 * 0.5 + 0.5) * 1000 = 0.6 * 1000 = 600
  // screenY = (-(-0.4 * 0.5) + 0.5) * 800 = (0.2 + 0.5) * 800 = 560
  assert.equal(screenPos.x, 600);
  assert.equal(screenPos.y, 560);

  // Behind camera check (z > 1.0)
  const behindCamera = {
    project: (vec) => {
      vec.z = 1.5;
      return vec;
    },
  };
  const behindPos = hud.project3DToScreen([2.0, 3.0, 1.0], behindCamera, mockContainer);
  assert.equal(behindPos, null, 'Points behind camera must return null');

  global.THREE = origThree;
});

test('1.3 clampHUDPosition keeps HUD inside viewport boundaries', () => {
  const hud = require('../src/telemetry-hud.js');
  const container = {
    getBoundingClientRect: () => ({ width: 800, height: 600 }),
  };

  // Normal position
  const p1 = hud.clampHUDPosition(300, 300, container, 250, 160);
  assert.equal(p1.x, 320); // 300 + 20
  assert.equal(p1.y, 130); // 300 - 160 - 10

  // Near right edge: clamps to maxW (800 - 250 - 16 = 534)
  const p2 = hud.clampHUDPosition(750, 300, container, 250, 160);
  assert.equal(p2.x, 534);

  // Near top edge: clamps to 16
  const p3 = hud.clampHUDPosition(300, 50, container, 250, 160);
  assert.equal(p3.y, 16);
});

test('2.1 renderTelemetry correctly displays OFF_TARGET state (Amber)', () => {
  const { mockDocument, mockWindow } = setupMockDOM();
  global.document = mockDocument;
  global.window = mockWindow;

  const hud = require('../src/telemetry-hud.js');
  const container = mockDocument.createElement('div');
  hud.mountHUD(container);

  const telemetryData = {
    residuals: {
      deltaZ_cm: 14.5,
      deltaYaw_deg: 8.2,
      dist3D_cm: 18.0,
      roll_deg: 2.1,
      pitch_deg: 1.5,
      statusText: 'OFF_TARGET',
      isSnapped: false,
      isGreenLocked: false,
    },
  };

  hud.renderTelemetry(telemetryData);
  const hudEl = hud.getHUDElement();
  assert.ok(hudEl);
  assert.ok(hudEl.className.includes('off-target'));

  const badge = hudEl.querySelector('#ps-hud-badge-status');
  assert.ok(badge);
  assert.ok(badge.className.includes('off-target'));
  assert.equal(badge.textContent, '⚡ ĐANG CĂN CHỈNH');

  const elDz = hudEl.querySelector('#ps-hud-val-dz');
  assert.equal(elDz.textContent, '+14.5 cm');

  const elDyaw = hudEl.querySelector('#ps-hud-val-dyaw');
  assert.equal(elDyaw.textContent, '+8.2°');

  const elDist = hudEl.querySelector('#ps-hud-val-dist');
  assert.equal(elDist.textContent, '18.0 cm');

  hud.hideHUD();
});

test('2.2 renderTelemetry correctly displays SNAPPED state (Blue magnet snap)', () => {
  const { mockDocument, mockWindow } = setupMockDOM();
  global.document = mockDocument;
  global.window = mockWindow;

  const hud = require('../src/telemetry-hud.js');
  const container = mockDocument.createElement('div');
  hud.mountHUD(container);

  const telemetryData = {
    residuals: {
      deltaZ_cm: 4.8,
      deltaYaw_deg: 2.5,
      dist3D_cm: 6.2,
      roll_deg: 0.2,
      pitch_deg: 0.1,
      statusText: 'SNAPPED',
      isSnapped: true,
      isGreenLocked: false,
    },
  };

  hud.renderTelemetry(telemetryData);
  const hudEl = hud.getHUDElement();
  assert.ok(hudEl.className.includes('snapped'));

  const badge = hudEl.querySelector('#ps-hud-badge-status');
  assert.ok(badge.className.includes('snapped'));
  assert.equal(badge.textContent, '🧲 ĐANG HÚT NAM CHÂM');

  const elDist = hudEl.querySelector('#ps-hud-val-dist');
  assert.equal(elDist.textContent, '6.2 cm');
  assert.ok(!elDist.className.includes('perfect'));

  hud.hideHUD();
});

test('2.3 renderTelemetry correctly displays GREEN_LOCK state (Emerald Green confirmation)', () => {
  const { mockDocument, mockWindow } = setupMockDOM();
  global.document = mockDocument;
  global.window = mockWindow;

  const hud = require('../src/telemetry-hud.js');
  const container = mockDocument.createElement('div');
  hud.mountHUD(container);

  const telemetryData = {
    residuals: {
      deltaZ_cm: 0.8,
      deltaYaw_deg: -0.4,
      dist3D_cm: 1.1,
      roll_deg: 0.1,
      pitch_deg: 0.1,
      statusText: 'GREEN_LOCK',
      isSnapped: true,
      isGreenLocked: true,
    },
  };

  hud.renderTelemetry(telemetryData);
  const hudEl = hud.getHUDElement();
  assert.ok(hudEl.className.includes('green-lock'));

  const badge = hudEl.querySelector('#ps-hud-badge-status');
  assert.ok(badge.className.includes('green-lock'));
  assert.equal(badge.textContent, '✓ VỊ TRÍ HOÀN HẢO');

  const elDz = hudEl.querySelector('#ps-hud-val-dz');
  assert.ok(elDz.className.includes('perfect'));

  const elDyaw = hudEl.querySelector('#ps-hud-val-dyaw');
  assert.ok(elDyaw.className.includes('perfect'));

  const elDist = hudEl.querySelector('#ps-hud-val-dist');
  assert.ok(elDist.className.includes('perfect'));

  const elHint = hudEl.querySelector('#ps-hud-footer-hint');
  assert.equal(elHint.textContent, '✓ Nhả chuột để chốt');

  hud.hideHUD();
});

test('2.4 renderTelemetry displays facial clearances when point cloud data is available', () => {
  const { mockDocument, mockWindow } = setupMockDOM();
  global.document = mockDocument;
  global.window = mockWindow;

  const hud = require('../src/telemetry-hud.js');
  const container = mockDocument.createElement('div');
  hud.mountHUD(container);

  const telemetryData = {
    residuals: {
      deltaZ_cm: 1.0,
      deltaYaw_deg: 0.5,
      dist3D_cm: 1.5,
      clearance_front_cm: 15.0,
      clearance_back_cm: 22.0,
      clearance_left_cm: 8.0,
      clearance_right_cm: 11.0,
      statusText: 'GREEN_LOCK',
      isGreenLocked: true,
    },
  };

  hud.renderTelemetry(telemetryData);
  const hudEl = hud.getHUDElement();
  const elClearances = hudEl.querySelector('#ps-hud-clearances');
  assert.equal(elClearances.style.display, 'flex');

  const clf = hudEl.querySelector('#ps-hud-cl-f');
  assert.equal(clf.textContent, '15cm');
  const clb = hudEl.querySelector('#ps-hud-cl-b');
  assert.equal(clb.textContent, '22cm');

  hud.hideHUD();
});

test('3.1 onLockCommitted triggers committed visual badge and feedback', () => {
  const { mockDocument, mockWindow } = setupMockDOM();
  global.document = mockDocument;
  global.window = mockWindow;

  const hud = require('../src/telemetry-hud.js');
  const container = mockDocument.createElement('div');
  hud.mountHUD(container);

  hud.renderTelemetry({
    residuals: {
      deltaZ_cm: 0.5,
      deltaYaw_deg: 0.2,
      dist3D_cm: 0.7,
      statusText: 'GREEN_LOCK',
      isGreenLocked: true,
    },
  });

  hud.onLockCommitted({ box: {}, residuals: {} });
  const hudEl = hud.getHUDElement();
  assert.ok(hudEl.className.includes('committed'));

  const badge = hudEl.querySelector('#ps-hud-badge-status');
  assert.equal(badge.textContent, '✓ ĐÃ KHÓA HOÀN HẢO');

  const elHint = hudEl.querySelector('#ps-hud-footer-hint');
  assert.equal(elHint.textContent, '✓ Đã cập nhật nhãn CVAT');
});

test('3.2 Event bridge listeners trigger HUD updates and hide on clear', () => {
  const { mockDocument, mockWindow } = setupMockDOM();
  global.document = mockDocument;
  global.window = mockWindow;

  const hud = require('../src/telemetry-hud.js');
  const container = mockDocument.createElement('div');
  hud.initTelemetryHUD({ container });

  // Dispatch POINTSNAP_3D_TELEMETRY event
  mockWindow.dispatchEvent({
    type: 'POINTSNAP_3D_TELEMETRY',
    detail: {
      residuals: {
        deltaZ_cm: 3.0,
        deltaYaw_deg: 1.0,
        dist3D_cm: 3.5,
        statusText: 'SNAPPED',
        isSnapped: true,
      },
    },
  });

  assert.equal(hud.isVisible(), true);
  const hudEl = hud.getHUDElement();
  assert.ok(hudEl.className.includes('snapped'));

  // Dispatch POINTSNAP_CLEAR_GHOST_TARGET event
  mockWindow.dispatchEvent({
    type: 'POINTSNAP_CLEAR_GHOST_TARGET',
  });

  assert.equal(hud.isVisible(), false);
});
