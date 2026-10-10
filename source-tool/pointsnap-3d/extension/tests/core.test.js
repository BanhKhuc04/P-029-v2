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

test('parseFlag nhận luật sai hướng box, box lệch (C1) và luật bám spec (C2)', () => {
  const cases = {
    'heading.flip': 'Hướng box ngược đầu (lật box) 180° so với keyframe gần nhất của phần còn lại của track (frame 3); đổi hướng nhanh bất thường (ngưỡng 75°)',
    'heading.motion': 'Hướng box ngược chiều 178° so với hướng chuyển động của vật (10.0 m/s, frame 2–4; ngưỡng 135°)',
    'heading.points': 'Trục box lệch 25° so với trục của cụm điểm LiDAR của vật (ngưỡng 15°)',
    'fit.empty': 'Box không có điểm LiDAR nào (0 điểm): vẽ vào chỗ trống, hoặc vật bị che thì đánh dấu occluded',
    'fit.outside': '40/60 điểm của vật (67%) nằm ngoài box, nhiều nhất phía đầu (tới 50 cm): box nhỏ hoặc lệch khỏi vật (ngưỡng 50%)',
    'fit.loose': 'Mặt đầu của box cách điểm gần nhất của vật 80 cm dù nhìn thấy rõ từ LiDAR: box dư so với vật (ngưỡng 50 cm)',
    'fit.overlap': 'Box chồng 90% diện tích lên box car (track 2): nghi vẽ trùng một vật hoặc hai box lấn nhau (ngưỡng 50%)',
    'track.reuse_id': 'Track đã kết thúc (outside) ở frame 2 rồi xuất hiện lại ở frame 4 sau 2 frame vắng: vật chỉ bị che tạm thời thì bỏ outside, đánh dấu occluded (spec 4.4.5)',
    'track.occluded_long': 'Box đánh occluded 8 frame liền (frame 1–8), quá 6 frame: spec 4.4.5 chỉ dùng occluded cho che khuất tạm thời',
    'attr.missing': 'Vehicle thiếu thuộc tính bắt buộc `subtype` (2 keyframe, từ frame 0); spec 3.1.3: không chắc thì chọn other',
    'attr.invalid': "Thuộc tính `pose` = 'walking' không có trong danh sách cho phép (standing, sitting, bending) (frame 0)",
    'track.static_shift': 'Vật đứng yên (các keyframe khác tụ trong 3 cm) nhưng box ở frame này lệch 31 cm so với vị trí chung (ngưỡng 20 cm)',
    'heading.static': 'Vật đứng yên nhưng hướng box ở frame này lệch 14.3° so với các keyframe khác của track (ngưỡng 10°)',
    'cam.mismatch': 'Box chiếu lên ảnh CAM_FRONT: 48% thân vật trên ảnh nằm ngoài khung box, các frame khác của track chỉ 6% (IoU 41%): box lệch hoặc nhỏ so với vật',
    'cam.class': 'Ảnh camera nhận vật là người ở 5/6 lần nhìn rõ, nhãn là car: nghi sai class',
    'cam.missing': 'Ảnh CAM_FRONT thấy xe (độ tin cậy 97%, cách ~18 m, 120 điểm LiDAR) nhưng không có box 3D nào: nghi sót đối tượng',
    'critic.box': 'Box Critic: box nghi vẽ sai (xác suất 93%); gợi ý sửa: dời (+0.32, -0.05, +0.00) m, kích thước (+0.00, +0.00, +0.00) m, xoay +3.1°',
  };
  for (const [rule, text] of Object.entries(cases)) {
    const items = core.parseFlag(`[Lỗi] ${text}`);
    assert.equal(items.length, 1, rule);
    assert.equal(items[0].rule, rule);
    assert.notEqual(items[0].tip, core.parseFlag('[Lỗi] câu lạ')[0].tip, rule);
  }
});
