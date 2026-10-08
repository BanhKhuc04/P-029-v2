/**
 * PointSnap 3D — Trình điều khiển giao diện Single Page Application (A11)
 */

(function () {
  'use strict';

  // --- State Toàn cục ---
  const state = {
    projects: [],
    currentSlug: null,
    currentProject: null,
    currentGuideline: null,
    currentRun: null,
    tasksList: [],
    scanPollTimer: null,
    theme: localStorage.getItem('pointsnap_theme') || 'dark',
  };

  // --- Khởi tạo khi load trang ---
  document.addEventListener('DOMContentLoaded', () => {
    applyTheme(state.theme);
    setupEventListeners();
    loadProjects();
  });

  // --- Quản lý Theme sáng/tối ---
  function applyTheme(theme) {
    state.theme = theme;
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('pointsnap_theme', theme);
  }

  // --- Toast Notifications ---
  function showToast(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }

  // --- Gán Event Listeners ---
  function setupEventListeners() {
    // Chuyển Theme
    document.getElementById('btn-toggle-theme').addEventListener('click', () => {
      applyTheme(state.theme === 'dark' ? 'light' : 'dark');
    });

    // Chuyển Tab
    document.querySelectorAll('.tab-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const targetTab = btn.getAttribute('data-tab');
        window.location.hash = targetTab;
        switchTab(targetTab);
      });
    });

    window.addEventListener('hashchange', () => {
      if (window.location.hash) {
        switchTab(window.location.hash.substring(1));
      }
    });

    // Modal Tạo dự án
    document.getElementById('btn-open-create-proj').addEventListener('click', () => {
      populatePresetOptions();
      openModal('modal-create-proj');
    });
    document.getElementById('btn-submit-create-proj').addEventListener('click', handleCreateProject);

    // Modal Xóa dự án (Điểm 5 Mục 6)
    document.getElementById('btn-open-delete-proj').addEventListener('click', () => {
      if (!state.currentProject) return;
      document.getElementById('delete-proj-target-name').textContent = state.currentProject.name;
      const confirmInput = document.getElementById('delete-proj-confirm-input');
      confirmInput.value = '';
      document.getElementById('btn-confirm-delete-proj').disabled = true;
      openModal('modal-delete-proj');
    });

    document.getElementById('delete-proj-confirm-input').addEventListener('input', (e) => {
      const btn = document.getElementById('btn-confirm-delete-proj');
      btn.disabled = e.target.value.trim() !== state.currentProject.name;
    });

    document.getElementById('btn-confirm-delete-proj').addEventListener('click', handleDeleteProject);

    // Đóng Modals
    document.querySelectorAll('[data-close]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const modalId = btn.getAttribute('data-close');
        closeModal(modalId);
      });
    });

    // Tab Quét (Scan)
    document.getElementById('btn-refresh-tasks').addEventListener('click', fetchCvatTasks);
    document.getElementById('select-cvat-task').addEventListener('change', handleTaskChange);
    document.getElementById('btn-start-scan').addEventListener('click', handleStartScan);

    // Tab Kết quả (Results)
    document.getElementById('btn-re-flag-cvat').addEventListener('click', handleReFlagScan);
    document.getElementById('filter-search-box').addEventListener('input', renderFindingsTable);
    document.getElementById('filter-severity').addEventListener('change', renderFindingsTable);
    document.getElementById('filter-error-type').addEventListener('change', renderFindingsTable);
    document.getElementById('filter-class').addEventListener('change', renderFindingsTable);

    // Tab Guideline
    document.getElementById('btn-mode-form').addEventListener('click', () => setGuidelineMode('form'));
    document.getElementById('btn-mode-yaml').addEventListener('click', () => setGuidelineMode('yaml'));
    document.getElementById('btn-save-guideline-form').addEventListener('click', handleSaveGuidelineForm);
    document.getElementById('btn-save-guideline-yaml').addEventListener('click', handleSaveGuidelineYaml);
    document.getElementById('btn-reload-guideline-yaml').addEventListener('click', loadGuideline);
    document.getElementById('btn-reset-guideline').addEventListener('click', handleResetGuideline);
    document.getElementById('btn-add-size-class').addEventListener('click', handleAddSizeClass);

    // Tab Kết nối
    document.getElementById('btn-check-cvat-connection').addEventListener('click', checkCvatConnection);
    document.getElementById('btn-save-connection-settings').addEventListener('click', handleSaveConnectionSettings);
  }

  // --- Chuyển Tab ---
  function switchTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach((b) => b.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach((p) => p.classList.remove('active'));

    const targetBtn = document.querySelector(`[data-tab="${tabId}"]`);
    const targetPane = document.getElementById(tabId);
    if (targetBtn) targetBtn.classList.add('active');
    if (targetPane) targetPane.classList.add('active');

    // Tự động nạp dữ liệu phù hợp khi vào tab
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

  async function loadLatestRun() {
    if (!state.currentSlug) return;
    try {
      const res = await fetch(`/api/projects/${state.currentSlug}/scans`);
      if (!res.ok) return;
      const runs = await res.json();
      if (runs.length > 0) {
        const fullRes = await fetch(`/api/projects/${state.currentSlug}/scans/${runs[0].run_id}`);
        if (fullRes.ok) {
          const runData = await fullRes.json();
          displayRunResults(runData);
        }
      }
    } catch (e) {
      console.error(e);
    }
  }

  // --- Modal Helpers ---
  function openModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.add('active');
  }

  function closeModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.remove('active');
  }

  // ==========================================
  // DỰ ÁN (PROJECTS)
  // ==========================================

  async function loadProjects() {
    try {
      const res = await fetch('/api/projects');
      if (!res.ok) throw new Error('Không thể tải danh sách dự án');
      state.projects = await res.json();
      renderProjectList();

      if (state.projects.length > 0) {
        if (!state.currentSlug || !state.projects.some((p) => p.slug === state.currentSlug)) {
          selectProject(state.projects[0].slug);
        } else {
          selectProject(state.currentSlug);
        }
      } else {
        // Chưa có dự án nào
        document.getElementById('current-project-name').textContent = 'Chưa có dự án nào';
        document.getElementById('current-project-desc').textContent = 'Bấm "Tạo dự án mới" để bắt đầu';
      }
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  function renderProjectList() {
    const ul = document.getElementById('project-list');
    ul.innerHTML = '';
    state.projects.forEach((p) => {
      const li = document.createElement('li');
      li.className = `project-item ${p.slug === state.currentSlug ? 'active' : ''}`;
      li.innerHTML = `
        <div class="project-item-title">${escapeHtml(p.name)}</div>
        <div class="project-item-meta">
          <span>${p.runs_count} lần quét</span>
          <span style="color: ${p.has_token ? 'var(--success)' : 'var(--warning)'}; font-size: 11px;">
            ${p.has_token ? '🔑 Có Token' : '⚠️ Chưa có Token'}
          </span>
        </div>
      `;
      li.addEventListener('click', () => selectProject(p.slug));
      ul.appendChild(li);
    });
  }

  async function selectProject(slug) {
    state.currentSlug = slug;
    renderProjectList();

    try {
      const res = await fetch(`/api/projects/${slug}`);
      if (!res.ok) throw new Error('Không thể tải chi tiết dự án');
      state.currentProject = await res.json();

      document.getElementById('current-project-name').textContent = state.currentProject.name;
      document.getElementById('current-project-desc').textContent =
        state.currentProject.description || `CVAT: ${state.currentProject.cvat_url}`;

      // Reset state cho dự án mới
      state.tasksList = [];
      state.currentRun = null;
      document.getElementById('results-empty-state').style.display = 'block';
      document.getElementById('results-content-box').style.display = 'none';

      // Kiểm tra kết nối CVAT ngầm
      checkCvatConnection(false);

      // Nạp tab hiện tại (ưu tiên theo URL hash nếu có)
      if (window.location.hash) {
        switchTab(window.location.hash.substring(1));
      } else {
        const activeTabBtn = document.querySelector('.tab-btn.active');
        if (activeTabBtn) switchTab(activeTabBtn.getAttribute('data-tab'));
      }
    } catch (err) {
      showToast(err.message, 'error');
    }
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

    const payload = {
      name,
      description: document.getElementById('create-proj-desc').value.trim(),
      cvat_url: document.getElementById('create-proj-url').value.trim() || 'http://localhost:8080',
      cvat_token: document.getElementById('create-proj-token').value.trim() || null,
      preset_slug: document.getElementById('create-proj-preset').value || null,
    };

    try {
      const res = await fetch('/api/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Lỗi khi tạo dự án');

      showToast(`Đã tạo dự án '${data.name}' thành công`, 'success');
      closeModal('modal-create-proj');
      await loadProjects();
      selectProject(data.slug);
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  async function handleDeleteProject() {
    if (!state.currentSlug) return;
    try {
      const res = await fetch(`/api/projects/${state.currentSlug}`, { method: 'DELETE' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Không thể xóa dự án');

      showToast('Đã xóa dự án thành công', 'success');
      closeModal('modal-delete-proj');
      state.currentSlug = null;
      await loadProjects();
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  // ==========================================
  // TAB QUÉT (SCAN)
  // ==========================================

  async function fetchCvatTasks() {
    if (!state.currentSlug) return;
    const taskSelect = document.getElementById('select-cvat-task');
    taskSelect.innerHTML = '<option value="">Đang tải danh sách từ CVAT...</option>';

    try {
      const res = await fetch(`/api/projects/${state.currentSlug}/cvat/tasks`);
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Không thể lấy danh sách Task');
      }
      const data = await res.json();
      state.tasksList = data.tasks || [];

      taskSelect.innerHTML = '<option value="">-- Chọn Task --</option>';
      state.tasksList.forEach((t) => {
        const opt = document.createElement('option');
        opt.value = t.id;
        opt.textContent = `Task #${t.id}: ${t.name} (${t.jobs ? t.jobs.length : 0} jobs)`;
        taskSelect.appendChild(opt);
      });

      handleTaskChange();
    } catch (err) {
      taskSelect.innerHTML = '<option value="">Lỗi tải danh sách (kiểm tra Token)</option>';
      showToast(err.message, 'error');
    }
  }

  function handleTaskChange() {
    const taskId = parseInt(document.getElementById('select-cvat-task').value, 10);
    const jobSelect = document.getElementById('select-cvat-job');
    jobSelect.innerHTML = '<option value="">-- Chọn Job --</option>';

    if (!taskId) return;
    const task = state.tasksList.find((t) => t.id === taskId);
    if (task && task.jobs) {
      task.jobs.forEach((j) => {
        const opt = document.createElement('option');
        opt.value = j.id;
        opt.textContent = `Job #${j.id} [${j.status || 'unknown'}]`;
        jobSelect.appendChild(opt);
      });
      if (task.jobs.length > 0) {
        jobSelect.value = task.jobs[0].id;
      }
    }
  }

  async function handleStartScan() {
    if (!state.currentSlug) return;

    let jobId = parseInt(document.getElementById('input-custom-job-id').value, 10);
    if (isNaN(jobId)) {
      jobId = parseInt(document.getElementById('select-cvat-job').value, 10);
    }
    if (!jobId) {
      showToast('Vui lòng chọn hoặc nhập Job ID để quét', 'error');
      return;
    }

    const flag = document.getElementById('check-scan-flag').checked;

    try {
      const btn = document.getElementById('btn-start-scan');
      btn.disabled = true;

      const res = await fetch(`/api/projects/${state.currentSlug}/scans`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: jobId, flag }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Không thể bắt đầu quét');

      showToast(`Đã bắt đầu quét Job #${jobId}`, 'info');
      startProgressPolling(data.run_id);
    } catch (err) {
      showToast(err.message, 'error');
      document.getElementById('btn-start-scan').disabled = false;
    }
  }

  function startProgressPolling(runId) {
    const progressBox = document.getElementById('scan-progress-box');
    const progressBar = document.getElementById('scan-progress-bar');
    const statusMsg = document.getElementById('scan-status-message');
    const percentText = document.getElementById('scan-progress-percent');
    const subNote = document.getElementById('scan-sub-note');

    progressBox.style.display = 'block';
    progressBar.style.width = '5%';
    percentText.textContent = '5%';
    statusMsg.textContent = 'Đang khởi động tiến trình...';
    subNote.textContent = '';

    if (state.scanPollTimer) clearInterval(state.scanPollTimer);

    state.scanPollTimer = setInterval(async () => {
      try {
        const res = await fetch(`/api/projects/${state.currentSlug}/scans/${runId}`);
        if (!res.ok) return;
        const runData = await res.json();

        progressBar.style.width = `${runData.progress || 0}%`;
        percentText.textContent = `${runData.progress || 0}%`;
        statusMsg.textContent = runData.message || runData.status;

        if (runData.status === 'done') {
          clearInterval(state.scanPollTimer);
          document.getElementById('btn-start-scan').disabled = false;
          showToast('Quét hoàn tất! Đang chuyển sang màn hình kết quả...', 'success');
          setTimeout(() => {
            progressBox.style.display = 'none';
            displayRunResults(runData);
            switchTab('tab-results');
          }, 1200);
        } else if (runData.status === 'failed') {
          clearInterval(state.scanPollTimer);
          document.getElementById('btn-start-scan').disabled = false;
          subNote.textContent = runData.error || 'Tác vụ thất bại';
          showToast(`Lỗi quét: ${runData.error || 'Thất bại'}`, 'error');
        }
      } catch (e) {
        console.error(e);
      }
    }, 1000);
  }

  // ==========================================
  // TAB KẾT QUẢ (RESULTS)
  // ==========================================

  function displayRunResults(runData) {
    state.currentRun = runData;
    document.getElementById('results-empty-state').style.display = 'none';
    document.getElementById('results-content-box').style.display = 'block';

    const sum = runData.summary || {};

    // 1. Gate Banner
    const banner = document.getElementById('gate-banner');
    const title = document.getElementById('gate-title');
    const subtitle = document.getElementById('gate-subtitle');
    const reasonsList = document.getElementById('gate-reasons-list');
    reasonsList.innerHTML = '';

    if (sum.gate_passed) {
      banner.className = 'gate-banner passed';
      title.textContent = '✅ CỔNG KIỂM TRA ĐẠT CHUẨN';
      subtitle.textContent = `Job #${sum.job_id} đạt mọi tiêu chuẩn kiểm định chất lượng gán nhãn.`;
    } else {
      banner.className = 'gate-banner failed';
      title.textContent = '❌ CỔNG KIỂM TRA KHÔNG ĐẠT';
      subtitle.textContent = `Job #${sum.job_id} có lỗi vi phạm tiêu chuẩn kiểm định:`;
      if (sum.gate_reasons) {
        sum.gate_reasons.forEach((r) => {
          const li = document.createElement('li');
          li.textContent = r;
          reasonsList.appendChild(li);
        });
      }
    }

    document.getElementById('run-time-display').textContent = `Thời điểm: ${new Date(
      sum.timestamp || Date.now()
    ).toLocaleString('vi-VN')}`;

    // 2. Thẻ số liệu
    document.getElementById('stat-errors-count').textContent = sum.num_errors ?? 0;
    document.getElementById('stat-warnings-count').textContent = sum.num_warnings ?? 0;
    document.getElementById('stat-info-count').textContent = sum.num_info ?? 0;
    document.getElementById('stat-boxes-count').textContent = sum.num_boxes ?? 0;

    // 3. Thông tin cờ lỗi (Điểm 4 Mục 6: hiển thị unmatched)
    const flagText = document.getElementById('flag-summary-text');
    if (sum.flagged && sum.flag_summary) {
      flagText.innerHTML = `🚩 <strong>Đã gắn cờ:</strong> ${sum.flag_summary.flagged} box, gỡ cờ ${sum.flag_summary.cleared} box. ${
        sum.flag_summary.unmatched > 0
          ? `<span style="color: var(--warning);">(${sum.flag_summary.unmatched} finding không khớp box trên CVAT)</span>`
          : ''
      }`;
    } else {
      flagText.innerHTML = '⚪ Kết quả này chưa gắn cờ lên CVAT.';
    }

    // 4. Liên kết tải báo cáo
    document.getElementById(
      'btn-download-html'
    ).href = `/api/projects/${state.currentSlug}/scans/${runData.run_id}/report.html`;
    document.getElementById(
      'btn-download-csv'
    ).href = `/api/projects/${state.currentSlug}/scans/${runData.run_id}/report.csv`;

    // 5. Populate dropdown class filter
    populateClassFilter(runData.findings || []);

    // 6. Bảng findings
    renderFindingsTable();
  }

  function populateClassFilter(findings) {
    const sel = document.getElementById('filter-class');
    sel.innerHTML = '<option value="">Mọi class</option>';
    const classes = Array.from(new Set(findings.map((f) => f.label).filter(Boolean))).sort();
    classes.forEach((c) => {
      const opt = document.createElement('option');
      opt.value = c;
      opt.textContent = c;
      sel.appendChild(opt);
    });
  }

  function renderFindingsTable() {
    if (!state.currentRun || !state.currentRun.findings) return;
    const tbody = document.getElementById('findings-table-body');
    tbody.innerHTML = '';

    const query = document.getElementById('filter-search-box').value.toLowerCase().trim();
    const sevFilter = document.getElementById('filter-severity').value;
    const typeFilter = document.getElementById('filter-error-type').value;
    const classFilter = document.getElementById('filter-class').value;

    const filtered = state.currentRun.findings.filter((f) => {
      if (sevFilter && f.severity !== sevFilter) return false;
      if (typeFilter && f.error_type !== typeFilter) return false;
      if (classFilter && f.label !== classFilter) return false;
      if (query) {
        const text = `${f.message} ${f.rule} ${f.label} ${f.frame} ${f.track_id}`.toLowerCase();
        if (!text.includes(query)) return false;
      }
      return true;
    });

    document.getElementById(
      'findings-count-summary'
    ).textContent = `Hiển thị ${filtered.length} / ${state.currentRun.findings.length} phát hiện`;

    if (filtered.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 24px;">Không có phát hiện nào phù hợp bộ lọc.</td></tr>';
      return;
    }

    filtered.forEach((f) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><span class="badge-sev ${f.severity}">${f.severity_label || f.severity}</span></td>
        <td><strong>#${f.frame}</strong></td>
        <td>${f.track_id !== null ? `#${f.track_id}` : '—'}</td>
        <td><code>${escapeHtml(f.label || '—')}</code></td>
        <td><span style="font-size: 12px; color: var(--text-muted);">${escapeHtml(f.rule)}</span></td>
        <td>${escapeHtml(f.message)}</td>
        <td>
          ${
            f.cvat_link
              ? `<a href="${f.cvat_link}" target="_blank" class="cvat-link-btn" title="Mở frame ${f.frame} trên CVAT">
                   Mở CVAT ↗
                 </a>`
              : '—'
          }
        </td>
      `;
      tbody.appendChild(tr);
    });
  }

  // Điểm 4 Mục 6: Nút gắn cờ quét lại để tránh trượt id
  async function handleReFlagScan() {
    if (!state.currentRun || !state.currentSlug) return;
    const btn = document.getElementById('btn-re-flag-cvat');
    btn.disabled = true;

    try {
      const res = await fetch(
        `/api/projects/${state.currentSlug}/scans/${state.currentRun.run_id}/flag`,
        { method: 'POST' }
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Không thể gắn cờ');

      showToast(data.message || 'Đang quét lại và gắn cờ lên CVAT...', 'info');
      switchTab('tab-scan');
      startProgressPolling(data.run_id);
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      btn.disabled = false;
    }
  }

  // ==========================================
  // TAB GUIDELINE
  // ==========================================

  function setGuidelineMode(mode) {
    const btnForm = document.getElementById('btn-mode-form');
    const btnYaml = document.getElementById('btn-mode-yaml');
    const viewForm = document.getElementById('guideline-form-view');
    const viewYaml = document.getElementById('guideline-yaml-view');

    if (mode === 'form') {
      btnForm.classList.add('active');
      btnYaml.classList.remove('active');
      viewForm.style.display = 'block';
      viewYaml.style.display = 'none';
    } else {
      btnYaml.classList.add('active');
      btnForm.classList.remove('active');
      viewYaml.style.display = 'block';
      viewForm.style.display = 'none';
    }
  }

  async function loadGuideline() {
    if (!state.currentSlug) return;
    try {
      const res = await fetch(`/api/projects/${state.currentSlug}/guideline`);
      if (!res.ok) throw new Error('Không thể tải guideline');
      const data = await res.json();
      state.currentGuideline = data;

      populateGuidelineForm(data.config);
      document.getElementById('guideline-yaml-textarea').value = data.yaml;
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  function populateGuidelineForm(cfg) {
    if (!cfg) return;

    // Rules
    const r = cfg.rules || {};
    document.getElementById('rule-floating').checked = r.floating !== false;
    document.getElementById('rule-size-class-range').checked = r.size_class_range !== false;
    document.getElementById('rule-size-in-track').checked = r.size_in_track !== false;
    document.getElementById('rule-track-jump').checked = r.track_jump !== false;
    document.getElementById('rule-track-split-id').checked =
      r.track_split_id !== false;
    document.getElementById('rule-track-long-interpolation').checked =
      r.track_long_interpolation !== false;

    // Gate
    const g = cfg.gate || {};
    document.getElementById('gate-max-errors').value = g.max_errors ?? 0;
    document.getElementById('gate-max-warnings').value = g.max_warnings ?? 10;

    // Floating
    const fl = cfg.floating || {};
    document.getElementById('fl-warning-m').value = fl.warning_m ?? 0.12;
    document.getElementById('fl-error-m').value = fl.error_m ?? 0.22;
    document.getElementById('fl-single-warning-m').value = fl.single_warning_m ?? 0.15;
    document.getElementById('fl-single-error-m').value = fl.single_error_m ?? 0.3;

    // Size manual ranges
    renderSizeClassesTable(cfg.size ? cfg.size.manual_ranges || {} : {});
  }

  function renderSizeClassesTable(manualRanges) {
    const tbody = document.getElementById('size-classes-table-body');
    tbody.innerHTML = '';

    Object.entries(manualRanges).forEach(([cls, dims]) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><strong class="cls-name-cell">${escapeHtml(cls)}</strong></td>
        <td><input type="number" step="0.1" class="cls-l-min" value="${dims.length ? dims.length[0] : 0}"></td>
        <td><input type="number" step="0.1" class="cls-l-max" value="${dims.length ? dims.length[1] : 0}"></td>
        <td><input type="number" step="0.1" class="cls-w-min" value="${dims.width ? dims.width[0] : 0}"></td>
        <td><input type="number" step="0.1" class="cls-w-max" value="${dims.width ? dims.width[1] : 0}"></td>
        <td><input type="number" step="0.1" class="cls-h-min" value="${dims.height ? dims.height[0] : 0}"></td>
        <td><input type="number" step="0.1" class="cls-h-max" value="${dims.height ? dims.height[1] : 0}"></td>
        <td><button class="btn btn-outline btn-remove-cls" style="color: var(--error); padding: 4px 8px; font-size: 11px;">Xóa</button></td>
      `;
      tr.querySelector('.btn-remove-cls').addEventListener('click', () => tr.remove());
      tbody.appendChild(tr);
    });
  }

  function handleAddSizeClass() {
    const name = prompt('Nhập tên class mới (ví dụ: emergency_vehicle):');
    if (!name || !name.trim()) return;
    const cleanName = name.trim().toLowerCase();

    const tbody = document.getElementById('size-classes-table-body');
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong class="cls-name-cell">${escapeHtml(cleanName)}</strong></td>
      <td><input type="number" step="0.1" class="cls-l-min" value="1.0"></td>
      <td><input type="number" step="0.1" class="cls-l-max" value="5.0"></td>
      <td><input type="number" step="0.1" class="cls-w-min" value="1.0"></td>
      <td><input type="number" step="0.1" class="cls-w-max" value="2.5"></td>
      <td><input type="number" step="0.1" class="cls-h-min" value="1.0"></td>
      <td><input type="number" step="0.1" class="cls-h-max" value="3.0"></td>
      <td><button class="btn btn-outline btn-remove-cls" style="color: var(--error); padding: 4px 8px; font-size: 11px;">Xóa</button></td>
    `;
    tr.querySelector('.btn-remove-cls').addEventListener('click', () => tr.remove());
    tbody.appendChild(tr);
  }

  async function handleSaveGuidelineForm() {
    if (!state.currentGuideline || !state.currentGuideline.config) return;
    const cfg = JSON.parse(JSON.stringify(state.currentGuideline.config));

    // Cập nhật Rules
    cfg.rules = {
      floating: document.getElementById('rule-floating').checked,
      size_class_range: document.getElementById('rule-size-class-range').checked,
      size_in_track: document.getElementById('rule-size-in-track').checked,
      track_jump: document.getElementById('rule-track-jump').checked,
      track_split_id: document.getElementById('rule-track-split-id').checked,
      track_long_interpolation: document.getElementById('rule-track-long-interpolation').checked,
    };

    // Cập nhật Gate
    cfg.gate = {
      max_errors: parseInt(document.getElementById('gate-max-errors').value, 10) || 0,
      max_warnings: parseInt(document.getElementById('gate-max-warnings').value, 10) || 0,
    };

    // Cập nhật Floating
    if (!cfg.floating) cfg.floating = {};
    cfg.floating.warning_m = parseFloat(document.getElementById('fl-warning-m').value) || 0.12;
    cfg.floating.error_m = parseFloat(document.getElementById('fl-error-m').value) || 0.22;
    cfg.floating.single_warning_m = parseFloat(document.getElementById('fl-single-warning-m').value) || 0.15;
    cfg.floating.single_error_m = parseFloat(document.getElementById('fl-single-error-m').value) || 0.3;

    // Cập nhật manual_ranges
    if (!cfg.size) cfg.size = {};
    const manualRanges = {};
    document.querySelectorAll('#size-classes-table-body tr').forEach((tr) => {
      const cls = tr.querySelector('.cls-name-cell').textContent.trim();
      const lMin = parseFloat(tr.querySelector('.cls-l-min').value) || 0;
      const lMax = parseFloat(tr.querySelector('.cls-l-max').value) || 0;
      const wMin = parseFloat(tr.querySelector('.cls-w-min').value) || 0;
      const wMax = parseFloat(tr.querySelector('.cls-w-max').value) || 0;
      const hMin = parseFloat(tr.querySelector('.cls-h-min').value) || 0;
      const hMax = parseFloat(tr.querySelector('.cls-h-max').value) || 0;
      manualRanges[cls] = {
        length: [lMin, lMax],
        width: [wMin, wMax],
        height: [hMin, hMax],
      };
    });
    cfg.size.manual_ranges = manualRanges;

    // Gửi PUT
    await submitGuideline({ config: cfg });
  }

  async function handleSaveGuidelineYaml() {
    const yamlText = document.getElementById('guideline-yaml-textarea').value;
    await submitGuideline({ yaml: yamlText });
  }

  async function submitGuideline(payload) {
    if (!state.currentSlug) return;
    try {
      const res = await fetch(`/api/projects/${state.currentSlug}/guideline`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Cấu hình guideline không hợp lệ');

      showToast('Đã lưu cấu hình Guideline thành công', 'success');
      await loadGuideline();
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  async function handleResetGuideline() {
    if (!state.currentSlug) return;
    if (!confirm('Khôi phục Guideline về cấu hình mặc định ban đầu?')) return;
    try {
      const res = await fetch(`/api/projects/${state.currentSlug}/guideline/reset`, { method: 'POST' });
      if (!res.ok) throw new Error('Không thể khôi phục guideline');
      showToast('Đã khôi phục cấu hình mặc định', 'success');
      await loadGuideline();
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  // ==========================================
  // TAB KẾT NỐI (CONNECTION)
  // ==========================================

  function loadConnectionTab() {
    if (!state.currentProject) return;
    document.getElementById('conn-cvat-url').value = state.currentProject.cvat_url || '';
    document.getElementById('conn-cvat-token').value = '';
    document.getElementById('conn-nuscenes-root').value = state.currentProject.nuscenes_root || '';
    document.getElementById('conn-export-dirs').value = (state.currentProject.export_dirs || []).join(';');
  }

  async function checkCvatConnection(showToastMsg = true) {
    if (!state.currentSlug) return;
    const badge = document.getElementById('cvat-status-badge');
    const msg = document.getElementById('cvat-test-result-msg');

    badge.className = 'status-badge neutral';
    badge.innerHTML = '<span>●</span> CVAT: Đang kiểm tra...';

    try {
      const res = await fetch(`/api/projects/${state.currentSlug}/cvat/check`);
      const data = await res.json();
      if (data.connected) {
        badge.className = 'status-badge online';
        badge.innerHTML = `<span>●</span> CVAT v${data.version}`;
        if (msg) msg.textContent = `Kết nối thành công tới CVAT v${data.version}`;
        if (showToastMsg) showToast(`CVAT Online (Phiên bản ${data.version})`, 'success');
      } else {
        badge.className = 'status-badge offline';
        badge.innerHTML = '<span>●</span> CVAT: Ngoại tuyến';
        if (msg) msg.textContent = `Lỗi: ${data.error}`;
        if (showToastMsg) showToast(`CVAT Offline: ${data.error}`, 'error');
      }
    } catch (err) {
      badge.className = 'status-badge offline';
      badge.innerHTML = '<span>●</span> CVAT: Lỗi mạng';
    }
  }

  async function handleSaveConnectionSettings() {
    if (!state.currentSlug) return;
    const cvatUrl = document.getElementById('conn-cvat-url').value.trim();
    const token = document.getElementById('conn-cvat-token').value.trim();
    const nuscenesRoot = document.getElementById('conn-nuscenes-root').value.trim();
    const exportDirsStr = document.getElementById('conn-export-dirs').value.trim();
    const exportDirs = exportDirsStr ? exportDirsStr.split(';').map((s) => s.trim()).filter(Boolean) : [];

    const payload = {
      cvat_url: cvatUrl,
      nuscenes_root: nuscenesRoot,
      export_dirs: exportDirs,
    };
    if (token) payload.cvat_token = token;

    try {
      const res = await fetch(`/api/projects/${state.currentSlug}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Không thể lưu cài đặt kết nối');

      state.currentProject = data;
      showToast('Đã lưu cấu hình kết nối thành công', 'success');
      checkCvatConnection(true);
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  // ==========================================
  // TAB LỊCH SỬ (HISTORY)
  // ==========================================

  async function loadHistoryTab() {
    if (!state.currentSlug) return;
    const tbody = document.getElementById('history-table-body');
    tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; padding: 20px;">Đang tải lịch sử...</td></tr>';

    try {
      const res = await fetch(`/api/projects/${state.currentSlug}/scans`);
      if (!res.ok) throw new Error('Không thể tải lịch sử');
      const runs = await res.json();

      tbody.innerHTML = '';
      if (runs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 30px;">Dự án chưa có lần quét nào.</td></tr>';
        renderHistoryChart([]);
        return;
      }

      runs.forEach((r) => {
        const s = r.summary || {};
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><strong>${new Date(r.started_at || Date.now()).toLocaleString('vi-VN')}</strong></td>
          <td>Job #${r.job_id || '—'}</td>
          <td>${s.num_boxes ?? '—'}</td>
          <td style="color: var(--error); font-weight: 700;">${s.num_errors ?? 0}</td>
          <td style="color: var(--warning); font-weight: 700;">${s.num_warnings ?? 0}</td>
          <td>
            <span class="badge-sev ${s.gate_passed ? 'info' : 'error'}">
              ${s.gate_passed ? 'ĐẠT' : 'KHÔNG ĐẠT'}
            </span>
          </td>
          <td>${s.flagged ? '🚩 Có' : '—'}</td>
          <td>
            <div style="display: flex; gap: 6px;">
              <button class="btn btn-secondary btn-view-run" style="padding: 4px 8px; font-size: 11.5px;">Xem kết quả</button>
              <a href="/api/projects/${state.currentSlug}/scans/${r.run_id}/report.html" target="_blank" class="btn btn-outline" style="padding: 4px 8px; font-size: 11.5px;">HTML</a>
            </div>
          </td>
        `;
        tr.querySelector('.btn-view-run').addEventListener('click', async () => {
          const detailRes = await fetch(`/api/projects/${state.currentSlug}/scans/${r.run_id}`);
          if (detailRes.ok) {
            const detailData = await detailRes.json();
            displayRunResults(detailData);
            switchTab('tab-results');
          }
        });
        tbody.appendChild(tr);
      });

      renderHistoryChart(runs);
    } catch (err) {
      showToast(err.message, 'error');
    }
  }

  // Vẽ biểu đồ xu hướng bằng SVG thuần (Không dùng CDN, chạy offline hoàn hảo)
  function renderHistoryChart(runs) {
    const svg = document.getElementById('history-svg-chart');
    svg.innerHTML = '';

    const validRuns = runs
      .filter((r) => r.summary && typeof r.summary.num_errors === 'number')
      .reverse(); // cũ nhất sang mới nhất

    if (validRuns.length === 0) {
      svg.innerHTML = '<text x="400" y="90" fill="var(--text-muted)" text-anchor="middle" font-size="14">Chưa có dữ liệu để vẽ biểu đồ</text>';
      return;
    }

    const width = 800;
    const height = 180;
    const padX = 50;
    const padY = 30;

    let maxVal = 10;
    validRuns.forEach((r) => {
      const total = (r.summary.num_errors || 0) + (r.summary.num_warnings || 0);
      if (total > maxVal) maxVal = total;
    });

    const stepX = (width - 2 * padX) / Math.max(validRuns.length - 1, 1);

    // Vẽ lưới ngang
    for (let i = 0; i <= 4; i++) {
      const y = height - padY - (i * (height - 2 * padY)) / 4;
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', padX);
      line.setAttribute('x2', width - padX);
      line.setAttribute('y1', y);
      line.setAttribute('y2', y);
      line.setAttribute('stroke', 'var(--border-color)');
      line.setAttribute('stroke-dasharray', '3 3');
      svg.appendChild(line);

      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      text.setAttribute('x', padX - 8);
      text.setAttribute('y', y + 4);
      text.setAttribute('fill', 'var(--text-muted)');
      text.setAttribute('font-size', '10');
      text.setAttribute('text-anchor', 'end');
      text.textContent = Math.round((i * maxVal) / 4);
      svg.appendChild(text);
    }

    const errorPoints = [];
    const warningPoints = [];

    validRuns.forEach((r, idx) => {
      const x = padX + (validRuns.length === 1 ? (width - 2 * padX) / 2 : idx * stepX);
      const errY = height - padY - ((r.summary.num_errors || 0) / maxVal) * (height - 2 * padY);
      const warnY = height - padY - ((r.summary.num_warnings || 0) / maxVal) * (height - 2 * padY);
      errorPoints.push(`${x},${errY}`);
      warningPoints.push(`${x},${warnY}`);

      // Điểm tròn
      const circleErr = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      circleErr.setAttribute('cx', x);
      circleErr.setAttribute('cy', errY);
      circleErr.setAttribute('r', '4');
      circleErr.setAttribute('fill', 'var(--error)');
      svg.appendChild(circleErr);

      const circleWarn = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      circleWarn.setAttribute('cx', x);
      circleWarn.setAttribute('cy', warnY);
      circleWarn.setAttribute('r', '4');
      circleWarn.setAttribute('fill', 'var(--warning)');
      svg.appendChild(circleWarn);
    });

    if (errorPoints.length > 1) {
      const polyErr = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
      polyErr.setAttribute('points', errorPoints.join(' '));
      polyErr.setAttribute('fill', 'none');
      polyErr.setAttribute('stroke', 'var(--error)');
      polyErr.setAttribute('stroke-width', '2.5');
      svg.appendChild(polyErr);

      const polyWarn = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
      polyWarn.setAttribute('points', warningPoints.join(' '));
      polyWarn.setAttribute('fill', 'none');
      polyWarn.setAttribute('stroke', 'var(--warning)');
      polyWarn.setAttribute('stroke-width', '2.5');
      svg.appendChild(polyWarn);
    }

    // Chú thích
    const legend = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    legend.setAttribute('x', width - padX);
    legend.setAttribute('y', 18);
    legend.setAttribute('text-anchor', 'end');
    legend.setAttribute('font-size', '11');
    legend.innerHTML = '<tspan fill="var(--error)">● Số Lỗi </tspan> <tspan fill="var(--warning)">● Cảnh báo</tspan>';
    svg.appendChild(legend);
  }

  // --- Helper escape HTML ---
  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
})();
