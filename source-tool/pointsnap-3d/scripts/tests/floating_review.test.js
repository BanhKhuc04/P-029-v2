// Viewer contract tests with synthetic fixtures; these answers never enter real review packets.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function viewer(initial = {}, storageFails = false) {
  const template = fs.readFileSync(path.join(__dirname, '..', 'floating_review.html'), 'utf8');
  const code = template.match(/<script>\s*([\s\S]*?)<\/script>/)[1];
  const packet = {
    provenance: { package_sha256: 'test-package', config_sha256: 'test-config', dataset: 'synthetic test only' },
    cases: [0, 1].map(i => ({
      number: i + 1, scene: 'synthetic', object_points: 40, context: 'fixture.png', context_frames: [0, 2],
      camera: null, camera_channel: null, box: { length: 4, width: 2, height: 1.6 }, points: [[0, 0, 0]],
      ground: { z: -.9, pitch_deg: 0 },
      finding: { frame: 1, track_id: i + 1, label: 'car', rule: 'floating', severity: 'warning',
        severity_label: 'Cảnh báo', message: 'synthetic only', value: .2, threshold: .08 },
      proposal: i === 0 ? { delta_z_m: -.2, reference_distance_m: .05, reference_frames: [0, 2] } : null,
      proposal_reason: i === 1 ? 'Ambiguous ground' : '',
    })),
  };
  const elements = new Map();
  function element(id) {
    if (!elements.has(id)) {
      const rects = [];
      elements.set(id, { id, value: '', textContent: '', hidden: false, disabled: false, checked: false,
        clientWidth: 400, children: [], rects, append(item) { this.children.push(item); }, click() {},
        getContext() { return new Proxy({ strokeRect(...args) { rects.push(args); } }, { get: (o, k) => o[k] || (() => {}) }); },
      });
    }
    return elements.get(id);
  }
  element('packet').textContent = JSON.stringify(packet);
  const radios = { verdict: ['Đúng lỗi', 'Báo nhầm', 'Không rõ'].map(value => ({ value })),
    'repair-verdict': ['Tốt hơn', 'Không tốt hơn', 'Không rõ'].map(value => ({ value })) };
  const storage = new Map(Object.entries(initial));
  let exported;
  const context = vm.createContext({
    document: { getElementById: element, createElement: () => element('created-' + elements.size),
      querySelectorAll: q => radios[q.match(/name=([^\]]+)/)[1]], },
    window: { devicePixelRatio: 1, addEventListener() {} },
    localStorage: { getItem: k => storage.get(k) || null, setItem(k, value) { if (storageFails) throw Error('full'); storage.set(k, value); } },
    Blob, URL: { createObjectURL(blob) { exported = blob; return 'blob:test'; }, revokeObjectURL() {} },
    setTimeout: f => f(),
  });
  vm.runInContext(code, context);
  return { element, storage, key: 'pointsnap-floating-review:test-package:test-config:2',
    verdict(v) { element('detection-answers').onchange({ target: { value: v } }); },
    next() { element('next').onclick(); },
    async csv() { element('export').onclick(); return exported.text(); },
  };
}

test('Initial packet has no human verdicts and does not present a repair before review', async () => {
  const ui = viewer();
  assert.match(ui.element('progress').textContent, /Đã chấm 0\/2/);
  assert.match(ui.element('progress').textContent, /Precision mô tả chưa có/);
  assert.equal(ui.element('repair-section').hidden, true);
  assert.equal(ui.storage.size, 0);
  const csv = await ui.csv();
  assert.equal(csv.split('\r\n').length, 3);
  assert.match(csv, /"synthetic only","","","",""/);
});

test('Unknown is counted separately and excluded from the precision denominator', () => {
  const ui = viewer();
  ui.verdict('Không rõ');
  assert.match(ui.element('progress').textContent, /Không rõ 1/);
  assert.match(ui.element('progress').textContent, /Precision mô tả chưa có/);
  ui.next(); ui.verdict('Đúng lỗi');
  assert.match(ui.element('progress').textContent, /Precision mô tả 100\.0%/);
  assert.match(ui.element('progress').textContent, /G7 chưa nghiệm thu/);
});

test('Show proposal changes side-view rectangle only after the user accepts the detection', () => {
  const ui = viewer();
  ui.verdict('Đúng lỗi');
  assert.equal(ui.element('repair-section').hidden, false);
  assert.equal(ui.element('repair-answers').hidden, true);
  ui.element('preview-toggle').onclick();
  const rects = ui.element('side').rects.slice(-2);
  assert.equal(rects.length, 2);
  assert.notEqual(rects[0][1], rects[1][1]);
  assert.equal(ui.element('repair-answers').hidden, false);
});

test('Blocked proposal stays manual and cannot be displayed as an available correction', () => {
  const ui = viewer(); ui.next(); ui.verdict('Đúng lỗi');
  assert.equal(ui.element('preview-toggle').disabled, true);
  assert.match(ui.element('repair-text').textContent, /Giữ sửa tay: Ambiguous ground/);
});

test('Changing the detection verdict clears a stale repair verdict', () => {
  const ui = viewer(); ui.verdict('Đúng lỗi');
  const saved = JSON.parse(ui.storage.get(ui.key));
  saved['synthetic|1|1|car|floating'].repair_verdict = 'Tốt hơn';
  saved['synthetic|1|1|car|floating'].repair_note = 'synthetic only';
  const again = viewer({ [ui.key]: JSON.stringify(saved) });
  again.verdict('Báo nhầm');
  const result = JSON.parse(again.storage.get(again.key))['synthetic|1|1|car|floating'];
  assert.equal(result.repair_verdict, ''); assert.equal(result.repair_note, '');
  assert.equal(again.element('repair-section').hidden, true);
});

test('CSV preserves human labels and quotes text; text formula prefixes are escaped', async () => {
  const ui = viewer(); ui.verdict('Đúng lỗi');
  ui.element('note').oninput({ target: { value: '=1+1,"line"\nnext' } });
  const csv = await ui.csv();
  assert.match(csv, /"Đúng lỗi"/);
  assert.match(csv, /"'=1\+1,""line""\nnext"/);
});

test('Storage failure is visible and does not prevent CSV export', async () => {
  const ui = viewer({}, true); ui.verdict('Không rõ');
  assert.match(ui.element('storage-status').textContent, /Hãy tải CSV/);
  assert.match(await ui.csv(), /"Không rõ"/);
});
