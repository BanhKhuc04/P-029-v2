/*
 * PointSnap 3D Live Telemetry HUD (CVAT Viewport Glassmorphic Component)
 * Milestone M3: Real-time telemetry, 60 FPS throttled screen projection, and Green Target Lock confirmation.
 * Module runs in both browser (MAIN/ISOLATED world) and Node.js (module.exports) for unit testing.
 *
 * Responsibilities:
 * 1. Mounts glassmorphic HUD DOM overlay on CVAT 3D canvas viewport (#cvat-canvas3d-wrapper, .cvat-canvas3d-perspective).
 * 2. 60 FPS update loop throttled via requestAnimationFrame (< 16ms latency).
 * 3. Screen projection of 3D box top coordinates using camera.project() with viewport bounds clamping.
 * 4. Real-time telemetry: delta z (cm), delta yaw (deg), 3D distance (cm), roll/pitch (deg), clearances.
 * 5. Visual state transitions: Amber (OFF_TARGET) -> Blue Snap (SNAPPED) -> Emerald Green (GREEN_LOCK).
 * 6. Lock committed confirmation feedback and smooth auto-hide on release.
 */
(function (root) {
  'use strict';

  // HUD Internal State
  let hudElement = null;
  let isVisible = false;
  let rafId = null;
  let latestTelemetry = null;
  let cameraRef = null;
  let customContainer = null;
  let initialized = false;

  // Formatting helpers
  function formatSigned(num, decimals = 1, unit = '') {
    if (!Number.isFinite(num)) return '--';
    const sign = num > 0 ? '+' : '';
    return `${sign}${num.toFixed(decimals)}${unit}`;
  }

  function formatAbs(num, decimals = 1, unit = '') {
    if (!Number.isFinite(num)) return '--';
    return `${Math.abs(num).toFixed(decimals)}${unit}`;
  }

  /**
   * Tạo cấu trúc DOM của Telemetry HUD.
   */
  function createHUD() {
    if (typeof document === 'undefined') return null;
    let hud = document.getElementById('pointsnap-telemetry-hud');
    if (hud) return hud;

    hud = document.createElement('div');
    hud.id = 'pointsnap-telemetry-hud';
    hud.className = 'ps-telemetry-hud off-target';
    hud.style.display = 'none';

    hud.innerHTML = `
      <div class="ps-hud-head">
        <span class="ps-hud-title">3D Telemetry</span>
        <span class="ps-hud-badge off-target" id="ps-hud-badge-status">⚡ ĐANG CĂN CHỈNH</span>
      </div>
      <div class="ps-hud-grid">
        <div class="ps-hud-metric">
          <span class="ps-hud-metric-lbl">Δz (Cao độ đáy)</span>
          <span class="ps-hud-metric-val" id="ps-hud-val-dz">0.0 cm</span>
        </div>
        <div class="ps-hud-metric">
          <span class="ps-hud-metric-lbl">Δyaw (Góc quay)</span>
          <span class="ps-hud-metric-val" id="ps-hud-val-dyaw">0.0°</span>
        </div>
        <div class="ps-hud-metric">
          <span class="ps-hud-metric-lbl">Khoảng cách 3D</span>
          <span class="ps-hud-metric-val" id="ps-hud-val-dist">0.0 cm</span>
        </div>
        <div class="ps-hud-metric">
          <span class="ps-hud-metric-lbl">Nghiêng (Roll/Pitch)</span>
          <span class="ps-hud-metric-val" id="ps-hud-val-tilt">0.0° / 0.0°</span>
        </div>
      </div>
      <div class="ps-hud-clearances" id="ps-hud-clearances" style="display: none;">
        <span>F: <b id="ps-hud-cl-f">0cm</b></span>
        <span>B: <b id="ps-hud-cl-b">0cm</b></span>
        <span>L: <b id="ps-hud-cl-l">0cm</b></span>
        <span>R: <b id="ps-hud-cl-r">0cm</b></span>
      </div>
      <div class="ps-hud-footer">
        <span><kbd>L</kbd> Cân bằng</span>
        <span><kbd>Shift+S</kbd> Sàn</span>
        <span id="ps-hud-footer-hint">Kéo về khung xanh</span>
      </div>
    `;

    return hud;
  }

  function injectHUDStyles() {
    if (typeof document === 'undefined') return;
    if (document.getElementById('pointsnap-hud-styles')) return;
    const style = document.createElement('style');
    style.id = 'pointsnap-hud-styles';
    style.textContent = `
      .ps-telemetry-hud {
        position: absolute; z-index: 2147483001; pointer-events: none; width: 250px;
        background: rgba(15, 23, 42, 0.88); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.18); border-radius: 8px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
        font-family: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        color: #F8FAFC; padding: 10px 12px; display: flex; flex-direction: column; gap: 8px;
        transition: border-color 0.15s ease, box-shadow 0.15s ease; user-select: none;
      }
      .ps-telemetry-hud.off-target { border-color: #f59e0b; box-shadow: 0 0 12px rgba(245, 158, 11, 0.35); }
      .ps-telemetry-hud.snapped { border-color: #3b82f6; box-shadow: 0 0 16px rgba(59, 130, 246, 0.5); }
      .ps-telemetry-hud.green-lock {
        border-color: #10b981; box-shadow: 0 0 24px rgba(16, 185, 129, 0.8), inset 0 0 12px rgba(16, 185, 129, 0.2);
        animation: ps-pulse-glow 1.5s infinite alternate ease-in-out;
      }
      @keyframes ps-pulse-glow {
        0% { box-shadow: 0 0 16px rgba(16, 185, 129, 0.6); }
        100% { box-shadow: 0 0 28px rgba(16, 185, 129, 0.95), inset 0 0 14px rgba(16, 185, 129, 0.3); }
      }
      .ps-hud-head { display: flex; align-items: center; justify-content: space-between; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
      .ps-hud-badge { display: inline-flex; align-items: center; gap: 4px; padding: 2px 7px; border-radius: 12px; font-size: 10px; font-weight: 700; }
      .ps-hud-badge.off-target { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4); }
      .ps-hud-badge.snapped { background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.4); }
      .ps-hud-badge.green-lock { background: rgba(16, 185, 129, 0.25); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.6); }
      .ps-hud-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px; }
      .ps-hud-metric { background: rgba(255, 255, 255, 0.06); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 4px; padding: 4px 6px; display: flex; flex-direction: column; }
      .ps-hud-metric-lbl { font-size: 9px; font-weight: 500; color: #94A3B8; text-transform: uppercase; }
      .ps-hud-metric-val { font-family: 'IBM Plex Mono', Consolas, monospace; font-size: 12px; font-weight: 600; color: #F1F5F9; }
      .ps-hud-metric-val.perfect { color: #34d399; }
      .ps-hud-metric-val.warn { color: #fbbf24; }
      .ps-hud-clearances { font-size: 10px; color: #94A3B8; font-family: 'IBM Plex Mono', Consolas, monospace; display: flex; justify-content: space-between; background: rgba(0, 0, 0, 0.2); padding: 3px 6px; border-radius: 4px; }
      .ps-hud-footer { display: flex; align-items: center; justify-content: space-between; font-size: 10px; color: #64748B; border-top: 1px solid rgba(255, 255, 255, 0.08); padding-top: 5px; }
      .ps-hud-footer kbd { background: rgba(255, 255, 255, 0.1); padding: 1px 4px; border-radius: 3px; color: #CBD5E1; font-family: 'IBM Plex Mono', monospace; }
    `;
    document.head.appendChild(style);
  }

  /**
   * Gắn HUD vào container 3D canvas của CVAT.
   */
  function isJobPage() {
    return typeof window !== 'undefined' && /^\/tasks\/\d+\/jobs\/\d+\/?$/.test(window.location?.pathname || '');
  }

  function mountHUD(container = null) {
    if (typeof document === 'undefined') return null;
    if (!isJobPage()) { hideHUD(); return null; }
    const targetContainer = container || customContainer ||
      document.querySelector('#cvat-canvas3d-wrapper, .cvat-canvas3d-perspective, .cvat-canvas3d-fullsize') || document.body;
    if (!targetContainer) return null;

    injectHUDStyles();

    if (!hudElement) {
      hudElement = createHUD();
    }
    if (hudElement && hudElement.parentElement !== targetContainer) {
      targetContainer.appendChild(hudElement);
    }
    return hudElement;
  }

  /**
   * Chiếu toạ độ 3D sang toạ độ màn hình 2D bằng camera Three.js.
   */
  function project3DToScreen(coords, camera, container) {
    if (!coords || !camera || typeof camera.project !== 'function' || !container) {
      return null;
    }
    const THREE_LIB = (typeof THREE !== 'undefined') ? THREE : (typeof window !== 'undefined' ? window.THREE : null);
    if (!THREE_LIB || !THREE_LIB.Vector3) return null;

    const vec = new THREE_LIB.Vector3(coords[0], coords[1], coords[2]);
    vec.project(camera);

    // Điểm nằm sau lưng camera
    if (vec.z > 1.0) return null;

    const rect = container.getBoundingClientRect ? container.getBoundingClientRect() : { width: 800, height: 600, left: 0, top: 0 };
    const width = rect.width || 800;
    const height = rect.height || 600;

    const screenX = (vec.x * 0.5 + 0.5) * width;
    const screenY = (-(vec.y * 0.5) + 0.5) * height;

    return { x: screenX, y: screenY };
  }

  /**
   * Giới hạn toạ độ HUD trong khung nhìn viewport tránh tràn viền.
   */
  function clampHUDPosition(x, y, container, hudWidth = 250, hudHeight = 160) {
    const rect = container && container.getBoundingClientRect ? container.getBoundingClientRect() : { width: 800, height: 600 };
    const maxW = (rect.width || 800) - hudWidth - 16;
    const maxH = (rect.height || 600) - hudHeight - 16;

    const clampedX = Math.max(16, Math.min(maxW, x + 20));
    const clampedY = Math.max(16, Math.min(maxH, y - hudHeight - 10));

    return { x: clampedX, y: clampedY };
  }

  /**
   * Render dữ liệu telemetry trực tiếp lên DOM.
   */
  function renderTelemetry(data) {
    if (!isJobPage()) { hideHUD(); return; }
    if (!hudElement) {
      mountHUD();
    }
    if (!hudElement || !data) return;

    const res = data.residuals;
    if (!res) return;

    const statusText = res.statusText || (res.isGreenLocked ? 'GREEN_LOCK' : (res.isSnapped ? 'SNAPPED' : 'OFF_TARGET'));
    const isGreen = statusText === 'GREEN_LOCK';
    const isSnap = statusText === 'SNAPPED';

    // Cập nhật class trạng thái
    hudElement.className = `ps-telemetry-hud ${isGreen ? 'green-lock' : (isSnap ? 'snapped' : 'off-target')}`;

    // Cập nhật badge
    const badge = hudElement.querySelector('#ps-hud-badge-status');
    if (badge) {
      if (isGreen) {
        badge.className = 'ps-hud-badge green-lock';
        badge.textContent = '✓ VỊ TRÍ HOÀN HẢO';
      } else if (isSnap) {
        badge.className = 'ps-hud-badge snapped';
        badge.textContent = '🧲 ĐANG HÚT NAM CHÂM';
      } else {
        badge.className = 'ps-hud-badge off-target';
        badge.textContent = '⚡ ĐANG CĂN CHỈNH';
      }
    }

    // Cập nhật chỉ số cao độ đáy (delta z)
    const elDz = hudElement.querySelector('#ps-hud-val-dz');
    if (elDz) {
      const dzVal = res.deltaZ_cm != null ? res.deltaZ_cm : 0.0;
      elDz.textContent = formatSigned(dzVal, 1, ' cm');
      elDz.className = `ps-hud-metric-val ${Math.abs(dzVal) <= 2.0 ? 'perfect' : (Math.abs(dzVal) <= 8.0 ? 'warn' : '')}`;
    }

    // Cập nhật độ lệch góc xoay (delta yaw)
    const elDyaw = hudElement.querySelector('#ps-hud-val-dyaw');
    if (elDyaw) {
      const dyawVal = res.deltaYaw_deg != null ? res.deltaYaw_deg : 0.0;
      elDyaw.textContent = formatSigned(dyawVal, 1, '°');
      elDyaw.className = `ps-hud-metric-val ${Math.abs(dyawVal) <= 2.0 ? 'perfect' : (Math.abs(dyawVal) <= 4.0 ? 'warn' : '')}`;
    }

    // Cập nhật khoảng cách 3D
    const elDist = hudElement.querySelector('#ps-hud-val-dist');
    if (elDist) {
      const distVal = res.dist3D_cm != null ? res.dist3D_cm : 0.0;
      elDist.textContent = `${distVal.toFixed(1)} cm`;
      elDist.className = `ps-hud-metric-val ${distVal <= 2.0 ? 'perfect' : (distVal <= 8.0 ? 'warn' : '')}`;
    }

    // Cập nhật góc nghiêng roll/pitch
    const elTilt = hudElement.querySelector('#ps-hud-val-tilt');
    if (elTilt) {
      const rVal = res.roll_deg != null ? res.roll_deg : 0.0;
      const pVal = res.pitch_deg != null ? res.pitch_deg : 0.0;
      elTilt.textContent = `R: ${rVal.toFixed(1)}° | P: ${pVal.toFixed(1)}°`;
      elTilt.className = `ps-hud-metric-val ${(rVal <= 0.5 && pVal <= 0.5) ? 'perfect' : ''}`;
    }

    // Cập nhật khoảng hở 4 mặt LiDAR
    const elClearances = hudElement.querySelector('#ps-hud-clearances');
    if (elClearances) {
      if (res.clearance_front_cm != null && (res.clearance_front_cm !== 0 || res.clearance_back_cm !== 0)) {
        elClearances.style.display = 'flex';
        const clf = hudElement.querySelector('#ps-hud-cl-f');
        const clb = hudElement.querySelector('#ps-hud-cl-b');
        const cll = hudElement.querySelector('#ps-hud-cl-l');
        const clr = hudElement.querySelector('#ps-hud-cl-r');
        if (clf) clf.textContent = `${res.clearance_front_cm.toFixed(0)}cm`;
        if (clb) clb.textContent = `${res.clearance_back_cm.toFixed(0)}cm`;
        if (cll) cll.textContent = `${res.clearance_left_cm.toFixed(0)}cm`;
        if (clr) clr.textContent = `${res.clearance_right_cm.toFixed(0)}cm`;
      } else {
        elClearances.style.display = 'none';
      }
    }

    // Cập nhật gợi ý chân trang
    const elHint = hudElement.querySelector('#ps-hud-footer-hint');
    if (elHint) {
      if (isGreen) {
        elHint.textContent = '✓ Nhả chuột để chốt';
        elHint.style.color = '#34d399';
        elHint.style.fontWeight = 'bold';
      } else {
        elHint.textContent = 'Kéo về khung xanh';
        elHint.style.color = '#64748B';
        elHint.style.fontWeight = 'normal';
      }
    }

    // Định vị toạ độ HUD
    const container = hudElement.parentElement;
    if (data.box && data.box.center && cameraRef && container) {
      const c = data.box.center;
      const h = (data.box.dims && data.box.dims[2]) || 1.5;
      const screenPos = project3DToScreen([c[0], c[1], c[2] + h / 2.0], cameraRef, container);
      if (screenPos) {
        const clamped = clampHUDPosition(screenPos.x, screenPos.y, container);
        hudElement.style.left = `${clamped.x}px`;
        hudElement.style.top = `${clamped.y}px`;
        hudElement.style.right = 'auto';
      } else {
        hudElement.style.top = '16px';
        hudElement.style.right = '16px';
        hudElement.style.left = 'auto';
      }
    } else {
      hudElement.style.top = '16px';
      hudElement.style.right = '16px';
      hudElement.style.left = 'auto';
    }

    if (!isVisible) {
      hudElement.style.display = 'flex';
      isVisible = true;
    }
    if (canvasUnavailable) showUnavailable();
  }

  /**
   * Cập nhật Telemetry qua requestAnimationFrame (< 16ms, 60 FPS).
   */
  function updateTelemetry(data) {
    if (!isJobPage() || (!hasGhostTarget && !canvasUnavailable)) return;
    latestTelemetry = data;
    if (typeof requestAnimationFrame === 'function') {
      if (rafId == null) {
        rafId = requestAnimationFrame(() => {
          rafId = null;
          renderTelemetry(latestTelemetry);
        });
      }
    } else {
      renderTelemetry(latestTelemetry);
    }
  }

  /**
   * Ẩn HUD khi kết thúc hoặc hủy ghost target.
   */
  function hideHUD() {
    if (hudElement) {
      hudElement.style.display = 'none';
      isVisible = false;
    }
    if (rafId != null && typeof cancelAnimationFrame === 'function') {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
  }

  /**
   * Xử lý hiệu ứng xác nhận khi người dùng khóa thành công (Green Lock Committed).
   */
  function onLockCommitted(data) {
    if (!isJobPage()) { hideHUD(); return; }
    if (!hudElement) return;
    hudElement.className = 'ps-telemetry-hud green-lock committed';
    const badge = hudElement.querySelector('#ps-hud-badge-status');
    if (badge) {
      badge.textContent = '✓ ĐÃ KHÓA HOÀN HẢO';
      badge.className = 'ps-hud-badge green-lock';
    }
    const elHint = hudElement.querySelector('#ps-hud-footer-hint');
    if (elHint) {
      elHint.textContent = '✓ Đã cập nhật nhãn CVAT';
    }
    setTimeout(() => {
      hideHUD();
    }, 1500);
  }

  /**
   * Khởi tạo HUD và lắng nghe các tín hiệu telemetry từ 3D Hook.
   */
  let canvasUnavailable = false;
  let hasGhostTarget = false;

  function showUnavailable() {
    if (!isJobPage()) { hideHUD(); return; }
    canvasUnavailable = true;
    if (!hudElement) mountHUD();
    if (!hudElement) return;
    const hint = hudElement.querySelector('#ps-hud-footer-hint');
    if (hint) hint.textContent = 'Chưa kết nối được canvas 3D của CVAT';
    const badge = hudElement.querySelector('#ps-hud-badge-status');
    if (badge) {
      badge.textContent = 'CHƯA KẾT NỐI CANVAS';
      badge.className = 'ps-hud-badge off-target';
    }
    hudElement.className = 'ps-telemetry-hud off-target';
    hudElement.style.display = 'flex';
    isVisible = true;
  }

  function initTelemetryHUD(options = {}) {
    if (initialized) return;
    initialized = true;

    if (options.container) customContainer = options.container;
    if (options.camera) cameraRef = options.camera;

    if (typeof window !== 'undefined') {
      // CVAT uses pushState for navigation; check routes without replacing its history methods.
      let pathname = window.location?.pathname;
      const checkRoute = () => {
        if (pathname !== window.location?.pathname) {
          pathname = window.location?.pathname;
          canvasUnavailable = false;
          hasGhostTarget = false;
          latestTelemetry = null;
          hideHUD();
        }
      };
      window.addEventListener('popstate', checkRoute);
      if (typeof window.setInterval === 'function') window.setInterval(checkRoute, 300);

      const showGhostTarget = (detail) => {
        if (!detail?.ghostTarget || !isJobPage()) return;
        hasGhostTarget = true;
        mountHUD();
        if (hudElement) {
          hudElement.style.display = 'flex';
          isVisible = true;
          if (canvasUnavailable) showUnavailable();
        }
      };
      window.addEventListener('POINTSNAP_SET_GHOST_TARGET', (e) => showGhostTarget(e.detail));
      window.addEventListener('POINTSNAP_3D_UNAVAILABLE', showUnavailable);
      const clearTarget = () => {
        hasGhostTarget = false;
        canvasUnavailable = false;
        hideHUD();
      };
      window.addEventListener('POINTSNAP_3D_TELEMETRY', (e) => {
        if (e.detail) {
          if (!cameraRef && window.__THREE_CAMERA__) cameraRef = window.__THREE_CAMERA__;
          updateTelemetry(e.detail);
        }
      });

      window.addEventListener('message', (e) => {
        if (e.source !== window) return;
        if (!e.data || typeof e.data !== 'object') return;
        if (e.data.type === 'POINTSNAP_3D_UNAVAILABLE') {
          showUnavailable();
        } else if (e.data.type === 'POINTSNAP_SET_GHOST_TARGET') {
          showGhostTarget(e.data.detail);
        } else if (e.data.type === 'POINTSNAP_3D_TELEMETRY' && e.data.detail) {
          if (!cameraRef && window.__THREE_CAMERA__) cameraRef = window.__THREE_CAMERA__;
          updateTelemetry(e.data.detail);
        } else if (e.data.type === 'POINTSNAP_CLEAR_GHOST_TARGET') {
          clearTarget();
        } else if (e.data.type === 'POINTSNAP_3D_LOCK_COMMITTED' && e.data.detail) {
          if (hasGhostTarget || canvasUnavailable) onLockCommitted(e.data.detail);
        }
      });

      window.addEventListener('POINTSNAP_CLEAR_GHOST_TARGET', () => {
        clearTarget();
      });

      window.addEventListener('POINTSNAP_3D_LOCK_COMMITTED', (e) => {
        if (hasGhostTarget || canvasUnavailable) onLockCommitted(e.detail);
      });
    }
  }

  const api = {
    initTelemetryHUD,
    mountHUD,
    createHUD,
    updateTelemetry,
    renderTelemetry,
    hideHUD,
    onLockCommitted,
    project3DToScreen,
    clampHUDPosition,
    formatSigned,
    formatAbs,
    getHUDElement: () => hudElement,
    isVisible: () => isVisible,
    setCamera: (cam) => { cameraRef = cam; },
    setContainer: (ctn) => { customContainer = ctn; },
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  } else {
    root.PointSnapTelemetryHUD = api;
    if (typeof window !== 'undefined') {
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => initTelemetryHUD());
      } else {
        initTelemetryHUD();
      }
    }
  }
})(typeof globalThis !== 'undefined' ? globalThis : this);
