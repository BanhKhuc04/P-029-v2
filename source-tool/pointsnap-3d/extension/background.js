/*
 * Service worker của extension PointSnap cho CVAT (A15).
 * - Gọi API PointSnap thay cho content script (quyền host của extension nên PointSnap không cần mở CORS).
 * - Đăng ký content script cho địa chỉ CVAT khác mặc định mà người dùng đã cấp quyền ở trang Tùy chọn.
 */
'use strict';

const DEFAULTS = { pointsnapUrl: 'http://127.0.0.1:8765', cvatUrls: [] };
const METHODS = new Set(['GET', 'POST', 'PUT']);
const EARLY_JS = ['src/core.js', 'src/cvat-dom.js', 'src/cvat-api.js', 'src/seed.js'];
const PANEL_JS = ['src/panel-css.js', 'src/content.js'];

function originPattern(url) {
  return `${new URL(url).origin}/*`;
}

async function callPointSnap({ method, path, body }) {
  if (!METHODS.has(method) || typeof path !== 'string' || !path.startsWith('/api/') || path.includes('..')) {
    return { ok: false, error: 'Yêu cầu không hợp lệ' };
  }
  const { pointsnapUrl } = await chrome.storage.sync.get(DEFAULTS);
  const base = String(pointsnapUrl || DEFAULTS.pointsnapUrl).replace(/\/+$/, '');
  try {
    const res = await fetch(`${base}${path}`, {
      method,
      headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(10000),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      const detail = data && data.detail;
      return { ok: false, status: res.status, error: typeof detail === 'string' ? detail : `PointSnap trả ${res.status}` };
    }
    return { ok: true, status: res.status, data };
  } catch (_) {
    return { ok: false, error: `Không kết nối được PointSnap ở ${base}` };
  }
}

const BUILT_IN_CVAT = ['http://localhost:8080', 'http://127.0.0.1:8080'];

/** Chỉ nhận yêu cầu từ trang của chính extension hoặc từ trang CVAT đã cấu hình, không từ trang web khác. */
async function trustedSender(sender) {
  if (sender.id !== chrome.runtime.id) return false;
  if ((sender.url || '').startsWith(chrome.runtime.getURL(''))) return true;
  let origin;
  try {
    origin = new URL(sender.url || '').origin;
  } catch (_) {
    return false;
  }
  if (BUILT_IN_CVAT.includes(origin)) return true;
  const { cvatUrls } = await chrome.storage.sync.get(DEFAULTS);
  return (cvatUrls || []).some((url) => {
    try {
      return new URL(url).origin === origin;
    } catch (_) {
      return false;
    }
  });
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || message.type !== 'pointsnap') return false;
  trustedSender(sender).then((ok) => (ok ? callPointSnap(message) : { ok: false, error: 'Nguồn yêu cầu không được phép' }))
    .then(sendResponse);
  return true;
});

/** Đăng ký content script cho các địa chỉ CVAT thêm ở trang Tùy chọn (chỉ những địa chỉ đã được cấp quyền). */
async function syncContentScripts() {
  const { cvatUrls } = await chrome.storage.sync.get(DEFAULTS);
  const matches = [];
  for (const url of cvatUrls || []) {
    try {
      const pattern = originPattern(url);
      if (await chrome.permissions.contains({ origins: [pattern] })) matches.push(pattern);
    } catch (_) {
      // Bỏ qua địa chỉ không hợp lệ.
    }
  }
  const registered = await chrome.scripting.getRegisteredContentScripts();
  const ids = registered.map((s) => s.id).filter((id) => id.startsWith('pointsnap-'));
  if (ids.length) await chrome.scripting.unregisterContentScripts({ ids });
  if (!matches.length) return;
  await chrome.scripting.registerContentScripts([
    { id: 'pointsnap-early', matches, js: EARLY_JS, runAt: 'document_start', persistAcrossSessions: true },
    { id: 'pointsnap-panel', matches, js: PANEL_JS, runAt: 'document_idle', persistAcrossSessions: true },
  ]);
}

chrome.runtime.onInstalled.addListener(() => { syncContentScripts(); });
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === 'sync' && changes.cvatUrls) syncContentScripts();
});
chrome.permissions.onAdded.addListener(() => { syncContentScripts(); });
chrome.permissions.onRemoved.addListener(() => { syncContentScripts(); });
chrome.action.onClicked.addListener(() => { chrome.runtime.openOptionsPage(); });
