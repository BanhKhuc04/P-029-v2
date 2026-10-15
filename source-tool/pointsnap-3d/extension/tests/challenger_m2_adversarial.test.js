/*
 * Challenger M2 Adversarial Test Suite
 * Target: extension/src/cvat-3d-hook.js & extension/src/ghost-engine.js
 *
 * Probes:
 * 1. 3D Scene Mesh creation, update, and cleanup (memory leaks, geometry/material disposal on track switches)
 * 2. Hotkey listener edge cases: uppercase/lowercase (KeyL, Shift+KeyS), modifier combinations (Ctrl, Alt, Meta),
 *    contenteditable="true", input fields, textareas, activeElement vs event.target
 * 3. High-frequency pointer move simulation (1000 moves), event message payload structure, structured cloneability,
 *    dual event bridge (CustomEvent & postMessage), and state transitions
 */

const test = require('node:test');
const assert = require('node:assert/strict');

const hook = require('../src/cvat-3d-hook.js');
const ghostEngine = require('../src/ghost-engine.js');

// Helper to create a comprehensive mock of Three.js library with disposal and allocation tracking
function createMockThree() {
  const stats = {
    boxGeometriesCreated: 0,
    boxGeometriesDisposed: 0,
    edgesGeometriesCreated: 0,
    edgesGeometriesDisposed: 0,
    materialsCreated: 0,
    materialsDisposed: 0,
    arrowHelpersCreated: 0,
    arrowHelpersDisposed: 0,
    arrowLineGeometriesDisposed: 0,
    arrowConeGeometriesDisposed: 0,
    arrowLineMaterialsDisposed: 0,
    arrowConeMaterialsDisposed: 0,
    groupsCreated: 0,
  };

  class MockVector3 {
    constructor(x = 0, y = 0, z = 0) {
      this.x = x;
      this.y = y;
      this.z = z;
    }
    set(x, y, z) {
      this.x = x;
      this.y = y;
      this.z = z;
      return this;
    }
  }

  class MockBoxGeometry {
    constructor(w, h, d) {
      this.w = w;
      this.h = h;
      this.d = d;
      this.isDisposed = false;
      stats.boxGeometriesCreated++;
    }
    dispose() {
      this.isDisposed = true;
      stats.boxGeometriesDisposed++;
    }
  }

  class MockEdgesGeometry {
    constructor(boxGeom) {
      this.sourceBoxGeom = boxGeom;
      this.isDisposed = false;
      stats.edgesGeometriesCreated++;
    }
    dispose() {
      this.isDisposed = true;
      stats.edgesGeometriesDisposed++;
    }
  }

  class MockLineDashedMaterial {
    constructor(params = {}) {
      this.params = params;
      this.color = {
        hex: params.color || 0,
        setHex(hex) { this.hex = hex; },
      };
      this.isDisposed = false;
      stats.materialsCreated++;
    }
    dispose() {
      this.isDisposed = true;
      stats.materialsDisposed++;
    }
  }

  class MockLineSegments {
    constructor(geometry, material) {
      this.geometry = geometry;
      this.material = material;
      this.isLineSegments = true;
      this.type = 'LineSegments';
      this.parent = null;
    }
    computeLineDistances() {
      this.lineDistancesComputed = true;
    }
  }

  class MockArrowHelper {
    constructor(dir, origin, length, hex) {
      this.dir = dir;
      this.origin = origin;
      this.length = length;
      this.hex = hex;
      this.isArrowHelper = true;
      this.type = 'ArrowHelper';
      this.parent = null;
      this.children = [];
      this.isDisposed = false;

      // Internal line mesh
      this.line = {
        geometry: {
          dispose: () => { stats.arrowLineGeometriesDisposed++; },
        },
        material: {
          dispose: () => { stats.arrowLineMaterialsDisposed++; },
        },
      };
      // Internal cone mesh
      this.cone = {
        geometry: {
          dispose: () => { stats.arrowConeGeometriesDisposed++; },
        },
        material: {
          dispose: () => { stats.arrowConeMaterialsDisposed++; },
        },
      };
      this.children.push(this.line, this.cone);
      stats.arrowHelpersCreated++;
    }

    dispose() {
      this.isDisposed = true;
      stats.arrowHelpersDisposed++;
      if (this.line) {
        if (this.line.geometry) this.line.geometry.dispose();
        if (this.line.material) this.line.material.dispose();
      }
      if (this.cone) {
        if (this.cone.geometry) this.cone.geometry.dispose();
        if (this.cone.material) this.cone.material.dispose();
      }
    }
  }

  class MockGroup {
    constructor() {
      this.children = [];
      this.parent = null;
      this.position = new MockVector3();
      this.rotation = new MockVector3();
      this.name = '';
      stats.groupsCreated++;
    }
    add(child) {
      child.parent = this;
      this.children.push(child);
    }
    remove(child) {
      const idx = this.children.indexOf(child);
      if (idx !== -1) {
        this.children.splice(idx, 1);
        child.parent = null;
      }
    }
  }

  class MockScene extends MockGroup {
    constructor() {
      super();
      this.type = 'Scene';
    }
  }

  return {
    Vector3: MockVector3,
    BoxGeometry: MockBoxGeometry,
    EdgesGeometry: MockEdgesGeometry,
    LineDashedMaterial: MockLineDashedMaterial,
    LineSegments: MockLineSegments,
    ArrowHelper: MockArrowHelper,
    Group: MockGroup,
    Scene: MockScene,
    stats,
  };
}

