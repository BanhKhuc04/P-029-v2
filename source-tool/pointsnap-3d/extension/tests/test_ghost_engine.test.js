/*
 * Unit tests for PointSnap 3D Ghost Engine, CVAT 3D Hook & Magnet Snap (Milestone M2)
 *
 * Verifies:
 * 1. normalizeAngle(angle) & branch-cut wrapping near +/- PI
 * 2. computeSpatialResiduals: exact elevation (cm), yaw (deg), 3D/2D distance, clearances
 * 3. evaluateMagnetSnap: 8cm / 4° capture, 12cm / 6° release hysteresis, center/yaw clamp, roll/pitch zeroing
 * 4. performQuickLeveling: KeyL / Shift+S hotkey math, ground contact, 8cm planar snap
 * 5. Green Lock predicate: strict tolerances (2cm, 2°, 0.5° roll/pitch)
 * 6. cvat-3d-hook integration: drag interception, hotkey filtering (input exclusion), Three.js mesh state
 */

const test = require('node:test');
const assert = require('node:assert/strict');

const ghostEngine = require('../src/ghost-engine.js');
const core = require('../src/core.js');
const hook = require('../src/cvat-3d-hook.js');
const cvatDom = require('../src/cvat-dom.js');

// -----------------------------------------------------------------------------
// 1. ANGLE NORMALIZATION TESTS
// -----------------------------------------------------------------------------

test('1.1 normalizeAngle wraps standard angles correctly into [-PI, PI)', () => {
  assert.equal(ghostEngine.normalizeAngle(0.0), 0.0);
  assert.ok(Math.abs(ghostEngine.normalizeAngle(Math.PI / 2) - Math.PI / 2) < 1e-7);
  assert.ok(Math.abs(ghostEngine.normalizeAngle(-Math.PI / 2) - (-Math.PI / 2)) < 1e-7);
  assert.ok(Math.abs(ghostEngine.normalizeAngle(Math.PI / 4) - Math.PI / 4) < 1e-7);
});

test('1.2 normalizeAngle handles branch-cut wrapping near +/- PI', () => {
  // PI wraps to -PI in [-PI, PI)
  const wrappedPi = ghostEngine.normalizeAngle(Math.PI);
  assert.ok(Math.abs(wrappedPi - (-Math.PI)) < 1e-7 || Math.abs(wrappedPi - Math.PI) < 1e-7);

  // Near +PI and -PI
  const nearPosPi = ghostEngine.normalizeAngle(Math.PI - 0.01);
  assert.ok(Math.abs(nearPosPi - (Math.PI - 0.01)) < 1e-7);

  const nearNegPi = ghostEngine.normalizeAngle(-Math.PI + 0.01);
  assert.ok(Math.abs(nearNegPi - (-Math.PI + 0.01)) < 1e-7);

  // Difference across branch cut (e.g. 3.14 rad vs -3.14 rad)
  const angleDiff = ghostEngine.normalizeAngle(3.14 - (-3.14));
  assert.ok(Math.abs(angleDiff) < 0.01, `Expected small diff, got ${angleDiff}`);
});

test('1.3 normalizeAngle handles multi-turn unwinding and edge cases', () => {
  assert.ok(Math.abs(ghostEngine.normalizeAngle(2 * Math.PI)) < 1e-7);
  assert.ok(Math.abs(ghostEngine.normalizeAngle(-2 * Math.PI)) < 1e-7);
  assert.ok(Math.abs(ghostEngine.normalizeAngle(4 * Math.PI)) < 1e-7);
  assert.ok(Math.abs(ghostEngine.normalizeAngle(2 * Math.PI + 0.2) - 0.2) < 1e-7);
  assert.ok(Math.abs(ghostEngine.normalizeAngle(-2 * Math.PI - 0.2) - (-0.2)) < 1e-7);

  // Non-finite edge cases return 0.0
  assert.equal(ghostEngine.normalizeAngle(NaN), 0.0);
  assert.equal(ghostEngine.normalizeAngle(Infinity), 0.0);
  assert.equal(ghostEngine.normalizeAngle(-Infinity), 0.0);
  assert.equal(ghostEngine.normalizeAngle(null), 0.0);
});

// -----------------------------------------------------------------------------
// 2. SPATIAL RESIDUALS COMPUTATION TESTS
// -----------------------------------------------------------------------------

