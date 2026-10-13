/**
 * PointSnap 3D — Trình điều khiển giao diện Doanh nghiệp (Enterprise UI - A13)
 * Giữ nguyên 100% backend API hiện hữu, đáp ứng toàn diện thiết kế Brand & Main .dc.html
 */

(function () {
  'use strict';

  // --- Từ điển hướng dẫn sửa lỗi cố định theo luật (A13) ---
  const RULE_FIX_TIPS = {
    'floating': 'Hạ đáy box cho chạm mặt đường, đối chiếu ảnh camera trước và các frame lân cận của track.',
    'floating.no_evidence': 'Không cần sửa. Nếu nghi ngờ, kiểm tra bằng mắt trên ảnh camera.',
    'size.class_range': 'Kiểm tra xem đối tượng có bị gán nhầm class không (ví dụ nhầm car với truck/bus); nếu đúng class thì điều chỉnh kích thước box cho vừa khít vật.',
    'size.in_track': 'Kiểm tra kích thước box so với các frame khác của cùng track; điều chỉnh lại box bất thường.',
    'track.jump': 'Kéo box về đúng vị trí vật ở frame này, hoặc kiểm tra có bị gán nhầm sang vật khác không.',
    'track.split_id': 'Kiểm tra hai track nối tiếp nhau; nếu là cùng một đối tượng thì hợp nhất ID track.',
    'track.long_interpolation': 'Chèn thêm keyframe vào giữa khoảng nội suy dài để box bám sát chuyển động của vật.',
    'heading.flip': 'Xoay box về cùng hướng với các keyframe lân cận của track; bật Cuboid orientation và cho mũi tên đỏ chỉ đầu vật.',
    'heading.motion': 'Xoay box cho mũi tên đỏ (Cuboid orientation) trùng hướng vật đang chạy (spec 4.2). Xe lùi thật thì bỏ qua.',
    'heading.points': 'Xoay box cho các cạnh song song với thân vật trên point cloud (nhìn từ Top view).',
    'fit.empty': 'Xóa box nếu không có vật; vật bị che khuất tạm thời thì đánh dấu occluded thay vì để box rỗng.',
    'fit.outside': 'Nới hoặc dời box cho bao trọn các điểm của vật (spec 4.2), đối chiếu Top / Side / Front view.',
    'fit.loose': 'Kéo mặt box về sát các điểm của vật ở phía được nhìn rõ, không để dư khoảng trống.',
    'fit.overlap': 'Kiểm tra hai box có cùng là một vật không: vẽ trùng thì xóa box thừa; hai vật sát nhau thì thu box cho khỏi lấn.',
    'track.reuse_id': 'Vật chỉ bị che tạm thời (≤ 6 frame) thì bỏ outside và bật occluded; vắng lâu hơn thì tách phần sau thành track mới (spec 4.4.3–4.4.5).',
    'attr.height': 'Xem vật trên point cloud / ảnh: sửa thuộc tính (tư thế, nhóm tuổi, có người lái) hoặc chiều cao box cho khớp.',
    'spec.inside': 'Spec 4.3B: không gán người ngồi trong xe — xóa box người (người đứng trên nóc / thùng xe thì giữ).',
    'spec.rider_double': 'Spec 4.3C: người lái nằm trong box xe hai bánh — xóa box người; người đã xuống xe thì đổi xe sang without_rider.',
    'lidar.missing': 'Mở point cloud tại vị trí trong mục (tâm cụm từng frame): vật thật đang di chuyển mà chưa gán thì vẽ box và track mới (spec 4.2).',
    'attr.rider_state': 'Spec 4.3C: lên xe thì đổi sang with_rider, xuống xe thì đổi sang without_rider (người xuống thành track Pedestrian mới).',
    'cam.sparse': 'Spec 4.2: không gán vật quá ít điểm. Xem lại point cloud / ảnh các frame khác: không suy luận được vật thì xóa box.',
    'track.id_swap': 'Hai vật bị nối nhầm ID: tách lại từ frame bị đổi, mỗi đoạn về đúng track của vật (đối chiếu quỹ đạo, ảnh camera).',
    'track.occluded_long': 'Che khuất quá 6 frame: kết thúc track (Switch outside) và tạo track mới khi vật xuất hiện lại, trừ khi chắc chắn là cùng vật (spec 4.4.5).',
    'attr.missing': 'Chọn giá trị cho thuộc tính bắt buộc; không chắc thì chọn other (spec 3.1.3).',
    'attr.invalid': 'Chọn lại giá trị thuộc tính theo danh sách của guideline dự án.',
    'track.static_shift': 'Vật đứng yên: kéo box về trùng vị trí ở các keyframe khác của track (hoặc copy box từ keyframe đúng).',
    'heading.static': 'Vật đứng yên: xoay box về cùng hướng với các keyframe khác của track.',
    'cam.mismatch': 'Mở ảnh camera của frame, so khung box với vật: dời / chỉnh kích thước box cho khớp vật (đối chiếu cả point cloud).',
    'cam.class': 'Xem vật trên ảnh camera: nhãn sai thì đổi class cho cả track; ảnh nhận nhầm (vật bị che, phản chiếu) thì bỏ qua.',
    'cam.missing': 'Mở ảnh camera và point cloud của frame: có vật thật mà chưa gán thì vẽ thêm box (spec: gán mọi vật trong vùng quan tâm).',
    'critic.box': 'Box Critic nghi box sai: xem gợi ý sửa (dời / kích thước / xoay) trong chi tiết, đối chiếu point cloud rồi chỉnh tay.'
  };

  // Công tắc luật trong tab Guideline (khóa `rules:` của cấu hình); C1 thêm 7 luật sai hướng / box lệch.
  const RULE_IDS = ['floating', 'size_class_range', 'size_in_track', 'track_jump', 'track_split_id',
    'track_long_interpolation', 'heading_flip', 'heading_motion', 'heading_points', 'fit_empty', 'fit_outside',
    'fit_loose', 'fit_overlap', 'track_reuse_id', 'track_occluded_long', 'track_id_swap', 'attr_height', 'spec_inside', 'spec_rider_double', 'attr_rider_state', 'lidar_missing', 'cam_sparse', 'attr_missing', 'attr_invalid',
    'track_static_shift', 'heading_static', 'cam_mismatch', 'cam_class', 'cam_missing', 'critic_box'];

  let DEFAULT_FIX_TIP = 'Kiểm tra lại bounding box và nhãn trên CVAT theo hướng dẫn gán nhãn của dự án.';
  let SINK_FIX_TIP = 'Nâng đáy box lên cho chạm mặt đường, đối chiếu ảnh camera trước và các frame lân cận của track.';

  // --- Logo động khi tải (Loading.dc.html): khối hộp rơi xuống mặt đất, chấm "snap" bật ra ---
  function loaderSvg(size, opts = {}) {
    const small = size < 32;
    const ground = opts.ground
      ? '<path d="M3 38 H16 M32 38 H45" stroke="currentColor" stroke-width="3" stroke-linecap="round" opacity="0.4"></path>'
      : '';
    const ring = opts.ring
      ? '<circle class="ps-ring" cx="24" cy="38" r="4.5" stroke="var(--loader-dot)" stroke-width="1.2"></circle>'
      : '';
    const a11y = opts.label ? `role="img" aria-label="${escapeHtml(opts.label)}"` : 'aria-hidden="true"';
    return `<svg class="ps-loader" width="${size}" height="${size}" viewBox="0 0 48 48" fill="none" ${a11y}>${ground}`
      + `<g class="ps-box"><path d="M24 6 L38 14 L24 22 L10 14 Z M10 14 V30 L24 38 L38 30 V14 M24 22 V38" stroke="currentColor" stroke-width="${small ? 4 : 3}" stroke-linejoin="round" stroke-linecap="round"></path></g>`
      + `${ring}<circle class="ps-dot" cx="24" cy="38" r="${small ? 6 : 4.5}" fill="var(--loader-dot)"></circle></svg>`;
  }

  function setButtonBusy(btn, busyText) {
    if (!btn.dataset.idleText) btn.dataset.idleText = btn.textContent.trim();
    btn.disabled = true;
    btn.classList.add('is-busy');
    btn.innerHTML = `${loaderSvg(18)}<span>${escapeHtml(busyText)}</span>`;
  }

  function setButtonIdle(btn) {
    btn.disabled = false;
    btn.classList.remove('is-busy');
    if (btn.dataset.idleText) btn.textContent = btn.dataset.idleText;
  }

  function showScanLoader(show) {
    const el = document.getElementById('scan-loader');
    if (!el) return;
    el.hidden = !show;
    el.innerHTML = show ? loaderSvg(48, { ground: true, ring: true }) : '';
  }

  // Giá trị đo / ngưỡng kèm đơn vị theo luật (detectors trả mét, m/s hoặc số frame).
  function formatMeasure(f, v, signed = false) {
    if (v === null || v === undefined || v === '' || Number.isNaN(Number(v))) return '—';
    const n = Number(v);
    const fixed = (x, d) => x.toFixed(d).replace('.', ',');
    const sign = signed && n > 0 ? '+' : '';
    switch (f.rule) {
      case 'floating':
        return `${sign}${Math.round(n * 100)} cm`;
      case 'floating.no_evidence':
      case 'track.long_interpolation':
        return `${Math.round(n)} frame`;
      case 'track.jump':
        return (f.message || '').includes('m/s') ? `${fixed(n, 1)} m/s` : `${fixed(n, 2)} m`;
      case 'heading.flip':
      case 'heading.motion':
      case 'heading.points':
        return `${Math.round(n)}°`;
      case 'heading.static':
        return `${fixed(n, 1)}°`;
      case 'track.static_shift':
        return `${Math.round(n * 100)} cm`;
      case 'cam.mismatch':
      case 'cam.class':
      case 'cam.missing':
      case 'critic.box':
        return `${Math.round(n * 100)}%`;
      case 'fit.outside':
      case 'fit.overlap':
        return `${Math.round(n * 100)}%`;
      case 'fit.loose':
        return `${Math.round(n * 100)} cm`;
      case 'fit.empty':
        return `${Math.round(n)} điểm`;
      case 'track.reuse_id':
      case 'track.id_swap':
      case 'attr.height':
        return `${fixed(n, 2)} m`;
      case 'lidar.missing':
        return `${fixed(n, 1)} m/s`;
      case 'spec.inside':
      case 'spec.rider_double':
        return `${Math.round(n)} frame`;
      case 'track.occluded_long':
        return `${Math.round(n)} frame`;
      case 'attr.missing':
      case 'attr.invalid':
        return `${Math.round(n)} keyframe`;
      default:
        return `${fixed(n, 2)} m`;
    }
  }

  // --- State toàn cục ---
  const state = {
    projects: [],
    currentSlug: null,
    projectEpoch: 0,
    runLoadVersion: 0,
    currentProject: null,
    currentGuideline: null,
    currentRun: null,
    tasksList: [],
    scanPollTimer: null,
    theme: getInitialTheme(),
    currentTab: 'tab-results',

    // Bộ lọc & phân trang kết quả
    findingsPage: 1,
    findingsPerPage: 50,
    selectedFindingIndex: 0,
    selectedSeverityTab: 'all', // 'all', 'error', 'warning', 'info'

    // Liên kết với extension trên tab CVAT (A15): có tab CVAT đang mở job này không, phiên bản kết luận xem tay
    cvatLink: { online: false, jobId: null, rev: null },

    // Trạng thái dirty của Guideline
    guidelineDirty: false,
    guidelineMode: 'form', // 'form' hoặc 'yaml'
  };

  function projectScope() {
    const slug = state.currentSlug, epoch = state.projectEpoch;
    return { slug, current: () => slug === state.currentSlug && epoch === state.projectEpoch };
  }

  function errorDetail(detail, fallback) {
    if (Array.isArray(detail)) return detail.map(e => `${(e.loc || []).join('.')}: ${e.msg || 'Không hợp lệ'}`).join('; ');
    return typeof detail === 'string' ? detail : fallback;
  }

  // --- Khởi tạo Theme an toàn ---
  function getInitialTheme() {
    try {
      const urlParams = new URLSearchParams(window.location.search);
      const paramTheme = urlParams.get('theme');
      if (paramTheme === 'light' || paramTheme === 'dark') return paramTheme;
    } catch (_) {}

    try {
      const saved = localStorage.getItem('pointsnap_theme');
      if (saved === 'light' || saved === 'dark') return saved;
    } catch (_) {}
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark';
    }
    return 'light';
  }

  function applyTheme(theme) {
    state.theme = theme;
    document.documentElement.setAttribute('data-theme', theme);
    try {
      localStorage.setItem('pointsnap_theme', theme);
    } catch (_) {}

    const btnLight = document.getElementById('theme-btn-light');
    const btnDark = document.getElementById('theme-btn-dark');
    if (btnLight && btnDark) {
      btnLight.setAttribute('aria-pressed', theme === 'light' ? 'true' : 'false');
      btnDark.setAttribute('aria-pressed', theme === 'dark' ? 'true' : 'false');
    }
  }

  // --- Toast Notifications ---
  function showToast(message, type = 'info', duration = 3500) {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(8px)';
      setTimeout(() => toast.remove(), 250);
    }, duration);
  }

  // --- Modals Helper ---
  function openModal(id) {
    const m = document.getElementById(id);
    if (m) {
      m.returnFocus = document.activeElement?.closest('#project-dropdown-menu') ? document.getElementById('btn-project-dropdown') : document.activeElement;
      m.classList.add('open');
      document.getElementById('app-container').inert = true;
      m.querySelector('input, button, textarea, select')?.focus();
    }
  }

  function closeModal(id) {
    const m = document.getElementById(id);
    if (m) {
      m.classList.remove('open');
      document.getElementById('app-container').inert = false;
      m.returnFocus?.focus();
    }
  }

  // --- Tải Rule Catalog đồng bộ từ backend PointSnap API ---
  async function loadRulesCatalog() {
    try {
      const res = await fetch('/api/rules');
      if (res.ok) {
        const data = await res.json();
        if (data.tips) Object.assign(RULE_FIX_TIPS, data.tips);
        if (data.default_fix_tip) DEFAULT_FIX_TIP = data.default_fix_tip;
        if (data.sink_fix_tip) SINK_FIX_TIP = data.sink_fix_tip;
        if (data.labels) state.ruleLabels = data.labels;
      }
    } catch (_) {
      // Offline fallback: tiếp tục chạy bình thường với các giá trị mặc định
    }
  }

  // --- Khởi động ứng dụng khi DOM sẵn sàng ---
  document.addEventListener('DOMContentLoaded', () => {
    applyTheme(state.theme);
    setupEventListeners();
    setupQuickReview();
    setupCvatLink();
    handleHashNavigation();
    loadRulesCatalog();
    setupSplash(loadProjects());
  });

  // --- Màn chào (A14): logo + nút Bắt đầu; logo động che đúng thời gian đang tải dự án ---
  function setupSplash(appReady) {
    const splash = document.getElementById('splash');
    let seen = false;
    try {
      seen = sessionStorage.getItem('pointsnap_splash_done') === '1';
    } catch (_) {}
    if (seen || !splash) return;

    splash.hidden = false;
    const appContainer = document.getElementById('app-container');
    const previousInert = appContainer.inert;
    appContainer.inert = true;
    splash.tabIndex = -1;
    const startBtn = document.getElementById('splash-start');
    const onSplashKeydown = (event) => {
      if (event.key === 'Tab') {
        event.preventDefault();
        (startBtn.hidden ? splash : startBtn).focus();
      } else if (event.key === 'Escape' && !startBtn.hidden) {
        event.preventDefault();
        startBtn.click();
      }
    };
    splash.addEventListener('keydown', onSplashKeydown);
    startBtn.focus();
    startBtn.addEventListener('click', async () => {
      startBtn.hidden = true;
      splash.focus();
      document.getElementById('splash-logo').innerHTML = loaderSvg(120, { ground: true, ring: true, label: 'Đang mở PointSnap 3D' });
      const status = document.getElementById('splash-status');
      status.textContent = 'Đang tải dự án và kết nối CVAT…';
      await Promise.all([appReady.catch(() => {}), new Promise((r) => setTimeout(r, 1200))]);
      status.textContent = 'Đã sẵn sàng';
      splash.classList.add('leaving');
      setTimeout(() => {
        splash.hidden = true;
        splash.removeEventListener('keydown', onSplashKeydown);
        appContainer.inert = previousInert;
        document.getElementById('btn-project-dropdown').focus();
      }, 350);
      try {
        sessionStorage.setItem('pointsnap_splash_done', '1');
      } catch (_) {}
    }, { once: true });
  }

  // --- Thiết lập các bộ lắng nghe sự kiện ---
  function setupEventListeners() {
    document.addEventListener('keydown', (event) => {
      const modal = document.querySelector('.modal-overlay.open');
      if (!modal) return;
      if (event.key === 'Escape') { event.preventDefault(); closeModal(modal.id); }
      if (event.key === 'Tab') {
        const controls = [...modal.querySelectorAll('button:not(:disabled), input:not(:disabled), textarea, select, [tabindex="0"]')];
        const first = controls[0], last = controls[controls.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    });
    // 1. Chuyển đổi Theme Sáng | Tối
    document.getElementById('theme-btn-light').addEventListener('click', () => applyTheme('light'));
    document.getElementById('theme-btn-dark').addEventListener('click', () => applyTheme('dark'));

    // 2. Dropdown chọn dự án ở Topbar
    const projectBtn = document.getElementById('btn-project-dropdown');
    const projectMenu = document.getElementById('project-dropdown-menu');

    projectBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      const isOpen = projectMenu.classList.toggle('open');
      projectBtn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    });

    document.addEventListener('click', (e) => {
      if (!projectMenu.contains(e.target) && !projectBtn.contains(e.target)) {
        projectMenu.classList.remove('open');
        projectBtn.setAttribute('aria-expanded', 'false');
      }
    });

    // Modal Tạo dự án mới
    document.getElementById('btn-open-create-proj').addEventListener('click', () => {
      projectMenu.classList.remove('open');
      projectBtn.setAttribute('aria-expanded', 'false');
      populatePresetOptions();
      openModal('modal-create-proj');
    });
    document.getElementById('btn-submit-create-proj').addEventListener('click', handleCreateProject);

    // Modal Xóa dự án (bắt buộc gõ lại tên)
    document.getElementById('btn-open-delete-proj').addEventListener('click', () => {
      projectMenu.classList.remove('open');
      projectBtn.setAttribute('aria-expanded', 'false');
      if (!state.currentProject) return;
      document.getElementById('delete-proj-target-name').textContent = state.currentProject.name;
      const confirmInput = document.getElementById('delete-proj-confirm-input');
      confirmInput.value = '';
      document.getElementById('btn-confirm-delete-proj').disabled = true;
      openModal('modal-delete-proj');
    });

    document.getElementById('delete-proj-confirm-input').addEventListener('input', (e) => {
      const btn = document.getElementById('btn-confirm-delete-proj');
      btn.disabled = e.target.value.trim() !== state.currentProject?.name;
    });

    document.getElementById('btn-confirm-delete-proj').addEventListener('click', handleDeleteProject);

    // Đóng Modal qua thuộc tính data-close
    document.querySelectorAll('[data-close]').forEach((btn) => {
      btn.addEventListener('click', () => {
        closeModal(btn.getAttribute('data-close'));
      });
    });

    // 3. Chuyển đổi Tab Sidebar
    document.querySelectorAll('.app-sidebar .nav-link').forEach((btn) => {
      btn.addEventListener('click', () => {
        const tabId = btn.getAttribute('data-tab');
        window.location.hash = tabId.replace('tab-', '');
      });
    });

    window.addEventListener('hashchange', handleHashNavigation);

    // 4. Tab Quét (Scan)
    document.getElementById('btn-refresh-tasks').addEventListener('click', fetchCvatTasks);
    document.getElementById('select-cvat-task').addEventListener('change', handleTaskChange);
    document.getElementById('btn-start-scan').addEventListener('click', handleStartScan);

    // 5. Tab Kết quả (Results)
    document.getElementById('btn-re-flag-cvat').addEventListener('click', handleReFlagScan);
    document.getElementById('btn-learn').addEventListener('click', handleLearn);
    document.getElementById('filter-search-box').addEventListener('input', () => {
      state.findingsPage = 1;
      renderFindingsTable();
    });
    document.getElementById('filter-error-type').addEventListener('change', () => {
      state.findingsPage = 1;
      renderFindingsTable();
    });
    document.getElementById('filter-class').addEventListener('change', () => {
      state.findingsPage = 1;
      renderFindingsTable();
    });

    // Severity tabs
    ['all', 'error', 'warning', 'info'].forEach((sev) => {
      const tabBtn = document.getElementById(`sev-tab-${sev}`);
      if (tabBtn) {
        tabBtn.addEventListener('click', () => {
          state.selectedSeverityTab = sev;
          state.findingsPage = 1;
          updateSeverityTabs();
          renderFindingsTable();
        });
      }
    });

    // Nút phân trang
    document.getElementById('btn-pagination-prev').addEventListener('click', () => {
      if (state.findingsPage > 1) {
        state.findingsPage--;
        renderFindingsTable();
      }
    });
    document.getElementById('btn-pagination-next').addEventListener('click', () => {
      state.findingsPage++;
      renderFindingsTable();
    });

    // 6. Tab Guideline
    document.getElementById('btn-mode-form').addEventListener('click', () => setGuidelineMode('form'));
    document.getElementById('btn-mode-yaml').addEventListener('click', () => setGuidelineMode('yaml'));
    document.getElementById('btn-reset-guideline').addEventListener('click', handleResetGuideline);
    document.getElementById('btn-save-guideline').addEventListener('click', handleSaveGuideline);
    document.getElementById('btn-add-size-class').addEventListener('click', handleAddSizeClass);

    // Setup switch toggles
    document.querySelectorAll('#rules-toggles-container .switch-btn').forEach((sw) => {
      sw.addEventListener('click', () => {
        const checked = sw.getAttribute('aria-checked') === 'true';
        const next = !checked;
        sw.setAttribute('aria-checked', next ? 'true' : 'false');
        const id = sw.id;
        const labelEl = document.getElementById(`label-${id}`);
        if (labelEl) labelEl.textContent = next ? 'Bật' : 'Tắt';
        setGuidelineDirty(true);
      });
    });

    // Inputs trong Guideline đánh dấu dirty
    const formInputs = [
      'gate-max-errors', 'gate-max-warnings',
      'fl-warning-m', 'fl-error-m', 'fl-single-warning-m', 'fl-single-error-m'
    ];
    formInputs.forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.addEventListener('input', () => setGuidelineDirty(true));
    });

    const yamlArea = document.getElementById('guideline-yaml-textarea');
    if (yamlArea) yamlArea.addEventListener('input', () => setGuidelineDirty(true));

    // 7. Tab Kết nối CVAT
    document.getElementById('btn-check-cvat-connection').addEventListener('click', checkCvatConnection);
    document.getElementById('btn-save-connection-settings').addEventListener('click', handleSaveConnectionSettings);
  }

  // --- Điều hướng Tab dựa theo URL Hash ---
  function handleHashNavigation() {
    let hash = window.location.hash.substring(1) || 'results';
    const validTabs = ['results', 'scan', 'guideline', 'connection', 'history'];
    if (!validTabs.includes(hash)) hash = 'results';

    const tabId = `tab-${hash}`;
    state.currentTab = tabId;

    // Cập nhật trạng thái sidebar
    document.querySelectorAll('.app-sidebar .nav-link').forEach((btn) => {
      btn.classList.toggle('active', btn.getAttribute('data-tab') === tabId);
    });

    // Cập nhật tab pane
    document.querySelectorAll('.app-main .tab-pane').forEach((pane) => {
      pane.style.display = pane.id === tabId ? 'block' : 'none';
      pane.classList.toggle('active', pane.id === tabId);
    });

    // Nạp dữ liệu tương ứng cho tab
    if (tabId === 'tab-guideline') {
      loadGuideline();
    } else if (tabId === 'tab-connection') {
      loadConnectionTab();
    } else if (tabId === 'tab-history') {
      loadHistoryTab();
    } else if (tabId === 'tab-scan') {
      if (state.tasksList.length === 0) fetchCvatTasks();
    } else if (tabId === 'tab-results') {
      if (!state.currentRun && state.currentSlug) {
        loadLatestRun();
      }
    }
  }

  // --- 1. Quản lý Dự án (Project Management) ---
  async function loadProjects() {
    try {
      const res = await fetch('/api/projects');
      if (!res.ok) throw new Error('Không thể lấy danh sách dự án');
      state.projects = await res.json();
      renderProjectDropdown();

      if (state.projects.length > 0) {
        let saved;
        try { saved = localStorage.getItem('pointsnap_project'); } catch (_) {}
        const wanted = state.currentSlug || saved;
        const lastSlug = state.projects.some(p => p.slug === wanted) ? wanted : state.projects[0].slug;
        await selectProject(lastSlug);
      } else {
        document.getElementById('current-project-name').textContent = 'Chưa có dự án';
      }
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  function renderProjectDropdown() {
    const list = document.getElementById('project-dropdown-list');
    list.innerHTML = '';

    if (state.projects.length === 0) {
      list.innerHTML = '<li style="padding: 8px 14px; font-size: 13px; color: var(--text-3);">Không có dự án nào</li>';
      return;
    }

    state.projects.forEach((p) => {
      const li = document.createElement('li');
      const btn = document.createElement('button');
      btn.className = `project-menu-item ${p.slug === state.currentSlug ? 'active' : ''}`;
      btn.innerHTML = `
        <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(p.name)}</span>
        ${p.slug === state.currentSlug ? '<svg width="14" height="14" viewBox="0 0 14 14" fill="none" role="img" aria-label="Đang chọn" style="color: var(--primary); flex: none;"><path d="M2.5 7.5 L5.5 10.5 L11.5 3.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"></path></svg>' : ''}
      `;
      btn.addEventListener('click', async () => {
        document.getElementById('project-dropdown-menu').classList.remove('open');
        await selectProject(p.slug);
      });
      li.appendChild(btn);
      list.appendChild(li);
    });
  }

  async function selectProject(slug) {
    if (state.guidelineDirty && !confirm('Bỏ thay đổi Guideline chưa lưu để đổi dự án?')) return;
    state.projectEpoch++;
    state.currentSlug = slug;
    const scope = projectScope();
    try { localStorage.setItem('pointsnap_project', slug); } catch (_) {}
    clearInterval(state.scanPollTimer);
    state.scanPollTimer = null;
    setButtonIdle(document.getElementById('btn-start-scan'));
    showScanLoader(false);
    state.currentGuideline = null;
    document.getElementById('guideline-form-view').inert = true;
    document.getElementById('guideline-yaml-textarea').disabled = true;
    setGuidelineDirty(false);
    showEmptyResults();
    updateRecentScanCard(null);
    state.currentProject = state.projects.find((p) => p.slug === slug) || null;
    state.currentRun = null;

    if (state.currentProject) {
      document.getElementById('current-project-name').textContent = state.currentProject.name;
      updateBreadcrumbs(state.currentProject.name);
    }

    renderProjectDropdown();
    checkCvatConnectionStatus();

    // Reset danh sách task để nạp mới theo dự án
    state.tasksList = [];

    // Nạp lần quét gần nhất
    await loadLatestRun();
    if (!scope.current()) return;

    // Nạp lại tab đang mở
    handleHashNavigation();
  }

  function updateBreadcrumbs(projName) {
    const ids = ['breadcrumb-project', 'scan-breadcrumb-project', 'guideline-breadcrumb-project', 'conn-breadcrumb-project', 'history-breadcrumb-project'];
    ids.forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.textContent = projName;
    });
  }

  function populatePresetOptions() {
    const sel = document.getElementById('create-proj-preset');
    sel.innerHTML = '<option value="">-- Dùng Guideline mặc định --</option>';
    state.projects.forEach((p) => {
      const opt = document.createElement('option');
      opt.value = p.slug;
      opt.textContent = `Sao chép từ: ${p.name}`;
      sel.appendChild(opt);
    });
  }

  async function handleCreateProject() {
    const name = document.getElementById('create-proj-name').value.trim();
    if (!name) {
      showToast('Vui lòng nhập tên dự án', 'error');
      return;
    }

    const desc = document.getElementById('create-proj-desc').value.trim();
    const url = document.getElementById('create-proj-url').value.trim();
    const token = document.getElementById('create-proj-token').value.trim();
    const preset = document.getElementById('create-proj-preset').value || null;

    try {
      const res = await fetch('/api/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          description: desc,
          cvat_url: url || 'http://localhost:8080',
          cvat_token: token || null,
          preset_slug: preset,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(errorDetail(err.detail, 'Không thể tạo dự án'));
      }

      const created = await res.json();
      closeModal('modal-create-proj');
      showToast(`Đã tạo dự án '${created.name}'`, 'success');

      // Reset form
      document.getElementById('create-proj-name').value = '';
      document.getElementById('create-proj-desc').value = '';
      document.getElementById('create-proj-token').value = '';

      await loadProjects();
      await selectProject(created.slug);
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  async function handleDeleteProject() {
    if (!state.currentSlug) return;
    const btn = document.getElementById('btn-confirm-delete-proj');
    btn.disabled = true;

    try {
      const res = await fetch(`/api/projects/${state.currentSlug}`, { method: 'DELETE' });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(errorDetail(err.detail, 'Không thể xóa dự án'));
      }

      closeModal('modal-delete-proj');
      showToast('Đã xóa dự án thành công', 'success');
      state.currentSlug = null;
      await loadProjects();
    } catch (err) {
      showToast(err.message, 'error');
      btn.disabled = false;
    }
  }

  // --- Kiểm tra trạng thái CVAT trên Topbar ---
  async function checkCvatConnectionStatus() {
    const scope = projectScope();
    const dot = document.getElementById('cvat-status-dot');
    const text = document.getElementById('cvat-status-text');
    dot.className = 'status-dot checking';
    text.textContent = 'CVAT · Đang kiểm tra';

    if (!state.currentSlug) {
      dot.className = 'status-dot disconnected';
      text.textContent = 'CVAT · Chưa chọn dự án';
      return;
    }

    try {
      const res = await fetch(`/api/projects/${scope.slug}/cvat/check`);
      const data = await res.json();
      if (!scope.current()) return;
      if (data.connected) {
        dot.className = 'status-dot';
        text.textContent = `CVAT ${data.version || ''} · đã kết nối`;
      } else {
        dot.className = 'status-dot disconnected';
        text.textContent = 'CVAT · Mất kết nối';
      }
    } catch (_) {
      if (!scope.current()) return;
      dot.className = 'status-dot disconnected';
      text.textContent = 'CVAT · Không kết nối được';
    }
  }

  // --- 2. Tab Kết quả (Results View - Main.dc.html) ---
  async function loadLatestRun() {
    if (!state.currentSlug) {
      showEmptyResults();
      return;
    }
    const scope = projectScope();
    try {
      const res = await fetch(`/api/projects/${scope.slug}/scans`);
      if (!res.ok) throw new Error('Không thể tải kết quả. Kiểm tra kết nối rồi thử lại.');
      if (res.ok) {
        const runs = await res.json();
        if (!scope.current()) return;
        const latest = runs.find(r => r.status === 'done');
        if (latest) {
          await loadRunDetails(latest.run_id);
          if (scope.current()) updateRecentScanCard(latest);
          return;
        }
      }
      showEmptyResults();
    } catch (err) {
      if (!scope.current()) return;
      showEmptyResults();
      document.getElementById('results-header-subtitle').textContent = err.message;
      showToast(err.message, 'error');
    }
  }

  function showEmptyResults() {
    state.currentRun = null;
    state.currentDetail = null;
    state.previewData = null;
    clearPreviewCanvases();
    document.getElementById('results-empty-state').style.display = 'block';
    document.getElementById('results-content-box').style.display = 'none';
    document.getElementById('results-actions-group').style.display = 'none';
    document.getElementById('results-header-title').textContent = 'Kết quả quét';
    document.getElementById('results-header-subtitle').textContent = 'Chưa có lượt quét nào.';
    document.getElementById('breadcrumb-job').textContent = 'Job —';
    document.getElementById('nav-badge-findings').textContent = '0';
  }

  async function loadRunDetails(runId) {
    if (!state.currentSlug || !runId) return;
    const scope = projectScope();
    const version = ++state.runLoadVersion;
    try {
      const res = await fetch(`/api/projects/${scope.slug}/scans/${runId}`);
      if (!res.ok) throw new Error('Không thể nạp chi tiết lần quét');
      const data = await res.json();
      if (!scope.current() || version !== state.runLoadVersion) return;
      if (data.status !== 'done') throw new Error(data.error || 'Lần quét chưa hoàn tất, chưa có kết quả để xem.');
      state.currentRun = data;
      renderRunResults(data);
    } catch (err) {
      if (!scope.current() || version !== state.runLoadVersion) return;
      showToast(err.message, 'error');
    }
  }

  function renderRunResults(runData) {
    const sum = runData.summary || {};
    const findings = runData.findings || [];

    document.getElementById('results-empty-state').style.display = 'none';
    document.getElementById('results-content-box').style.display = 'flex';
    document.getElementById('results-actions-group').style.display = 'flex';

    // Breadcrumb & Title
    document.getElementById('breadcrumb-job').textContent = `Job #${runData.job_id}`;
    document.getElementById('results-header-title').textContent = `Kết quả quét job #${runData.job_id}`;
    const runTimeStr = formatDateTime(sum.timestamp || runData.started_at);
    document.getElementById('results-header-subtitle').textContent =
      `Quét lúc ${runTimeStr} · ${sum.num_boxes ?? 0} box · guideline của dự án`;

    // Cổng kiểm soát (Gate Banner)
    const gateBanner = document.getElementById('gate-banner-strip');
    const gateTitle = document.getElementById('gate-verdict-title');
    const gateDesc = document.getElementById('gate-verdict-desc');

    if (sum.gate_passed) {
      gateBanner.className = 'gate-banner-strip pass';
      gateTitle.textContent = 'Đạt cổng kiểm soát';
      gateDesc.textContent = `${sum.num_errors ?? 0} Lỗi · ${sum.num_warnings ?? 0} Cảnh báo. Đạt ngưỡng của các luật đang bật.`;
    } else {
      gateBanner.className = 'gate-banner-strip fail';
      gateTitle.textContent = 'Không đạt cổng kiểm soát';
      const reasons = sum.gate_reasons && sum.gate_reasons.length > 0 ? sum.gate_reasons.join(' · ') : 'Vượt ngưỡng cho phép';
      const partial = (sum.gate_reasons || []).some(reason => reason.startsWith('Kiểm tra một phần:'));
      gateDesc.textContent = partial
        ? `${reasons}. Bổ sung dữ liệu cần thiết, kiểm tra các box thiếu bằng chứng rồi quét lại.`
        : `${reasons}. Sửa các mục Lỗi trên CVAT rồi quét lại.`;
    }

    // Thẻ số lượng (Stats Grid)
    document.getElementById('stat-errors-count').textContent = sum.num_errors ?? 0;
    document.getElementById('stat-warnings-count').textContent = sum.num_warnings ?? 0;
    document.getElementById('stat-info-count').textContent = sum.num_info ?? 0;
    document.getElementById('stat-boxes-count').textContent = sum.num_boxes ?? 0;

    // Cập nhật badge trên Sidebar
    const totalIssues = (sum.num_errors ?? 0) + (sum.num_warnings ?? 0);
    document.getElementById('nav-badge-findings').textContent = totalIssues;

    // Liên kết xuất báo cáo
    document.getElementById('btn-download-csv').href = `/api/projects/${state.currentSlug}/scans/${runData.run_id}/report.csv`;
    document.getElementById('btn-download-html').href = `/api/projects/${state.currentSlug}/scans/${runData.run_id}/report.html`;

    // Nút Gắn cờ lên CVAT / Quét lại
    const btnReflag = document.getElementById('btn-re-flag-cvat');
    btnReflag.textContent = sum.flagged ? 'Quét lại & Gắn cờ' : 'Gắn cờ lên CVAT';

    // Populate dropdown class filter
    populateClassFilter(findings);

    // Cập nhật tab severity đếm số
    updateSeverityTabs();

    // Reset về trang 1 và chọn dòng đầu tiên
    state.findingsPage = 1;
    state.selectedFindingIndex = 0;
    renderFindingsTable();
  }

  function populateClassFilter(findings) {
    const sel = document.getElementById('filter-class');
    const currentVal = sel.value;
    sel.innerHTML = '<option value="">Mọi class</option>';
    const classes = Array.from(new Set(findings.map((f) => f.label).filter(Boolean))).sort();
    classes.forEach((c) => {
      const opt = document.createElement('option');
      opt.value = c;
      opt.textContent = c;
      if (c === currentVal) opt.selected = true;
      sel.appendChild(opt);
    });
  }

  function updateSeverityTabs() {
    if (!state.currentRun) return;
    const findings = state.currentRun.findings || [];
    const errCount = findings.filter((f) => f.severity === 'error').length;
    const warnCount = findings.filter((f) => f.severity === 'warning').length;
    const infoCount = findings.filter((f) => f.severity === 'info').length;

    document.getElementById('sev-tab-all').textContent = `Tất cả ${findings.length}`;
    document.getElementById('sev-tab-error').textContent = `Lỗi ${errCount}`;
    document.getElementById('sev-tab-warning').textContent = `Cảnh báo ${warnCount}`;
    document.getElementById('sev-tab-info').textContent = `Thông tin ${infoCount}`;

    ['all', 'error', 'warning', 'info'].forEach((sev) => {
      const btn = document.getElementById(`sev-tab-${sev}`);
      if (btn) btn.setAttribute('aria-pressed', state.selectedSeverityTab === sev ? 'true' : 'false');
    });
  }

  function getFilteredFindings() {
    if (!state.currentRun || !state.currentRun.findings) return [];
    const query = document.getElementById('filter-search-box').value.toLowerCase().trim();
    const typeFilter = document.getElementById('filter-error-type').value;
    const classFilter = document.getElementById('filter-class').value;
    const sevTab = state.selectedSeverityTab;

    return state.currentRun.findings.filter((f) => {
      if (sevTab !== 'all' && f.severity !== sevTab) return false;
      if (typeFilter && f.error_type !== typeFilter) return false;
      if (classFilter && f.label !== classFilter) return false;
      if (query) {
        const text = `${f.message || ''} ${f.rule || ''} ${f.label || ''} ${f.frame ?? ''} ${f.track_id ?? ''}`.toLowerCase();
        if (!text.includes(query)) return false;
      }
      return true;
    });
  }

  function renderFindingsTable() {
    const tbody = document.getElementById('findings-table-body');
    tbody.innerHTML = '';

    const filtered = getFilteredFindings();
    const total = filtered.length;
    const perPage = state.findingsPerPage;
    const totalPages = Math.ceil(total / perPage) || 1;

    if (state.findingsPage > totalPages) state.findingsPage = totalPages;
    const startIndex = (state.findingsPage - 1) * perPage;
    const endIndex = Math.min(startIndex + perPage, total);
    const pageItems = filtered.slice(startIndex, endIndex);
    if (total) state.selectedFindingIndex = Math.min(Math.max(state.selectedFindingIndex, startIndex), endIndex - 1);

    // Cập nhật phân trang footer
    const prevBtn = document.getElementById('btn-pagination-prev');
    const nextBtn = document.getElementById('btn-pagination-next');
    prevBtn.disabled = state.findingsPage <= 1;
    nextBtn.disabled = state.findingsPage >= totalPages || totalPages === 0;

    const summaryText = total === 0 ? '0–0 trên 0 mục' : `${startIndex + 1}–${endIndex} trên ${total} mục`;
    document.getElementById('pagination-summary-text').textContent = summaryText;

    if (pageItems.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: var(--text-3); padding: 32px;">Không có mục nào phù hợp bộ lọc.</td></tr>';
      clearDetailDrawer();
      return;
    }

    pageItems.forEach((f, idx) => {
      const globalIndex = startIndex + idx;
      const tr = document.createElement('tr');
      if (globalIndex === state.selectedFindingIndex) {
        tr.className = 'selected';
      }

      const sevClass = f.severity === 'error' ? 'error' : f.severity === 'warning' ? 'warning' : 'info';
      const sevLabel = f.severity_label || (f.severity === 'error' ? 'Lỗi' : f.severity === 'warning' ? 'Cảnh báo' : 'Thông tin');

      tr.innerHTML = `
        <td><span class="pill-badge ${sevClass}">${escapeHtml(sevLabel)}</span>${reviewLabel(runFindingIndex(f)) ? `<span class="review-mark">${reviewLabel(runFindingIndex(f))}</span>` : ''}</td>
        <td class="mono">#${escapeHtml(f.frame)}</td>
        <td class="mono">${f.track_id !== null && f.track_id !== undefined ? `#${escapeHtml(f.track_id)}` : '—'}</td>
        <td>${escapeHtml(f.label || '—')}</td>
        <td style="color: var(--text-2);">${escapeHtml(f.error_type_label || f.error_type || '—')}</td>
        <td style="color: var(--text);">${escapeHtml(f.message || '')}</td>
      `;

      tr.addEventListener('click', () => {
        state.selectedFindingIndex = globalIndex;
        document.querySelectorAll('#findings-table-body tr').forEach((r) => r.classList.remove('selected'));
        tr.classList.add('selected');
        renderDetailDrawer(f);
      });

      tbody.appendChild(tr);
    });

    // Nạp chi tiết cho dòng đang chọn
    const currentPick = filtered[state.selectedFindingIndex] || pageItems[0];
    if (currentPick) renderDetailDrawer(currentPick);
  }

  // --- Duyệt nhanh (A14): xem point cloud quanh box, chuyển mục, ghi kết luận, không cần mở CVAT ---
  const previewCache = new Map();

  function runFindingIndex(f) {
    return state.currentRun && state.currentRun.findings ? state.currentRun.findings.indexOf(f) : -1;
  }

  function setupQuickReview() {
    document.getElementById('btn-quick-prev').addEventListener('click', () => moveSelection(-1));
    document.getElementById('btn-quick-next').addEventListener('click', () => moveSelection(1));
    document.getElementById('btn-review-ok').addEventListener('click', () => markReview('ok'));
    document.getElementById('btn-review-fp').addEventListener('click', () => markReview('fp'));
    document.addEventListener('keydown', (e) => {
      if (state.currentTab !== 'tab-results' || e.ctrlKey || e.metaKey || e.altKey) return;
      const tag = (e.target.tagName || '').toLowerCase();
      if (['input', 'textarea', 'select'].includes(tag) || e.target.isContentEditable) return;
      if (document.querySelector('.modal-overlay.open') || !document.getElementById('splash').hidden) return;
      const key = e.key.toLowerCase();
      if (key === 'j' || e.key === 'ArrowDown') moveSelection(1);
      else if (key === 'k' || e.key === 'ArrowUp') moveSelection(-1);
      else if (key === '1') markReview('ok');
      else if (key === '2') markReview('fp');
      else return;
      e.preventDefault();
    });
    window.addEventListener('resize', () => {
      if (state.previewData) drawPreviewViews(state.previewData);
    });
  }

  // --- Liên kết với extension trên tab CVAT (A15): chọn mục trên web thì tab CVAT tự đi theo, không tải lại trang ---
  let linkTimer = null;
  let syncTimer = null;

  function setupCvatLink() {
    document.getElementById('detail-btn-cvat-link').addEventListener('click', openInCvat);
    const tick = () => { pollCvatLink().finally(() => { linkTimer = setTimeout(tick, 2500); }); };
    tick();
  }

  /** Hỏi PointSnap: có tab CVAT (cài extension) đang mở job của lần quét này không; kết luận xem tay có đổi không. */
  async function pollCvatLink() {
    const run = state.currentRun;
    if (!run || !run.job_id || document.hidden) return;
    try {
      const cvatUrl = run.summary?.cvat_url || state.projects.find((p) => p.slug === state.currentSlug)?.cvat_url || '';
      const res = await fetch(`/api/extension/status?job_id=${run.job_id}&cvat_url=${encodeURIComponent(cvatUrl)}`);
      if (!res.ok) return;
      const data = await res.json();
      if (state.currentRun !== run) return;
      const changed = data.extension_online !== state.cvatLink.online || state.cvatLink.jobId !== run.job_id;
      const rev = state.cvatLink.jobId === run.job_id ? state.cvatLink.rev : null;
      state.cvatLink = { online: data.extension_online, jobId: run.job_id, rev: data.reviews_rev };
      if (changed) updateCvatButton();
      if (rev !== null && rev !== data.reviews_rev) await refreshReviewsFromServer(run);
    } catch (_) {
      // PointSnap tạm không trả lời: giữ trạng thái cũ, lần sau hỏi lại.
    }
  }

  /** Kết luận xem tay vừa đổi ở extension: đọc lại và vẽ lại bảng, giữ nguyên mục đang chọn. */
  async function refreshReviewsFromServer(run) {
    const res = await fetch(`/api/projects/${state.currentSlug}/scans/${run.run_id}/reviews`);
    if (!res.ok || state.currentRun !== run) return;
    const { reviews } = await res.json();
    if (state.currentRun !== run) return;
    if (JSON.stringify(reviews) === JSON.stringify(run.reviews || {})) return;
    run.reviews = reviews;
    renderFindingsTable();
  }

  function updateCvatButton() {
    const btn = document.getElementById('detail-btn-cvat-link');
    const status = document.getElementById('cvat-link-status');
    if (state.cvatLink.online) {
      btn.textContent = 'Chuyển CVAT tới box này';
      status.innerHTML = '<span class="link-dot on"></span>CVAT đang mở job này: chọn mục ở đây thì CVAT tự chuyển theo, không tải lại trang.';
    } else {
      btn.textContent = 'Mở trong CVAT để sửa';
      status.innerHTML = '<span class="link-dot"></span>Cài extension PointSnap cho CVAT để chuyển box mà không tải lại job.';
    }
  }

  function sendFocus(f, bring) {
    const index = runFindingIndex(f);
    return fetch('/api/extension/focus', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        job_id: state.currentRun.job_id,
        cvat_url: state.currentRun.summary?.cvat_url || state.projects.find((p) => p.slug === state.currentSlug)?.cvat_url || '',
        frame: f.frame,
        label: f.label,
        message: f.message,
        track_id: f.track_id ?? null,
        source_id: f.source_id ?? null,
        run_id: state.currentRun.run_id,
        index: index >= 0 ? index : null,
        bring,
      }),
    }).then((res) => (res.ok ? res.json() : { extension_online: false }));
  }

  /** "Mở trong CVAT": có tab CVAT đang mở job thì chuyển trong tab đó; chưa có thì mở link như cũ. */
  async function openInCvat(e) {
    const f = state.currentDetail;
    if (!f || !state.currentRun) return;
    e.preventDefault();
    const link = e.currentTarget.href;
    try {
      const data = await sendFocus(f, true);
      if (data.extension_online) {
        showToast(`Đã chuyển CVAT tới frame ${f.frame} (không tải lại trang).`, 'success');
        return;
      }
    } catch (_) {
      // Không gửi được lệnh: mở link như cũ.
    }
    if (link && link !== '#') window.open(link, 'pointsnap-cvat');
  }

  /** Chọn mục khác trên web: nếu CVAT đang mở job này thì gửi lệnh đồng bộ (chờ 250 ms để J/K liên tục chỉ gửi mục cuối). */
  function syncCvatSelection(f) {
    if (!state.cvatLink.online || !state.currentRun || state.cvatLink.jobId !== state.currentRun.job_id) return;
    clearTimeout(syncTimer);
    syncTimer = setTimeout(() => { if (state.currentDetail === f) sendFocus(f, false).catch(() => {}); }, 250);
  }

  function moveSelection(step) {
    const filtered = getFilteredFindings();
    if (filtered.length === 0) return;
    const next = Math.min(Math.max(state.selectedFindingIndex + step, 0), filtered.length - 1);
    if (next === state.selectedFindingIndex) return;
    state.selectedFindingIndex = next;
    state.findingsPage = Math.floor(next / state.findingsPerPage) + 1;
    renderFindingsTable();
    const row = document.querySelector('#findings-table-body tr.selected');
    if (row) row.scrollIntoView({ block: 'nearest' });
  }

  async function markReview(verdict) {
    const f = state.currentDetail;
    const index = runFindingIndex(f);
    if (!f || index < 0 || !state.currentSlug) return;
    const scope = projectScope(), run = state.currentRun;
    const reviews = state.currentRun.reviews || {};
    const value = reviews[String(index)] === verdict ? null : verdict;
    try {
      const res = await fetch(`/api/projects/${state.currentSlug}/scans/${state.currentRun.run_id}/reviews/${index}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ verdict: value }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || 'Không lưu được kết luận');
      const data = await res.json();
      if (!scope.current() || state.currentRun !== run) return;
      run.reviews = data.reviews;
      if (value) moveSelection(1);
      renderFindingsTable();
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  function reviewLabel(index) {
    const v = state.currentRun && state.currentRun.reviews ? state.currentRun.reviews[String(index)] : undefined;
    return v === 'ok' ? 'Đúng' : v === 'fp' ? 'Báo nhầm' : '';
  }

  function updateReviewPanel(f) {
    const index = runFindingIndex(f);
    const reviews = (state.currentRun && state.currentRun.reviews) || {};
    const v = reviews[String(index)];
    const ok = document.getElementById('btn-review-ok');
    const fp = document.getElementById('btn-review-fp');
    ok.disabled = fp.disabled = !f;
    ok.setAttribute('aria-pressed', v === 'ok' ? 'true' : 'false');
    fp.setAttribute('aria-pressed', v === 'fp' ? 'true' : 'false');

    const values = Object.values(reviews);
    const nOk = values.filter((x) => x === 'ok').length;
    const nFp = values.filter((x) => x === 'fp').length;
    const total = (state.currentRun && state.currentRun.findings || []).length;
    const precision = nOk + nFp > 0 ? ` · precision xem tay ${Math.round((nOk / (nOk + nFp)) * 100)}%` : '';
    document.getElementById('review-progress-text').textContent =
      `Đã xem ${nOk + nFp} / ${total} (đúng ${nOk}, báo nhầm ${nFp})${precision}.`;

    const filtered = getFilteredFindings();
    document.getElementById('quick-nav-counter').textContent =
      `${filtered.length ? state.selectedFindingIndex + 1 : 0} / ${filtered.length}`;
    document.getElementById('btn-quick-prev').disabled = state.selectedFindingIndex <= 0;
    document.getElementById('btn-quick-next').disabled = state.selectedFindingIndex >= filtered.length - 1;
  }

  function fetchPreview(index) {
    const key = `${state.currentSlug}/${state.currentRun.run_id}/${index}`;
    if (!previewCache.has(key)) {
      const p = fetch(`/api/projects/${state.currentSlug}/scans/${state.currentRun.run_id}/findings/${index}/preview`)
        .then(async (res) => {
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || 'Không dựng được bản xem nhanh');
          return data;
        });
      p.catch(() => previewCache.delete(key));
      previewCache.set(key, p);
    }
    return previewCache.get(key);
  }

  async function loadPreview(f) {
    const index = runFindingIndex(f);
    const status = document.getElementById('preview-status');
    state.previewData = null;
    clearPreviewCanvases();
    if (index < 0 || !state.currentSlug) return;
    status.innerHTML = `<span class="inline-loading">${loaderSvg(20)}<span>Đang tải point cloud…</span></span>`;
    loadCamera(f, index);
    try {
      const data = await fetchPreview(index);
      if (state.currentDetail !== f) return;
      data.color = f.severity === 'error' ? 'error' : f.severity === 'warning' ? 'warn' : 'primary';
      state.previewData = data;
      drawPreviewViews(data);
      status.textContent = data.synthetic_box
        ? `Khung tham khảo của cụm chưa có nhãn · ${data.points.length} điểm · cách LiDAR ${data.distance_m} m · frame ${data.frame}`
        : data.exact_frame
        ? `${data.points.length} điểm quanh box · cách LiDAR ${data.distance_m} m · frame ${data.frame}`
        : `Box gần nhất của track ở frame ${data.frame} · ${data.points.length} điểm · cách LiDAR ${data.distance_m} m`;
      const nextF = getFilteredFindings()[state.selectedFindingIndex + 1];
      if (nextF) fetchPreview(runFindingIndex(nextF)).catch(() => {});
    } catch (err) {
      if (state.currentDetail === f) status.textContent = err.message;
    }
  }

  function clearPreviewCanvases() {
    ['preview-canvas-top', 'preview-canvas-side', 'preview-canvas-front'].forEach((id) => {
      const c = document.getElementById(id);
      c.getContext('2d').clearRect(0, 0, c.width, c.height);
    });
    const img = document.getElementById('preview-camera');
    img.hidden = true;
    img.removeAttribute('src');
    document.getElementById('preview-camera-link').removeAttribute('href');
    document.getElementById('preview-camera-caption').textContent = 'Ảnh camera';
  }

  // Ảnh camera thấy box rõ nhất (máy chủ chọn camera, vẽ khung 3D, mặt đầu box màu đỏ); bấm để mở cả ảnh.
  const cameraCache = new Map();
  function fetchCamera(index) {
    const base = `/api/projects/${state.currentSlug}/scans/${state.currentRun.run_id}/findings/${index}/camera`;
    if (!cameraCache.has(base)) {
      const p = fetch(base).then(async (res) => {
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data.detail || 'Không có ảnh camera cho box này');
        }
        return { url: URL.createObjectURL(await res.blob()), channel: res.headers.get('X-Camera-Channel') || '', full: `${base}?full=true` };
      });
      p.catch(() => cameraCache.delete(base));
      cameraCache.set(base, p);
    }
    return cameraCache.get(base);
  }

  async function loadCamera(f, index) {
    const img = document.getElementById('preview-camera');
    const caption = document.getElementById('preview-camera-caption');
    caption.textContent = 'Ảnh camera · đang tải…';
    try {
      const cam = await fetchCamera(index);
      if (state.currentDetail !== f) return;
      img.src = cam.url;
      img.hidden = false;
      document.getElementById('preview-camera-link').href = cam.full;
      caption.textContent = `Ảnh camera ${cam.channel} · khung đỏ là mặt đầu box · bấm để xem cả ảnh`;
    } catch (err) {
      if (state.currentDetail === f) caption.textContent = `Ảnh camera · ${err.message}`;
    }
  }

  function drawPreviewViews(data) {
    drawPreview(document.getElementById('preview-canvas-top'), data, 'top');
    drawPreview(document.getElementById('preview-canvas-side'), data, 'side');
    drawPreview(document.getElementById('preview-canvas-front'), data, 'front');
  }

  // Vẽ điểm trong hệ của box (x dọc chiều dài, hướng đầu box; y theo chiều rộng; z lên), như ba khung Top / Side / Front
  // của CVAT: nhìn từ trên (x, y), nhìn ngang (x, z) và nhìn từ đầu box (y, z). Mũi tên đỏ chỉ đầu box; đường đứt
  // là mặt đất đo được của finding lơ lửng / lún, nghiêng theo độ dốc dọc thân box.
  function drawPreview(canvas, data, view) {
    const css = getComputedStyle(document.documentElement);
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    const { length: L, width: W, height: H } = data.box;
    const margin = 2.0;
    // Trục ngang của khung: x (top, side) hoặc y (front); trục dọc: y (top) hoặc z (side, front).
    const hr = view === 'front' ? W / 2 + margin : L / 2 + margin;
    const [v0, v1] = view === 'top' ? [-(W / 2 + margin), W / 2 + margin] : [-H / 2 - 1.5, H / 2 + 1.0];
    const scale = Math.min((w - 8) / (2 * hr), (h - 8) / (v1 - v0));
    const vc = (v0 + v1) / 2;
    const px = (u) => w / 2 + u * scale;
    const py = (v) => h / 2 - (v - vc) * scale;
    const project = ([x, y, z]) => view === 'top' ? [x, y] : view === 'side' ? [x, z] : [y, z];

    const outside = css.getPropertyValue('--text-3').trim();
    const inside = css.getPropertyValue('--text').trim();
    data.points.forEach((p) => {
      const [x, y, z] = p;
      const isIn = Math.abs(x) <= L / 2 && Math.abs(y) <= W / 2 && Math.abs(z) <= H / 2;
      const [u, v] = project(p);
      ctx.fillStyle = isIn ? inside : outside;
      ctx.fillRect(px(u) - 0.75, py(v) - 0.75, 1.5, 1.5);
    });

    if (data.ground && view !== 'top') {
      const slope = view === 'side' ? Math.tan((data.ground.pitch_deg || 0) * Math.PI / 180) : 0;
      ctx.save();
      ctx.strokeStyle = css.getPropertyValue('--success').trim();
      ctx.setLineDash([5, 4]);
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(px(-hr), py(data.ground.z - slope * hr));
      ctx.lineTo(px(hr), py(data.ground.z + slope * hr));
      ctx.stroke();
      ctx.restore();
    }

    ctx.strokeStyle = css.getPropertyValue(`--${data.color}`).trim();
    ctx.lineWidth = 1.5;
    const halfU = view === 'front' ? W / 2 : L / 2;
    const halfV = view === 'top' ? W / 2 : H / 2;
    ctx.strokeRect(px(-halfU), py(halfV), 2 * halfU * scale, 2 * halfV * scale);

    // Mũi tên đỏ từ tâm ra quá mép đầu box (top, side); nhìn từ đầu box thì là chấm đỏ ở tâm (mũi tên hướng về người xem).
    ctx.strokeStyle = ctx.fillStyle = css.getPropertyValue('--error').trim();
    ctx.lineWidth = 2;
    if (view === 'front') {
      ctx.beginPath();
      ctx.arc(px(0), py(0), 4, 0, 2 * Math.PI);
      ctx.fill();
    } else {
      const tip = px(L / 2) + 14;
      ctx.beginPath();
      ctx.moveTo(px(0), py(0));
      ctx.lineTo(tip, py(0));
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(tip + 2, py(0));
      ctx.lineTo(tip - 6, py(0) - 5);
      ctx.lineTo(tip - 6, py(0) + 5);
      ctx.closePath();
      ctx.fill();
    }
  }

  function renderDetailDrawer(f) {
    if (!f) return;
    if (state.currentDetail !== f) {
      state.currentDetail = f;
      loadPreview(f);
      syncCvatSelection(f);
    }
    updateReviewPanel(f);
    const sevClass = f.severity === 'error' ? 'error' : f.severity === 'warning' ? 'warning' : 'info';
    const sevLabel = f.severity_label || (f.severity === 'error' ? 'Lỗi' : f.severity === 'warning' ? 'Cảnh báo' : 'Thông tin');

    const badge = document.getElementById('detail-sev-badge');
    badge.className = `pill-badge ${sevClass}`;
    badge.textContent = sevLabel;

    document.getElementById('detail-rule-code').textContent = f.rule || 'custom';
    document.getElementById('detail-title-text').textContent = generateFindingTitle(f);

    document.getElementById('detail-frame-val').textContent = `#${f.frame}`;
    document.getElementById('detail-track-class-val').textContent =
      `${f.track_id !== null && f.track_id !== undefined ? `#${f.track_id}` : '—'} · ${f.label || '—'}`;

    document.getElementById('detail-measured-val').textContent = formatMeasure(f, f.value, true);
    document.getElementById('detail-threshold-val').textContent = formatMeasure(f, f.threshold);
    document.getElementById('detail-confidence-val').textContent =
      f.confidence === null || f.confidence === undefined ? 'chưa học' : `${Math.round(f.confidence * 100)}%`;
    document.getElementById('detail-message-desc').textContent = f.message || '—';

    // Gợi ý cách sửa từ từ điển A13
    const fixTip = findingFixTip(f);
    document.getElementById('detail-fix-hint').textContent = fixTip;

    // Nút mở CVAT
    const cvatBtn = document.getElementById('detail-btn-cvat-link');
    const link = safeHttpLink(f.cvat_link);
    if (link) {
      cvatBtn.href = link;
      cvatBtn.style.display = 'flex';
    } else {
      cvatBtn.style.display = 'none';
    }
  }

  function clearDetailDrawer() {
    state.currentDetail = null;
    state.previewData = null;
    clearPreviewCanvases();
    document.getElementById('preview-status').textContent = '';
    document.getElementById('detail-sev-badge').textContent = '—';
    document.getElementById('detail-rule-code').textContent = '—';
    document.getElementById('detail-title-text').textContent = 'Chưa chọn mục';
    document.getElementById('detail-frame-val').textContent = '—';
    document.getElementById('detail-track-class-val').textContent = '—';
    document.getElementById('detail-measured-val').textContent = '—';
    document.getElementById('detail-threshold-val').textContent = '—';
    document.getElementById('detail-confidence-val').textContent = '—';
    document.getElementById('detail-message-desc').textContent = '—';
    document.getElementById('detail-fix-hint').textContent = '—';
    document.getElementById('detail-btn-cvat-link').style.display = 'none';
    document.getElementById('quick-nav-counter').textContent = '0 / 0';
    ['btn-review-ok', 'btn-review-fp', 'btn-quick-prev', 'btn-quick-next'].forEach(id => { document.getElementById(id).disabled = true; });
  }

  function generateFindingTitle(f) {
    if (f.rule === 'floating') {
      if ((f.message || '').includes('lún')) return 'Box lún so với mặt đất';
      return 'Box lơ lửng so với mặt đất';
    }
    if (state.ruleLabels && state.ruleLabels[f.rule]) {
      return state.ruleLabels[f.rule];
    }
    if (f.rule === 'floating.no_evidence') return 'Không đủ điểm mặt đất';

    if (f.rule === 'size.class_range') return 'Kích thước ngoài khoảng của class';
    if (f.rule === 'size.in_track') return 'Kích thước bất thường trong track';
    if (f.rule === 'track.jump') return 'Track nhảy vị trí';
    if (f.rule === 'track.split_id') return 'Nghi tách ID track';
    if (f.rule === 'track.long_interpolation') return 'Khoảng nội suy dài';
    if (f.rule === 'heading.flip') return 'Hướng box đổi đột ngột';
    if (f.rule === 'heading.motion') return 'Hướng box lệch hướng chuyển động';
    if (f.rule === 'heading.points') return 'Trục box lệch cụm điểm';
    if (f.rule === 'fit.empty') return 'Box rỗng';
    if (f.rule === 'fit.outside') return 'Điểm của vật nằm ngoài box';
    if (f.rule === 'fit.loose') return 'Box dư so với vật';
    if (f.rule === 'fit.overlap') return 'Hai box chồng nhau';
    if (f.rule === 'track.reuse_id') return 'Dùng lại track sau khi kết thúc';
    if (f.rule === 'track.occluded_long') return 'Che khuất quá lâu';
    if (f.rule === 'track.id_swap') return 'Nghi đổi nhầm ID';
    if (f.rule === 'attr.rider_state') return 'Quên đổi trạng thái người lái';
    if (f.rule === 'cam.sparse') return 'Box quá ít điểm, ảnh không thấy';
    if (f.rule === 'lidar.missing') return 'Nghi sót đối tượng (LiDAR)';
    if (f.rule === 'attr.height') return 'Thuộc tính lệch chiều cao';
    if (f.rule === 'spec.inside') return 'Người bên trong xe';
    if (f.rule === 'spec.rider_double') return 'Người lái bị gán 2 lần';
    if (f.rule === 'attr.missing') return 'Thiếu thuộc tính bắt buộc';
    if (f.rule === 'attr.invalid') return 'Thuộc tính sai giá trị';
    if (f.rule === 'track.static_shift') return 'Vật đứng yên: box dịch';
    if (f.rule === 'heading.static') return 'Vật đứng yên: box xoay';
    if (f.rule === 'cam.mismatch') return 'Box lệch vật trên ảnh';
    if (f.rule === 'cam.class') return 'Ảnh camera thấy class khác';
    if (f.rule === 'cam.missing') return 'Ảnh thấy vật chưa có box';
    if (f.rule === 'critic.box') return 'Box Critic nghi box sai';
    return f.message ? f.message.split(';')[0] : 'Phát hiện bất thường';
  }

  // --- Quét lại và gắn cờ (Re-flag) ---
  async function handleReFlagScan() {
    const scope = projectScope();
    if (!state.currentRun || !state.currentSlug) return;
    const btn = document.getElementById('btn-re-flag-cvat');
    setButtonBusy(btn, 'Đang khởi động…');

    try {
      showToast('Đang khởi động quét lại và gắn cờ lên CVAT...', 'info');
      const res = await fetch(`/api/projects/${scope.slug}/scans/${state.currentRun.run_id}/flag`, {
        method: 'POST',
      });

      if (!res.ok) {
        const err = await res.json();
      if (!scope.current()) return;
        throw new Error(errorDetail(err.detail, 'Không thể quét lại và gắn cờ'));
      }

      const result = await res.json();
      if (!scope.current()) return;
      showToast(result.message || 'Đang quét lại và gắn cờ...', 'info');
      window.location.hash = 'scan';
      resetScanProgress();
      pollScanProgress(result.run_id);
    } catch (err) {
      if (!scope.current()) return;
      showToast(err.message, 'error');
    } finally {
      setButtonIdle(btn);
    }
  }

  // --- 3. Tab Quét (Scan View - Quet.dc.html) ---
  async function fetchCvatTasks() {
    const scope = projectScope();
    if (!state.currentSlug) return;
    const taskSelect = document.getElementById('select-cvat-task');
    const refreshBtn = document.getElementById('btn-refresh-tasks');
    setButtonBusy(refreshBtn, 'Đang tải');
    taskSelect.innerHTML = '<option value="">Đang tải Task từ CVAT...</option>';

    try {
      const res = await fetch(`/api/projects/${scope.slug}/cvat/tasks`);
      if (!scope.current()) return;
      if (!res.ok) throw new Error('Không thể lấy danh sách Task');
      const data = await res.json();
      if (!scope.current()) return;
      state.tasksList = data.tasks || [];

      taskSelect.innerHTML = '<option value="">-- Chọn Task --</option>';
      state.tasksList.forEach((t) => {
        const opt = document.createElement('option');
        opt.value = t.id;
        opt.textContent = `#${t.id} · ${t.name} (${t.jobs ? t.jobs.length : 0} job)`;
        taskSelect.appendChild(opt);
      });

      // Tự động chọn task đầu tiên nếu có
      if (state.tasksList.length > 0) {
        taskSelect.value = state.tasksList[0].id;
        handleTaskChange();
      }
    } catch (err) {
      if (!scope.current()) return;
      taskSelect.innerHTML = '<option value="">Không tải được Task (kiểm tra kết nối)</option>';
      showToast(err.message, 'error');
    } finally {
      setButtonIdle(refreshBtn);
    }
  }

  function handleTaskChange() {
    const taskId = document.getElementById('select-cvat-task').value;
    const jobSelect = document.getElementById('select-cvat-job');
    jobSelect.innerHTML = '<option value="">-- Chọn Job --</option>';

    if (!taskId) return;
    const task = state.tasksList.find((t) => String(t.id) === String(taskId));
    if (task && task.jobs) {
      task.jobs.forEach((j) => {
        const opt = document.createElement('option');
        opt.value = j.id;
        const frames = j.frame_count ?? (Number.isInteger(j.stop_frame) && Number.isInteger(j.start_frame) ? j.stop_frame - j.start_frame + 1 : null);
        opt.textContent = `#${j.id} · ${j.stage || 'annotation'} · ${frames == null ? 'chưa rõ số' : frames} frame`;
        jobSelect.appendChild(opt);
      });

      if (task.jobs.length > 0) {
        jobSelect.value = task.jobs[0].id;
      }
    }
  }

  async function handleStartScan() {
    const scope = projectScope();
    if (!state.currentSlug) {
      showToast('Vui lòng chọn hoặc tạo dự án trước', 'error');
      return;
    }

    let jobId = document.getElementById('input-custom-job-id').value.trim();
    if (!jobId) {
      jobId = document.getElementById('select-cvat-job').value;
    }
    if (!jobId) {
      showToast('Vui lòng chọn Job hoặc nhập ID job', 'error');
      return;
    }

    const flag = document.getElementById('check-scan-flag').checked;
    const btn = document.getElementById('btn-start-scan');
    setButtonBusy(btn, 'Đang quét…');

    resetScanProgress();

    try {
      const res = await fetch(`/api/projects/${scope.slug}/scans`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: parseInt(jobId, 10), flag }),
      });

      if (!res.ok) {
        const err = await res.json();
      if (!scope.current()) return;
        throw new Error(errorDetail(err.detail, 'Không thể bắt đầu quét'));
      }

      const scanInfo = await res.json();
      if (!scope.current()) return;
      pollScanProgress(scanInfo.run_id);
    } catch (err) {
      if (!scope.current()) return;
      showToast(err.message, 'error');
      setButtonIdle(btn);
      showScanLoader(false);
    }
  }

  function resetScanProgress() {
    document.getElementById('scan-progress-bar').style.width = '0%';
    document.getElementById('scan-progress-region').setAttribute('aria-valuenow', '0');
    document.getElementById('scan-progress-percent').textContent = '0%';
    document.getElementById('scan-status-message').textContent = 'Khởi tạo tác vụ quét…';
    showScanLoader(true);

    for (let i = 1; i <= 5; i++) {
      const dot = document.getElementById(`step-dot-${i}`);
      const label = document.getElementById(`step-label-${i}`);
      const stateEl = document.getElementById(`step-state-${i}`);
      dot.className = i === 1 ? 'step-indicator-dot active' : 'step-indicator-dot';
      label.style.color = i === 1 ? 'var(--text)' : 'var(--text-3)';
      stateEl.textContent = i === 1 ? 'Đang chạy' : 'Chờ';
    }
  }

  function pollScanProgress(runId) {
    if (state.scanPollTimer) clearInterval(state.scanPollTimer);

    const scope = projectScope();
    let polling = false;
    state.scanPollTimer = setInterval(async () => {
      if (polling || !scope.current()) return;
      polling = true;
      try {
        const res = await fetch(`/api/projects/${scope.slug}/scans/${runId}`);
        if (!res.ok) throw new Error("Không nhận được tiến độ quét. Xem Lịch sử hoặc thử lại.");
        const data = await res.json();
        if (!scope.current()) return;

        if (data.status === 'running' || data.status === 'queued') {
          const progressSim = Math.max(0, Math.min(100, Number(data.progress) || 0));
          document.getElementById('scan-progress-bar').style.width = `${progressSim}%`;
          document.getElementById('scan-progress-region').setAttribute('aria-valuenow', String(progressSim));
          document.getElementById('scan-progress-percent').textContent = `${progressSim}%`;
          document.getElementById('scan-status-message').textContent = data.message || 'Đang quét kiểm tra nhãn 3D…';

          const activeStep = progressSim < 30 ? 1 : progressSim < 55 ? 2 : 3;
          updateScanStepsUI(activeStep);
        } else if (data.status === 'done') {
          clearInterval(state.scanPollTimer);
          document.getElementById('scan-progress-bar').style.width = '100%';
          document.getElementById('scan-progress-region').setAttribute('aria-valuenow', '100');
          document.getElementById('scan-progress-percent').textContent = '100%';
          document.getElementById('scan-status-message').textContent = 'Quét hoàn tất thành công!';
          updateScanStepsUI(5, true);

          const btn = document.getElementById('btn-start-scan');
          setButtonIdle(btn);
          showScanLoader(false);

          showToast('Quá trình quét hoàn tất!', 'success');
          state.currentRun = data;
          renderRunResults(data);
          updateRecentScanCard(data);

          // Tự động chuyển qua tab Kết quả sau 800ms
          setTimeout(() => {
            if (scope.current()) window.location.hash = 'results';
          }, 800);
        } else if (data.status === 'failed') {
          clearInterval(state.scanPollTimer);
          document.getElementById('scan-status-message').textContent = `Lỗi: ${data.error || 'Quét thất bại'}`;
          const btn = document.getElementById('btn-start-scan');
          setButtonIdle(btn);
          showScanLoader(false);
          showToast(`Lỗi quét: ${data.error}`, 'error');
        }
      } catch (err) {
        if (!scope.current()) return;
        clearInterval(state.scanPollTimer);
        document.getElementById('scan-status-message').textContent = err.message;
        showToast(err.message, 'error');
        setButtonIdle(document.getElementById('btn-start-scan'));
        showScanLoader(false);
      } finally { polling = false; }
    }, 800);
  }

  function updateScanStepsUI(activeStep, allDone = false) {
    for (let i = 1; i <= 5; i++) {
      const dot = document.getElementById(`step-dot-${i}`);
      const label = document.getElementById(`step-label-${i}`);
      const stateEl = document.getElementById(`step-state-${i}`);

      if (allDone || i < activeStep) {
        dot.className = 'step-indicator-dot done';
        label.style.color = 'var(--text)';
        stateEl.textContent = 'Xong';
      } else if (i === activeStep) {
        dot.className = 'step-indicator-dot active';
        label.style.color = 'var(--text)';
        stateEl.textContent = 'Đang chạy';
      } else {
        dot.className = 'step-indicator-dot';
        label.style.color = 'var(--text-3)';
        stateEl.textContent = 'Chờ';
      }
    }
  }

  function updateRecentScanCard(runData) {
    const box = document.getElementById('recent-scan-box');
    if (!runData) {
      box.innerHTML = '<span class="mono" style="font-size: 13px;">Chưa có lượt quét nào</span>';
      return;
    }

    const sum = runData.summary || {};
    const timeStr = formatDateTime(sum.timestamp || runData.started_at);
    const gateClass = sum.gate_passed ? 'pill-badge pass' : 'pill-badge error';
    const gateLabel = sum.gate_passed ? 'ĐẠT' : 'KHÔNG ĐẠT';

    box.innerHTML = `
      <span class="mono" style="font-size: 13px;">${escapeHtml(timeStr)} · job #${escapeHtml(runData.job_id)}</span>
      <span style="color: var(--error);">${escapeHtml(sum.num_errors ?? 0)} Lỗi</span>
      <span style="color: var(--warn);">${escapeHtml(sum.num_warnings ?? 0)} Cảnh báo</span>
      <span class="${gateClass}">${gateLabel}</span>
      <a href="#results" class="btn btn-primary btn-sm" style="margin-left: auto;">Mở kết quả</a>
    `;
  }

  // --- 4. Tab Guideline (Guideline.dc.html) ---
  function setGuidelineDirty(dirty) {
    state.guidelineDirty = dirty;
    const bar = document.getElementById('guideline-save-bar');
    const note = document.getElementById('guideline-dirty-note');
    if (dirty) {
      bar.classList.add('dirty');
      note.textContent = 'Có thay đổi chưa lưu';
      note.style.color = 'var(--primary-text)';
    } else {
      bar.classList.remove('dirty');
      note.textContent = 'Guideline hợp lệ · đã lưu';
      note.style.color = 'var(--text-2)';
    }
  }

  function setGuidelineMode(mode) {
    if (mode !== state.guidelineMode && state.guidelineDirty) {
      if (!confirm('Bỏ thay đổi chưa lưu để chuyển chế độ?')) return;
      setGuidelineDirty(false);
      loadGuideline();
    }
    state.guidelineMode = mode;
    const formView = document.getElementById('guideline-form-view');
    const yamlView = document.getElementById('guideline-yaml-view');
    const btnForm = document.getElementById('btn-mode-form');
    const btnYaml = document.getElementById('btn-mode-yaml');

    if (mode === 'form') {
      formView.style.display = 'flex';
      yamlView.style.display = 'none';
      btnForm.className = 'btn btn-sm btn-primary';
      btnYaml.className = 'btn btn-sm btn-outline';
      btnYaml.style.border = '0';
    } else {
      formView.style.display = 'none';
      yamlView.style.display = 'block';
      btnForm.className = 'btn btn-sm btn-outline';
      btnForm.style.border = '0';
      btnYaml.className = 'btn btn-sm btn-primary';
    }
  }

  async function loadGuideline() {
    const scope = projectScope();
    if (!state.currentSlug || state.guidelineDirty) return;
    try {
      const res = await fetch(`/api/projects/${scope.slug}/guideline`);
      if (!scope.current()) return;
      if (!res.ok) throw new Error('Không thể tải guideline');
      const data = await res.json();
      if (!scope.current() || state.guidelineDirty) return;
      state.currentGuideline = data.config || {};
      document.getElementById('guideline-form-view').inert = false;
      document.getElementById('guideline-yaml-textarea').disabled = false;
      document.getElementById('guideline-yaml-textarea').value = data.yaml || '';

      populateGuidelineForm(state.currentGuideline);
      if (!scope.current()) return;
      setGuidelineDirty(false);
    } catch (err) {
      if (!scope.current()) return;
      showToast(err.message, 'error');
    }
  }

  function populateGuidelineForm(cfg) {
    // 1. Toggles luật
    const rules = cfg.rules || {};
    RULE_IDS.forEach((id) => {
      const enabled = rules[id] !== false;
      const sw = document.getElementById(`rule-${id.replace(/_/g, '-')}`);
      const lbl = document.getElementById(`label-rule-${id.replace(/_/g, '-')}`);
      if (sw) sw.setAttribute('aria-checked', enabled ? 'true' : 'false');
      if (lbl) lbl.textContent = enabled ? 'Bật' : 'Tắt';
    });

    // 2. Gate criteria
    const gate = cfg.gate || {};
    document.getElementById('gate-max-errors').value = gate.max_errors ?? 0;
    document.getElementById('gate-max-warnings').value = gate.max_warnings ?? 10;

    // 3. Floating thresholds
    const fl = cfg.floating || {};
    document.getElementById('fl-warning-m').value = fl.warning_m ?? 0.12;
    document.getElementById('fl-error-m').value = fl.error_m ?? 0.22;
    document.getElementById('fl-single-warning-m').value = fl.single_warning_m ?? 0.15;
    document.getElementById('fl-single-error-m').value = fl.single_error_m ?? 0.30;

    // 4. Size classes table
    const ranges = cfg.size?.manual_ranges || {};
    renderSizeClassesTable(ranges);
  }

  function renderSizeClassesTable(ranges) {
    const tbody = document.getElementById('size-classes-table-body');
    tbody.innerHTML = '';

    const entries = Object.entries(ranges);
    if (entries.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-3); padding: 18px;">Chưa cấu hình khoảng kích thước thủ công.</td></tr>';
      return;
    }

    entries.forEach(([cls, bounds]) => {
      const tr = document.createElement('tr');
      const lStr = bounds.length ? `${bounds.length[0]} – ${bounds.length[1]}` : '—';
      const wStr = bounds.width ? `${bounds.width[0]} – ${bounds.width[1]}` : '—';
      const hStr = bounds.height ? `${bounds.height[0]} – ${bounds.height[1]}` : '—';

      tr.innerHTML = `
        <td class="mono" style="padding-left: 20px;">${escapeHtml(cls)}</td>
        <td class="mono">${escapeHtml(lStr)}</td>
        <td class="mono">${escapeHtml(wStr)}</td>
        <td class="mono">${escapeHtml(hStr)}</td>
        <td style="text-align: right; padding-right: 20px;">
          <button class="btn btn-outline btn-sm btn-delete-class" data-cls="${escapeHtml(cls)}" style="color: var(--error);">Xóa</button>
        </td>
      `;

      tr.querySelector('.btn-delete-class').addEventListener('click', () => {
        delete ranges[cls];
        renderSizeClassesTable(ranges);
        setGuidelineDirty(true);
      });

      tbody.appendChild(tr);
    });
  }

  function handleAddSizeClass() {
    const clsName = prompt('Nhập tên class mới (ví dụ: bus, trailer, van):');
    if (!clsName || !clsName.trim()) return;
    const clean = clsName.trim().toLowerCase();

    if (!state.currentGuideline) state.currentGuideline = {};
    if (!state.currentGuideline.size) state.currentGuideline.size = {};
    if (!state.currentGuideline.size.manual_ranges) state.currentGuideline.size.manual_ranges = {};

    state.currentGuideline.size.manual_ranges[clean] = {
      length: [2.0, 5.0],
      width: [1.5, 2.5],
      height: [1.2, 2.0],
    };

    renderSizeClassesTable(state.currentGuideline.size.manual_ranges);
    setGuidelineDirty(true);
  }

  async function handleResetGuideline() {
    const scope = projectScope();
    if (!confirm('Khôi phục toàn bộ Guideline về cấu hình mặc định?')) return;
    try {
      const res = await fetch(`/api/projects/${scope.slug}/guideline/reset`, { method: 'POST' });
      if (!scope.current()) return;
      if (!res.ok) throw new Error('Không thể khôi phục guideline');
      showToast('Đã khôi phục guideline mặc định', 'success');
      setGuidelineDirty(false);
      await loadGuideline();
    } catch (err) {
      if (!scope.current()) return;
      showToast(err.message, 'error');
    }
  }

  async function handleSaveGuideline() {
    const scope = projectScope();
    if (!state.currentSlug) return;
    if (!state.currentGuideline) { showToast('Đợi Guideline tải xong trước khi lưu.', 'error'); return; }
    const btn = document.getElementById('btn-save-guideline');
    btn.disabled = true;

    try {
      let payload = {};
      if (state.guidelineMode === 'yaml') {
        payload = { yaml: document.getElementById('guideline-yaml-textarea').value };
      } else {
        // Thu thập dữ liệu từ Form
        const rules = Object.fromEntries(RULE_IDS.map((id) => [
          id, document.getElementById(`rule-${id.replace(/_/g, '-')}`).getAttribute('aria-checked') === 'true',
        ]));

        const gate = {
          max_errors: parseInt(document.getElementById('gate-max-errors').value, 10) || 0,
          max_warnings: parseInt(document.getElementById('gate-max-warnings').value, 10) || 0,
        };

        const fl = {
          warning_m: Number(document.getElementById('fl-warning-m').value),
          error_m: Number(document.getElementById('fl-error-m').value),
          single_warning_m: Number(document.getElementById('fl-single-warning-m').value),
          single_error_m: Number(document.getElementById('fl-single-error-m').value),
        };

        const currentManual = state.currentGuideline?.size?.manual_ranges || {};
        const configObj = {
          ...(state.currentGuideline || {}),
          rules,
          gate,
          floating: { ...(state.currentGuideline?.floating || {}), ...fl },
          size: {
            ...(state.currentGuideline?.size || {}),
            manual_ranges: currentManual,
          },
        };
        payload = { config: configObj };
      }

      const res = await fetch(`/api/projects/${scope.slug}/guideline`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json();
      if (!scope.current()) return;
        throw new Error(errorDetail(err.detail, 'Không thể lưu guideline'));
      }

      if (!scope.current()) return;
      setGuidelineDirty(false);
      showToast('Đã lưu cấu hình Guideline thành công', 'success');
      await loadGuideline();
    } catch (err) {
      if (!scope.current()) return;
      showToast(err.message, 'error');
    } finally {
      btn.disabled = false;
    }
  }

  // --- 5. Tab Kết nối CVAT (Connection View) ---
  async function loadConnectionTab() {
    const scope = projectScope();
    if (!state.currentSlug) return;
    try {
      const res = await fetch(`/api/projects/${scope.slug}`);
      if (!scope.current()) return;
      if (!res.ok) throw new Error('Không thể tải thông tin kết nối');
      const p = await res.json();
      if (!scope.current()) return;

      document.getElementById('conn-cvat-url').value = p.cvat_url || '';
      document.getElementById('conn-cvat-token').value = '';
      document.getElementById('conn-nuscenes-root').value = p.nuscenes_root || '';
      document.getElementById('conn-export-dirs').value = (p.export_dirs || []).join(';');
    } catch (err) {
      if (!scope.current()) return;
      showToast(err.message, 'error');
    }
  }

  async function checkCvatConnection() {
    const scope = projectScope();
    const msg = document.getElementById('cvat-test-result-msg');
    msg.innerHTML = `<span class="inline-loading">${loaderSvg(20)}<span>Đang kiểm tra kết nối tới CVAT…</span></span>`;
    msg.style.color = 'var(--text-2)';

    try {
      const res = await fetch(`/api/projects/${scope.slug}/cvat/check`);
      const data = await res.json();
      if (!scope.current()) return;
      if (data.connected) {
        msg.textContent = `Kết nối thành công! Phiên bản CVAT: ${data.version || 'Không xác định'}`;
        msg.style.color = 'var(--success)';
        checkCvatConnectionStatus();
      } else {
        msg.textContent = `Thất bại: ${data.error || 'Không kết nối được'}`;
        msg.style.color = 'var(--error)';
      }
    } catch (err) {
      if (!scope.current()) return;
      msg.textContent = `Lỗi mạng: ${err.message}`;
      msg.style.color = 'var(--error)';
    }
  }

  async function handleSaveConnectionSettings() {
    const scope = projectScope();
    if (!state.currentSlug) return;
    const cvatUrl = document.getElementById('conn-cvat-url').value.trim();
    const token = document.getElementById('conn-cvat-token').value.trim();
    const nuRoot = document.getElementById('conn-nuscenes-root').value.trim();
    const exportDirsStr = document.getElementById('conn-export-dirs').value.trim();

    const exportDirs = exportDirsStr
      ? exportDirsStr.split(';').map((s) => s.trim()).filter(Boolean)
      : [];

    const body = {
      cvat_url: cvatUrl || 'http://localhost:8080',
      nuscenes_root: nuRoot,
      export_dirs: exportDirs,
    };
    if (token) body.cvat_token = token;

    try {
      const res = await fetch(`/api/projects/${scope.slug}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await res.json();
      if (!scope.current()) return;
        throw new Error(errorDetail(err.detail, 'Không thể lưu thông tin kết nối'));
      }

      if (!scope.current()) return;
      showToast('Đã lưu cấu hình kết nối thành công', 'success');
      checkCvatConnectionStatus();
      loadConnectionTab();
    } catch (err) {
      if (!scope.current()) return;
      showToast(err.message, 'error');
    }
  }

  // --- 6. Tab Lịch sử (History View - LichSu.dc.html) ---
  async function handleLearn() {
    if (!state.currentSlug) return;
    const btn = document.getElementById('btn-learn');
    setButtonBusy(btn, 'Đang học…');
    try {
      const res = await fetch(`/api/projects/${encodeURIComponent(state.currentSlug)}/learn`, { method: 'POST' });
      if (!res.ok) throw new Error((await res.json()).detail || 'Không học được');
      const data = await res.json();
      const box = document.getElementById('learn-report');
      box.textContent = data.report;
      box.style.display = 'block';
      showToast('Đã học từ kết luận đã duyệt; áp dụng từ lần quét sau.', 'success');
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      setButtonIdle(btn);
    }
  }

  async function loadHistoryTab() {
    const scope = projectScope();
    if (!state.currentSlug) return;
    try {
      const res = await fetch(`/api/projects/${scope.slug}/scans`);
      if (!scope.current()) return;
      if (!res.ok) throw new Error('Không thể tải lịch sử');
      const runs = await res.json();
      if (!scope.current()) return;
      renderHistoryRuns(runs);
      renderHistoryChart(runs);
    } catch (err) {
      if (!scope.current()) return;
      showToast(err.message, 'error');
    }
  }

  function renderHistoryRuns(runs) {
    const tbody = document.getElementById('history-table-body');
    tbody.innerHTML = '';

    if (!runs || runs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-3); padding: 32px;">Chưa có lịch sử lần quét nào.</td></tr>';
      return;
    }

    runs.forEach((r) => {
      const sum = r.summary || {};
      const tr = document.createElement('tr');
      const timeStr = formatDateTime(sum.timestamp || r.started_at);
      const isPass = !!sum.gate_passed;
      const gateClass = isPass ? 'pill-badge pass' : 'pill-badge error';
      const gateText = r.status === 'done' ? (isPass ? 'Đạt' : 'Không đạt') : ({queued:'Đang chờ', running:'Đang quét', failed:'Thất bại'}[r.status] || 'Chưa có kết quả');

      tr.innerHTML = `
        <td class="mono" style="padding-left: 20px;">${escapeHtml(timeStr)}</td>
        <td class="mono">#${escapeHtml(r.job_id)}</td>
        <td style="color: var(--text-2);">${sum.flagged ? 'Quét & gắn cờ' : 'Quét'}</td>
        <td class="mono" style="color: var(--error);">${escapeHtml(sum.num_errors ?? 0)}</td>
        <td class="mono" style="color: var(--warn);">${escapeHtml(sum.num_warnings ?? 0)}</td>
        <td><span class="${gateClass}">${gateText}</span></td>
        <td style="text-align: right; padding-right: 20px;">
          <button class="btn btn-outline btn-sm btn-view-run" ${r.status === 'done' ? '' : 'disabled'} data-id="${escapeHtml(r.run_id)}" style="color: var(--primary-text);">Xem kết quả</button>
        </td>
      `;

      tr.querySelector('.btn-view-run').addEventListener('click', async () => {
        await loadRunDetails(r.run_id);
        window.location.hash = 'results';
      });

      tbody.appendChild(tr);
    });
  }

  function renderHistoryChart(runs) {
    runs = (runs || []).filter(r => r.status === 'done');
    const emptyBox = document.getElementById('history-chart-empty');
    const svgWrapper = document.getElementById('history-chart-svg-wrapper');
    const svg = document.getElementById('history-svg-chart');

    if (!runs || runs.length === 0) {
      emptyBox.style.display = 'block';
      svgWrapper.style.display = 'none';
      return;
    }

    emptyBox.style.display = 'none';
    svgWrapper.style.display = 'block';
    svg.innerHTML = '';

    // Lấy tối đa 8 lần quét gần nhất theo thứ tự thời gian tăng dần
    const chartRuns = runs.slice(0, 8).reverse();
    const maxTotal = Math.max(
      1,
      ...chartRuns.map((r) => ((r.summary?.num_errors || 0) + (r.summary?.num_warnings || 0)))
    );

    const svgWidth = 800;
    const svgHeight = 200;
    const chartH = 140; // Chiều cao tối đa của cột
    const bottomY = 160; // Trục hoành

    const colWidth = 44;
    const numCols = chartRuns.length;
    const spacing = numCols > 1 ? (svgWidth - 120 - numCols * colWidth) / (numCols - 1) : 0;
    const startX = numCols === 1 ? svgWidth / 2 - colWidth / 2 : 60;

    // Đường kẻ trục hoành
    const axis = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    axis.setAttribute('x1', '20');
    axis.setAttribute('y1', String(bottomY));
    axis.setAttribute('x2', '780');
    axis.setAttribute('y2', String(bottomY));
    axis.setAttribute('stroke', 'var(--border-strong)');
    axis.setAttribute('stroke-width', '1');
    svg.appendChild(axis);

    chartRuns.forEach((r, idx) => {
      const sum = r.summary || {};
      const err = sum.num_errors || 0;
      const warn = sum.num_warnings || 0;
      const total = err + warn;

      const totalH = Math.max(4, Math.round((total / maxTotal) * chartH));
      const errH = total > 0 ? Math.round((err / total) * totalH) : 0;
      const warnH = totalH - errH;

      const x = startX + idx * (colWidth + spacing);
      const colTopY = bottomY - totalH;

      // Nhãn tổng số trên đầu cột
      const totalText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      totalText.setAttribute('x', String(x + colWidth / 2));
      totalText.setAttribute('y', String(colTopY - 6));
      totalText.setAttribute('text-anchor', 'middle');
      totalText.setAttribute('fill', 'var(--text-2)');
      totalText.setAttribute('font-family', 'IBM Plex Mono, monospace');
      totalText.setAttribute('font-size', '11');
      totalText.textContent = String(total);
      svg.appendChild(totalText);

      // Cột Cảnh báo (nửa trên)
      if (warnH > 0) {
        const warnRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        warnRect.setAttribute('x', String(x));
        warnRect.setAttribute('y', String(colTopY));
        warnRect.setAttribute('width', String(colWidth));
        warnRect.setAttribute('height', String(warnH));
        warnRect.setAttribute('fill', 'var(--warn-bar)');
        warnRect.setAttribute('rx', '3');
        svg.appendChild(warnRect);
      }

      // Cột Lỗi (nửa dưới)
      if (errH > 0) {
        const errRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        errRect.setAttribute('x', String(x));
        errRect.setAttribute('y', String(bottomY - errH));
        errRect.setAttribute('width', String(colWidth));
        errRect.setAttribute('height', String(errH));
        errRect.setAttribute('fill', 'var(--error)');
        errRect.setAttribute('rx', errH === totalH ? '3' : '0');
        svg.appendChild(errRect);
      }

      // Nhãn thời gian dưới trục hoành
      const timeText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      timeText.setAttribute('x', String(x + colWidth / 2));
      timeText.setAttribute('y', String(bottomY + 18));
      timeText.setAttribute('text-anchor', 'middle');
      timeText.setAttribute('fill', 'var(--text-3)');
      timeText.setAttribute('font-size', '11');
      timeText.setAttribute('font-family', 'IBM Plex Mono, monospace');
      const dStr = sum.timestamp || r.started_at;
      timeText.textContent = dStr ? formatShortDate(dStr) : `#${idx + 1}`;
      svg.appendChild(timeText);
    });
  }

  // --- Tiện ích định dạng ---
  function formatDateTime(iso) {
    if (!iso) return '—';
    try {
      const d = new Date(iso);
      if (isNaN(d.getTime())) return iso;
      const hh = String(d.getHours()).padStart(2, '0');
      const mm = String(d.getMinutes()).padStart(2, '0');
      const DD = String(d.getDate()).padStart(2, '0');
      const MM = String(d.getMonth() + 1).padStart(2, '0');
      return `${hh}:${mm}, ${DD}/${MM}`;
    } catch (_) {
      return iso;
    }
  }

  function formatShortDate(iso) {
    if (!iso) return '—';
    try {
      const d = new Date(iso);
      if (isNaN(d.getTime())) return iso;
      const DD = String(d.getDate()).padStart(2, '0');
      const MM = String(d.getMonth() + 1).padStart(2, '0');
      return `${DD}/${MM}`;
    } catch (_) {
      return iso;
    }
  }

  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function safeHttpLink(value) {
    try {
      const url = new URL(value);
      return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.href : '';
    } catch (_) { return ''; }
  }

  function findingFixTip(f) {
    if (f.rule === 'floating' && /\(lún\)|nằm dưới mặt đất/i.test(f.message || '')) {
      return 'Nâng đáy box lên cho chạm mặt đường, đối chiếu ảnh camera trước và các frame lân cận của track.';
    }
    return RULE_FIX_TIPS[f.rule] || DEFAULT_FIX_TIP;
  }
})();