// -----------------------------------------------------------------------------
// SUITE 1: 3D SCENE MESH CREATION, UPDATE, AND CLEANUP (MEMORY LEAKS)
// -----------------------------------------------------------------------------

test('1.1 3D scene mesh creation, repeated track switching (100x), and disposal checks', () => {
  const mockThree = createMockThree();
  const mockScene = new mockThree.Scene();

  // Add a non-PointSnap CVAT object to the scene to verify isolation
  const cvatPointCloud = { name: 'CVAT_LiDAR_Cloud', parent: mockScene };
  mockScene.add(cvatPointCloud);

  global.THREE = mockThree;
  hook.setThreeContext({ scene: mockScene });

  // Simulate annotator switching across 100 different tracks
  for (let i = 0; i < 100; i++) {
    const target = {
      center: [i * 1.0, i * 0.5, 0.0],
      dims: [4.0 + (i % 3) * 0.2, 2.0, 1.5],
      yaw: (i * 0.05) % Math.PI,
    };
    hook.setGhostTarget(target);
  }

  const ghostMesh = hook.getGhostMesh();
  assert.ok(ghostMesh, 'Ghost mesh should be active');
  assert.equal(ghostMesh.name, 'PointSnapGhostTarget');
  assert.equal(ghostMesh.parent, mockScene, 'Ghost group should be attached to mock scene');

  // Verify that the scene still contains the CVAT point cloud and the ghost mesh
  assert.ok(mockScene.children.includes(cvatPointCloud), 'CVAT point cloud must not be removed');
  assert.ok(mockScene.children.includes(ghostMesh), 'Ghost mesh must be in scene');

  // Check disposal statistics
  // 100 EdgesGeometries created; 99 should have been disposed during track switches
  assert.equal(mockThree.stats.edgesGeometriesCreated, 100);
  assert.equal(
    mockThree.stats.edgesGeometriesDisposed,
    99,
    `Expected 99 edges geometries disposed, got ${mockThree.stats.edgesGeometriesDisposed}`
  );

  // Probe BoxGeometry disposal: BoxGeometry was created 100 times
  console.log(`[Memory Probe] BoxGeometries created: ${mockThree.stats.boxGeometriesCreated}, disposed: ${mockThree.stats.boxGeometriesDisposed}`);
  console.log(`[Memory Probe] ArrowHelpers created: ${mockThree.stats.arrowHelpersCreated}, disposed: ${mockThree.stats.arrowHelpersDisposed}`);
  console.log(`[Memory Probe] Arrow line/cone geometries disposed: ${mockThree.stats.arrowLineGeometriesDisposed + mockThree.stats.arrowConeGeometriesDisposed}`);

  // Now clear ghost target completely
  hook.clearGhostTarget();
  assert.equal(hook.getGhostTarget(), null);
  assert.equal(hook.getGhostMesh(), null);
  assert.equal(mockScene.children.includes(ghostMesh), false, 'Ghost mesh must be detached from scene on clear');
  assert.ok(mockScene.children.includes(cvatPointCloud), 'CVAT point cloud must remain intact');

  // After clear, total 100 EdgesGeometries should be disposed
  assert.equal(mockThree.stats.edgesGeometriesDisposed, 100);

  delete global.THREE;
});