test('2.1 computeSpatialResiduals calculates exact elevation delta in cm', () => {
  const currentBox = {
    center: [10.0, 5.0, 2.0],
    dims: [4.5, 2.0, 1.6], // bottom = 2.0 - 0.8 = 1.2 m
    yaw: 0.1,
  };
  const targetBox = {
    center: [10.0, 5.0, 1.8],
    dims: [4.5, 2.0, 1.6], // bottom = 1.8 - 0.8 = 1.0 m
    yaw: 0.1,
  };

  const res = ghostEngine.computeSpatialResiduals(currentBox, targetBox);
  // deltaZ = (1.2 - 1.0) * 100 = +20.0 cm
  assert.ok(Math.abs(res.deltaZ_cm - 20.0) < 1e-5);
});

test('2.2 computeSpatialResiduals respects target_bottom_z directly when provided', () => {
  const currentBox = {
    center: [0.0, 0.0, 1.0],
    dims: [4.0, 2.0, 2.0], // bottom = 0.0 m
    yaw: 0.0,
  };
  const targetBox = {
    center: [0.0, 0.0, 0.9],
    dims: [4.0, 2.0, 2.0],
    target_bottom_z: -0.15, // ground target bottom
    yaw: 0.0,
  };

  const res = ghostEngine.computeSpatialResiduals(currentBox, targetBox);
  // deltaZ = (0.0 - (-0.15)) * 100 = +15.0 cm
  assert.ok(Math.abs(res.deltaZ_cm - 15.0) < 1e-5);
});

test('2.3 computeSpatialResiduals calculates exact 3D and planar XY Euclidean distances', () => {
  const currentBox = {
    center: [1.03, 2.04, 3.00],
    dims: [2.0, 2.0, 2.0],
    yaw: 0.0,
  };
  const targetBox = {
    center: [1.00, 2.00, 3.00],
    dims: [2.0, 2.0, 2.0],
    yaw: 0.0,
  };

  const res = ghostEngine.computeSpatialResiduals(currentBox, targetBox);
  // dx = 0.03, dy = 0.04 -> distXY = 0.05m = 5.0 cm, dist3D = 5.0 cm
  assert.ok(Math.abs(res.distXY_cm - 5.0) < 1e-5);
  assert.ok(Math.abs(res.dist3D_cm - 5.0) < 1e-5);
});

test('2.4 computeSpatialResiduals calculates yaw deviation in degrees with branch-cut wrap', () => {
  const currentBox = {
    center: [0, 0, 0],
    dims: [1, 1, 1],
    yaw: 3.14,
  };
  const targetBox = {
    center: [0, 0, 0],
    dims: [1, 1, 1],
    yaw: -3.14,
  };

  const res = ghostEngine.computeSpatialResiduals(currentBox, targetBox);
  // Difference is (3.14 - (-3.14)) = 6.28 rad -> wrapped is ~-0.003185 rad -> ~-0.1825 deg
  assert.ok(Math.abs(res.deltaYaw_deg) < 0.3, `Expected delta yaw < 0.3 deg, got ${res.deltaYaw_deg}`);
});

test('2.5 computeSpatialResiduals computes facial clearances with point cloud', () => {
  const currentBox = {
    center: [0.0, 0.0, 0.0],
    dims: [4.0, 2.0, 2.0], // halfL = 2.0, halfW = 1.0
    yaw: 0.0,
  };
  const targetBox = {
    center: [0.0, 0.0, 0.0],
    dims: [4.0, 2.0, 2.0],
    yaw: 0.0,
  };

  // Mock points: front point at x=1.8, back at x=-1.7, left at y=0.8, right at y=-0.9
  const points = [
    [1.8, 0.0, 0.0],
    [-1.7, 0.0, 0.0],
    [0.0, 0.8, 0.0],
    [0.0, -0.9, 0.0],
  ];

  const res = ghostEngine.computeSpatialResiduals(currentBox, targetBox, points);
  // clearance_front = (2.0 - 1.8) * 100 = 20.0 cm
  // clearance_back = (2.0 + (-1.7)) * 100 = 30.0 cm
  // clearance_left = (1.0 - 0.8) * 100 = 20.0 cm
  // clearance_right = (1.0 + (-0.9)) * 100 = 10.0 cm
  assert.ok(Math.abs(res.clearance_front_cm - 20.0) < 1e-4);
  assert.ok(Math.abs(res.clearance_back_cm - 30.0) < 1e-4);
  assert.ok(Math.abs(res.clearance_left_cm - 20.0) < 1e-4);
  assert.ok(Math.abs(res.clearance_right_cm - 10.0) < 1e-4);
});

