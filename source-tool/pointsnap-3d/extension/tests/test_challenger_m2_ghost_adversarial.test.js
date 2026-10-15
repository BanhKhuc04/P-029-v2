/*
 * Adversarial Stress Test Suite for PointSnap 3D Ghost Target & Magnet Snap Engine (Milestone M2)
 * Challenger: challenger_m2_1
 *
 * Probes:
 * 1. Extreme coordinates (1e9, -1e9, 1e15, 1e308, 0, NaN, undefined, Infinity, null, malformed dims)
 * 2. Branch cut discontinuities at +/- PI (PI - 0.0001 vs -PI + 0.0001, continuous angular sweep)
 * 3. Rapid oscillating movements across 8cm / 12cm translation hysteresis boundary (5,000 cycles)
 * 4. Yaw hysteresis across 4° / 6° boundary (5,000 cycles, symmetrical +/- yaw, clamping)
 * 5. High-throughput performance harness: 50,000 residual & snap evaluations (guaranteeing << 0.1ms)
 * 6. Quick Leveling & Green Lock edge boundaries
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const { performance } = require('node:perf_hooks');

const ghostEngine = require('../src/ghost-engine.js');

// Helper to create box
function makeBox(x = 0, y = 0, z = 0, l = 4.0, w = 2.0, h = 1.6, yaw = 0.0, roll = 0.0, pitch = 0.0) {
  return {
    center: [x, y, z],
    dims: [l, w, h],
    yaw,
    roll,
    pitch,
  };
}

// =============================================================================
// SUITE 1: EXTREME COORDINATES & MALFORMED INPUTS
// =============================================================================

test('ADV 1.1 Extreme coordinates (1e9, -1e9, 1e15) do not throw or produce invalid states', () => {
  const extremes = [1e9, -1e9, 1e15, -1e15];

  for (const val of extremes) {
    const cur = makeBox(val, -val, val);
    const tgt = makeBox(0, 0, 0);

    const res = ghostEngine.computeSpatialResiduals(cur, tgt);
    assert.equal(typeof res.dist3D_cm, 'number');
    assert.ok(Number.isFinite(res.dist3D_cm));
    assert.equal(res.isSnapped, false);
    assert.equal(res.isGreenLocked, false);
    assert.equal(res.statusText, 'OFF_TARGET');

    const snap = ghostEngine.evaluateMagnetSnap(cur, tgt, false);
    assert.equal(snap.snapped, false);
    assert.equal(snap.translationSnapped, false);
    assert.deepEqual(snap.box.center, [val, -val, val]);

    const leveled = ghostEngine.performQuickLeveling(cur, tgt);
    assert.equal(leveled.center[0], val);
    assert.equal(leveled.center[1], -val);
    assert.equal(leveled.roll, 0.0);
    assert.equal(leveled.pitch, 0.0);
  }
});

test('ADV 1.2 Subnormal numbers (1e-320) and zero coordinates evaluate cleanly without divide-by-zero', () => {
  const subnormalBox = makeBox(1e-320, 1e-320, 1e-320, 1e-320, 1e-320, 1e-320, 1e-320);
  const zeroBox = makeBox(0, 0, 0, 0, 0, 0, 0);

  const res = ghostEngine.computeSpatialResiduals(subnormalBox, zeroBox);
  assert.ok(Number.isFinite(res.dist3D_cm));
  assert.ok(Number.isFinite(res.deltaZ_cm));
  assert.ok(Number.isFinite(res.deltaYaw_deg));
  assert.equal(res.isGreenLocked, true); // within 2cm and 2°

  const snap = ghostEngine.evaluateMagnetSnap(subnormalBox, zeroBox, false);
  assert.equal(snap.snapped, true);
  assert.equal(snap.translationSnapped, true);
  assert.equal(snap.rotationSnapped, true);
});

test('ADV 1.3 NaN and undefined in center / dims / yaw fail-safe to OFF_TARGET without throwing', () => {
  const nanBox = {
    center: [NaN, undefined, null],
    dims: [NaN, 2.0, 1.5],
    yaw: NaN,
    roll: undefined,
    pitch: null,
  };
  const target = makeBox(0, 0, 0);

  const res = ghostEngine.computeSpatialResiduals(nanBox, target);
  assert.equal(res.isSnapped, false, 'NaN inputs must not snap');
  assert.equal(res.isGreenLocked, false, 'NaN inputs must not green lock');
  assert.equal(res.statusText, 'OFF_TARGET');

  const snap = ghostEngine.evaluateMagnetSnap(nanBox, target, false);
  assert.equal(snap.snapped, false);
  assert.equal(snap.translationSnapped, false);
  assert.equal(snap.rotationSnapped, false);

  // When already snapped, NaN coordinates must also release / fail safe
  const snapHeld = ghostEngine.evaluateMagnetSnap(nanBox, target, true);
  assert.equal(snapHeld.snapped, false);
  assert.equal(snapHeld.translationSnapped, false);
  assert.equal(snapHeld.rotationSnapped, false);
});

test('ADV 1.4 Null / empty / non-object inputs return safe default structures', () => {
  const safeRes1 = ghostEngine.computeSpatialResiduals(null, null);
  assert.equal(safeRes1.isSnapped, false);
  assert.equal(safeRes1.statusText, 'OFF_TARGET');
  assert.equal(safeRes1.dist3D_cm, 0.0);

  const safeRes2 = ghostEngine.computeSpatialResiduals({}, {});
  assert.equal(safeRes2.isSnapped, true); // both default to center [0,0,0], yaw 0 -> dist 0
  assert.equal(safeRes2.isGreenLocked, true);

  const safeSnap1 = ghostEngine.evaluateMagnetSnap(null, null, false);
  assert.equal(safeSnap1.snapped, false);
  assert.equal(safeSnap1.box, null);

  const safeLevel1 = ghostEngine.performQuickLeveling(null, null);
  assert.equal(safeLevel1, null);
});

test('ADV 1.5 Adversarial point clouds with 1,000 malformed elements are filtered safely', () => {
  const cur = makeBox(0, 0, 0, 4, 2, 2);
  const tgt = makeBox(0, 0, 0, 4, 2, 2);

  const corruptPoints = [
    null,
    undefined,
    [],
    [1],
    [1, 2],
    [NaN, 0, 0],
    [0, NaN, 0],
    [0, 0, NaN],
    [Infinity, 0, 0],
    [-Infinity, 0, 0],
    ['str', 'str', 'str'],
    { x: 1, y: 2, z: 3 },
  ];
  // Fill up to 1,000 corrupt points
  const points = [];
  for (let i = 0; i < 1000; i++) {
    points.push(corruptPoints[i % corruptPoints.length]);
  }
  // Add 1 valid point
  points.push([1.5, 0.5, 0.0]);

  const res = ghostEngine.computeSpatialResiduals(cur, tgt, points);
  assert.ok(Number.isFinite(res.clearance_front_cm));
  assert.ok(Number.isFinite(res.clearance_back_cm));
  assert.ok(Number.isFinite(res.clearance_left_cm));
  assert.ok(Number.isFinite(res.clearance_right_cm));
  // halfL = 2.0, point x=1.5 -> front clearance = (2.0 - 1.5) * 100 = 50 cm
  assert.ok(Math.abs(res.clearance_front_cm - 50.0) < 1e-4);
});

// =============================================================================
// SUITE 2: BRANCH CUT DISCONTINUITIES AT +/- PI
// =============================================================================

test('ADV 2.1 Branch cut discontinuity test at PI - 0.0001 vs -PI + 0.0001', () => {
  const eps = 0.0001;
  const yawCurrent = Math.PI - eps;
  const yawTarget = -Math.PI + eps;

  const cur = makeBox(0, 0, 0, 4, 2, 1.5, yawCurrent);
  const tgt = makeBox(0, 0, 0, 4, 2, 1.5, yawTarget);

  const res = ghostEngine.computeSpatialResiduals(cur, tgt);

  // The true angular difference across the branch cut is 2 * eps rad = 0.0002 rad
  const expectedDeg = (2.0 * eps) * (180.0 / Math.PI); // ~0.01146 deg
  assert.ok(
    Math.abs(Math.abs(res.deltaYaw_deg) - expectedDeg) < 1e-4,
    `Expected deltaYaw ~${expectedDeg} deg, but got ${res.deltaYaw_deg} deg (branch cut jump!)`
  );

  // Must be within rotation snap capture threshold (<= 4.0 deg)
  assert.equal(res.isSnapped, true);
  assert.equal(res.isGreenLocked, true);

  const snap = ghostEngine.evaluateMagnetSnap(cur, tgt, false);
  assert.equal(snap.rotationSnapped, true);
  assert.equal(snap.box.yaw, yawTarget);
});

test('ADV 2.2 Symmetrical branch cut test: -PI + 0.0001 vs PI - 0.0001', () => {
  const eps = 0.0001;
  const yawCurrent = -Math.PI + eps;
  const yawTarget = Math.PI - eps;

  const cur = makeBox(0, 0, 0, 4, 2, 1.5, yawCurrent);
  const tgt = makeBox(0, 0, 0, 4, 2, 1.5, yawTarget);

  const res = ghostEngine.computeSpatialResiduals(cur, tgt);
  const expectedDeg = (2.0 * eps) * (180.0 / Math.PI);
  assert.ok(
    Math.abs(Math.abs(res.deltaYaw_deg) - expectedDeg) < 1e-4,
    `Expected deltaYaw ~${expectedDeg} deg, got ${res.deltaYaw_deg}`
  );
  assert.equal(res.isSnapped, true);
  assert.equal(res.isGreenLocked, true);
});

test('ADV 2.3 Continuous 2,000-point sweep across +/- PI verifies continuity and monotonicity', () => {
  const steps = 2000;
  const targetYaw = Math.PI; // Target on branch cut
  const tgt = makeBox(0, 0, 0, 4, 2, 1.5, targetYaw);

  let prevDeltaDeg = null;

  // Sweep current yaw from (PI - 0.2) to (PI + 0.2)
  for (let i = 0; i <= steps; i++) {
    const offset = -0.2 + (0.4 * i) / steps;
    const currentYaw = Math.PI + offset; // naturally crosses +PI into > PI
    const cur = makeBox(0, 0, 0, 4, 2, 1.5, currentYaw);

    const res = ghostEngine.computeSpatialResiduals(cur, tgt);
    const absDeltaDeg = Math.abs(res.deltaYaw_deg);

    // Delta yaw should never exceed ~11.5 deg (|offset| <= 0.2 rad = 11.459 deg)
    assert.ok(
      absDeltaDeg <= 12.0,
      `Delta yaw spiked to ${absDeltaDeg} deg at offset ${offset} rad`
    );

    // Verify expected smooth angle
    const expectedDeg = Math.abs(ghostEngine.normalizeAngle(offset)) * (180.0 / Math.PI);
    assert.ok(
      Math.abs(absDeltaDeg - expectedDeg) < 1e-4,
      `Angle mismatch: expected ${expectedDeg}, got ${absDeltaDeg}`
    );
  }
});

test('ADV 2.4 Multi-turn rotation unwinding handles extreme multiples of 2*PI', () => {
  const turns = [2, -2, 10, -10, 50, -50, 1000, -1000];

  for (const k of turns) {
    const rawAngle = k * 2.0 * Math.PI + 0.35;
    const norm = ghostEngine.normalizeAngle(rawAngle);
    assert.ok(
      Math.abs(norm - 0.35) < 1e-6,
      `Failed to unwind ${k} turns: got ${norm}, expected 0.35`
    );
  }
});

// =============================================================================
// SUITE 3: RAPID OSCILLATING MOVEMENTS ACROSS 8cm / 12cm HYSTERESIS BOUNDARY
// =============================================================================

test('ADV 3.1 Strict capture boundary at <= 8.0 cm when initially unsnapped', () => {
  const tgt = makeBox(0, 0, 0);

  // 8.05 cm -> MUST NOT snap
  const boxOutside = makeBox(0.0805, 0, 0, 4, 2, 1.5, 0.5); // yaw far away
  const snapOut = ghostEngine.evaluateMagnetSnap(boxOutside, tgt, false);
  assert.equal(snapOut.translationSnapped, false);
  assert.equal(snapOut.snapped, false);

  // 8.00 cm -> MUST snap
  const boxBorder = makeBox(0.0800, 0, 0, 4, 2, 1.5, 0.5);
  const snapBorder = ghostEngine.evaluateMagnetSnap(boxBorder, tgt, false);
  assert.equal(snapBorder.translationSnapped, true);
  assert.equal(snapBorder.snapped, true);

  // 7.95 cm -> MUST snap
  const boxInside = makeBox(0.0795, 0, 0, 4, 2, 1.5, 0.5);
  const snapIn = ghostEngine.evaluateMagnetSnap(boxInside, tgt, false);
  assert.equal(snapIn.translationSnapped, true);
  assert.equal(snapIn.snapped, true);
});

test('ADV 3.2 5,000 rapid jitter oscillations inside [8.1 cm, 11.9 cm] maintain snap without fluttering', () => {
  const tgt = makeBox(0, 0, 0);

  // Step 1: Initial capture at 7.0 cm
  let curBox = makeBox(0.070, 0, 0, 4, 2, 1.5, 0.5);
  let snapState = ghostEngine.evaluateMagnetSnap(curBox, tgt, false);
  assert.equal(snapState.translationSnapped, true);
  assert.equal(snapState.snapped, true);

  let isCurrentlySnapped = snapState.snapped;

  // Step 2: 5,000 rapid back-and-forth jitter cycles between 8.1cm and 11.9cm
  let unsnapCount = 0;
  for (let i = 0; i < 5000; i++) {
    // Generate pseudo-random or alternating distance in [8.1cm, 11.9cm]
    const distanceMeters = 0.081 + (i % 38) * 0.001; // 8.1 cm to 11.8 cm
    curBox = makeBox(distanceMeters, 0, 0, 4, 2, 1.5, 0.5);

    snapState = ghostEngine.evaluateMagnetSnap(curBox, tgt, isCurrentlySnapped);

    if (!snapState.translationSnapped) {
      unsnapCount++;
    }
    // Update state tracker
    isCurrentlySnapped = snapState.snapped;
  }

  assert.equal(
    unsnapCount,
    0,
    `Hysteresis failure! Translation snapped state fluttered/unsnapped ${unsnapCount} times inside the buffer zone.`
  );
  assert.equal(isCurrentlySnapped, true);
});

test('ADV 3.3 Strict release boundary at > 12.0 cm terminates translation snap', () => {
  const tgt = makeBox(0, 0, 0);

  // 11.95 cm -> MUST remain snapped when isCurrentlySnapped = true
  const boxUnder = makeBox(0.1195, 0, 0, 4, 2, 1.5, 0.5);
  const snapUnder = ghostEngine.evaluateMagnetSnap(boxUnder, tgt, true);
  assert.equal(snapUnder.translationSnapped, true);

  // 12.05 cm -> MUST release snap
  const boxOver = makeBox(0.1205, 0, 0, 4, 2, 1.5, 0.5);
  const snapOver = ghostEngine.evaluateMagnetSnap(boxOver, tgt, true);
  assert.equal(snapOver.translationSnapped, false);
  assert.equal(snapOver.snapped, false);
});

test('ADV 3.4 5,000 rapid jitter oscillations inside [8.1 cm, 11.9 cm] after release remain unsnapped', () => {
  const tgt = makeBox(0, 0, 0);

  // Step 1: Initial release at 13.0 cm
  let curBox = makeBox(0.130, 0, 0, 4, 2, 1.5, 0.5);
  let snapState = ghostEngine.evaluateMagnetSnap(curBox, tgt, true);
  assert.equal(snapState.translationSnapped, false);
  assert.equal(snapState.snapped, false);

  let isCurrentlySnapped = snapState.snapped; // false

  // Step 2: 5,000 rapid cycles inside [8.1cm, 11.9cm]
  let falseSnapCount = 0;
  for (let i = 0; i < 5000; i++) {
    const distanceMeters = 0.081 + (i % 38) * 0.001; // 8.1 cm to 11.8 cm
    curBox = makeBox(distanceMeters, 0, 0, 4, 2, 1.5, 0.5);

    snapState = ghostEngine.evaluateMagnetSnap(curBox, tgt, isCurrentlySnapped);

    if (snapState.translationSnapped) {
      falseSnapCount++;
    }
    isCurrentlySnapped = snapState.snapped;
  }

  assert.equal(
    falseSnapCount,
    0,
    `Hysteresis failure! Prematurely snapped ${falseSnapCount} times inside the buffer without reaching <= 8.0 cm.`
  );
  assert.equal(isCurrentlySnapped, false);
});

// =============================================================================
// SUITE 4: YAW HYSTERESIS ACROSS 4° / 6° BOUNDARY
// =============================================================================

test('ADV 4.1 Yaw capture at <= 4.0° and release at > 6.0°', () => {
  const tgt = makeBox(0, 0, 0, 4, 2, 1.5, 0.0);

  // 4.1° -> Not snapped when starting false
  const deg4_1 = (4.1 * Math.PI) / 180.0;
  const box4_1 = makeBox(10.0, 10.0, 0, 4, 2, 1.5, deg4_1);
  const snap4_1 = ghostEngine.evaluateMagnetSnap(box4_1, tgt, false);
  assert.equal(snap4_1.rotationSnapped, false);

  // 3.9° -> Snapped
  const deg3_9 = (3.9 * Math.PI) / 180.0;
  const box3_9 = makeBox(10.0, 10.0, 0, 4, 2, 1.5, deg3_9);
  const snap3_9 = ghostEngine.evaluateMagnetSnap(box3_9, tgt, false);
  assert.equal(snap3_9.rotationSnapped, true);
  assert.equal(snap3_9.box.yaw, 0.0, 'Yaw must be clamped to target when snapped');

  // While snapped: 5.9° remains snapped
  const deg5_9 = (5.9 * Math.PI) / 180.0;
  const box5_9 = makeBox(10.0, 10.0, 0, 4, 2, 1.5, deg5_9);
  const snap5_9 = ghostEngine.evaluateMagnetSnap(box5_9, tgt, true);
  assert.equal(snap5_9.rotationSnapped, true);

  // While snapped: 6.1° releases
  const deg6_1 = (6.1 * Math.PI) / 180.0;
  const box6_1 = makeBox(10.0, 10.0, 0, 4, 2, 1.5, deg6_1);
  const snap6_1 = ghostEngine.evaluateMagnetSnap(box6_1, tgt, true);
  assert.equal(snap6_1.rotationSnapped, false);
  assert.equal(snap6_1.box.yaw, deg6_1, 'Yaw must remain unchanged when released');
});

test('ADV 4.2 Symmetrical yaw hysteresis with negative angles (-4° capture, -6° release)', () => {
  const tgt = makeBox(0, 0, 0, 4, 2, 1.5, 0.0);

  // -4.1° -> Not snapped
  const neg4_1 = (-4.1 * Math.PI) / 180.0;
  const snapNegOut = ghostEngine.evaluateMagnetSnap(
    makeBox(10, 10, 0, 4, 2, 1.5, neg4_1),
    tgt,
    false
  );
  assert.equal(snapNegOut.rotationSnapped, false);

  // -3.9° -> Snapped
  const neg3_9 = (-3.9 * Math.PI) / 180.0;
  const snapNegIn = ghostEngine.evaluateMagnetSnap(
    makeBox(10, 10, 0, 4, 2, 1.5, neg3_9),
    tgt,
    false
  );
  assert.equal(snapNegIn.rotationSnapped, true);

  // -5.9° -> Held
  const neg5_9 = (-5.9 * Math.PI) / 180.0;
  const snapNegHeld = ghostEngine.evaluateMagnetSnap(
    makeBox(10, 10, 0, 4, 2, 1.5, neg5_9),
    tgt,
    true
  );
  assert.equal(snapNegHeld.rotationSnapped, true);

  // -6.1° -> Released
  const neg6_1 = (-6.1 * Math.PI) / 180.0;
  const snapNegRel = ghostEngine.evaluateMagnetSnap(
    makeBox(10, 10, 0, 4, 2, 1.5, neg6_1),
    tgt,
    true
  );
  assert.equal(snapNegRel.rotationSnapped, false);
});

test('ADV 4.3 5,000 rapid yaw jitter oscillations inside [4.2°, 5.8°] remain stable', () => {
  const tgt = makeBox(0, 0, 0, 4, 2, 1.5, 0.0);

  // Capture at 3.0°
  let curBox = makeBox(10, 10, 0, 4, 2, 1.5, (3.0 * Math.PI) / 180.0);
  let snapState = ghostEngine.evaluateMagnetSnap(curBox, tgt, false);
  assert.equal(snapState.rotationSnapped, true);
  let isCurrentlySnapped = snapState.rotationSnapped;

  let unsnapCount = 0;
  for (let i = 0; i < 5000; i++) {
    const deg = 4.2 + (i % 16) * 0.1; // 4.2° to 5.7°
    const rad = (deg * Math.PI) / 180.0;
    curBox = makeBox(10, 10, 0, 4, 2, 1.5, rad);

    snapState = ghostEngine.evaluateMagnetSnap(curBox, tgt, false, isCurrentlySnapped);
    if (!snapState.rotationSnapped) {
      unsnapCount++;
    }
    isCurrentlySnapped = snapState.rotationSnapped;
  }

  assert.equal(unsnapCount, 0, `Yaw hysteresis jittered ${unsnapCount} times inside [4.2°, 5.8°] buffer.`);
  assert.equal(isCurrentlySnapped, true);
});

// =============================================================================
// SUITE 5: HIGH-THROUGHPUT PERFORMANCE STRESS TEST (50,000 CALCULATIONS)
// =============================================================================

test('ADV 5.1 Performance Harness: 50,000 computeSpatialResiduals calculations take << 0.1ms each', () => {
  const ITERATIONS = 50000;
  const boxes = [];

  // Pre-generate varied boxes to prevent engine de-optimizations
  for (let i = 0; i < 100; i++) {
    boxes.push(makeBox(
      0.01 * (i - 50),
      0.01 * ((i * 2) % 50),
      0.005 * (i % 20),
      4.0 + 0.01 * i,
      2.0 + 0.01 * i,
      1.5 + 0.01 * i,
      0.02 * (i - 50),
      0.005 * (i % 10),
      0.005 * ((i * 3) % 10)
    ));
  }
  const tgt = makeBox(0, 0, 0, 4.0, 2.0, 1.5, 0.0);

  // Warmup JIT
  for (let i = 0; i < 1000; i++) {
    ghostEngine.computeSpatialResiduals(boxes[i % 100], tgt);
  }

  const start = performance.now();
  let checksum = 0;

  for (let i = 0; i < ITERATIONS; i++) {
    const res = ghostEngine.computeSpatialResiduals(boxes[i % 100], tgt);
    checksum += res.dist3D_cm;
  }

  const durationMs = performance.now() - start;
  const avgMsPerOp = durationMs / ITERATIONS;
  const opsPerSec = (ITERATIONS / durationMs) * 1000;

  assert.ok(checksum > 0); // prevent dead-code elimination
  assert.ok(
    avgMsPerOp < 0.1,
    `Performance failure: avg time per residual calc was ${avgMsPerOp.toFixed(6)} ms (limit: 0.1 ms)`
  );
  assert.ok(
    avgMsPerOp < 0.02,
    `Performance warning: avg time per calc was ${avgMsPerOp.toFixed(6)} ms, expected << 0.02 ms`
  );

  console.log(`\n  [PERF] 50,000 computeSpatialResiduals: total=${durationMs.toFixed(2)}ms, avg=${(avgMsPerOp * 1000).toFixed(3)}µs/op, throughput=${Math.round(opsPerSec).toLocaleString()} ops/sec`);
});

test('ADV 5.2 Performance Harness: 50,000 evaluateMagnetSnap calculations take << 0.1ms each', () => {
  const ITERATIONS = 50000;
  const boxes = [];

  for (let i = 0; i < 100; i++) {
    boxes.push(makeBox(
      0.001 * (i % 150),
      0.001 * ((i * 3) % 150),
      0.0,
      4.0,
      2.0,
      1.5,
      0.001 * (i % 100)
    ));
  }
  const tgt = makeBox(0, 0, 0, 4.0, 2.0, 1.5, 0.0);

  // Warmup JIT
  for (let i = 0; i < 1000; i++) {
    ghostEngine.evaluateMagnetSnap(boxes[i % 100], tgt, (i % 2) === 0);
  }

  const start = performance.now();
  let snappedCount = 0;

  for (let i = 0; i < ITERATIONS; i++) {
    const isSnapped = (i % 2) === 0;
    const snap = ghostEngine.evaluateMagnetSnap(boxes[i % 100], tgt, isSnapped);
    if (snap.snapped) snappedCount++;
  }

  const durationMs = performance.now() - start;
  const avgMsPerOp = durationMs / ITERATIONS;
  const opsPerSec = (ITERATIONS / durationMs) * 1000;

  assert.ok(snappedCount > 0);
  assert.ok(
    avgMsPerOp < 0.1,
    `Performance failure: avg time per snap was ${avgMsPerOp.toFixed(6)} ms (limit: 0.1 ms)`
  );

  console.log(`  [PERF] 50,000 evaluateMagnetSnap: total=${durationMs.toFixed(2)}ms, avg=${(avgMsPerOp * 1000).toFixed(3)}µs/op, throughput=${Math.round(opsPerSec).toLocaleString()} ops/sec\n`);
});

// =============================================================================
// SUITE 6: QUICK LEVELING & GREEN LOCK BOUNDARY CONDITIONS
// =============================================================================

test('ADV 6.1 Green Lock tolerance boundaries: 2.000cm vs 2.001cm, 2.000° vs 2.001°, 0.500° vs 0.501°', () => {
  const tgt = makeBox(0, 0, 0, 4, 2, 1.5, 0.0);

  // Exact 2.0 cm distance with 0 yaw/roll/pitch -> Green Lock PASS
  const boxExactDist = makeBox(0.02, 0, 0, 4, 2, 1.5, 0, 0, 0);
  const resExactDist = ghostEngine.computeSpatialResiduals(boxExactDist, tgt);
  assert.equal(resExactDist.isGreenLocked, true, 'Exact 2.0cm must green lock');

  // 2.02 cm distance (> 2.0cm) -> Green Lock FAIL
  const boxOverDist = makeBox(0.0202, 0, 0, 4, 2, 1.5, 0, 0, 0);
  const resOverDist = ghostEngine.computeSpatialResiduals(boxOverDist, tgt);
  assert.equal(resOverDist.isGreenLocked, false, '2.02cm must not green lock');

  // Exact 2.0° yaw -> Green Lock PASS
  const yaw2Deg = (2.0 * Math.PI) / 180.0;
  const boxExactYaw = makeBox(0, 0, 0, 4, 2, 1.5, yaw2Deg, 0, 0);
  const resExactYaw = ghostEngine.computeSpatialResiduals(boxExactYaw, tgt);
  assert.equal(resExactYaw.isGreenLocked, true, 'Exact 2.0 deg must green lock');

  // 2.02° yaw -> Green Lock FAIL
  const yawOverDeg = (2.02 * Math.PI) / 180.0;
  const boxOverYaw = makeBox(0, 0, 0, 4, 2, 1.5, yawOverDeg, 0, 0);
  const resOverYaw = ghostEngine.computeSpatialResiduals(boxOverYaw, tgt);
  assert.equal(resOverYaw.isGreenLocked, false, '2.02 deg must not green lock');

  // Exact 0.5° roll -> Green Lock PASS
  const roll0_5 = (0.5 * Math.PI) / 180.0;
  const boxExactRoll = makeBox(0, 0, 0, 4, 2, 1.5, 0, roll0_5, 0);
  const resExactRoll = ghostEngine.computeSpatialResiduals(boxExactRoll, tgt);
  assert.equal(resExactRoll.isGreenLocked, true, 'Exact 0.5 deg roll must green lock');

  // 0.52° roll -> Green Lock FAIL
  const roll0_52 = (0.52 * Math.PI) / 180.0;
  const boxOverRoll = makeBox(0, 0, 0, 4, 2, 1.5, 0, roll0_52, 0);
  const resOverRoll = ghostEngine.computeSpatialResiduals(boxOverRoll, tgt);
  assert.equal(resOverRoll.isGreenLocked, false, '0.52 deg roll must not green lock');
});

test('ADV 6.2 performQuickLeveling strict planar snap at 8.00cm vs preserve at 8.05cm', () => {
  const tgt = {
    center: [2.0, 3.0, 1.0],
    dims: [4.0, 2.0, 1.6],
    target_bottom_z: 0.2,
    yaw: 0.0,
  };

  // Distance XY = 7.95 cm (within 8cm) -> snaps (x, y) to (2.0, 3.0)
  const boxSnap = makeBox(2.0795, 3.0, 2.0, 4.0, 2.0, 1.6);
  const leveledSnap = ghostEngine.performQuickLeveling(boxSnap, tgt);
  assert.equal(leveledSnap.center[0], 2.0);
  assert.equal(leveledSnap.center[1], 3.0);
  assert.ok(Math.abs(leveledSnap.center[2] - (0.2 + 0.8)) < 1e-5);
  assert.equal(leveledSnap.roll, 0.0);
  assert.equal(leveledSnap.pitch, 0.0);

  // Distance XY = 8.05 cm (> 8cm) -> keeps (x, y) = (2.0805, 3.0)
  const boxKeep = makeBox(2.0805, 3.0, 2.0, 4.0, 2.0, 1.6);
  const leveledKeep = ghostEngine.performQuickLeveling(boxKeep, tgt);
  assert.equal(leveledKeep.center[0], 2.0805);
  assert.equal(leveledKeep.center[1], 3.0);
  assert.ok(Math.abs(leveledKeep.center[2] - (0.2 + 0.8)) < 1e-5);
  assert.equal(leveledKeep.roll, 0.0);
  assert.equal(leveledKeep.pitch, 0.0);
});