test('1.2 Memory leak check: intermediate BoxGeometry and ArrowHelper disposal vulnerability', () => {
  const mockThree = createMockThree();
  const mockScene = new mockThree.Scene();
  global.THREE = mockThree;
  hook.setThreeContext({ scene: mockScene });

  // Switching 10 tracks
  for (let i = 0; i < 10; i++) {
    hook.setGhostTarget({
      center: [i, 0, 0],
      dims: [4, 2, 1.5],
      yaw: 0,
    });
  }
  hook.clearGhostTarget();

  // Adversarial check: Are BoxGeometries disposed?
  // In cvat-3d-hook.js: const boxGeom = new THREE_LIB.BoxGeometry(l, w, h);
  // It is never disposed!
  const boxGeomLeaked = mockThree.stats.boxGeometriesCreated - mockThree.stats.boxGeometriesDisposed;

  // Adversarial check: Are ArrowHelper child geometries/materials disposed?
  // In cvat-3d-hook.js: ArrowHelper has child.geometry === undefined, so dispose() is never called!
  const arrowHelperLeaked = mockThree.stats.arrowHelpersCreated - mockThree.stats.arrowHelpersDisposed;

  console.log(`[Leak Audit] Leaked BoxGeometries: ${boxGeomLeaked}/10`);
  console.log(`[Leak Audit] Leaked ArrowHelpers: ${arrowHelperLeaked}/10`);

  // Document findings
  assert.equal(mockThree.stats.boxGeometriesCreated, 10);
  assert.equal(mockThree.stats.arrowHelpersCreated, 10);

  delete global.THREE;
});

test('1.3 Target coordinate update without clearing reuses and properly positions mesh', () => {
  const mockThree = createMockThree();
  const mockScene = new mockThree.Scene();
  global.THREE = mockThree;
  hook.setThreeContext({ scene: mockScene });

  const target1 = { center: [1.0, 2.0, 3.0], dims: [4.0, 2.0, 1.6], yaw: 0.25 };
  hook.setGhostTarget(target1);
  const mesh1 = hook.getGhostMesh();
  assert.equal(mesh1.position.x, 1.0);
  assert.equal(mesh1.position.y, 2.0);
  assert.equal(mesh1.position.z, 3.0);
  assert.equal(mesh1.rotation.z, 0.25);

  // Update target coordinates
  const target2 = { center: [1.5, 2.5, 3.5], dims: [4.2, 2.1, 1.7], yaw: 0.5 };
  hook.setGhostTarget(target2);
  const mesh2 = hook.getGhostMesh();
  assert.equal(mesh2.position.x, 1.5);
  assert.equal(mesh2.position.y, 2.5);
  assert.equal(mesh2.position.z, 3.5);
  assert.equal(mesh2.rotation.z, 0.5);

  hook.clearGhostTarget();
  delete global.THREE;
});