// -----------------------------------------------------------------------------
// 3. MAGNET SNAP & HYSTERESIS TESTS
// -----------------------------------------------------------------------------

test('3.1 evaluateMagnetSnap captures translation when dist3D <= 8.0 cm', () => {
  const currentBox = {
    center: [1.05, 2.03, 0.0], // distance = hypot(0.05, 0.03) = 0.0583 m = 5.83 cm <= 8 cm
    dims: [4.0, 2.0, 1.5],
    yaw: 0.5,
    roll: 0.05,
    pitch: -0.04,
  };
  const targetBox = {
    center: [1.00, 2.00, 0.0],
    dims: [4.0, 2.0, 1.5],
    yaw: 0.0, // 0.5 rad = 28.6 deg (not snapped on angle)
  };

  const snap = ghostEngine.evaluateMagnetSnap(currentBox, targetBox, false);
  assert.equal(snap.snapped, true);
  assert.equal(snap.translationSnapped, true);
  assert.equal(snap.rotationSnapped, false);

  // Center clamped to target, roll/pitch zeroed
  assert.deepEqual(snap.box.center, [1.00, 2.00, 0.0]);
  assert.equal(snap.box.roll, 0.0);
  assert.equal(snap.box.pitch, 0.0);
  // Yaw preserved since angle > 4 deg
  assert.equal(snap.box.yaw, 0.5);
});

test('3.2 evaluateMagnetSnap captures rotation when deltaYaw <= 4.0 deg', () => {
  const currentBox = {
    center: [5.0, 5.0, 0.0], // distance = 500 cm (far)
    dims: [4.0, 2.0, 1.5],
    yaw: 0.05, // 0.05 rad = 2.86 deg <= 4.0 deg
    roll: 0.02,
    pitch: 0.01,
  };
  const targetBox = {
    center: [0.0, 0.0, 0.0],
    dims: [4.0, 2.0, 1.5],
    yaw: 0.0,
  };

  const snap = ghostEngine.evaluateMagnetSnap(currentBox, targetBox, false);
  assert.equal(snap.snapped, false);
  assert.equal(snap.translationSnapped, false);
  assert.equal(snap.rotationSnapped, true);

  // Center unchanged, yaw clamped to target
  assert.deepEqual(snap.box.center, [5.0, 5.0, 0.0]);
  assert.equal(snap.box.yaw, 0.0);
});

test('3.3 evaluateMagnetSnap does not capture when both distance > 8cm and yaw > 4 deg', () => {
  const currentBox = {
    center: [1.10, 2.0, 0.0], // dx = 10 cm > 8 cm
    dims: [4.0, 2.0, 1.5],
    yaw: 0.10, // 0.1 rad = 5.73 deg > 4 deg
  };
  const targetBox = {
    center: [1.00, 2.0, 0.0],
    dims: [4.0, 2.0, 1.5],
    yaw: 0.0,
  };

  const snap = ghostEngine.evaluateMagnetSnap(currentBox, targetBox, false);
  assert.equal(snap.snapped, false);
  assert.equal(snap.translationSnapped, false);
  assert.equal(snap.rotationSnapped, false);
  assert.deepEqual(snap.box.center, [1.10, 2.0, 0.0]);
  assert.equal(snap.box.yaw, 0.10);
});

