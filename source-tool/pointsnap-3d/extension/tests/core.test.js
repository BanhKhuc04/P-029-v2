// Test phần logic thuần của extension: `node --test extension/tests`
const test = require('node:test');
const assert = require('node:assert/strict');
const core = require('../src/core.js');

test('parseJobUrl nhận trang job, bỏ qua trang khác', () => {
  assert.deepEqual(core.parseJobUrl('http://localhost:8080/tasks/2/jobs/2?frame=5'), { taskId: 2, jobId: 2 });
  assert.equal(core.parseJobUrl('http://localhost:8080/tasks/2'), null);
  assert.equal(core.parseJobUrl('không phải url'), null);
});

test('parseFlag tách nhiều mục, nhận luật và gợi ý sửa', () => {
  const items = core.parseFlag(
    '[Lỗi] Tâm box nhảy vị trí 2.31 m so với vị trí nội suy (ngưỡng 2.0 m); '
    + '[Cảnh báo] Đáy box lơ lửng 18.0 cm so với mặt đất (ngưỡng 12 cm)',
  );
  assert.equal(items.length, 2);
  assert.equal(items[0].severity, 'error');
  assert.equal(items[0].rule, 'track.jump');
  assert.equal(items[1].severity, 'warning');
  assert.equal(items[1].rule, 'floating');
  assert.match(items[1].tip, /Hạ đáy box/);
  assert.equal(core.worstSeverity(items), 'error');
  assert.deepEqual(core.parseFlag(''), []);
  // Mẫu câu thật của luật lơ lửng / lún (so với track) trên job scene-0061.
  const sink = core.parseFlag('[Lỗi] Đáy box nằm dưới mặt đất 31 cm (lún); thấp hơn 27 cm so với các frame khác của track (trung vị -4 cm)')[0];
  assert.equal(sink.rule, 'floating');
  assert.match(sink.tip, /Nâng đáy box/);
  assert.equal(core.parseFlag('[Cảnh báo] Đáy box cách mặt đất 14 cm (lơ lửng); cao hơn 25 cm so với các frame khác của track (trung vị -11 cm)').length, 1);
});

test('collectFlags đọc cờ từ shape lẻ và keyframe của track', () => {
  const labels = [
    { id: 1, name: 'car', attributes: [{ id: 11, name: 'pointsnap_error' }] },
    { id: 2, name: 'tree', attributes: [] },
  ];
  const specs = core.flagSpecs(labels);
  assert.deepEqual([...specs.keys()], [1]);
  const annotations = {
    shapes: [
      { id: 5, type: 'cuboid', frame: 7, label_id: 1, attributes: [{ spec_id: 11, value: '[Cảnh báo] Chiều rộng 3.52 m bất thường so với class car' }] },
      { id: 6, type: 'cuboid', frame: 1, label_id: 1, attributes: [{ spec_id: 11, value: '' }] },
      { id: 7, type: 'cuboid', frame: 1, label_id: 2, attributes: [] },
    ],
    tracks: [{
      id: 9,
      label_id: 1,
      shapes: [
        { type: 'cuboid', frame: 3, outside: false, attributes: [{ spec_id: 11, value: '[Lỗi] Box dịch 40.0 m/s so với frame 2 (tối đa 30 m/s cho car)' }] },
        { type: 'cuboid', frame: 4, outside: false, attributes: [] },
        { type: 'cuboid', frame: 7, outside: true, attributes: [{ spec_id: 11, value: '[Lỗi] cũ' }] },
      ],
    }],
  };
  const flags = core.collectFlags(annotations, specs);
  assert.deepEqual(flags.map((f) => [f.frame, f.kind, f.objectId, f.severity]), [
    [3, 'track', 9, 'error'],
    [7, 'shape', 5, 'warning'],
  ]);
  assert.deepEqual(core.flaggedFrames(flags), [3, 7]);
});

test('stepFrame đi tới / lui giữa các frame có cờ', () => {
  const frames = [3, 7, 12];
  assert.equal(core.stepFrame(frames, 0, 1), 3);
  assert.equal(core.stepFrame(frames, 3, 1), 7);
  assert.equal(core.stepFrame(frames, 12, 1), null);
  assert.equal(core.stepFrame(frames, 7, -1), 3);
  assert.equal(core.stepFrame(frames, 3, -1), null);
});

test('filterLogic dùng đúng tên trường của bộ lọc CVAT', () => {
  assert.deepEqual(core.filterLogic(['car', 'vehicle.bus', 'car']), {
    or: [
      { '!!': { var: 'attr.car.pointsnap_error' } },
      { '!!': { var: 'attr.vehicle∙bus.pointsnap_error' } },
    ],
  });
});

test('matchFindings ghép mục của lần quét với cờ trên CVAT', () => {
  const flag = { frame: 3, label: 'car', value: '[Lỗi] A; [Cảnh báo] B' };
  const findings = [
    { frame: 3, label: 'car', message: 'B' },
    { frame: 3, label: 'truck', message: 'A' },
    { frame: 4, label: 'car', message: 'A' },
    { frame: 3, label: 'car', message: 'A' },
  ];
  assert.deepEqual(core.matchFindings(findings, flag), [0, 3]);
});