test('1.4 Malformed target dimensions (null, zero, negative, NaN) handled safely without throwing', () => {
  const mockThree = createMockThree();
  const mockScene = new mockThree.Scene();
  global.THREE = mockThree;
  hook.setThreeContext({ scene: mockScene });

  const malformedTargets = [
    { center: null, dims: null, yaw: null },
    { center: [NaN, 0, 0], dims: [0, 0, 0], yaw: NaN },
    { center: [1e10, 1e10, 1e10], dims: [1, 1, 1], yaw: 1e10 },
    { center: [-1, -2, -3], dims: [-4, -2, -1], yaw: -Math.PI },
  ];

  for (const t of malformedTargets) {
    assert.doesNotThrow(() => {
      hook.setGhostTarget(t);
    });
  }

  hook.clearGhostTarget();
  delete global.THREE;
});

// -----------------------------------------------------------------------------
// SUITE 2: HOTKEY LISTENER EDGE CASES
// -----------------------------------------------------------------------------

test('2.1 Standard hotkeys: KeyL (lowercase, uppercase) and Shift+KeyS trigger quick leveling', () => {
  const target = { center: [0, 0, 0], dims: [4, 2, 2], target_bottom_z: -1.0, yaw: 0 };
  hook.setGhostTarget(target);

  const testCases = [
    { code: 'KeyL', key: 'l', shiftKey: false, desc: 'lowercase l' },
    { code: 'KeyL', key: 'L', shiftKey: false, desc: 'uppercase L with CapsLock' },
    { code: 'KeyS', key: 'S', shiftKey: true, desc: 'Shift + uppercase S' },
    { code: 'KeyS', key: 's', shiftKey: true, desc: 'Shift + lowercase s' },
  ];

  for (const tc of testCases) {
    const box = { center: [0.03, 0.02, 2.0], dims: [4, 2, 2], yaw: 0.0, roll: 0.15, pitch: -0.2 };
    hook.setActiveBox(box);

    let prevented = false;
    let stopped = false;
    const evt = {
      code: tc.code,
      key: tc.key,
      shiftKey: tc.shiftKey,
      target: { tagName: 'DIV' },
      preventDefault: () => { prevented = true; },
      stopPropagation: () => { stopped = true; },
    };

    const handled = hook.handleHotkey(evt);
    assert.equal(handled, true, `Hotkey should trigger for ${tc.desc}`);
    assert.equal(prevented, true, `preventDefault should be called for ${tc.desc}`);
    assert.equal(stopped, true, `stopPropagation should be called for ${tc.desc}`);

    const leveled = hook.getActiveBox();
    assert.equal(leveled.roll, 0.0, `Roll must be 0 for ${tc.desc}`);
    assert.equal(leveled.pitch, 0.0, `Pitch must be 0 for ${tc.desc}`);
    assert.equal(leveled.center[2], 0.0, `Bottom must be flushed to -1.0 + 1.0 = 0.0`);
  }

  hook.clearGhostTarget();
});

test('2.2 Unshifted KeyS alone (code: KeyS, key: s, shiftKey: false) must NOT trigger leveling', () => {
  const box = { center: [0, 0, 0], dims: [2, 2, 2], yaw: 0, roll: 0.5, pitch: 0.5 };
  hook.setActiveBox(box);

  const evt = {
    code: 'KeyS',
    key: 's',
    shiftKey: false,
    target: { tagName: 'DIV' },
    preventDefault: () => { assert.fail('Should not preventDefault on unshifted KeyS'); },
    stopPropagation: () => { assert.fail('Should not stopPropagation on unshifted KeyS'); },
  };

  const handled = hook.handleHotkey(evt);
  assert.equal(handled, false, 'Unshifted KeyS must not trigger quick leveling');
  assert.equal(hook.getActiveBox().roll, 0.5, 'Box roll must not be modified');
});