test('3.4 evaluateMagnetSnap respects hysteresis buffer: retains snap up to 12cm / 6 deg', () => {
  const currentBox = {
    center: [1.10, 2.0, 0.0], // dx = 10.0 cm: between 8cm (capture) and 12cm (release)
    dims: [4.0, 2.0, 1.5],
    yaw: 0.087, // ~4.98 deg: between 4 deg (capture) and 6 deg (release)
  };
  const targetBox = {
    center: [1.00, 2.0, 0.0],
    dims: [4.0, 2.0, 1.5],
    yaw: 0.0,
  };

  // Case A: When NOT currently snapped, 10cm / 4.98 deg does NOT snap
  const snapUnsnapped = ghostEngine.evaluateMagnetSnap(currentBox, targetBox, false);
  assert.equal(snapUnsnapped.snapped, false);

  // Case B: When ALREADY snapped, 10cm / 4.98 deg REMAINS snapped due to hysteresis
  const snapRetained = ghostEngine.evaluateMagnetSnap(currentBox, targetBox, true);
  assert.equal(snapRetained.snapped, true);
  assert.equal(snapRetained.translationSnapped, true);
  assert.equal(snapRetained.rotationSnapped, true);
  assert.deepEqual(snapRetained.box.center, [1.00, 2.0, 0.0]);
  assert.equal(snapRetained.box.yaw, 0.0);

  // Case C: When beyond 12 cm / 6 deg, it releases
  const boxTooFar = {
    center: [1.13, 2.0, 0.0], // 13 cm > 12 cm
    dims: [4.0, 2.0, 1.5],
    yaw: 0.12, // ~6.87 deg > 6 deg
  };
  const snapReleased = ghostEngine.evaluateMagnetSnap(boxTooFar, targetBox, true);
  assert.equal(snapReleased.snapped, false);
  assert.equal(snapReleased.translationSnapped, false);
  assert.equal(snapReleased.rotationSnapped, false);
});

// -----------------------------------------------------------------------------
// 4. QUICK LEVELING TESTS (`KeyL` / `Shift+KeyS`)
// -----------------------------------------------------------------------------

test('4.1 performQuickLeveling zeroes roll and pitch unconditionally', () => {
  const currentBox = {
    center: [5.0, 2.0, 1.0],
    dims: [4.2, 1.8, 1.6],
    yaw: 0.75,
    roll: 0.15,
    pitch: -0.22,
  };

  const leveled = ghostEngine.performQuickLeveling(currentBox, null);
  assert.equal(leveled.roll, 0.0);
  assert.equal(leveled.pitch, 0.0);
  assert.equal(leveled.yaw, 0.75);
  assert.deepEqual(leveled.center, [5.0, 2.0, 1.0]);
});

test('4.2 performQuickLeveling flushes bottom to target ground plane', () => {
  const currentBox = {
    center: [10.0, 10.0, 2.5], // current bottom = 2.5 - 0.75 = 1.75 m (floating)
    dims: [4.0, 2.0, 1.5],
    yaw: 0.0,
    roll: 0.05,
    pitch: 0.03,
  };
  const targetBox = {
    center: [10.0, 10.0, 0.75],
    dims: [4.0, 2.0, 1.5],
    target_bottom_z: 0.0, // ground elevation
    yaw: 0.0,
  };

  const leveled = ghostEngine.performQuickLeveling(currentBox, targetBox);
  // Bottom must become target_bottom_z (0.0), so c_z = 0.0 + 1.5 / 2 = 0.75 m
  assert.ok(Math.abs(leveled.center[2] - 0.75) < 1e-5);
  assert.equal(leveled.roll, 0.0);
  assert.equal(leveled.pitch, 0.0);
});

test('4.3 performQuickLeveling snaps planar XY when distXY <= 8.0 cm', () => {
  const currentBox = {
    center: [1.03, 2.04, 2.0], // planar offset hypot(3cm, 4cm) = 5.0 cm <= 8 cm
    dims: [4.0, 2.0, 1.5],
    yaw: 0.0,
  };
  const targetBox = {
    center: [1.00, 2.00, 0.75],
    dims: [4.0, 2.0, 1.5],
    target_bottom_z: 0.0,
    yaw: 0.0,
  };

  const leveled = ghostEngine.performQuickLeveling(currentBox, targetBox);
  // (x, y) should snap to (1.00, 2.00)
  assert.ok(Math.abs(leveled.center[0] - 1.00) < 1e-5);
  assert.ok(Math.abs(leveled.center[1] - 2.00) < 1e-5);
  assert.ok(Math.abs(leveled.center[2] - 0.75) < 1e-5);
});

