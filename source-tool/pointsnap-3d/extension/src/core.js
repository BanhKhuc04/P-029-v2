/*
 * Phần logic thuần của extension PointSnap cho CVAT (A15): không đụng DOM, không gọi mạng.
 * Chạy được cả trong content script (gắn vào globalThis.PointSnapCore) lẫn Node (module.exports) để test.
 */
(function (root) {
  'use strict';

  const FLAG_ATTR = 'pointsnap_error';

  // Gợi ý sửa theo luật, cùng nội dung với bảng RULE_FIX_TIPS của giao diện web PointSnap.
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
    'track.occluded_long': 'Che khuất quá 6 frame: kết thúc track (Switch outside) và tạo track mới khi vật xuất hiện lại, trừ khi chắc chắn là cùng vật (spec 4.4.5).',
    'attr.missing': 'Chọn giá trị cho thuộc tính bắt buộc; không chắc thì chọn other (spec 3.1.3).',
    'attr.invalid': 'Chọn lại giá trị thuộc tính theo danh sách của guideline dự án.',
    'track.static_shift': 'Vật đứng yên: kéo box về trùng vị trí ở các keyframe khác của track (hoặc copy box từ keyframe đúng).',
    'heading.static': 'Vật đứng yên: xoay box về cùng hướng với các keyframe khác của track.',
  };
  const SINK_FIX_TIP = 'Nâng đáy box lên cho chạm mặt đường, đối chiếu ảnh camera trước và các frame lân cận của track.';
  const DEFAULT_FIX_TIP = 'Kiểm tra lại box và nhãn theo hướng dẫn gán nhãn của dự án.';

  // Cờ trên CVAT chỉ chứa câu thông báo, nên nhận luật từ mẫu câu của từng bộ phát hiện.
  const RULE_PATTERNS = [
    ['track.static_shift', /^Vật đứng yên \(các keyframe khác/i],
    ['heading.static', /^Vật đứng yên nhưng hướng box/i],
    ['heading.flip', /đổi hướng nhanh bất thường/i],
    ['heading.motion', /so với hướng chuyển động/i],
    ['heading.points', /trục của cụm điểm/i],
    ['fit.empty', /^Box (không có|chỉ có) .*điểm LiDAR/i],
    ['fit.outside', /nằm ngoài box/i],
    ['fit.loose', /box dư so với vật/i],
    ['fit.overlap', /^Box chồng .* diện tích/i],
    ['track.reuse_id', /đã kết thúc \(outside\)/i],
    ['track.occluded_long', /đánh occluded \d+ frame liền/i],
    ['attr.missing', /thiếu thuộc tính bắt buộc/i],
    ['attr.invalid', /không có trong danh sách cho phép/i],
    ['floating.no_evidence', /thiếu bằng chứng/i],
    ['floating', /\((lơ lửng|lún)\)|so với mặt đất/i],
    ['size.class_range', /bất thường so với class/i],
    ['size.in_track', /so với trung vị track/i],
    ['track.long_interpolation', /nên thêm keyframe/i],
    ['track.split_id', /nghi tách ID/i],
    ['track.jump', /(Tâm box nhảy|Box dịch .* m\/s)/i],
  ];

  const SEVERITIES = { 'Lỗi': 'error', 'Cảnh báo': 'warning', 'Thông tin': 'info' };
  const SEVERITY_RANK = { error: 0, warning: 1, info: 2 };

  /** `/tasks/<t>/jobs/<j>` → { taskId, jobId }; trang khác → null. */
  function parseJobUrl(href) {
    let url;
    try {
      url = new URL(href);
    } catch (_) {
      return null;
    }
    const m = url.pathname.match(/\/tasks\/(\d+)\/jobs\/(\d+)\/?$/);
    return m ? { taskId: Number(m[1]), jobId: Number(m[2]) } : null;
  }

  /** Bỏ dấu `/` cuối để so sánh URL gốc (http://localhost:8080/ ≡ http://localhost:8080). */
  function normalizeBase(url) {
    return String(url || '').trim().replace(/\/+$/, '');
  }

  function ruleOfMessage(text) {
    const hit = RULE_PATTERNS.find(([, re]) => re.test(text));
    return hit ? hit[0] : null;
  }

  /** Gợi ý sửa của một câu thông báo; box lún thì nâng lên thay vì hạ xuống. */
  function fixTip(rule, text) {
    if (rule === 'floating' && /\(lún\)|nằm dưới mặt đất/i.test(text || '')) return SINK_FIX_TIP;
    return RULE_FIX_TIPS[rule] || DEFAULT_FIX_TIP;
  }

  /**
   * Tách nội dung cờ "[Lỗi] a; [Cảnh báo] b" thành từng mục { severity, text, rule, tip }.
   * Câu không có tiền tố mức thì coi là Cảnh báo.
   */
  function parseFlag(value) {
    const text = String(value || '').trim();
    if (!text) return [];
    const parts = text.split(/;\s*(?=\[(?:Lỗi|Cảnh báo|Thông tin)\])/);
    return parts.map((part) => {
      const m = part.match(/^\[(Lỗi|Cảnh báo|Thông tin)\]\s*(.*)$/s);
      const body = (m ? m[2] : part).trim();
      const rule = ruleOfMessage(body);
      return { severity: m ? SEVERITIES[m[1]] : 'warning', text: body, rule, tip: fixTip(rule, body) };
    });
  }

  /** Mức nặng nhất trong các mục của một cờ. */
  function worstSeverity(items) {
    return items.reduce(
      (worst, it) => (SEVERITY_RANK[it.severity] < SEVERITY_RANK[worst] ? it.severity : worst),
      'info',
    );
  }

  /** labels (GET /api/labels) → Map(label_id → { name, specId }) cho các nhãn có thuộc tính cờ. */
  function flagSpecs(labels, attrName) {
    const name = attrName || FLAG_ATTR;
    const specs = new Map();
    for (const label of labels || []) {
      const attr = (label.attributes || []).find((a) => a.name === name);
      if (attr) specs.set(label.id, { name: label.name, specId: attr.id });
    }
    return specs;
  }

  function attrValue(attributes, specId) {
    const hit = (attributes || []).find((a) => a.spec_id === specId);
    return hit ? String(hit.value || '') : '';
  }

  /**
   * Mọi box đang mang cờ trong GET /api/jobs/<id>/annotations, sắp theo frame.
   * Track: lấy keyframe có cờ (thuộc tính mutable nằm ở từng keyframe); bỏ keyframe `outside`.
   */
  function collectFlags(annotations, specs) {
    const flags = [];
    const push = (frame, labelId, value, kind, objectId) => {
      const items = parseFlag(value);
      if (!items.length) return;
      flags.push({
        frame,
        label: specs.get(labelId).name,
        kind,
        objectId,
        value,
        items,
        severity: worstSeverity(items),
      });
    };
    for (const shape of (annotations && annotations.shapes) || []) {
      const spec = specs.get(shape.label_id);
      if (!spec || shape.type !== 'cuboid') continue;
      push(shape.frame, shape.label_id, attrValue(shape.attributes, spec.specId), 'shape', shape.id);
    }
    for (const track of (annotations && annotations.tracks) || []) {
      const spec = specs.get(track.label_id);
      if (!spec) continue;
      for (const shape of track.shapes || []) {
        if (shape.outside || shape.type !== 'cuboid') continue;
        push(shape.frame, track.label_id, attrValue(shape.attributes, spec.specId), 'track', track.id);
      }
    }
    return flags.sort((a, b) => a.frame - b.frame || SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity]);
  }

  /** Các frame có cờ, tăng dần, không trùng. */
  function flaggedFrames(flags) {
    return [...new Set(flags.map((f) => f.frame))].sort((a, b) => a - b);
  }

  /** Frame có cờ kế tiếp (dir = 1) hoặc trước đó (dir = -1) so với `current`; hết thì null. */
  function stepFrame(frames, current, dir) {
    if (dir > 0) return frames.find((f) => f > current) ?? null;
    for (let i = frames.length - 1; i >= 0; i -= 1) {
      if (frames[i] < current) return frames[i];
    }
    return null;
  }

  /** Tên nhãn trong bộ lọc của CVAT: dấu `.` được thay bằng `∙` (adjustName trong filters-modal). */
  function adjustName(name) {
    return String(name).replace(/\./g, '∙');
  }

  /**
   * JsonLogic của bộ lọc "pointsnap_error không rỗng" trên mọi nhãn có thuộc tính cờ.
   * Cùng dạng CVAT lưu trong lịch sử bộ lọc, để mục "Recently used" nạp lại được.
   */
  function filterLogic(labelNames, attrName) {
    const name = adjustName(attrName || FLAG_ATTR);
    const rules = [...new Set(labelNames)].map((label) => ({
      '!!': { var: `attr.${adjustName(label)}.${name}` },
    }));
    return { or: rules };
  }

  /**
   * Các mục của lần quét PointSnap ứng với một cờ trên CVAT: cùng frame, cùng nhãn,
   * và câu thông báo của mục nằm trong nội dung cờ. Trả về chỉ số trong `findings`.
   */
  function matchFindings(findings, flag) {
    const out = [];
    (findings || []).forEach((f, index) => {
      if (f.frame === flag.frame && f.label === flag.label && f.message && flag.value.includes(f.message)) {
        out.push(index);
      }
    });
    return out;
  }

  const api = {
    FLAG_ATTR,
    RULE_FIX_TIPS,
    parseJobUrl,
    normalizeBase,
    ruleOfMessage,
    fixTip,
    parseFlag,
    worstSeverity,
    flagSpecs,
    collectFlags,
    flaggedFrames,
    stepFrame,
    adjustName,
    filterLogic,
    matchFindings,
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.PointSnapCore = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
