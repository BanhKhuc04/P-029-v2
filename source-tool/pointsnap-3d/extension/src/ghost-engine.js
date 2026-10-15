/*
 * PointSnap 3D Ghost Target & Magnet Snap Engine
 * Module runs in both Node.js (module.exports) and Browser (globalThis.PointSnapGhostEngine).
 *
 * Implements:
 * 1. normalizeAngle(angle): wrap to [-Math.PI, Math.PI)
 * 2. computeSpatialResiduals(currentBox, targetBox, points): continuous spatial deltas & clearances
 * 3. evaluateMagnetSnap(currentBox, targetBox, isCurrentlySnapped): 8cm / 4° snap with 12cm / 6° hysteresis
 * 4. performQuickLeveling(currentBox, targetBox): zero roll/pitch, ground contact, planar snapping
 */
(function (root) {
  'use strict';

  const SNAP_THRESHOLDS = {
    DIST_CAPTURE_CM: 8.0,
    DIST_RELEASE_CM: 12.0,
    ANGLE_CAPTURE_DEG: 4.0,
    ANGLE_RELEASE_DEG: 6.0,
    LOCK_DIST_CM: 2.0,
    LOCK_ANGLE_DEG: 2.0,
    LOCK_ROLL_DEG: 0.5,
    LOCK_PITCH_DEG: 0.5,
  };

  /**
   * Chuẩn hóa góc xoay (radian) về nửa khoảng [-Math.PI, Math.PI).
   * Đảm bảo tính liên tục và giải quyết branch-cut wrapping quanh +/- pi.
   *
   * @param {number} angle - Góc đầu vào tính bằng radian
   * @returns {number} Góc đã chuẩn hóa trong [-PI, PI)
   */
  function normalizeAngle(angle) {
    if (!Number.isFinite(angle)) return 0.0;
    const twoPi = 2.0 * Math.PI;
    let a = (angle + Math.PI) % twoPi;
    if (a < 0.0) a += twoPi;
    return a - Math.PI;
  }

  /**
   * Tính toán các chỉ số chênh lệch không gian (Spatial Residuals) giữa box hiện tại và target.
   *
   * @param {Object} currentBox - { center: [x, y, z], dims: [l, w, h], yaw: rad, roll?: rad, pitch?: rad }
   * @param {Object} targetBox  - { center: [x, y, z], dims: [l, w, h], yaw: rad, target_bottom_z?: number, ground_z?: number }
   * @param {Array<Array<number>>|null} [points] - Mảng điểm LiDAR [[x, y, z], ...] (tùy chọn)
   * @returns {Object} Spatial Residuals metrics
   */
  function computeSpatialResiduals(currentBox, targetBox, points = null) {
    if (!currentBox || !targetBox) {
      return {
        deltaZ_cm: 0.0,
        deltaYaw_deg: 0.0,
        dist3D_cm: 0.0,
        distXY_cm: 0.0,
        delta_dims_cm: [0.0, 0.0, 0.0],
        clearance_front_cm: 0.0,
        clearance_back_cm: 0.0,
        clearance_left_cm: 0.0,
        clearance_right_cm: 0.0,
        roll_deg: 0.0,
        pitch_deg: 0.0,
        isSnapped: false,
        isGreenLocked: false,
        statusText: 'OFF_TARGET',
      };
    }

    const c = currentBox.center || [0, 0, 0];
    const cDims = currentBox.dims || [0, 0, 0];
    const t = targetBox.center || [0, 0, 0];
    const tDims = targetBox.dims || [0, 0, 0];

    const cHeight = cDims[2] || 0.0;
    const tHeight = tDims[2] || 0.0;

    const cBottom = c[2] - cHeight / 2.0;
    const tBottom = targetBox.target_bottom_z != null
      ? targetBox.target_bottom_z
      : (targetBox.ground_z != null ? targetBox.ground_z : (t[2] - tHeight / 2.0));

    // deltaZ_cm: khoảng cách cao độ đáy box tới mục tiêu
    const deltaZ_cm = (cBottom - tBottom) * 100.0;

    // deltaYaw_deg: độ lệch góc yaw (độ)
    const cYaw = (currentBox.yaw != null && Number.isFinite(currentBox.yaw)) ? currentBox.yaw : 0.0;
    const tYaw = (targetBox.yaw != null && Number.isFinite(targetBox.yaw)) ? targetBox.yaw : 0.0;

    let deltaYaw_deg;
    if (
      (currentBox.yaw != null && !Number.isFinite(currentBox.yaw)) ||
      (targetBox.yaw != null && !Number.isFinite(targetBox.yaw))
    ) {
      deltaYaw_deg = NaN;
    } else {
      const deltaYaw_rad = normalizeAngle(cYaw - tYaw);
      deltaYaw_deg = deltaYaw_rad * (180.0 / Math.PI);
    }

    // dist3D_cm và distXY_cm (cm)
    const dx = c[0] - t[0];
    const dy = c[1] - t[1];
    const dz = c[2] - t[2];
    const distXY_cm = Math.hypot(dx, dy) * 100.0;
    const dist3D_cm = Math.hypot(dx, dy, dz) * 100.0;

    // delta_dims_cm
    const delta_dims_cm = [
      (cDims[0] - tDims[0]) * 100.0,
      (cDims[1] - tDims[1]) * 100.0,
      (cDims[2] - tDims[2]) * 100.0,
    ];

    // roll_deg, pitch_deg
    const roll_deg = Math.abs(currentBox.roll || 0.0) * (180.0 / Math.PI);
    const pitch_deg = Math.abs(currentBox.pitch || 0.0) * (180.0 / Math.PI);

    // Clearances
    let clearance_front_cm = 0.0;
    let clearance_back_cm = 0.0;
    let clearance_left_cm = 0.0;
    let clearance_right_cm = 0.0;

    if (Array.isArray(points) && points.length > 0) {
      const cosY = Math.cos(cYaw);
      const sinY = Math.sin(cYaw);
      const halfL = (cDims[0] || 0.0) / 2.0;
      const halfW = (cDims[1] || 0.0) / 2.0;
      const halfH = (cDims[2] || 0.0) / 2.0;

      let maxLx = -Infinity;
      let minLx = Infinity;
      let maxLy = -Infinity;
      let minLy = Infinity;
      let count = 0;

      for (let i = 0; i < points.length; i++) {
        const pt = points[i];
        if (!pt || pt.length < 3) continue;
        const px = pt[0] - c[0];
        const py = pt[1] - c[1];
        const pz = pt[2] - c[2];

        // Biến đổi sang hệ toạ độ cục bộ của box
        const lx = px * cosY + py * sinY;
        const ly = -px * sinY + py * cosY;
        const lz = pz;

        if (
          Math.abs(lx) <= halfL + 0.3 &&
          Math.abs(ly) <= halfW + 0.3 &&
          Math.abs(lz) <= halfH + 0.3
        ) {
          if (lx > maxLx) maxLx = lx;
          if (lx < minLx) minLx = lx;
          if (ly > maxLy) maxLy = ly;
          if (ly < minLy) minLy = ly;
          count++;
        }
      }

      if (count > 0) {
        clearance_front_cm = (halfL - maxLx) * 100.0;
        clearance_back_cm = (halfL + minLx) * 100.0;
        clearance_left_cm = (halfW - maxLy) * 100.0;
        clearance_right_cm = (halfW + minLy) * 100.0;
      }
    }

    // Predicates
    const isFiniteDist = Number.isFinite(dist3D_cm);
    const isFiniteYaw = Number.isFinite(deltaYaw_deg);
    const isWithinScene = isFiniteDist && dist3D_cm <= 50000.0; // 500m max scene interaction

    const isSnapped = isWithinScene && (
      (isFiniteDist && dist3D_cm <= SNAP_THRESHOLDS.DIST_CAPTURE_CM + 1e-4) ||
      (isFiniteYaw && Math.abs(deltaYaw_deg) <= SNAP_THRESHOLDS.ANGLE_CAPTURE_DEG + 1e-4)
    );

    const isGreenLocked = isWithinScene && isFiniteYaw &&
      dist3D_cm <= SNAP_THRESHOLDS.LOCK_DIST_CM + 1e-4 &&
      Math.abs(deltaYaw_deg) <= SNAP_THRESHOLDS.LOCK_ANGLE_DEG + 1e-4 &&
      roll_deg <= SNAP_THRESHOLDS.LOCK_ROLL_DEG + 1e-4 &&
      pitch_deg <= SNAP_THRESHOLDS.LOCK_PITCH_DEG + 1e-4;

    const statusText = isGreenLocked ? 'GREEN_LOCK' : (isSnapped ? 'SNAPPED' : 'OFF_TARGET');

    return {
      deltaZ_cm,
      deltaYaw_deg,
      dist3D_cm,
      distXY_cm,
      delta_dims_cm,
      clearance_front_cm,
      clearance_back_cm,
      clearance_left_cm,
      clearance_right_cm,
      roll_deg,
      pitch_deg,
      isSnapped,
      isGreenLocked,
      statusText,
    };
  }

  /**
   * Đánh giá cơ chế Magnet Snap với Hysteresis buffer chống giật ngưỡng (jitter).
   * - Ngưỡng bắt dính (capture): 8 cm / 4°
   * - Ngưỡng nhả dính (release): 12 cm / 6°
   * - Khi bắt dính tịnh tiến: khóa tâm về target, triệt tiêu roll = 0, pitch = 0
   * - Khi bắt dính góc xoay: khóa yaw về target.yaw
   *
   * @param {Object} currentBox - Box hiện tại
   * @param {Object} targetBox  - Box mục tiêu
   * @param {boolean} [isCurrentlySnapped=false] - Trạng thái bắt dính trước đó
   * @returns {Object} { snapped, translationSnapped, rotationSnapped, box, residuals }
   */
  function evaluateMagnetSnap(currentBox, targetBox, isCurrentlySnapped = false) {
    if (!currentBox || !targetBox) {
      return {
        snapped: false,
        translationSnapped: false,
        rotationSnapped: false,
        box: currentBox ? { ...currentBox } : null,
        residuals: null,
      };
    }

    const distThreshold_cm = isCurrentlySnapped
      ? SNAP_THRESHOLDS.DIST_RELEASE_CM
      : SNAP_THRESHOLDS.DIST_CAPTURE_CM;
    const angleThreshold_deg = isCurrentlySnapped
      ? SNAP_THRESHOLDS.ANGLE_RELEASE_DEG
      : SNAP_THRESHOLDS.ANGLE_CAPTURE_DEG;

    const rawResiduals = computeSpatialResiduals(currentBox, targetBox);
    const dist3D_cm = rawResiduals.dist3D_cm;
    const deltaYaw_deg = Math.abs(rawResiduals.deltaYaw_deg);

    const isWithinScene = Number.isFinite(dist3D_cm) && dist3D_cm <= 50000.0;
    const isFiniteYaw = Number.isFinite(deltaYaw_deg);

    const translationSnapped = isWithinScene && dist3D_cm <= distThreshold_cm + 1e-4;
    const rotationSnapped = isWithinScene && isFiniteYaw && deltaYaw_deg <= angleThreshold_deg + 1e-4;
    const snapped = translationSnapped || rotationSnapped;

    const newCenter = translationSnapped
      ? [...targetBox.center]
      : [...currentBox.center];

    const newYaw = rotationSnapped
      ? targetBox.yaw
      : currentBox.yaw;

    const newRoll = translationSnapped
      ? 0.0
      : (currentBox.roll || 0.0);

    const newPitch = translationSnapped
      ? 0.0
      : (currentBox.pitch || 0.0);

    const newDims = targetBox.dims
      ? [...targetBox.dims]
      : [...currentBox.dims];

    const box = {
      center: newCenter,
      dims: newDims,
      yaw: newYaw,
      roll: newRoll,
      pitch: newPitch,
    };

    const residuals = {
      ...rawResiduals,
      isSnapped: snapped,
      isGreenLocked: rawResiduals.isGreenLocked,
      statusText: rawResiduals.isGreenLocked ? 'GREEN_LOCK' : (snapped ? 'SNAPPED' : 'OFF_TARGET'),
    };

    return {
      snapped,
      translationSnapped,
      rotationSnapped,
      box,
      residuals,
      rawResiduals,
    };
  }

  /**
   * Cân bằng nhanh (Quick Leveling Hotkey `KeyL` / `Shift+KeyS`):
   * - Triệt tiêu tuyệt đối roll = 0.0 và pitch = 0.0
   * - Hạ/nâng đáy box về sát mặt sàn mục tiêu (target_bottom_z + h/2)
   * - Nếu khoảng cách mặt phẳng distXY <= 8 cm, tự động hút tâm phẳng (x, y) về target
   *
   * @param {Object} currentBox - Box hiện tại
   * @param {Object} [targetBox] - Box mục tiêu (nếu có)
   * @returns {Object} Box đã được cân bằng phẳng với roll=0, pitch=0
   */
  function performQuickLeveling(currentBox, targetBox = null) {
    if (!currentBox) return null;

    const c = currentBox.center ? [...currentBox.center] : [0, 0, 0];
    const cDims = currentBox.dims ? [...currentBox.dims] : [1, 1, 1];
    const cHeight = cDims[2] || 0.0;

    let c_x = c[0];
    let c_y = c[1];
    let c_z = c[2];

    if (targetBox && targetBox.center) {
      const t = targetBox.center;
      const tDims = targetBox.dims || cDims;
      const tHeight = tDims[2] || cHeight;

      // Xác định cao độ đáy sàn mục tiêu
      let targetBottomZ;
      if (targetBox.target_bottom_z != null) {
        targetBottomZ = targetBox.target_bottom_z;
      } else if (targetBox.ground_z != null) {
        targetBottomZ = targetBox.ground_z;
      } else {
        targetBottomZ = t[2] - tHeight / 2.0;
      }

      // Đặt tâm z sao cho đáy box tiếp xúc phẳng với sàn
      c_z = targetBottomZ + cHeight / 2.0;

      // Nếu gần mục tiêu trong phạm vi 8 cm (mặt phẳng XY), hút tâm phẳng
      const distXY_cm = Math.hypot(c_x - t[0], c_y - t[1]) * 100.0;
      if (distXY_cm <= SNAP_THRESHOLDS.DIST_CAPTURE_CM + 1e-4) {
        c_x = t[0];
        c_y = t[1];
      }
    }

    return {
      center: [c_x, c_y, c_z],
      dims: [...cDims],
      yaw: currentBox.yaw || 0.0,
      roll: 0.0,
      pitch: 0.0,
    };
  }

  const api = {
    SNAP_THRESHOLDS,
    normalizeAngle,
    computeSpatialResiduals,
    evaluateMagnetSnap,
    performQuickLeveling,
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  } else {
    root.PointSnapGhostEngine = api;
  }
})(typeof globalThis !== 'undefined' ? globalThis : this);