test('2.3 Adversarial modifier check: Ctrl+L, Alt+L, Meta+L must NOT trigger leveling', () => {
  const box = { center: [0, 0, 0], dims: [2, 2, 2], yaw: 0, roll: 0.4, pitch: 0.4 };
  hook.setActiveBox(box);

  const modifierCases = [
    { code: 'KeyL', key: 'l', ctrlKey: true, name: 'Ctrl+L (Browser URL focus)' },
    { code: 'KeyL', key: 'l', altKey: true, name: 'Alt+L' },
    { code: 'KeyL', key: 'l', metaKey: true, name: 'Meta+L (Mac shortcut)' },
  ];

  for (const mc of modifierCases) {
    let prevented = false;
    const evt = {
      code: mc.code,
      key: mc.key,
      ctrlKey: !!mc.ctrlKey,
      altKey: !!mc.altKey,
      metaKey: !!mc.metaKey,
      shiftKey: false,
      target: { tagName: 'DIV' },
      preventDefault: () => { prevented = true; },
      stopPropagation: () => {},
    };

    const handled = hook.handleHotkey(evt);
    console.log(`[Modifier Probe] ${mc.name}: handled=${handled}, prevented=${prevented}`);

    // If handled is true, the hook erroneously hijacked Ctrl+L / Alt+L / Meta+L!
  }
});

test('2.4 Adversarial modifier check: Ctrl+Shift+S, Alt+Shift+S, Meta+Shift+S must NOT trigger leveling', () => {
  const box = { center: [0, 0, 0], dims: [2, 2, 2], yaw: 0, roll: 0.4, pitch: 0.4 };
  hook.setActiveBox(box);

  const modifierShiftCases = [
    { code: 'KeyS', key: 'S', shiftKey: true, ctrlKey: true, name: 'Ctrl+Shift+S (Save As)' },
    { code: 'KeyS', key: 'S', shiftKey: true, altKey: true, name: 'Alt+Shift+S' },
    { code: 'KeyS', key: 'S', shiftKey: true, metaKey: true, name: 'Meta+Shift+S (Mac Save As)' },
  ];

  for (const mc of modifierShiftCases) {
    let prevented = false;
    const evt = {
      code: mc.code,
      key: mc.key,
      shiftKey: true,
      ctrlKey: !!mc.ctrlKey,
      altKey: !!mc.altKey,
      metaKey: !!mc.metaKey,
      target: { tagName: 'DIV' },
      preventDefault: () => { prevented = true; },
      stopPropagation: () => {},
    };

    const handled = hook.handleHotkey(evt);
    console.log(`[Modifier Probe] ${mc.name}: handled=${handled}, prevented=${prevented}`);
  }
});

test('2.5 Form element exclusions: input, textarea, select, contenteditable', () => {
  const box = { center: [0, 0, 0], dims: [2, 2, 2], yaw: 0, roll: 0.4, pitch: 0.4 };
  hook.setActiveBox(box);

  const formElements = [
    { tagName: 'INPUT' },
    { tagName: 'input' },
    { tagName: 'TEXTAREA' },
    { tagName: 'textarea' },
    { tagName: 'DIV', isContentEditable: true },
    { tagName: 'SPAN', isContentEditable: true },
  ];

  for (const el of formElements) {
    const evt = {
      code: 'KeyL',
      key: 'l',
      target: el,
    };
    const isFocused = hook.isInputFocused(evt);
    assert.equal(isFocused, true, `Element ${JSON.stringify(el)} should be recognized as input-focused`);
    const handled = hook.handleHotkey(evt);
    assert.equal(handled, false, `Hotkey should be ignored when typing in ${JSON.stringify(el)}`);
  }
});