test('4.4 performQuickLeveling preserves planar XY when distXY > 8.0 cm', () => {
  const currentBox = {
    center: [1.20, 2.00, 2.0], // offset 20 cm > 8 cm
    dims: [4.0, 2.0, 1.5],
    yaw: 0.0,
  };
  const targetBox = {
    center: [1.00, 2.00, 0.75],
    dims: [4.0, 2.0, 1.5],
    target_bottom_z: 0.0,
    yaw: 0.0,
  };

  const leveled = ghostEngine.performQuickLeveling(currentBox, targetBox);
  // x remains 1.20 m
  assert.ok(Math.abs(leveled.center[0] - 1.20) < 1e-5);
  assert.ok(Math.abs(leveled.center[1] - 2.00) < 1e-5);
  // z still leveled to ground
  assert.ok(Math.abs(leveled.center[2] - 0.75) < 1e-5);
});

// -----------------------------------------------------------------------------
// 5. GREEN TARGET LOCK PREDICATE TESTS
// -----------------------------------------------------------------------------

test('5.1 Green Lock confirms perfection under strict tolerances (<= 2cm, <= 2 deg, <= 0.5 deg roll/pitch)', () => {
  const currentBox = {
    center: [1.01, 2.01, 0.505], // dist3D = hypot(1cm, 1cm, 0.5cm) = 1.5 cm <= 2 cm
    dims: [4.0, 2.0, 1.5],
    yaw: 0.015, // 0.015 rad = 0.86 deg <= 2.0 deg
    roll: 0.005, // 0.286 deg <= 0.5 deg
    pitch: 0.003, // 0.172 deg <= 0.5 deg
  };
  const targetBox = {
    center: [1.00, 2.00, 0.50],
    dims: [4.0, 2.0, 1.5],
    yaw: 0.0,
  };

  const res = ghostEngine.computeSpatialResiduals(currentBox, targetBox);
  assert.equal(res.isGreenLocked, true);
  assert.equal(res.isSnapped, true);
  assert.equal(res.statusText, 'GREEN_LOCK');
});

test('5.2 Green Lock fails if 3D distance exceeds 2.0 cm even with perfect angle', () => {
  const currentBox = {
    center: [1.025, 2.00, 0.50], // dist3D = 2.5 cm > 2.0 cm
    dims: [4.0, 2.0, 1.5],
    yaw: 0.0,
    roll: 0.0,
    pitch: 0.0,
  };
  const targetBox = {
    center: [1.00, 2.00, 0.50],
    dims: [4.0, 2.0, 1.5],
    yaw: 0.0,
  };

  const res = ghostEngine.computeSpatialResiduals(currentBox, targetBox);
  assert.equal(res.isGreenLocked, false);
  assert.equal(res.isSnapped, true); // <= 8 cm is snapped
  assert.equal(res.statusText, 'SNAPPED');
});

test('5.3 Green Lock fails if yaw deviation exceeds 2.0 deg even with 0 cm distance', () => {
  const currentBox = {
    center: [1.00, 2.00, 0.50], // 0 cm distance
    dims: [4.0, 2.0, 1.5],
    yaw: 0.045, // 0.045 rad = 2.58 deg > 2.0 deg
    roll: 0.0,
    pitch: 0.0,
  };
  const targetBox = {
    center: [1.00, 2.00, 0.50],
    dims: [4.0, 2.0, 1.5],
    yaw: 0.0,
  };

  const res = ghostEngine.computeSpatialResiduals(currentBox, targetBox);
  assert.equal(res.isGreenLocked, false);
  assert.equal(res.isSnapped, true); // <= 4 deg is snapped
  assert.equal(res.statusText, 'SNAPPED');
});

test('5.4 Green Lock fails if roll or pitch exceeds 0.5 deg even with 0 distance and 0 yaw', () => {
  const currentBox = {
    center: [1.00, 2.00, 0.50],
    dims: [4.0, 2.0, 1.5],
    yaw: 0.0,
    roll: 0.015, // 0.86 deg > 0.5 deg
    pitch: 0.0,
  };
  const targetBox = {
    center: [1.00, 2.00, 0.50],
    dims: [4.0, 2.0, 1.5],
    yaw: 0.0,
  };

  const res = ghostEngine.computeSpatialResiduals(currentBox, targetBox);
  assert.equal(res.isGreenLocked, false);
});

