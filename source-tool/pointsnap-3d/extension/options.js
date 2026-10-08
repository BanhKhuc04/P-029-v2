'use strict';

const DEFAULTS = { pointsnapUrl: 'http://127.0.0.1:8765', cvatUrls: [], autoFilter: true, autoHighlight: true };
const BUILT_IN = new Set(['http://localhost:8080', 'http://127.0.0.1:8080']);
const $ = (id) => document.getElementById(id);

function setStatus(text, kind) {
  $('status').textContent = text;
  $('status').className = kind || '';
}

function readForm() {
  const urls = $('cvat-urls').value.split('\n').map((s) => s.trim()).filter(Boolean);
  const origins = [];
  for (const url of urls) {
    try {
      const origin = new URL(url).origin;
      if (!BUILT_IN.has(origin) && !origins.includes(origin)) origins.push(origin);
    } catch (_) {
      return { error: `Địa chỉ CVAT không hợp lệ: ${url}` };
    }
  }
  let pointsnap;
  try {
    pointsnap = new URL($('pointsnap-url').value.trim() || DEFAULTS.pointsnapUrl).origin;
  } catch (_) {
    return { error: 'Địa chỉ PointSnap không hợp lệ' };
  }
  return {
    pointsnapUrl: pointsnap,
    cvatUrls: origins,
    autoFilter: $('auto-filter').checked,
    autoHighlight: $('auto-highlight').checked,
  };
}

chrome.storage.sync.get(DEFAULTS, (data) => {
  $('pointsnap-url').value = data.pointsnapUrl;
  $('cvat-urls').value = (data.cvatUrls || []).join('\n');
  $('auto-filter').checked = !!data.autoFilter;
  $('auto-highlight').checked = !!data.autoHighlight;
});

$('save').addEventListener('click', () => {
  const values = readForm();
  if (values.error) {
    setStatus(values.error, 'err');
    return;
  }
  // Xin quyền ngay trong lần bấm (Chrome chỉ cho xin quyền khi người dùng vừa thao tác).
  const origins = [...values.cvatUrls, values.pointsnapUrl].map((o) => `${o}/*`);
  chrome.permissions.request({ origins }, (granted) => {
    if (!granted) {
      setStatus('Chưa được cấp quyền truy cập các địa chỉ trên, chưa lưu.', 'err');
      return;
    }
    chrome.storage.sync.set(values, () => setStatus('Đã lưu. Tải lại trang CVAT để áp dụng.', 'ok'));
  });
});

$('test').addEventListener('click', () => {
  setStatus('Đang kiểm tra…');
  chrome.runtime.sendMessage({ type: 'pointsnap', method: 'GET', path: '/api/projects' }, (res) => {
    if (res && res.ok) setStatus(`Kết nối được PointSnap: ${res.data.length} dự án.`, 'ok');
    else setStatus((res && res.error) || 'Không kết nối được PointSnap.', 'err');
  });
});