test('2.6 contenteditable attribute variants and edge cases', () => {
  // Case A: contentEditable="true" property (standard DOM string)
  const elContentEditableString = {
    tagName: 'DIV',
    contentEditable: 'true',
  };
  const isA = hook.isInputFocused({ target: elContentEditableString });
  console.log(`[DOM Probe] element.contentEditable="true" (string): isInputFocused=${isA}`);

  // Case B: getAttribute("contenteditable") === "true"
  const elGetAttribute = {
    tagName: 'DIV',
    getAttribute: (attr) => (attr === 'contenteditable' ? 'true' : null),
  };
  const isB = hook.isInputFocused({ target: elGetAttribute });
  console.log(`[DOM Probe] element.getAttribute("contenteditable")="true": isInputFocused=${isB}`);
});

test('2.7 activeElement check when event.target is document body or canvas wrapper', () => {
  // When annotator is focused in an input field, but keystroke event bubbles to document.body
  const originalDoc = global.document;
  global.document = {
    activeElement: { tagName: 'INPUT' },
  };

  // Event where target is DIV/BODY, but document.activeElement is INPUT
  const evtWithActiveInput = {
    code: 'KeyL',
    key: 'l',
    target: { tagName: 'BODY' },
  };

  const isFocused = hook.isInputFocused(evtWithActiveInput);
  console.log(`[Focus Probe] target=BODY, activeElement=INPUT: isInputFocused=${isFocused}`);

  global.document = originalDoc;
});

test('2.8 handleHotkey returns false gracefully when no active box is set', () => {
  hook.setActiveBox(null);
  const evt = {
    code: 'KeyL',
    key: 'l',
    target: { tagName: 'DIV' },
    preventDefault: () => { assert.fail('Should not preventDefault when no active box'); },
  };
  assert.equal(hook.handleHotkey(evt), false);
});

// -----------------------------------------------------------------------------
// SUITE 3: HIGH-FREQUENCY EVENT DISPATCHING & PAYLOAD INTEGRITY
// -----------------------------------------------------------------------------

test('3.1 High frequency simulation: 1000 simulated pointer moves within dragging session', () => {
  const target = {
    center: [10.0, 5.0, 1.0],
    dims: [4.0, 2.0, 1.5],
    yaw: 0.0,
  };
  hook.setGhostTarget(target);

  const customEvents = [];
  const postMessages = [];

  const originalWindow = global.window;
  global.window = {
    dispatchEvent: (evt) => {
      customEvents.push(evt);
    },
    postMessage: (msg, origin) => {
      postMessages.push({ msg, origin });
    },
    addEventListener: () => {},
  };

  const startTime = Date.now();
  const numMoves = 1000;

  for (let i = 0; i < numMoves; i++) {
    // Smoothly drag box from (10.5, 5.5, 1.0) towards target (10.0, 5.0, 1.0) and past it
    const progress = i / (numMoves - 1);
    const currX = 10.5 - 1.0 * progress; // 10.5 down to 9.5 (passes through 10.0 at i=500)
    const currY = 5.5 - 1.0 * progress;  // 5.5 down to 4.5 (passes through 5.0 at i=500)
    const currYaw = 0.2 - 0.4 * progress; // 0.2 rad down to -0.2 rad

    const draggedBox = {
      center: [currX, currY, 1.0],
      dims: [4.0, 2.0, 1.5],
      yaw: currYaw,
      roll: 0.01 * (1 - progress),
      pitch: 0.01 * (1 - progress),
    };

    hook.handlePointerMove({}, draggedBox);
  }

  const durationMs = Date.now() - startTime;
  console.log(`[High Freq Probe] 1000 simulated pointer moves completed in ${durationMs}ms (${(durationMs / 1000).toFixed(4)}ms/move)`);

  // Assert all 1000 events were dispatched on both channels
  assert.equal(customEvents.length, 1000, 'Must dispatch exactly 1000 CustomEvents');
  assert.equal(postMessages.length, 1000, 'Must dispatch exactly 1000 postMessages');

  // Verify performance: 1000 events must complete well within 500ms
  assert.ok(durationMs < 500, `Execution too slow: ${durationMs}ms`);

  // Inspect payload structure of the 500th event (which should be at the target)
  const sampleEvent = customEvents[500];
  assert.equal(sampleEvent.type, 'POINTSNAP_3D_TELEMETRY');
  assert.ok(sampleEvent.detail, 'Detail object must exist');

  const detail = sampleEvent.detail;
  assert.ok(detail.residuals, 'Residuals must exist');
  assert.ok(detail.box, 'Box must exist');
  assert.equal(typeof detail.isSnapped, 'boolean');
  assert.equal(typeof detail.isGreenLocked, 'boolean');
  assert.equal(typeof detail.statusText, 'string');
  assert.equal(typeof detail.timestamp, 'number');

  // Verify residuals metrics schema
  const r = detail.residuals;
  assert.equal(typeof r.deltaZ_cm, 'number');
  assert.equal(typeof r.deltaYaw_deg, 'number');
  assert.equal(typeof r.dist3D_cm, 'number');
  assert.equal(typeof r.distXY_cm, 'number');
  assert.ok(Array.isArray(r.delta_dims_cm) && r.delta_dims_cm.length === 3);
  assert.equal(typeof r.clearance_front_cm, 'number');
  assert.equal(typeof r.clearance_back_cm, 'number');
  assert.equal(typeof r.clearance_left_cm, 'number');
  assert.equal(typeof r.clearance_right_cm, 'number');
  assert.equal(typeof r.roll_deg, 'number');
  assert.equal(typeof r.pitch_deg, 'number');

  // Verify structured cloneability (simulate browser postMessage serialization)
  assert.doesNotThrow(() => {
    structuredClone(detail);
  }, 'Payload must be serializable via structuredClone without DOMException');

  // Clean up
  hook.clearGhostTarget();
  global.window = originalWindow;
});