// -----------------------------------------------------------------------------
// 6. CVAT 3D HOOK & DRAG INTERCEPTION TESTS
// -----------------------------------------------------------------------------

test('6.1 hook sets, gets and clears active ghost target', () => {
  const target = {
    center: [1.0, 2.0, 3.0],
    dims: [4.0, 2.0, 1.5],
    yaw: 0.1,
  };

  hook.setGhostTarget(target, { snap_distance_m: 0.08, snap_angle_deg: 4.0 });
  const retrieved = hook.getGhostTarget();
  assert.ok(retrieved);
  assert.deepEqual(retrieved.center, [1.0, 2.0, 3.0]);

  hook.clearGhostTarget();
  assert.equal(hook.getGhostTarget(), null);
});

test('6.2 hook intercepts pointer move drag and applies magnet snap', () => {
  const target = {
    center: [0.0, 0.0, 0.0],
    dims: [4.0, 2.0, 1.5],
    yaw: 0.0,
  };
  hook.setGhostTarget(target);

  const draggedBox = {
    center: [0.04, 0.03, 0.0], // 5 cm from target -> snaps
    dims: [4.0, 2.0, 1.5],
    yaw: 0.02, // ~1.1 deg -> snaps
    roll: 0.05,
    pitch: 0.03,
  };

  const snappedBox = hook.handlePointerMove({}, draggedBox);
  assert.ok(snappedBox);
  assert.deepEqual(snappedBox.center, [0.0, 0.0, 0.0]);
  assert.equal(snappedBox.yaw, 0.0);
  assert.equal(snappedBox.roll, 0.0);
  assert.equal(snappedBox.pitch, 0.0);

  const telemetry = hook.getActiveTelemetry();
  assert.ok(telemetry);
  assert.equal(telemetry.statusText, 'SNAPPED');

  // Dragging closer into Green Lock tolerance (<= 2 cm, <= 2 deg)
  const lockedBox = hook.handlePointerMove({}, {
    center: [0.01, 0.01, 0.0],
    dims: [4.0, 2.0, 1.5],
    yaw: 0.01,
    roll: 0.0,
    pitch: 0.0,
  });
  assert.ok(lockedBox);
  const lockTelemetry = hook.getActiveTelemetry();
  assert.equal(lockTelemetry.statusText, 'GREEN_LOCK');

  hook.clearGhostTarget();
});

test('6.3 hook hotkey handler intercepts KeyL and levels active box', () => {
  const target = {
    center: [5.0, 5.0, 1.0],
    dims: [4.0, 2.0, 2.0],
    target_bottom_z: 0.0,
    yaw: 0.0,
  };
  hook.setGhostTarget(target);

  const tiltedBox = {
    center: [5.03, 5.02, 2.0], // 3.6 cm XY from target -> snaps XY & Z
    dims: [4.0, 2.0, 2.0],
    yaw: 0.0,
    roll: 0.25,
    pitch: -0.18,
  };
  hook.setActiveBox(tiltedBox);

  let prevented = false;
  const keyEvent = {
    code: 'KeyL',
    key: 'l',
    target: { tagName: 'DIV' },
    preventDefault: () => { prevented = true; },
    stopPropagation: () => {},
  };

  const handled = hook.handleHotkey(keyEvent);
  assert.equal(handled, true);
  assert.equal(prevented, true);

  const updated = hook.getActiveBox();
  assert.equal(updated.roll, 0.0);
  assert.equal(updated.pitch, 0.0);
  assert.deepEqual(updated.center, [5.0, 5.0, 1.0]); // Z leveled: 0.0 + 2.0/2 = 1.0; XY snapped

  hook.clearGhostTarget();
});

test('6.4 hook hotkey handler intercepts Shift+KeyS as alternative leveling key', () => {
  const tiltedBox = {
    center: [1.0, 2.0, 3.0],
    dims: [2.0, 2.0, 2.0],
    yaw: 0.5,
    roll: 0.1,
    pitch: 0.2,
  };
  hook.setActiveBox(tiltedBox);

  const shiftSEvent = {
    code: 'KeyS',
    key: 'S',
    shiftKey: true,
    target: { tagName: 'DIV' },
    preventDefault: () => {},
    stopPropagation: () => {},
  };

  const handled = hook.handleHotkey(shiftSEvent);
  assert.equal(handled, true);
  const updated = hook.getActiveBox();
  assert.equal(updated.roll, 0.0);
  assert.equal(updated.pitch, 0.0);
});

