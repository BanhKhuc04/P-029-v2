'use strict';
// Đề xuất sửa theo mục của lần quét: extension chỉ đọc được mục thuộc đúng job / CVAT đang mở, như route camera.
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

function background(fetch) {
  const noop = { addListener() {} };
  const id = 'a'.repeat(32);
  const context = { URL, Set, AbortSignal, fetch, btoa, Uint8Array, chrome: {
    runtime: { id, getURL: () => `chrome-extension://${id}/`, onMessage: noop, onInstalled: noop },
    storage: { sync: { get: async () => ({ pointsnapUrl: 'http://127.0.0.1:8765', cvatUrls: [] }) }, onChanged: noop },
    permissions: { onAdded: noop, onRemoved: noop, contains: async () => true }, action: { onClicked: noop }, scripting: {} } };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../background.js'), 'utf8')
    + '\nglobalThis.api={requestRoute,callPointSnap};', context);
  return context.api;
}

const sender = { id: 'a'.repeat(32), url: 'http://localhost:8080/tasks/1/jobs/2', frameId: 0, tab: { id: 1 } };
const run = '20261011-123456-job2';
const repairPath = `/api/projects/a/scans/${run}/findings/0/repair`;

test('finding repair route is read-only and refuses smuggling', () => {
  const b = background();
  assert.ok(b.requestRoute('GET', repairPath, undefined, sender));
  for (const p of [repairPath + '?full=1', repairPath.replace('/0/', '/%30/'), repairPath.replace('/repair', '/apply-repair'),
    repairPath.replace('/projects/a/', '/projects/../'), `/api/projects/a/scans/${run}/findings/x/repair`]) {
    assert.equal(b.requestRoute('GET', p, undefined, sender), null, p);
  }
  assert.equal(b.requestRoute('POST', repairPath, { frame: 1 }, sender), null);
  assert.equal(b.requestRoute('GET', repairPath, {}, sender), null);
});

test('finding repair is refused for another job, missing finding or another CVAT', async () => {
  const cases = [
    [{ cvat_url: 'http://localhost:8080' }, { job_id: 99, findings: [{}] }],
    [{ cvat_url: 'http://localhost:8080' }, { job_id: 2, findings: [] }],
    [{ cvat_url: 'http://other:8080' }, { job_id: 2, findings: [{}] }],
  ];
  for (const [project, runData] of cases) {
    const calls = [];
    const b = background(async (u) => { calls.push(u); return { ok: true, status: 200, json: async () => (u.endsWith('/api/projects/a') ? project : runData) }; });
    const r = await b.callPointSnap({ method: 'GET', path: repairPath }, sender);
    assert.equal(r.ok, false);
    assert.ok(!calls.some((u) => u.endsWith('/repair')), 'không gọi endpoint sửa khi kiểm tra thất bại');
  }
});

test('finding repair returns the proposal for the open job', async () => {
  const b = background(async (u) => ({ ok: true, status: 200, json: async () => (
    u.endsWith('/api/projects/a') ? { cvat_url: 'http://localhost:8080' }
      : u.endsWith('/repair') ? { repair: { delta_center: [0, 0, -0.26], confidence: 0.9 }, track_etag: 'e' }
        : { job_id: 2, findings: [{}] }) }));
  const r = await b.callPointSnap({ method: 'GET', path: repairPath }, sender);
  assert.equal(r.ok, true);
  assert.equal(r.data.track_etag, 'e');
  assert.deepEqual(r.data.repair.delta_center, [0, 0, -0.26]);
});