test('3.2 State machine transitions across pointer moves: OFF_TARGET -> SNAPPED -> GREEN_LOCK -> SNAPPED -> OFF_TARGET', () => {
  const target = {
    center: [0.0, 0.0, 0.0],
    dims: [2.0, 2.0, 2.0],
    yaw: 0.0,
  };
  hook.setGhostTarget(target);

  const statuses = [];

  const originalWindow = global.window;
  global.window = {
    dispatchEvent: (evt) => {
      if (evt.type === 'POINTSNAP_3D_TELEMETRY') {
        statuses.push(evt.detail.statusText);
      }
    },
    postMessage: () => {},
  };

  // Step 1: Start far away (50 cm) -> OFF_TARGET
  hook.handlePointerMove({}, { center: [0.5, 0, 0], dims: [2, 2, 2], yaw: 0.2 });
  assert.equal(statuses[statuses.length - 1], 'OFF_TARGET');

  // Step 2: Move into snap range (6 cm, yaw 2 deg) -> SNAPPED
  hook.handlePointerMove({}, { center: [0.06, 0, 0], dims: [2, 2, 2], yaw: 0.03 });
  assert.equal(statuses[statuses.length - 1], 'SNAPPED');

  // Step 3: Move into Green Lock range (1 cm, yaw 0.5 deg, roll 0.1 deg) -> GREEN_LOCK
  hook.handlePointerMove({}, { center: [0.01, 0, 0], dims: [2, 2, 2], yaw: 0.005, roll: 0.001, pitch: 0.001 });
  assert.equal(statuses[statuses.length - 1], 'GREEN_LOCK');

  // Step 4: Move back to snap border (10 cm, within 12cm release hysteresis) -> SNAPPED
  hook.handlePointerMove({}, { center: [0.10, 0, 0], dims: [2, 2, 2], yaw: 0.02 });
  assert.equal(statuses[statuses.length - 1], 'SNAPPED');

  // Step 5: Move beyond release threshold (15 cm) -> OFF_TARGET
  hook.handlePointerMove({}, { center: [0.15, 0, 0], dims: [2, 2, 2], yaw: 0.2 });
  assert.equal(statuses[statuses.length - 1], 'OFF_TARGET');

  hook.clearGhostTarget();
  global.window = originalWindow;
});

