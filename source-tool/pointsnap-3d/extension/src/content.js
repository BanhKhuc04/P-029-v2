/*
 * Bảng PointSnap trên trang job của CVAT (A15).
 * E1 nhận diện trang job · E2 tự bật bộ lọc · E3 thông báo lỗi của box đang chọn · E4 lỗi tiếp / trước
 * E5 danh sách lỗi của job · E6 quét lại, gắn cờ, ghi Đúng / Báo nhầm qua PointSnap.
 * E1–E4 chỉ cần cờ `pointsnap_error` trên CVAT; E5 lấy từ cờ, PointSnap chỉ thêm phần kết luận xem tay; E6 cần PointSnap.
 */
(function (root) {
  'use strict';

  const core = root.PointSnapCore;
  const cvat = root.PointSnapCvat;
  const api = root.PointSnapCvatApi;
  const ATTR = core.FLAG_ATTR;
  const hasChrome = typeof chrome !== 'undefined' && !!(chrome.runtime && chrome.runtime.id);

  const SEV_LABEL = { error: 'Lỗi', warning: 'Cảnh báo', info: 'Thông tin' };
  const RULE_LABEL = {
    'floating': 'Lơ lửng / lún',
    'floating.no_evidence': 'Thiếu bằng chứng mặt đất',
    'size.class_range': 'Kích thước lạ so với class',
    'size.in_track': 'Kích thước lệch trong track',
    'track.jump': 'Nhảy vị trí',
    'track.split_id': 'Nghi tách ID',
    'track.long_interpolation': 'Nội suy dài',
  };

  // ---------------------------------------------------------------- trạng thái

  const S = {
    sid: 0,
    job: null,
    flags: [],
    frames: [],
    hasFlagAttr: true,
    loading: false,
    loadError: null,
    frame: null,
    navTarget: null,
    active: null,
    filterOn: false,
    filterBusy: false,
    filterProblem: null,
    ps: { checked: false, online: false, error: null, project: null, run: null, active: null, flagRun: false },
    confirmFlag: false,
    notice: null,
    listFilter: 'all',
    collapsed: false,
    pos: null,
    timing: {},
  };
  const settings = { autoFilter: true, autoHighlight: true, autoExpand: true };
  const expanded = new Set();

  // ---------------------------------------------------------------- PointSnap (qua service worker)

  /** Gọi API PointSnap qua service worker của extension (không cần mở CORS trên PointSnap). */
  function pointsnap(method, path, body) {
    if (root.PointSnapTransport) return root.PointSnapTransport(method, path, body);
    return new Promise((resolve) => {
      if (!hasChrome) {
        resolve({ ok: false, error: 'Không chạy trong extension' });
        return;
      }
      try {
        chrome.runtime.sendMessage({ type: 'pointsnap', method, path, body }, (res) => {
          if (chrome.runtime.lastError || !res) {
            resolve({ ok: false, error: (chrome.runtime.lastError && chrome.runtime.lastError.message) || 'Không có phản hồi' });
          } else {
            resolve(res);
          }
        });
      } catch (err) {
        resolve({ ok: false, error: String(err) });
      }
    });
  }

  function loadSettings() {
    if (!hasChrome || !chrome.storage) return Promise.resolve();
    return new Promise((resolve) => {
      chrome.storage.sync.get({ autoFilter: true, autoHighlight: true, autoExpand: true }, (data) => {
        Object.assign(settings, data || {});
        chrome.storage.local.get({ panelPos: null, panelCollapsed: false }, (local) => {
          S.pos = (local && local.panelPos) || null;
          S.collapsed = !!(local && local.panelCollapsed);
          resolve();
        });
      });
    });
  }

  function saveLocal(values) {
    if (hasChrome && chrome.storage) chrome.storage.local.set(values);
  }

  // ---------------------------------------------------------------- vòng đời theo trang

  let lastHref = '';
  let tickTimer = null;

  function onRoute() {
    if (location.href === lastHref) return;
    lastHref = location.href;
    const job = core.parseJobUrl(location.href);
    const task = location.pathname.match(/\/tasks\/(\d+)/);
    if (task && !job) api.seedFilterForTask(Number(task[1]), ATTR).catch(() => {});
    if (job && (!S.job || S.job.jobId !== job.jobId)) startJob(job);
    else if (!job && S.job) stopJob();
  }

  async function startJob(job) {
    stopJob();
    const sid = ++S.sid;
    expanded.clear();
    Object.assign(S, {
      job, flags: [], frames: [], hasFlagAttr: true, loading: true, loadError: null, frame: null, active: null,
      filterOn: false, filterBusy: false, filterProblem: null, confirmFlag: false, notice: null,
      ps: { checked: false, online: false, error: null, project: null, run: null, active: null, flagRun: false },
      timing: { start: performance.now() },
    });
    mountPanel();
    render();
    api.seedFilterForTask(job.taskId, ATTR).catch(() => {});
    loadPointSnap(sid);
    await loadFlags(sid);
    S.timing.flags = performance.now();
    const ready = await cvat.waitFor(cvat.workspaceReady, 120000, 250);
    if (sid !== S.sid || !ready) return;
    S.timing.ready = performance.now();
    S.frame = cvat.currentFrame();
    tickTimer = setInterval(tick, 300);
    if (settings.autoFilter && S.flags.length) await turnFilterOn(true);
    S.timing.filter = performance.now();
    render();
  }

  function stopJob() {
    S.sid += 1;
    S.job = null;
    clearInterval(tickTimer);
    tickTimer = null;
    unmountPanel();
  }

  async function loadFlags(sid) {
    S.loading = true;
    render();
    try {
      const [labels, annotations] = await Promise.all([api.labelsOfJob(S.job.jobId), api.annotations(S.job.jobId)]);
      if (sid !== S.sid) return;
      const specs = core.flagSpecs(labels, ATTR);
      S.hasFlagAttr = specs.size > 0;
      S.flags = core.collectFlags(annotations, specs);
      S.frames = core.flaggedFrames(S.flags);
      S.loadError = null;
    } catch (err) {
      if (sid !== S.sid) return;
      S.loadError = `Không đọc được nhãn của job từ CVAT (${err.message}).`;
    }
    S.loading = false;
    render();
  }

  /** Theo dõi frame hiện tại, box đang chọn và trạng thái bộ lọc; chỉ vẽ lại khi có thay đổi. */
  function tick() {
    // Bộ lọc đang bật thì danh sách bên phải chỉ còn box có cờ: mở DETAILS để thấy và đọc được nội dung cờ.
    if (settings.autoExpand && S.filterOn && !isTyping(document.activeElement)) cvat.expandDetails(expanded);
    const frame = cvat.currentFrame();
    const active = cvat.activeObject(ATTR);
    const filterOn = cvat.filtersActive();
    const activeKey = (a) => (a ? `${a.clientId}|${a.label}|${a.flag}` : '');
    if (frame !== S.frame || activeKey(active) !== activeKey(S.active) || filterOn !== S.filterOn) {
      S.frame = frame;
      S.active = active;
      S.filterOn = filterOn;
      render();
    }
  }

  // ---------------------------------------------------------------- hành động trên CVAT

  async function turnFilterOn(auto) {
    if (S.filterBusy) return;
    S.filterBusy = true;
    S.filterProblem = null;
    render();
    const res = await cvat.applyRecentFilter(ATTR);
    S.timing.filterSteps = res.steps;
    S.filterBusy = false;
    S.filterOn = cvat.filtersActive();
    if (!res.ok) S.filterProblem = { reason: res.reason, needsReload: !!res.needsReload, auto: !!auto };
    render();
  }

  async function turnFilterOff() {
    S.filterBusy = true;
    render();
    const res = await cvat.clearFilters();
    S.filterBusy = false;
    S.filterOn = cvat.filtersActive();
    if (!res.ok) setNotice('error', `${res.reason}. Mở Filters của CVAT và bấm "Clear filters".`);
    render();
  }

  let navigating = false;

  async function goTo(frame) {
    // Một lần chuyển frame tại một thời điểm: bấm dồn khi CVAT đang tải frame sẽ bị CVAT bỏ qua.
    if (navigating) return;
    navigating = true;
    S.navTarget = frame;
    render();
    let res;
    try {
      res = await cvat.goToFrame(frame);
    } finally {
      navigating = false;
      S.navTarget = null;
    }
    if (pendingStep) {
      const dir = Math.sign(pendingStep);
      pendingStep -= dir;
      if (!res.ok) pendingStep = 0;
      else {
        S.frame = frame;
        step(dir);
        return;
      }
    }
    if (!res.ok) {
      setNotice('error', `${res.reason}. Gõ ${frame} vào ô số frame của CVAT rồi nhấn Enter.`);
      return;
    }
    S.frame = frame;
    S.notice = null;
    render();
    // Chờ danh sách đối tượng của CVAT đổi sang frame mới rồi mới làm sáng box.
    if (settings.autoHighlight) setTimeout(() => highlight(flagsAt(frame)[0], 0), 250);
  }

  let pendingStep = 0;

  async function step(dir) {
    if (!S.frames.length) return;
    if (navigating) {
      // Bấm trong lúc CVAT đang tải frame: cộng dồn số lần bấm, chạy tiếp ngay khi frame tải xong.
      pendingStep += dir;
      return;
    }
    const current = cvat.currentFrame();
    const target = core.stepFrame(S.frames, current === null ? -1 : current, dir);
    if (target === null) {
      pendingStep = 0;
      setNotice('info', dir > 0 ? 'Đã tới frame có lỗi cuối cùng của job.' : 'Đây là frame có lỗi đầu tiên của job.');
      return;
    }
    await goTo(target);
  }

  const highlightTurn = new Map();

  /**
   * Làm sáng box của một cờ: rê chuột hộ vào mục cùng nhãn trong danh sách đối tượng của CVAT.
   * Bấm lại lần nữa thì chuyển sang mục cùng nhãn kế tiếp (khi frame có nhiều box cùng nhãn).
   */
  async function highlight(flag, turn) {
    if (!flag) return;
    const items = await cvat.waitFor(() => {
      const list = cvat.sidebarItems().filter((it) => it.label === flag.label);
      return list.length ? list : null;
    }, 1500);
    if (!items) {
      if (turn !== 0) setNotice('info', `Không thấy box ${flag.label} trong danh sách đối tượng của CVAT ở frame này.`);
      return;
    }
    const key = `${flag.frame}|${flag.label}`;
    const n = turn === 0 ? 0 : ((highlightTurn.get(key) || 0) + 1) % items.length;
    highlightTurn.set(key, n);
    cvat.hoverItem(items[n].el);
  }

  function flagsAt(frame) {
    return S.flags.filter((f) => f.frame === frame);
  }

  // ---------------------------------------------------------------- PointSnap: quét, gắn cờ, kết luận

  async function loadPointSnap(sid) {
    const res = await pointsnap('GET', `/api/extension/jobs/${S.job.jobId}?cvat_url=${encodeURIComponent(location.origin)}`);
    if (sid !== S.sid) return;
    S.ps.checked = true;
    S.ps.online = !!res.ok;
    S.ps.error = res.ok ? null : res.error;
    if (res.ok) {
      S.ps.project = res.data.project;
      S.ps.run = res.data.run;
      if (res.data.active && !S.ps.active) {
        S.ps.active = res.data.active;
        pollRun(sid);
      }
    }
    render();
  }

  async function startScan(flag) {
    S.confirmFlag = false;
    const project = S.ps.project;
    if (!project) {
      setNotice('warn', `PointSnap chưa có dự án nối với ${location.origin}. Tạo dự án ở giao diện PointSnap, tab Kết nối CVAT.`);
      return;
    }
    const res = await pointsnap('POST', `/api/projects/${project.slug}/scans`, { job_id: S.job.jobId, flag });
    if (!res.ok) {
      setNotice('error', `Không bắt đầu quét được: ${res.error}`);
      return;
    }
    S.ps.active = { run_id: res.data.run_id, status: 'queued', progress: 0, message: 'Đang chờ…' };
    S.ps.flagRun = flag;
    render();
    pollRun(S.sid);
  }

  async function pollRun(sid) {
    while (sid === S.sid && S.ps.active) {
      const res = await pointsnap('GET', `/api/projects/${S.ps.project.slug}/scans/${S.ps.active.run_id}`);
      if (sid !== S.sid) return;
      if (!res.ok) {
        setNotice('error', `Mất kết nối với PointSnap: ${res.error}`);
        S.ps.active = null;
        break;
      }
      const run = res.data;
      if (run.status === 'done' || run.status === 'failed') {
        const flagged = S.ps.flagRun && run.status === 'done';
        S.ps.active = null;
        S.ps.flagRun = false;
        if (run.status === 'failed') setNotice('error', `Quét thất bại: ${run.error || run.message}`);
        else if (flagged) {
          setNotice('warn', 'Đã gắn cờ mới lên CVAT. Tải lại trang CVAT để thấy cờ mới (Save trước nếu còn thay đổi).', [
            { action: 'reload', text: 'Tải lại trang' },
          ]);
        } else {
          setNotice('info', 'Đã quét xong. Danh sách bên dưới vẫn theo cờ trên CVAT; bấm "Quét + gắn cờ" để cập nhật cờ.');
        }
        await loadPointSnap(sid);
        break;
      }
      S.ps.active = { ...S.ps.active, ...run };
      render();
      await new Promise((resolve) => setTimeout(resolve, 1200));
    }
    render();
  }

  function reviewState(flag) {
    const run = S.ps.run;
    if (!run || !run.findings) return null;
    const indices = core.matchFindings(run.findings, flag);
    if (!indices.length) return null;
    const verdicts = indices.map((i) => (run.reviews || {})[String(i)] || null);
    const same = verdicts.every((v) => v === verdicts[0]);
    return { indices, verdict: same ? verdicts[0] : null };
  }

  async function review(flag, verdict) {
    const state = reviewState(flag);
    if (!state) return;
    const value = state.verdict === verdict ? null : verdict;
    const { slug } = S.ps.project;
    for (const index of state.indices) {
      const res = await pointsnap('PUT', `/api/projects/${slug}/scans/${S.ps.run.run_id}/reviews/${index}`, { verdict: value });
      if (!res.ok) {
        setNotice('error', `Không lưu được kết luận: ${res.error}`);
        break;
      }
      S.ps.run.reviews = res.data.reviews;
    }
    render();
  }

  // ---------------------------------------------------------------- giao diện

  let host = null;
  let shadow = null;

  function mountPanel() {
    if (host) return;
    host = document.createElement('div');
    host.id = 'pointsnap-cvat-panel';
    shadow = host.attachShadow({ mode: 'open' });
    const style = document.createElement('style');
    style.textContent = root.PointSnapPanelCss || '';
    const panel = document.createElement('div');
    panel.className = 'ps';
    panel.setAttribute('role', 'complementary');
    panel.setAttribute('aria-label', 'PointSnap');
    shadow.append(style, panel);
    document.documentElement.appendChild(host);
    placePanel(panel);
    panel.addEventListener('click', onClick);
    panel.addEventListener('mousedown', onDragStart);
  }

  function unmountPanel() {
    if (host) host.remove();
    host = null;
    shadow = null;
  }

  function placePanel(panel) {
    const pos = S.pos || { left: 64, top: 104 };
    const left = Math.max(0, Math.min(pos.left, window.innerWidth - 120));
    const top = Math.max(0, Math.min(pos.top, window.innerHeight - 40));
    panel.style.left = `${left}px`;
    panel.style.top = `${top}px`;
  }

  function onDragStart(event) {
    const head = event.target.closest('.head');
    if (!head || event.target.closest('button') || event.button !== 0) return;
    const panel = event.currentTarget;
    const rect = panel.getBoundingClientRect();
    const dx = event.clientX - rect.left;
    const dy = event.clientY - rect.top;
    const move = (e) => {
      S.pos = { left: e.clientX - dx, top: e.clientY - dy };
      placePanel(panel);
    };
    const up = () => {
      window.removeEventListener('mousemove', move, true);
      window.removeEventListener('mouseup', up, true);
      saveLocal({ panelPos: S.pos });
    };
    window.addEventListener('mousemove', move, true);
    window.addEventListener('mouseup', up, true);
    event.preventDefault();
  }

  function setNotice(kind, text, actions) {
    S.notice = { kind, text, actions: actions || [] };
    render();
  }

  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[c]);

  const LOGO = '<svg width="18" height="18" viewBox="0 0 48 48" fill="none" aria-hidden="true">'
    + '<path d="M24 6 L38 14 L24 22 L10 14 Z M10 14 V30 L24 38 L38 30 V14 M24 22 V38" stroke="currentColor" stroke-width="3.5" stroke-linejoin="round" stroke-linecap="round"/>'
    + '<circle cx="24" cy="38" r="5" fill="#4C9AFF"/></svg>';
  const ICON_MIN = '<svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8h10" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>';
  const ICON_MAX = '<svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path d="M3 6l5 5 5-5" stroke="currentColor" stroke-width="1.6" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>';

  function sevBadge(sev) {
    return `<span class="sev ${esc(sev)}">${esc(SEV_LABEL[sev] || sev)}</span>`;
  }

  function render() {
    if (!shadow) return;
    const panel = shadow.querySelector('.ps');
    const body = panel.querySelector('.body');
    const list = panel.querySelector('.list');
    const scroll = { body: body ? body.scrollTop : 0, list: list ? list.scrollTop : 0 };

    panel.classList.toggle('collapsed', S.collapsed);
    panel.innerHTML = renderHead() + (S.collapsed ? '' : `<div class="body">${renderBody()}</div>${renderFoot()}`);

    const newBody = panel.querySelector('.body');
    const newList = panel.querySelector('.list');
    if (newBody) newBody.scrollTop = scroll.body;
    if (newList) newList.scrollTop = scroll.list;
  }

  function renderHead() {
    const ps = S.ps;
    const status = !ps.checked ? '' : ps.online
      ? '<span class="status on" title="PointSnap đang chạy"><i></i>PointSnap</span>'
      : '<span class="status" title="PointSnap chưa bật: vẫn dùng được bộ lọc, chuyển lỗi và thông báo lỗi"><i></i>PointSnap tắt</span>';
    const count = S.collapsed && S.flags.length ? `<span class="small" style="color:#B8C6D8">${S.flags.length} lỗi</span>` : '';
    return `<div class="head">${LOGO}<span class="brand">PointSnap</span>${count}${status}`
      + `<button class="icon-btn" data-action="collapse" aria-label="${S.collapsed ? 'Mở rộng' : 'Thu gọn'}" title="${S.collapsed ? 'Mở rộng' : 'Thu gọn'}">${S.collapsed ? ICON_MAX : ICON_MIN}</button></div>`;
  }

  function renderBody() {
    if (S.loading && !S.flags.length) return '<div class="empty">Đang đọc cờ lỗi của job từ CVAT…</div>';
    if (S.loadError) {
      return `<div class="note error">${esc(S.loadError)}<div class="actions"><button class="btn small" data-action="refresh">Thử lại</button></div></div>`;
    }
    if (!S.hasFlagAttr) {
      return '<div class="note warn">Job này chưa có thuộc tính <b>pointsnap_error</b>. Quét job bằng PointSnap và bấm "Gắn cờ lên CVAT", rồi tải lại trang.</div>';
    }
    let html = '';
    if (S.notice) html += renderNotice();
    if (!S.flags.length) {
      return `${html}<div class="note">Job không còn box nào mang cờ lỗi. Nếu vừa sửa xong, bấm <b>Quét + gắn cờ</b> để kiểm lại.</div>`;
    }
    html += renderNav();
    html += renderFilter();
    html += renderActive();
    html += renderFrameFlags();
    html += renderAll();
    return html;
  }

  function renderNotice() {
    const n = S.notice;
    const kind = n.kind === 'error' ? 'error' : n.kind === 'warn' ? 'warn' : '';
    const actions = [...n.actions, { action: 'dismiss', text: 'Đóng' }]
      .map((a) => `<button class="btn small" data-action="${esc(a.action)}">${esc(a.text)}</button>`).join('');
    return `<div class="note ${kind}" role="status">${esc(n.text)}<div class="actions">${actions}</div></div>`;
  }

  function renderNav() {
    const frame = S.frame;
    const pos = S.frames.indexOf(frame);
    const prev = frame === null ? null : core.stepFrame(S.frames, frame, -1);
    const next = core.stepFrame(S.frames, frame === null ? -1 : frame, 1);
    if (S.navTarget !== null && S.navTarget !== undefined) {
      return `<div class="nav"><button class="btn" disabled>‹ Trước</button><div class="where"><b>Frame ${S.navTarget}</b>`
        + '<span>CVAT đang tải frame…</span></div><button class="btn primary" disabled>Tiếp ›</button></div>';
    }
    const where = pos >= 0
      ? `<b>Frame ${frame}</b><span>frame lỗi ${pos + 1}/${S.frames.length}</span>`
      : `<b>Frame ${frame ?? '—'}</b><span>${S.frames.length} frame có lỗi · ${S.flags.length} box</span>`;
    return `<div class="nav">`
      + `<button class="btn" data-action="prev" ${prev === null ? 'disabled' : ''} title="Frame có lỗi trước (phím , hoặc [)">‹ Trước</button>`
      + `<div class="where">${where}</div>`
      + `<button class="btn primary" data-action="next" ${next === null ? 'disabled' : ''} title="Frame có lỗi tiếp theo (phím . hoặc ])">Tiếp ›</button>`
      + `</div><div class="small muted" style="text-align:center">Phím <span class="kbd">,</span> <span class="kbd">.</span> (hoặc <span class="kbd">[</span> <span class="kbd">]</span>) để chuyển lỗi, không tải lại trang</div>`;
  }

  function renderFilter() {
    let html = '<div class="row"><div class="grow small">';
    if (S.filterBusy) html += 'Đang bấm hộ bộ lọc của CVAT…';
    else if (S.filterOn) html += '<b>Đang lọc</b>: CVAT chỉ hiện box của bộ lọc đang bật';
    else html += 'CVAT đang hiện mọi box';
    html += '</div>';
    html += S.filterOn
      ? `<button class="btn small" data-action="filter-off" ${S.filterBusy ? 'disabled' : ''}>Hiện tất cả</button>`
      : `<button class="btn small on" data-action="filter-on" ${S.filterBusy ? 'disabled' : ''}>Chỉ box lỗi</button>`;
    html += '</div>';
    const p = S.filterProblem;
    if (p && !S.filterOn) {
      html += '<div class="note warn">';
      if (p.needsReload) {
        html += 'CVAT chưa nạp bộ lọc PointSnap (lần đầu mở task này). Tải lại trang một lần là xong.';
        html += '<div class="actions"><button class="btn small" data-action="reload">Tải lại trang</button></div>';
      } else {
        html += `${esc(p.reason)}.`;
      }
      html += `<div class="tip">Làm tay: Filters → Add rule → Attributes → nhãn → <b>${ATTR}</b> → is not empty → Submit.</div></div>`;
    }
    return html;
  }

  function renderItems(items) {
    return items.map((it) => `<div class="msg">${sevBadge(it.severity)} ${it.rule ? `<b>${esc(RULE_LABEL[it.rule] || it.rule)}:</b> ` : ''}${esc(it.text)}</div>`
      + `<div class="tip"><b>Gợi ý sửa:</b> ${esc(it.tip)}</div>`).join('');
  }

  function renderActive() {
    const a = S.active;
    let html = '<div class="section-title">Box đang chọn</div>';
    if (!a) return `${html}<div class="small muted">Rê chuột vào box (hoặc vào mục ở danh sách bên phải của CVAT) để xem lỗi của nó.</div>`;
    const name = `#${a.clientId ?? '?'} ${esc(a.label || '')}`;
    if (a.flag) {
      return `${html}<div class="card active"><div class="top"><span class="label">${name}</span>${sevBadge(core.worstSeverity(core.parseFlag(a.flag)))}</div>${renderItems(core.parseFlag(a.flag))}</div>`;
    }
    const here = flagsAt(S.frame).filter((f) => f.label === a.label);
    if (a.flag === '' || (a.flag === null && !here.length)) {
      return `${html}<div class="small muted">${name}: không có cờ lỗi.</div>`;
    }
    if (here.length === 1) {
      return `${html}<div class="card active"><div class="top"><span class="label">${name}</span>${sevBadge(here[0].severity)}</div>${renderItems(here[0].items)}</div>`;
    }
    return `${html}<div class="small muted">${name}: frame này có ${here.length} box ${esc(a.label)} mang cờ, xem ở mục dưới. Mở DETAILS của box bên phải CVAT để biết chính xác.</div>`;
  }

  function renderFrameFlags() {
    const here = flagsAt(S.frame);
    let html = `<div class="section-title">Ở frame này (${here.length})</div>`;
    if (!here.length) return `${html}<div class="small muted">Frame này không có box mang cờ. Bấm <b>Tiếp ›</b>.</div>`;
    here.forEach((flag) => {
      const index = S.flags.indexOf(flag);
      const isActive = S.active && S.active.flag && S.active.flag === flag.value;
      const rs = reviewState(flag);
      let actions = `<button class="btn small" data-action="highlight" data-i="${index}" title="Làm sáng box này trên khung 3D">Làm sáng box</button>`;
      if (rs) {
        actions += `<button class="btn small ${rs.verdict === 'ok' ? 'on' : ''}" data-action="review-ok" data-i="${index}">Đúng là lỗi</button>`;
        actions += `<button class="btn small ${rs.verdict === 'fp' ? 'on' : ''}" data-action="review-fp" data-i="${index}">Báo nhầm</button>`;
      }
      html += `<div class="card ${isActive ? 'active' : ''}"><div class="top"><span class="label">${esc(flag.label)}</span>`
        + `<span style="margin-left:auto">${sevBadge(flag.severity)}</span></div>${renderItems(flag.items)}`
        + `<div class="actions">${actions}</div></div>`;
    });
    return html;
  }

  function renderAll() {
    const counts = { all: S.flags.length, error: 0, warning: 0 };
    S.flags.forEach((f) => { if (counts[f.severity] !== undefined) counts[f.severity] += 1; });
    const chip = (key, text) => `<button class="chip ${S.listFilter === key ? 'on' : ''}" data-action="list-filter" data-k="${key}">${text} ${counts[key]}</button>`;
    const shown = S.flags.filter((f) => S.listFilter === 'all' || f.severity === S.listFilter);
    let html = `<div class="section-title">Tất cả lỗi của job<span class="chips">${chip('all', 'Tất cả')}${chip('error', 'Lỗi')}${chip('warning', 'Cảnh báo')}</span></div>`;
    if (!shown.length) return `${html}<div class="empty">Không có mục nào.</div>`;
    html += '<div class="list">';
    shown.forEach((flag) => {
      const rs = reviewState(flag);
      const verdict = rs && rs.verdict ? `<span class="verdict ${rs.verdict}">${rs.verdict === 'ok' ? 'Đúng' : 'Nhầm'}</span>` : sevBadge(flag.severity);
      const first = flag.items[0];
      const more = flag.items.length > 1 ? ` (+${flag.items.length - 1})` : '';
      html += `<button class="item ${flag.frame === S.frame ? 'current' : ''}" data-action="goto" data-f="${flag.frame}" title="${esc(flag.value)}">`
        + `<span class="f">#${flag.frame}</span><span class="t"><b>${esc(flag.label)}</b> · ${esc(RULE_LABEL[first.rule] || first.text)}${more}</span>${verdict}</button>`;
    });
    return `${html}</div>`;
  }

  function renderFoot() {
    const ps = S.ps;
    let html = '<div class="foot">';
    if (!ps.checked) return `${html}<div class="small muted">Đang tìm PointSnap…</div></div>`;
    if (!ps.online) {
      return `${html}<div class="small muted">PointSnap chưa bật: chạy <b>pointsnap ui</b> để quét lại, gắn cờ và ghi Đúng / Báo nhầm ngay tại đây.</div>`
        + '<div class="row"><button class="btn small" data-action="refresh">Kiểm tra lại</button></div></div>';
    }
    if (ps.active) {
      const pct = Math.max(3, Math.min(100, Number(ps.active.progress) || 0));
      return `${html}<div class="small">${esc(ps.active.message || 'Đang quét…')}</div><div class="progress"><i style="width:${pct}%"></i></div></div>`;
    }
    const run = ps.run;
    if (run && run.summary) {
      const s = run.summary;
      const when = (run.started_at || '').replace('T', ' ').slice(0, 16);
      const reviewed = Object.keys(run.reviews || {}).length;
      html += `<div class="small"><b>Lần quét gần nhất</b> ${esc(when)} · ${s.num_errors ?? 0} Lỗi · ${s.num_warnings ?? 0} Cảnh báo`
        + `${reviewed ? ` · đã xem ${reviewed}` : ''}</div>`;
      const stale = S.flags.filter((f) => !reviewState(f)).length;
      if (stale) {
        html += `<div class="small muted">${stale} cờ trên CVAT không có trong lần quét này (cờ cũ hoặc box đã sửa): bấm <b>Quét + gắn cờ</b> để đồng bộ.</div>`;
      }
    } else if (ps.project) {
      html += `<div class="small muted">Dự án ${esc(ps.project.name)}: job này chưa được quét.</div>`;
    } else {
      html += `<div class="small muted">PointSnap chưa có dự án nối với ${esc(location.origin)}.</div>`;
    }
    if (S.confirmFlag) {
      html += '<div class="note warn">Gắn cờ sẽ ghi lên nhãn của job này. <b>Save</b> trên CVAT trước, và sau khi gắn cờ thì tải lại trang trước khi sửa tiếp.'
        + '<div class="actions"><button class="btn small primary" data-action="scan-flag-go">Gắn cờ</button><button class="btn small" data-action="scan-flag-cancel">Thôi</button></div></div>';
    }
    html += `<div class="row"><button class="btn small" data-action="scan" ${ps.project ? '' : 'disabled'}>Quét lại</button>`
      + `<button class="btn small" data-action="scan-flag" ${ps.project ? '' : 'disabled'}>Quét + gắn cờ</button>`
      + '<button class="btn small" data-action="refresh" title="Đọc lại cờ trên CVAT và kết quả PointSnap">Làm mới</button></div>';
    return `${html}</div>`;
  }

  // ---------------------------------------------------------------- sự kiện

  function onClick(event) {
    const button = event.target.closest('[data-action]');
    if (!button || button.disabled) return;
    const action = button.dataset.action;
    const flag = button.dataset.i !== undefined ? S.flags[Number(button.dataset.i)] : null;
    switch (action) {
      case 'collapse':
        S.collapsed = !S.collapsed;
        saveLocal({ panelCollapsed: S.collapsed });
        render();
        break;
      case 'prev': step(-1); break;
      case 'next': step(1); break;
      case 'goto': goTo(Number(button.dataset.f)); break;
      case 'filter-on': turnFilterOn(false); break;
      case 'filter-off': turnFilterOff(); break;
      case 'highlight': highlight(flag, 1); break;
      case 'review-ok': review(flag, 'ok'); break;
      case 'review-fp': review(flag, 'fp'); break;
      case 'list-filter':
        S.listFilter = button.dataset.k;
        render();
        break;
      case 'scan': startScan(false); break;
      case 'scan-flag':
        S.confirmFlag = true;
        render();
        break;
      case 'scan-flag-go': startScan(true); break;
      case 'scan-flag-cancel':
        S.confirmFlag = false;
        render();
        break;
      case 'refresh':
        S.notice = null;
        loadFlags(S.sid);
        loadPointSnap(S.sid);
        break;
      case 'reload': location.reload(); break;
      case 'dismiss':
        S.notice = null;
        render();
        break;
      default:
        break;
    }
  }

  function isTyping(target) {
    if (!target) return false;
    const tag = target.tagName;
    return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target.isContentEditable;
  }

  // Phím , . (như tua từng khung trên YouTube) và [ ]: CVAT không dùng các phím này (J là Join, K là Switch keyframe nên tránh).
  // Nhận theo cả mã phím lẫn ký tự; , . không bị bộ gõ tiếng Việt kiểu Telex đổi thành chữ như [ ] (ư, ơ).
  const NAV_KEYS = { Period: 1, BracketRight: 1, '.': 1, ']': 1, Comma: -1, BracketLeft: -1, ',': -1, '[': -1 };
  window.addEventListener('keydown', (event) => {
    if (!S.job || !S.frames.length || event.ctrlKey || event.metaKey || event.altKey || isTyping(event.target)) return;
    if (document.querySelector('.ant-modal-wrap:not([style*="display: none"]) .ant-modal')) return;
    const dir = NAV_KEYS[event.code] || NAV_KEYS[event.key] || 0;
    if (!dir) return;
    event.preventDefault();
    event.stopPropagation();
    step(dir);
  }, true);

  root.PointSnapPanel = { state: S, onRoute, step, goTo, turnFilterOn, render };

  loadSettings().then(() => {
    onRoute();
    setInterval(onRoute, 500);
  });
})(globalThis);
