/*
 * PointSnap 3D Canvas Hook (CVAT MAIN World Script)
 * Module runs in both browser (MAIN world) and Node.js (module.exports) for unit testing.
 *
 * Responsibilities:
 * 1. Manages Three.js scene overlay: adds dashed wireframe box (THREE.LineSegments) and directional arrow.
 * 2. Intercepts dragging: integrates evaluateMagnetSnap when annotator translates or rotates cuboid in 3D canvas.
 * 3. Hotkey handler: listens for KeyL or Shift+KeyS, ignores input/textarea, applies performQuickLeveling.
 * 4. Event bridge: dispatches CustomEvent & window.postMessage (POINTSNAP_3D_TELEMETRY, POINTSNAP_QUICK_LEVEL_APPLIED, POINTSNAP_3D_LOCK_COMMITTED).
 */
(function (root) {
  'use strict';

  // Get ghost engine reference (Node vs Browser)
  function getGhostEngine() {
    if (typeof module !== 'undefined' && module.exports) {
      try {
        return require('./ghost-engine.js');
      } catch (e) {
        return root.PointSnapGhostEngine || null;
      }
    }
    return root.PointSnapGhostEngine || (root.PointSnapCore && root.PointSnapCore.evaluateMagnetSnap ? root.PointSnapCore : null);
  }

  // Hook Internal State
  let activeGhostTarget = null;
  let activeTolerances = {
    snap_distance_m: 0.08,
    snap_angle_deg: 4.0,
    lock_distance_m: 0.02,
    lock_angle_deg: 2.0,
  };
  let isCurrentlySnapped = false;
  let currentResiduals = null;
  let ghostGroup = null;
  let currentActiveBox = null;
  let isDragging = false;
  let customThreeContext = null;
  let initialized = false;

  /**
   * Tìm hoặc nhận ngữ cảnh Three.js (scene, camera, canvas).
   */
  function findThreeContext() {
    if (customThreeContext) return customThreeContext;
    if (typeof window === 'undefined') return null;

    if (window.__THREE_SCENE__) {
      return { scene: window.__THREE_SCENE__, camera: window.__THREE_CAMERA__ };
    }

    const canvas = (typeof document !== 'undefined')
      ? document.querySelector('.cvat-canvas3d-perspective canvas, #cvat-canvas3d-wrapper canvas, .cvat-canvas3d-fullsize canvas')
      : null;

    if (canvas && canvas.__three_scene__) {
      return { scene: canvas.__three_scene__, camera: canvas.__three_camera__ };
    }

    const THREE_LIB = typeof THREE !== 'undefined' ? THREE : (window.THREE || null);
    if (THREE_LIB && window.cvat && window.cvat.canvas3d && window.cvat.canvas3d.scene) {
      return { scene: window.cvat.canvas3d.scene, camera: window.cvat.canvas3d.camera };
    }

    return null;
  }

  function setThreeContext(ctx) {
    customThreeContext = ctx;
  }

  /**
   * Khởi tạo hoặc cập nhật 3D dashed wireframe và mũi tên chỉ hướng cho Ghost Target.
   */
  function updateGhostMesh(target) {
    if (!target) {
      removeGhostMesh();
      return null;
    }

    const THREE_LIB = typeof THREE !== 'undefined' ? THREE : (typeof window !== 'undefined' ? window.THREE : null);
    if (!THREE_LIB) return null;

    if (!ghostGroup) {
      ghostGroup = new THREE_LIB.Group();
      ghostGroup.name = 'PointSnapGhostTarget';
    }

    // Dọn sạch các đối tượng cũ để tránh memory leak
    while (ghostGroup.children.length > 0) {
      const child = ghostGroup.children[0];
      if (child.geometry && typeof child.geometry.dispose === 'function') child.geometry.dispose();
      if (child.material) {
        if (Array.isArray(child.material)) child.material.forEach((m) => m.dispose && m.dispose());
        else if (typeof child.material.dispose === 'function') child.material.dispose();
      }
      ghostGroup.remove(child);
    }

    const dims = target.dims || [1, 1, 1];
    const [l, w, h] = dims;

    // Dựng khung hộp nét đứt
    const boxGeom = new THREE_LIB.BoxGeometry(l, w, h);
    const edgesGeom = new THREE_LIB.EdgesGeometry(boxGeom);
    const mat = new THREE_LIB.LineDashedMaterial({
      color: 0xf59e0b, // Amber mặc định khi chưa khóa
      dashSize: 0.15,
      gapSize: 0.08,
      depthTest: false,
      transparent: true,
      opacity: 0.85,
    });

    const wireframe = new THREE_LIB.LineSegments(edgesGeom, mat);
    if (typeof wireframe.computeLineDistances === 'function') {
      wireframe.computeLineDistances();
    }
    ghostGroup.add(wireframe);

    // Mũi tên đỏ chỉ hướng +X (forward)
    const dir = new THREE_LIB.Vector3(1, 0, 0);
    const origin = new THREE_LIB.Vector3(0, 0, 0);
    const arrowLen = Math.max(0.5, l / 2.0 + 0.35);
    const arrow = new THREE_LIB.ArrowHelper(dir, origin, arrowLen, 0xef4444, 0.25, 0.15);
    ghostGroup.add(arrow);

    // Định vị khung trong không gian 3D
    const c = target.center || [0, 0, 0];
    ghostGroup.position.set(c[0], c[1], c[2]);
    ghostGroup.rotation.set(0, 0, target.yaw || 0);

    // Thêm vào scene Three.js nếu chưa có
    const ctx = findThreeContext();
    if (ctx && ctx.scene && ghostGroup.parent !== ctx.scene) {
      ctx.scene.add(ghostGroup);
    }

    return ghostGroup;
  }

  /**
   * Gỡ bỏ khung gióng khỏi Three.js scene.
   */
  function removeGhostMesh() {
    if (ghostGroup) {
      if (ghostGroup.parent) {
        ghostGroup.parent.remove(ghostGroup);
      }
      while (ghostGroup.children.length > 0) {
        const child = ghostGroup.children[0];
        if (child.geometry && typeof child.geometry.dispose === 'function') child.geometry.dispose();
        if (child.material) {
          if (Array.isArray(child.material)) child.material.forEach((m) => m.dispose && m.dispose());
          else if (typeof child.material.dispose === 'function') child.material.dispose();
        }
        ghostGroup.remove(child);
      }
      ghostGroup = null;
    }
  }

  /**
   * Đổi màu sắc hiển thị của khung gióng (Amber -> Blue Snap -> Emerald Green Lock).
   */
  function setMeshHighlight(statusText) {
    if (!ghostGroup) return;
    const wireframe = ghostGroup.children.find(
      (c) => c.isLineSegments || c.type === 'LineSegments'
    );
    if (wireframe && wireframe.material && wireframe.material.color) {
      if (statusText === 'GREEN_LOCK') {
        wireframe.material.color.setHex(0x10b981); // Emerald green
      } else if (statusText === 'SNAPPED') {
        wireframe.material.color.setHex(0x3b82f6); // Blue snap
      } else {
        wireframe.material.color.setHex(0xf59e0b); // Amber off-target
      }
    }
  }

  /**
   * Phát đi tín hiệu CustomEvent và window.postMessage.
   */
  function dispatchEventBridge(type, detail) {
    if (typeof window !== 'undefined') {
      try {
        window.dispatchEvent(new CustomEvent(type, { detail }));
      } catch (e) {}
      try {
        window.postMessage({ type, detail }, '*');
      } catch (e) {}
    }
  }

  function dispatchTelemetry(data) {
    dispatchEventBridge('POINTSNAP_3D_TELEMETRY', data);
  }

  function dispatchLockCommitted(data) {
    dispatchEventBridge('POINTSNAP_3D_LOCK_COMMITTED', data);
  }

  function dispatchQuickLevelApplied(data) {
    dispatchEventBridge('POINTSNAP_QUICK_LEVEL_APPLIED', data);
  }

  /**
   * Thiết lập Ghost Target mới.
   */
  function setGhostTarget(target, tolerances = null) {
    activeGhostTarget = target ? { ...target } : null;
    if (tolerances) activeTolerances = { ...tolerances };
    isCurrentlySnapped = false;
    currentResiduals = null;

    updateGhostMesh(activeGhostTarget);

    if (activeGhostTarget && currentActiveBox) {
      const engine = getGhostEngine();
      if (engine) {
        currentResiduals = engine.computeSpatialResiduals(currentActiveBox, activeGhostTarget);
        setMeshHighlight(currentResiduals.statusText);
        dispatchTelemetry({
          residuals: currentResiduals,
          box: currentActiveBox,
          isSnapped: currentResiduals.isSnapped,
          isGreenLocked: currentResiduals.isGreenLocked,
          statusText: currentResiduals.statusText,
          timestamp: Date.now(),
        });
      }
    }
  }

  /**
   * Xóa bỏ Ghost Target.
   */
  function clearGhostTarget() {
    activeGhostTarget = null;
    isCurrentlySnapped = false;
    currentResiduals = null;
    removeGhostMesh();
  }

  function getGhostTarget() {
    return activeGhostTarget;
  }

  function getGhostMesh() {
    return ghostGroup;
  }

  function setActiveBox(box) {
    currentActiveBox = box ? { ...box } : null;
  }

  function getActiveBox() {
    return currentActiveBox;
  }

  function getActiveTelemetry() {
    return currentResiduals;
  }

  /**
   * Xử lý khi chuột kéo box: tính toán Magnet Snap và phát telemetry trực tiếp.
   */
  function handlePointerMove(event, boxOverride = null) {
    const box = boxOverride || currentActiveBox;
    if (!box || !activeGhostTarget) return box;

    const engine = getGhostEngine();
    if (!engine) return box;

    isDragging = true;
    const snapResult = engine.evaluateMagnetSnap(box, activeGhostTarget, isCurrentlySnapped);
    isCurrentlySnapped = snapResult.snapped;
    currentResiduals = snapResult.residuals;

    if (snapResult.residuals) {
      setMeshHighlight(snapResult.residuals.statusText);
    }

    currentActiveBox = snapResult.box;

    dispatchTelemetry({
      residuals: snapResult.residuals,
      box: snapResult.box,
      isSnapped: snapResult.snapped,
      translationSnapped: snapResult.translationSnapped,
      rotationSnapped: snapResult.rotationSnapped,
      isGreenLocked: snapResult.residuals ? snapResult.residuals.isGreenLocked : false,
      statusText: snapResult.residuals ? snapResult.residuals.statusText : 'OFF_TARGET',
      timestamp: Date.now(),
    });

    return snapResult.box;
  }

  /**
   * Xử lý khi nhả chuột: nếu đang ở Green Lock thì chốt vị trí chuẩn.
   */
  function handlePointerUp(event, boxOverride = null) {
    isDragging = false;
    const box = boxOverride || currentActiveBox;
    if (!activeGhostTarget || !currentResiduals) return;

    if (currentResiduals.isGreenLocked) {
      dispatchLockCommitted({
        box,
        target: activeGhostTarget,
        residuals: currentResiduals,
        timestamp: Date.now(),
      });
    }
  }

  /**
   * Kiểm tra người dùng có đang gõ văn bản trong input / textarea không.
   */
  function isInputFocused(event) {
    const el = event ? event.target : (typeof document !== 'undefined' ? document.activeElement : null);
    if (!el) return false;
    const tag = (el.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || el.isContentEditable) {
      return true;
    }
    return false;
  }

  /**
   * Xử lý phím tắt Cân bằng nhanh (Quick Leveling Hotkey `KeyL` hoặc `Shift + KeyS`).
   */
  function handleHotkey(event, boxOverride = null) {
    if (isInputFocused(event)) return false;

    const code = event.code || '';
    const key = event.key || '';
    const isL = code === 'KeyL' || key === 'l' || key === 'L';
    const isShiftS = (code === 'KeyS' || key === 's' || key === 'S') && event.shiftKey;

    if (!isL && !isShiftS) return false;

    const box = boxOverride || currentActiveBox;
    if (!box) return false;

    const engine = getGhostEngine();
    if (!engine) return false;

    const leveledBox = engine.performQuickLeveling(box, activeGhostTarget);
    currentActiveBox = leveledBox;

    if (event.preventDefault && typeof event.preventDefault === 'function') event.preventDefault();
    if (event.stopPropagation && typeof event.stopPropagation === 'function') event.stopPropagation();

    if (activeGhostTarget) {
      const residuals = engine.computeSpatialResiduals(leveledBox, activeGhostTarget);
      currentResiduals = residuals;
      setMeshHighlight(residuals.statusText);
      dispatchTelemetry({
        residuals,
        box: leveledBox,
        isSnapped: residuals.isSnapped,
        isGreenLocked: residuals.isGreenLocked,
        statusText: residuals.statusText,
        timestamp: Date.now(),
      });
    }

    dispatchQuickLevelApplied({
      box: leveledBox,
      hotkey: isL ? 'KeyL' : 'Shift+KeyS',
      timestamp: Date.now(),
    });

    return true;
  }

  /**
   * Thiết lập các event listener toàn cục trên window.
   */
  function init3DHook(options = {}) {
    if (initialized) return;
    initialized = true;

    if (options.threeContext) setThreeContext(options.threeContext);

    if (typeof window !== 'undefined') {
      // Nhận chỉ thị từ content.js qua CustomEvent & postMessage
      window.addEventListener('POINTSNAP_SET_GHOST_TARGET', (e) => {
        if (e.detail && e.detail.ghostTarget) {
          setGhostTarget(e.detail.ghostTarget, e.detail.tolerances);
        }
      });

      window.addEventListener('POINTSNAP_CLEAR_GHOST_TARGET', () => {
        clearGhostTarget();
      });

      window.addEventListener('message', (e) => {
        if (!e.data || typeof e.data !== 'object') return;
        if (e.data.type === 'POINTSNAP_SET_GHOST_TARGET' && e.data.detail) {
          setGhostTarget(e.data.detail.ghostTarget, e.data.detail.tolerances);
        } else if (e.data.type === 'POINTSNAP_CLEAR_GHOST_TARGET') {
          clearGhostTarget();
        }
      });

      // Lắng nghe phím tắt KeyL và Shift+KeyS
      window.addEventListener('keydown', (e) => {
        handleHotkey(e);
      }, true);

      // Lắng nghe thao tác chuột trên canvas 3D
      const canvasWrapper = document.querySelector('#cvat-canvas3d-wrapper, .cvat-canvas3d-perspective, .cvat-canvas3d-fullsize');
      if (canvasWrapper) {
        canvasWrapper.addEventListener('pointermove', (e) => {
          if (isDragging) handlePointerMove(e);
        });
        canvasWrapper.addEventListener('pointerdown', () => {
          isDragging = true;
        });
        canvasWrapper.addEventListener('pointerup', (e) => {
          handlePointerUp(e);
        });
      }
    }
  }

  const api = {
    init3DHook,
    setThreeContext,
    setGhostTarget,
    clearGhostTarget,
    getGhostTarget,
    getGhostMesh,
    setActiveBox,
    getActiveBox,
    getActiveTelemetry,
    handlePointerMove,
    handlePointerUp,
    handleHotkey,
    isInputFocused,
    updateGhostMesh,
    removeGhostMesh,
    setMeshHighlight,
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  } else {
    root.PointSnap3DHook = api;
    // Auto-init in browser MAIN world
    if (typeof window !== 'undefined') {
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => init3DHook());
      } else {
        init3DHook();
      }
    }
  }
})(typeof globalThis !== 'undefined' ? globalThis : this);