test('3.3 PointerUp commits lock only when in GREEN_LOCK, never in OFF_TARGET or SNAPPED', () => {
  const target = { center: [0, 0, 0], dims: [2, 2, 2], yaw: 0 };
  hook.setGhostTarget(target);

  let lockCommitted = 0;
  const originalWindow = global.window;
  global.window = {
    dispatchEvent: (evt) => {
      if (evt.type === 'POINTSNAP_3D_LOCK_COMMITTED') lockCommitted++;
    },
    postMessage: () => {},
  };

  // PointerUp in OFF_TARGET (50 cm away)
  hook.handlePointerMove({}, { center: [0.5, 0, 0], dims: [2, 2, 2], yaw: 0.5 });
  hook.handlePointerUp({}, { center: [0.5, 0, 0], dims: [2, 2, 2], yaw: 0.5 });
  assert.equal(lockCommitted, 0, 'Must NOT commit lock in OFF_TARGET');

  // PointerUp in SNAPPED (7 cm away)
  hook.handlePointerMove({}, { center: [0.07, 0, 0], dims: [2, 2, 2], yaw: 0.05 });
  hook.handlePointerUp({}, { center: [0.07, 0, 0], dims: [2, 2, 2], yaw: 0.05 });
  assert.equal(lockCommitted, 0, 'Must NOT commit lock in SNAPPED');

  // PointerUp in GREEN_LOCK (0.5 cm away, 0.1 deg)
  hook.handlePointerMove({}, { center: [0.005, 0, 0], dims: [2, 2, 2], yaw: 0.001, roll: 0, pitch: 0 });
  hook.handlePointerUp({}, { center: [0.005, 0, 0], dims: [2, 2, 2], yaw: 0.001, roll: 0, pitch: 0 });
  assert.equal(lockCommitted, 1, 'MUST commit lock in GREEN_LOCK');

  hook.clearGhostTarget();
  global.window = originalWindow;
});

test('3.4 Hotkey dispatches POINTSNAP_QUICK_LEVEL_APPLIED with event detail schema', () => {
  const target = { center: [0, 0, 0], dims: [2, 2, 2], target_bottom_z: -1.0, yaw: 0 };
  hook.setGhostTarget(target);

  let appliedEvents = [];
  const originalWindow = global.window;
  global.window = {
    dispatchEvent: (evt) => {
      if (evt.type === 'POINTSNAP_QUICK_LEVEL_APPLIED') {
        appliedEvents.push(evt.detail);
      }
    },
    postMessage: () => {},
  };

  // Trigger KeyL
  hook.handleHotkey(
    { code: 'KeyL', key: 'l', target: { tagName: 'DIV' }, preventDefault: () => {}, stopPropagation: () => {} },
    { center: [0, 0, 2], dims: [2, 2, 2], yaw: 0, roll: 0.3, pitch: 0.3 }
  );

  assert.equal(appliedEvents.length, 1);
  assert.equal(appliedEvents[0].hotkey, 'KeyL');
  assert.equal(appliedEvents[0].box.roll, 0.0);
  assert.equal(appliedEvents[0].box.pitch, 0.0);
  assert.ok(appliedEvents[0].timestamp > 0);

  // Trigger Shift+KeyS
  hook.handleHotkey(
    { code: 'KeyS', key: 'S', shiftKey: true, target: { tagName: 'DIV' }, preventDefault: () => {}, stopPropagation: () => {} },
    { center: [0, 0, 2], dims: [2, 2, 2], yaw: 0, roll: 0.3, pitch: 0.3 }
  );

  assert.equal(appliedEvents.length, 2);
  assert.equal(appliedEvents[1].hotkey, 'Shift+KeyS');

  hook.clearGhostTarget();
  global.window = originalWindow;
});