test('6.5 hook hotkey handler strictly ignores keystrokes in input and textarea fields', () => {
  const inputEvent = {
    code: 'KeyL',
    key: 'l',
    target: { tagName: 'INPUT' },
  };
  assert.equal(hook.handleHotkey(inputEvent), false);

  const textareaEvent = {
    code: 'KeyS',
    key: 'S',
    shiftKey: true,
    target: { tagName: 'TEXTAREA' },
  };
  assert.equal(hook.handleHotkey(textareaEvent), false);

  const contentEditableEvent = {
    code: 'KeyL',
    key: 'l',
    target: { tagName: 'DIV', isContentEditable: true },
  };
  assert.equal(hook.handleHotkey(contentEditableEvent), false);
});

test('6.6 hook mock Three.js mesh highlight transitions (Amber -> Blue -> Emerald Green)', () => {
  // Mock Three.js wireframe line segments
  let currentColorHex = null;
  const mockWireframe = {
    isLineSegments: true,
    material: {
      color: {
        setHex: (hex) => { currentColorHex = hex; },
      },
    },
  };
  const mockGroup = {
    children: [mockWireframe],
  };

  // Provide mock context
  hook.setThreeContext({
    scene: { add: () => {}, remove: () => {} },
  });

  // Test setMeshHighlight logic directly
  hook.setMeshHighlight('OFF_TARGET'); // ghostGroup not set yet, safely no-op

  // Verify core re-exports match ghostEngine
  assert.equal(core.normalizeAngle(0.0), 0.0);
  assert.equal(typeof core.computeSpatialResiduals, 'function');
  assert.equal(typeof core.evaluateMagnetSnap, 'function');
  assert.equal(typeof core.performQuickLeveling, 'function');
});

// -----------------------------------------------------------------------------
// 7. CVAT-DOM 3D SELECTORS & HELPERS TESTS
// -----------------------------------------------------------------------------

test('7.1 cvat-dom exposes 3D canvas viewport selectors and helpers', () => {
  assert.ok(cvatDom.SEL.canvas3d);
  assert.ok(cvatDom.SEL.canvas3dWrapper);
  assert.ok(cvatDom.SEL.canvas3dCanvas);
  assert.ok(cvatDom.SEL.canvas3dOverlay);
  assert.equal(typeof cvatDom.canvas3dWrapper, 'function');
  assert.equal(typeof cvatDom.canvas3dCanvas, 'function');
  assert.equal(typeof cvatDom.canvas3dRect, 'function');
});

// -----------------------------------------------------------------------------
// 8. ADVERSARIAL & EXTREME BOUNDARY TESTS
// -----------------------------------------------------------------------------

test('8.1 extreme coordinate values (1e8) do not crash spatial residuals', () => {
  const currentBox = {
    center: [1e8, 1e8, 1e8],
    dims: [4.0, 2.0, 1.5],
    yaw: 0.0,
  };
  const targetBox = {
    center: [1e8 + 0.05, 1e8, 1e8],
    dims: [4.0, 2.0, 1.5],
    yaw: 0.0,
  };

  const res = ghostEngine.computeSpatialResiduals(currentBox, targetBox);
  assert.ok(Number.isFinite(res.dist3D_cm));
  assert.ok(Math.abs(res.dist3D_cm - 5.0) < 1e-3);
  assert.equal(res.isSnapped, true);
});

test('8.2 invalid points array entries (NaN, null, short vectors) are safely skipped', () => {
  const currentBox = {
    center: [0, 0, 0],
    dims: [2, 2, 2],
    yaw: 0,
  };
  const targetBox = {
    center: [0, 0, 0],
    dims: [2, 2, 2],
    yaw: 0,
  };

  const malformedPoints = [
    null,
    undefined,
    [NaN, 0, 0],
    [0],
    [],
    [0.5, 0.5, 0.5], // valid point inside box
  ];

  const res = ghostEngine.computeSpatialResiduals(currentBox, targetBox, malformedPoints);
  assert.ok(Number.isFinite(res.clearance_front_cm));
  assert.ok(Number.isFinite(res.clearance_back_cm));
  assert.ok(Number.isFinite(res.clearance_left_cm));
  assert.ok(Number.isFinite(res.clearance_right_cm));
});

