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
    'track.long_interpolation': 'Chèn thêm keyframe vào giữa khoảng nội suy dài để box bám sát chuyển động của vật.'
  };

  const DEFAULT_FIX_TIP = 'Kiểm tra lại bounding box và nhãn trên CVAT theo hướng dẫn gán nhãn của dự án.';

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
      default:
        return `${fixed(n, 2)} m`;
    }
  }

  // --- State toàn cục ---
  const state = {
    projects: [],
    currentSlug: null,
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

    // Trạng thái dirty của Guideline
    guidelineDirty: false,
    guidelineMode: 'form', // 'form' hoặc 'yaml'
  };

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
    if (m) m.classList.add('open');
  }

  function closeModal(id) {
    const m = document.getElementById(id);
    if (m) m.classList.remove('open');
  }

  // --- Khởi động ứng dụng khi DOM sẵn sàng ---
  document.addEventListener('DOMContentLoaded', () => {
    applyTheme(state.theme);
    setupEventListeners();
    handleHashNavigation();
    loadProjects();
  });

  // --- Thiết lập các bộ lắng nghe sự kiện ---
  function setupEventListeners() {
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
      populatePresetOptions();
      openModal('modal-create-proj');
    });
    document.getElementById('btn-submit-create-proj').addEventListener('click', handleCreateProject);

    // Modal Xóa dự án (bắt buộc gõ lại tên)
    document.getElementById('btn-open-delete-proj').addEventListener('click', () => {
      projectMenu.classList.remove('open');
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
        const lastSlug = state.currentSlug || state.projects[0].slug;
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
    state.currentSlug = slug;
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
        throw new Error(err.detail || 'Không thể tạo dự án');
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
        throw new Error(err.detail || 'Không thể xóa dự án');
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
      const res = await fetch(`/api/projects/${state.currentSlug}/cvat/check`);
      const data = await res.json();
      if (data.connected) {
        dot.className = 'status-dot';
        text.textContent = `CVAT ${data.version || ''} · đã kết nối`;
      } else {
        dot.className = 'status-dot disconnected';
        text.textContent = 'CVAT · Mất kết nối';
      }
    } catch (_) {
      dot.className = 'status-dot disconnected';
      text.textContent = 'CVAT · Không kết nối được';
    }
  }

  // --- 2. Tab Kết quả (Results View - Main.dc.html) ---
  async function loadLatestRun() {
    if (!state.currentSlug) return;
    try {
      const res = await fetch(`/api/projects/${state.currentSlug}/scans`);
      if (res.ok) {
        const runs = await res.json();
        if (runs.length > 0) {
          await loadRunDetails(runs[0].run_id);
          updateRecentScanCard(runs[0]);
          return;
        }
      }
      showEmptyResults();
    } catch (_) {
      showEmptyResults();
    }
  }

  function showEmptyResults() {
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
    try {
      const res = await fetch(`/api/projects/${state.currentSlug}/scans/${runId}`);
      if (!res.ok) throw new Error('Không thể nạp chi tiết lần quét');
      const data = await res.json();
      state.currentRun = data;
      renderRunResults(data);
    } catch (err) {
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
    const runTimeStr = formatDateTime(sum.timestamp || runData.created_at);
    document.getElementById('results-header-subtitle').textContent =
      `Quét lúc ${runTimeStr} · ${sum.num_boxes ?? 0} box · guideline của dự án`;

    // Cổng kiểm soát (Gate Banner)
    const gateBanner = document.getElementById('gate-banner-strip');
    const gateTitle = document.getElementById('gate-verdict-title');
    const gateDesc = document.getElementById('gate-verdict-desc');

    if (sum.gate_passed) {
      gateBanner.className = 'gate-banner-strip pass';
      gateTitle.textContent = 'Đạt cổng kiểm soát';
      gateDesc.textContent = `${sum.num_errors ?? 0} Lỗi · ${sum.num_warnings ?? 0} Cảnh báo. Các chỉ số đều nằm trong ngưỡng quy định.`;
    } else {
      gateBanner.className = 'gate-banner-strip fail';
      gateTitle.textContent = 'Không đạt cổng kiểm soát';
      const reasons = sum.gate_reasons && sum.gate_reasons.length > 0 ? sum.gate_reasons.join(' · ') : 'Vượt ngưỡng cho phép';
      gateDesc.textContent = `${reasons}. Sửa các mục Lỗi trên CVAT rồi quét lại.`;
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
        <td><span class="pill-badge ${sevClass}">${sevLabel}</span></td>
        <td class="mono">#${f.frame}</td>
        <td class="mono">${f.track_id !== null && f.track_id !== undefined ? `#${f.track_id}` : '—'}</td>
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

  function renderDetailDrawer(f) {
    if (!f) return;
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
    document.getElementById('detail-message-desc').textContent = f.message || '—';

    // Gợi ý cách sửa từ từ điển A13
    const fixTip = RULE_FIX_TIPS[f.rule] || DEFAULT_FIX_TIP;
    document.getElementById('detail-fix-hint').textContent = fixTip;

    // Nút mở CVAT
    const cvatBtn = document.getElementById('detail-btn-cvat-link');
    if (f.cvat_link) {
      cvatBtn.href = f.cvat_link;
      cvatBtn.style.display = 'flex';
    } else {
      cvatBtn.style.display = 'none';
    }
  }

  function clearDetailDrawer() {
    document.getElementById('detail-sev-badge').textContent = '—';
    document.getElementById('detail-rule-code').textContent = '—';
    document.getElementById('detail-title-text').textContent = 'Chưa chọn mục';
    document.getElementById('detail-frame-val').textContent = '—';
    document.getElementById('detail-track-class-val').textContent = '—';
    document.getElementById('detail-measured-val').textContent = '—';
    document.getElementById('detail-threshold-val').textContent = '—';
    document.getElementById('detail-message-desc').textContent = '—';
    document.getElementById('detail-fix-hint').textContent = '—';
    document.getElementById('detail-btn-cvat-link').style.display = 'none';
  }

  function generateFindingTitle(f) {
    if (f.rule === 'floating') {
      if ((f.message || '').includes('lún')) return 'Box lún so với mặt đất';
      return 'Box lơ lửng so với mặt đất';
    }
    if (f.rule === 'floating.no_evidence') return 'Không đủ điểm mặt đất';
    if (f.rule === 'size.class_range') return 'Kích thước ngoài khoảng của class';
    if (f.rule === 'size.in_track') return 'Kích thước bất thường trong track';
    if (f.rule === 'track.jump') return 'Track nhảy vị trí';
    if (f.rule === 'track.split_id') return 'Nghi tách ID track';
    if (f.rule === 'track.long_interpolation') return 'Khoảng nội suy dài';
    return f.message ? f.message.split(';')[0] : 'Phát hiện bất thường';
  }

  // --- Quét lại và gắn cờ (Re-flag) ---
  async function handleReFlagScan() {
    if (!state.currentRun || !state.currentSlug) return;
    const btn = document.getElementById('btn-re-flag-cvat');
    setButtonBusy(btn, 'Đang khởi động…');

    try {
      showToast('Đang khởi động quét lại và gắn cờ lên CVAT...', 'info');
      const res = await fetch(`/api/projects/${state.currentSlug}/scans/${state.currentRun.run_id}/flag`, {
        method: 'POST',
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Không thể quét lại và gắn cờ');
      }

      const result = await res.json();
      showToast(result.message || 'Đang quét lại và gắn cờ...', 'info');
      window.location.hash = 'scan';
      resetScanProgress();
      pollScanProgress(result.run_id);
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      setButtonIdle(btn);
    }
  }

  // --- 3. Tab Quét (Scan View - Quet.dc.html) ---
  async function fetchCvatTasks() {
    if (!state.currentSlug) return;
    const taskSelect = document.getElementById('select-cvat-task');
    const refreshBtn = document.getElementById('btn-refresh-tasks');
    setButtonBusy(refreshBtn, 'Đang tải');
    taskSelect.innerHTML = '<option value="">Đang tải Task từ CVAT...</option>';

    try {
      const res = await fetch(`/api/projects/${state.currentSlug}/cvat/tasks`);
      if (!res.ok) throw new Error('Không thể lấy danh sách Task');
      const data = await res.json();
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
        opt.textContent = `#${j.id} · ${j.stage || 'annotation'} · ${j.frame_count || 0} frame`;
        jobSelect.appendChild(opt);
      });

      if (task.jobs.length > 0) {
        jobSelect.value = task.jobs[0].id;
      }
    }
  }

  async function handleStartScan() {
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
      const res = await fetch(`/api/projects/${state.currentSlug}/scans`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: parseInt(jobId, 10), flag }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Không thể bắt đầu quét');
      }

      const scanInfo = await res.json();
      pollScanProgress(scanInfo.run_id);
    } catch (err) {
      showToast(err.message, 'error');
      setButtonIdle(btn);
      showScanLoader(false);
    }
  }

  function resetScanProgress() {
    document.getElementById('scan-progress-bar').style.width = '10%';
    document.getElementById('scan-progress-percent').textContent = '10%';
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

    let progressSim = 15;
    state.scanPollTimer = setInterval(async () => {
      try {
        const res = await fetch(`/api/projects/${state.currentSlug}/scans/${runId}`);
        if (!res.ok) return;
        const data = await res.json();

        if (data.status === 'running' || data.status === 'queued') {
          progressSim = Math.min(progressSim + 15, 85);
          document.getElementById('scan-progress-bar').style.width = `${progressSim}%`;
          document.getElementById('scan-progress-percent').textContent = `${progressSim}%`;
          document.getElementById('scan-status-message').textContent = data.message || 'Đang quét kiểm tra nhãn 3D…';

          const activeStep = progressSim < 30 ? 1 : progressSim < 55 ? 2 : 3;
          updateScanStepsUI(activeStep);
        } else if (data.status === 'done') {
          clearInterval(state.scanPollTimer);
          document.getElementById('scan-progress-bar').style.width = '100%';
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
            window.location.hash = 'results';
          }, 800);
        } else if (data.status === 'failed') {
          clearInterval(state.scanPollTimer);
          document.getElementById('scan-status-message').textContent = `Lỗi: ${data.error || 'Quét thất bại'}`;
          const btn = document.getElementById('btn-start-scan');
          setButtonIdle(btn);
          showScanLoader(false);
          showToast(`Lỗi quét: ${data.error}`, 'error');
        }
      } catch (_) {}
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
    const timeStr = formatDateTime(sum.timestamp || runData.created_at);
    const gateClass = sum.gate_passed ? 'pill-badge pass' : 'pill-badge error';
    const gateLabel = sum.gate_passed ? 'ĐẠT' : 'KHÔNG ĐẠT';

    box.innerHTML = `
      <span class="mono" style="font-size: 13px;">${timeStr} · job #${runData.job_id}</span>
      <span style="color: var(--error);">${sum.num_errors ?? 0} Lỗi</span>
      <span style="color: var(--warn);">${sum.num_warnings ?? 0} Cảnh báo</span>
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
    if (!state.currentSlug) return;
    try {
      const res = await fetch(`/api/projects/${state.currentSlug}/guideline`);
      if (!res.ok) throw new Error('Không thể tải guideline');
      const data = await res.json();
      state.currentGuideline = data.config || {};
      document.getElementById('guideline-yaml-textarea').value = data.yaml || '';

      populateGuidelineForm(state.currentGuideline);
      setGuidelineDirty(false);
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  function populateGuidelineForm(cfg) {
    // 1. Toggles luật
    const rules = cfg.rules || {};
    const ruleIds = ['floating', 'size_class_range', 'size_in_track', 'track_jump', 'track_split_id', 'track_long_interpolation'];
    ruleIds.forEach((id) => {
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
    const ranges = (cfg.size && cfg.size.class_range && cfg.size.class_range.manual_ranges) || {};
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
        <td class="mono">${lStr}</td>
        <td class="mono">${wStr}</td>
        <td class="mono">${hStr}</td>
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
    if (!state.currentGuideline.size.class_range) state.currentGuideline.size.class_range = {};
    if (!state.currentGuideline.size.class_range.manual_ranges) state.currentGuideline.size.class_range.manual_ranges = {};

    state.currentGuideline.size.class_range.manual_ranges[clean] = {
      length: [2.0, 5.0],
      width: [1.5, 2.5],
      height: [1.2, 2.0],
    };

    renderSizeClassesTable(state.currentGuideline.size.class_range.manual_ranges);
    setGuidelineDirty(true);
  }

  async function handleResetGuideline() {
    if (!confirm('Khôi phục toàn bộ Guideline về cấu hình mặc định?')) return;
    try {
      const res = await fetch(`/api/projects/${state.currentSlug}/guideline/reset`, { method: 'POST' });
      if (!res.ok) throw new Error('Không thể khôi phục guideline');
      showToast('Đã khôi phục guideline mặc định', 'success');
      await loadGuideline();
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  async function handleSaveGuideline() {
    if (!state.currentSlug) return;
    const btn = document.getElementById('btn-save-guideline');
    btn.disabled = true;

    try {
      let payload = {};
      if (state.guidelineMode === 'yaml') {
        payload = { yaml: document.getElementById('guideline-yaml-textarea').value };
      } else {
        // Thu thập dữ liệu từ Form
        const rules = {
          floating: document.getElementById('rule-floating').getAttribute('aria-checked') === 'true',
          size_class_range: document.getElementById('rule-size-class-range').getAttribute('aria-checked') === 'true',
          size_in_track: document.getElementById('rule-size-in-track').getAttribute('aria-checked') === 'true',
          track_jump: document.getElementById('rule-track-jump').getAttribute('aria-checked') === 'true',
          track_split_id: document.getElementById('rule-track-split-id').getAttribute('aria-checked') === 'true',
          track_long_interpolation: document.getElementById('rule-track-long-interpolation').getAttribute('aria-checked') === 'true',
        };

        const gate = {
          max_errors: parseInt(document.getElementById('gate-max-errors').value, 10) || 0,
          max_warnings: parseInt(document.getElementById('gate-max-warnings').value, 10) || 0,
        };

        const fl = {
          warning_m: parseFloat(document.getElementById('fl-warning-m').value) || 0.12,
          error_m: parseFloat(document.getElementById('fl-error-m').value) || 0.22,
          single_warning_m: parseFloat(document.getElementById('fl-single-warning-m').value) || 0.15,
          single_error_m: parseFloat(document.getElementById('fl-single-error-m').value) || 0.30,
        };

        const currentManual = (state.currentGuideline?.size?.class_range?.manual_ranges) || {};
        const configObj = {
          ...(state.currentGuideline || {}),
          rules,
          gate,
          floating: { ...(state.currentGuideline?.floating || {}), ...fl },
          size: {
            ...(state.currentGuideline?.size || {}),
            class_range: {
              ...(state.currentGuideline?.size?.class_range || {}),
              manual_ranges: currentManual,
            },
          },
        };
        payload = { config: configObj };
      }

      const res = await fetch(`/api/projects/${state.currentSlug}/guideline`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Không thể lưu guideline');
      }

      setGuidelineDirty(false);
      showToast('Đã lưu cấu hình Guideline thành công', 'success');
      await loadGuideline();
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      btn.disabled = false;
    }
  }

  // --- 5. Tab Kết nối CVAT (Connection View) ---
  async function loadConnectionTab() {
    if (!state.currentSlug) return;
    try {
      const res = await fetch(`/api/projects/${state.currentSlug}`);
      if (!res.ok) throw new Error('Không thể tải thông tin kết nối');
      const p = await res.json();

      document.getElementById('conn-cvat-url').value = p.cvat_url || '';
      document.getElementById('conn-cvat-token').value = '';
      document.getElementById('conn-nuscenes-root').value = p.nuscenes_root || '';
      document.getElementById('conn-export-dirs').value = (p.export_dirs || []).join(';');
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  async function checkCvatConnection() {
    const msg = document.getElementById('cvat-test-result-msg');
    msg.innerHTML = `<span class="inline-loading">${loaderSvg(20)}<span>Đang kiểm tra kết nối tới CVAT…</span></span>`;
    msg.style.color = 'var(--text-2)';

    try {
      const res = await fetch(`/api/projects/${state.currentSlug}/cvat/check`);
      const data = await res.json();
      if (data.connected) {
        msg.textContent = `Kết nối thành công! Phiên bản CVAT: ${data.version || 'Không xác định'}`;
        msg.style.color = 'var(--success)';
        checkCvatConnectionStatus();
      } else {
        msg.textContent = `Thất bại: ${data.error || 'Không kết nối được'}`;
        msg.style.color = 'var(--error)';
      }
    } catch (err) {
      msg.textContent = `Lỗi mạng: ${err.message}`;
      msg.style.color = 'var(--error)';
    }
  }

  async function handleSaveConnectionSettings() {
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
      const res = await fetch(`/api/projects/${state.currentSlug}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Không thể lưu thông tin kết nối');
      }

      showToast('Đã lưu cấu hình kết nối thành công', 'success');
      checkCvatConnectionStatus();
      loadConnectionTab();
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  // --- 6. Tab Lịch sử (History View - LichSu.dc.html) ---
  async function loadHistoryTab() {
    if (!state.currentSlug) return;
    try {
      const res = await fetch(`/api/projects/${state.currentSlug}/scans`);
      if (!res.ok) throw new Error('Không thể tải lịch sử');
      const runs = await res.json();
      renderHistoryRuns(runs);
      renderHistoryChart(runs);
    } catch (err) {
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
      const timeStr = formatDateTime(sum.timestamp || r.created_at);
      const isPass = !!sum.gate_passed;
      const gateClass = isPass ? 'pill-badge pass' : 'pill-badge error';
      const gateText = isPass ? 'Đạt' : 'Không đạt';

      tr.innerHTML = `
        <td class="mono" style="padding-left: 20px;">${timeStr}</td>
        <td class="mono">#${r.job_id}</td>
        <td style="color: var(--text-2);">${sum.flagged ? 'Quét & gắn cờ' : 'Quét'}</td>
        <td class="mono" style="color: var(--error);">${sum.num_errors ?? 0}</td>
        <td class="mono" style="color: var(--warn);">${sum.num_warnings ?? 0}</td>
        <td><span class="${gateClass}">${gateText}</span></td>
        <td style="text-align: right; padding-right: 20px;">
          <button class="btn btn-outline btn-sm btn-view-run" data-id="${r.run_id}" style="color: var(--primary-text);">Xem kết quả</button>
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
      const dStr = sum.timestamp || r.created_at;
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
})();