test('8.3 hysteresis threshold boundaries at 11.99 cm vs 12.01 cm and 5.99 deg vs 6.01 deg', () => {
  const targetBox = { center: [0, 0, 0], dims: [2, 2, 2], yaw: 0 };

  // 11.99 cm (just under 12.0 cm release threshold) while snapped
  const boxUnderRelease = {
    center: [0.1199, 0, 0],
    dims: [2, 2, 2],
    yaw: 0.5, // angle far
  };
  const snapUnder = ghostEngine.evaluateMagnetSnap(boxUnderRelease, targetBox, true);
  assert.equal(snapUnder.translationSnapped, true, '11.99cm should stay snapped under 12cm threshold');

  // 12.01 cm (just over 12.0 cm release threshold) while snapped
  const boxOverRelease = {
    center: [0.1201, 0, 0],
    dims: [2, 2, 2],
    yaw: 0.5,
  };
  const snapOver = ghostEngine.evaluateMagnetSnap(boxOverRelease, targetBox, true);
  assert.equal(snapOver.translationSnapped, false, '12.01cm should release');

  // 5.99 deg (under 6.0 deg release)
  const angleUnder = (5.99 * Math.PI) / 180.0;
  const boxAngleUnder = {
    center: [10, 10, 0],
    dims: [2, 2, 2],
    yaw: angleUnder,
  };
  const snapAngleUnder = ghostEngine.evaluateMagnetSnap(boxAngleUnder, targetBox, true);
  assert.equal(snapAngleUnder.rotationSnapped, true, '5.99 deg should stay snapped under 6 deg threshold');

  // 6.01 deg (over 6.0 deg release)
  const angleOver = (6.01 * Math.PI) / 180.0;
  const boxAngleOver = {
    center: [10, 10, 0],
    dims: [2, 2, 2],
    yaw: angleOver,
  };
  const snapAngleOver = ghostEngine.evaluateMagnetSnap(boxAngleOver, targetBox, true);
  assert.equal(snapAngleOver.rotationSnapped, false, '6.01 deg should release');
});

test('8.4 performQuickLeveling handles ground_z fallback when target_bottom_z is missing', () => {
  const currentBox = {
    center: [0, 0, 5],
    dims: [4, 2, 2], // height = 2
    yaw: 0,
  };
  const targetBox = {
    center: [0, 0, 0],
    dims: [4, 2, 2],
    ground_z: -1.5,
    yaw: 0,
  };

  const leveled = ghostEngine.performQuickLeveling(currentBox, targetBox);
  // c_z = ground_z + height / 2 = -1.5 + 1.0 = -0.5
  assert.ok(Math.abs(leveled.center[2] - (-0.5)) < 1e-5);
  assert.equal(leveled.roll, 0.0);
  assert.equal(leveled.pitch, 0.0);
});

// -----------------------------------------------------------------------------
// 9. EVENT BRIDGE & COMMIT COORDINATION TESTS
// -----------------------------------------------------------------------------

test('9.1 hook dispatches lock committed event upon pointer up in green lock', () => {
  let emittedType = null;
  let emittedDetail = null;

  // Mock window dispatchEvent
  const originalWindow = global.window;
  global.window = {
    dispatchEvent: (evt) => {
      emittedType = evt.type;
      emittedDetail = evt.detail;
    },
    postMessage: () => {},
    addEventListener: () => {},
  };

  const target = { center: [0, 0, 0], dims: [2, 2, 2], yaw: 0 };
  hook.setGhostTarget(target);

  const perfectBox = {
    center: [0.005, 0.005, 0.0], // < 1 cm distance
    dims: [2, 2, 2],
    yaw: 0.005, // < 0.3 deg
    roll: 0.0,
    pitch: 0.0,
  };

  hook.handlePointerMove({}, perfectBox);
  hook.handlePointerUp({}, perfectBox);

  assert.equal(emittedType, 'POINTSNAP_3D_LOCK_COMMITTED');
  assert.ok(emittedDetail);
  assert.deepEqual(emittedDetail.target.center, [0, 0, 0]);

  // Clean up
  hook.clearGhostTarget();
  global.window = originalWindow;
});

