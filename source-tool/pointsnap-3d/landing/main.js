// PointSnap 3D — tương tác của landing page (không phụ thuộc thư viện).
// Cảnh 3D (Three.js) nạp riêng trong scenes.js để trang vẫn chạy nếu CDN lỗi.

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;

// ---------- theme ----------
const root = document.documentElement;
const toggle = $('#themeToggle');
const syncToggle = () => toggle.setAttribute('aria-checked', String(root.dataset.theme === 'dark'));
syncToggle();
toggle.addEventListener('click', () => {
  root.dataset.theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
  // Dùng chung khóa với ứng dụng web (/app) để hai trang cùng sáng / tối.
  try { localStorage.setItem('pointsnap_theme', root.dataset.theme); localStorage.setItem('pointsnap-theme', root.dataset.theme); } catch (e) {}
  syncToggle();
});

// ---------- marquee ----------
// Nhóm luật đứt track (track.*) đang tắt theo quyết định của dự án nên không đưa vào đây.
const RULES = ['floating', 'size.class_range', 'size.in_track', 'heading.flip', 'heading.motion', 'heading.points', 'fit.outside', 'fit.empty', 'fit.overlap', 'lidar.missing', 'cam.missing', 'spec.inside', 'attr.missing', 'attr.rider_state', 'critic.box', 'cam.mismatch'];
const si = (d, c) => `<svg viewBox="0 0 24 24"><path fill="${c}" d="${d}"/></svg>`;
const LOGOS = [
  ['CVAT', `<svg viewBox="0 0 24 24" fill="none"><rect x="4" y="5" width="16" height="14" rx="1.5" stroke="#5B5BD6" stroke-width="2"/><rect x="2.5" y="3.5" width="3.5" height="3.5" rx=".8" fill="#5B5BD6"/><rect x="18" y="3.5" width="3.5" height="3.5" rx=".8" fill="#5B5BD6"/><rect x="2.5" y="17" width="3.5" height="3.5" rx=".8" fill="#5B5BD6"/><rect x="18" y="17" width="3.5" height="3.5" rx=".8" fill="#5B5BD6"/><path d="M9 14.5 L12 9 L15 14.5" stroke="#5B5BD6" stroke-width="1.8" stroke-linejoin="round"/></svg>`],
  ['nuScenes', `<svg viewBox="0 0 24 24" fill="none"><path d="M9.5 3 L4 21 M14.5 3 L20 21" stroke="#0E9F8E" stroke-width="2" stroke-linecap="round"/><path d="M12 4 V7 M12 10 V13.5 M12 17 V21" stroke="#0E9F8E" stroke-width="2" stroke-linecap="round"/></svg>`],
  ['LiDAR', `<svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="2.5" fill="#4C9AFF"/><path d="M7.5 7.5 A6.4 6.4 0 0 0 7.5 16.5 M16.5 7.5 A6.4 6.4 0 0 1 16.5 16.5" stroke="#4C9AFF" stroke-width="2" stroke-linecap="round"/><path d="M4.2 4.2 A11 11 0 0 0 4.2 19.8 M19.8 4.2 A11 11 0 0 1 19.8 19.8" stroke="#4C9AFF" stroke-width="2" stroke-linecap="round" opacity=".55"/></svg>`],
  ['Python 3.11', si('M14.25.18l.9.2.73.26.59.3.45.32.34.34.25.34.16.33.1.3.04.26.02.2-.01.13V8.5l-.05.63-.13.55-.21.46-.26.38-.3.31-.33.25-.35.19-.35.14-.33.1-.3.07-.26.04-.21.02H8.77l-.69.05-.59.14-.5.22-.41.27-.33.32-.27.35-.2.36-.15.37-.1.35-.07.32-.04.27-.02.21v3.06H3.17l-.21-.03-.28-.07-.32-.12-.35-.18-.36-.26-.36-.36-.35-.46-.32-.59-.28-.73-.21-.88-.14-1.05-.05-1.23.06-1.22.16-1.04.24-.87.32-.71.36-.57.4-.44.42-.33.42-.24.4-.16.36-.1.32-.05.24-.01h.16l.06.01h8.16v-.83H6.18l-.01-2.75-.02-.37.05-.34.11-.31.17-.28.25-.26.31-.23.38-.2.44-.18.51-.15.58-.12.64-.1.71-.06.77-.04.84-.02 1.27.05zm-6.3 1.98l-.23.33-.08.41.08.41.23.34.33.22.41.09.41-.09.33-.22.23-.34.08-.41-.08-.41-.23-.33-.33-.22-.41-.09-.41.09zm13.09 3.95l.28.06.32.12.35.18.36.27.36.35.35.47.32.59.28.73.21.88.14 1.04.05 1.23-.06 1.23-.16 1.04-.24.86-.32.71-.36.57-.4.45-.42.33-.42.24-.4.16-.36.09-.32.05-.24.02-.16-.01h-8.22v.82h5.84l.01 2.76.02.36-.05.34-.11.31-.17.29-.25.25-.31.24-.38.2-.44.17-.51.15-.58.13-.64.09-.71.07-.77.04-.84.01-1.27-.04-1.07-.14-.9-.2-.73-.25-.59-.3-.45-.33-.34-.34-.25-.34-.16-.33-.1-.3-.04-.25-.02-.2.01-.13v-5.34l.05-.64.13-.54.21-.46.26-.38.3-.32.33-.24.35-.2.35-.14.33-.1.3-.06.26-.04.21-.02.13-.01h5.84l.69-.05.59-.14.5-.21.41-.28.33-.32.27-.35.2-.36.15-.36.1-.35.07-.32.04-.28.02-.21V6.07h2.09l.14.01zm-6.47 14.25l-.23.33-.08.41.08.41.23.33.33.23.41.08.41-.08.33-.23.23-.33.08-.41-.08-.41-.23-.33-.33-.23-.41-.08-.41.08z', '#3776AB')],
  ['Chrome', si('M12 0C8.21 0 4.831 1.757 2.632 4.501l3.953 6.848A5.454 5.454 0 0 1 12 6.545h10.691A12 12 0 0 0 12 0zM1.931 5.47A11.943 11.943 0 0 0 0 12c0 6.012 4.42 10.991 10.189 11.864l3.953-6.847a5.45 5.45 0 0 1-6.865-2.29zm13.342 2.166a5.446 5.446 0 0 1 1.45 7.09l.002.001h-.002l-5.344 9.257c.206.01.413.016.621.016 6.627 0 12-5.373 12-12 0-1.54-.29-3.011-.818-4.364zM12 16.364a4.364 4.364 0 1 1 0-8.728 4.364 4.364 0 0 1 0 8.728Z', '#4285F4')],
  ['Edge', si('M21.86 17.86q.14 0 .25.12.1.13.1.25t-.11.33l-.32.46-.43.53-.44.5q-.21.25-.38.42l-.22.23q-.58.53-1.34 1.04-.76.51-1.6.91-.86.4-1.74.64t-1.67.24q-.9 0-1.69-.28-.8-.28-1.48-.78-.68-.5-1.22-1.17-.53-.66-.92-1.44-.38-.77-.58-1.6-.2-.83-.2-1.67 0-1 .32-1.96.33-.97.87-1.8.14.95.55 1.77.41.82 1.02 1.5.6.68 1.38 1.21.78.54 1.64.9.86.36 1.77.56.92.2 1.8.2 1.12 0 2.18-.24 1.06-.23 2.06-.72l.2-.1.2-.05zm-15.5-1.27q0 1.1.27 2.15.27 1.06.78 2.03.51.96 1.24 1.77.74.82 1.66 1.4-1.47-.2-2.8-.74-1.33-.55-2.48-1.37-1.15-.83-2.08-1.9-.92-1.07-1.58-2.33T.36 14.94Q0 13.54 0 12.06q0-.81.32-1.49.31-.68.83-1.23.53-.55 1.2-.96.66-.4 1.35-.66.74-.27 1.5-.39.78-.12 1.55-.12.7 0 1.42.1.72.12 1.4.35.68.23 1.32.57.63.35 1.16.83-.35 0-.7.07-.33.07-.65.23v-.02q-.63.28-1.2.74-.57.46-1.05 1.04-.48.58-.87 1.26-.38.67-.65 1.39-.27.71-.42 1.44-.15.72-.15 1.38zM11.96.06q1.7 0 3.33.39 1.63.38 3.07 1.15 1.43.77 2.62 1.93 1.18 1.16 1.98 2.7.49.94.76 1.96.28 1 .28 2.08 0 .89-.23 1.7-.24.8-.69 1.48-.45.68-1.1 1.22-.64.53-1.45.88-.54.24-1.11.36-.58.13-1.16.13-.42 0-.97-.03-.54-.03-1.1-.12-.55-.1-1.05-.28-.5-.19-.84-.5-.12-.09-.23-.24-.1-.16-.1-.33 0-.15.16-.35.16-.2.35-.5.2-.28.36-.68.16-.4.16-.95 0-1.06-.4-1.96-.4-.91-1.06-1.64-.66-.74-1.52-1.28-.86-.55-1.79-.89-.84-.3-1.72-.44-.87-.14-1.76-.14-1.55 0-3.06.45T.94 7.55q.71-1.74 1.81-3.13 1.1-1.38 2.52-2.35Q6.68 1.1 8.37.58q1.7-.52 3.58-.52Z', '#0078D7')],
  ['REST API', `<svg viewBox="0 0 24 24" fill="none"><path d="M8 3.5 C5.5 3.5 6 7 6 9 C6 10.5 4.5 12 3.5 12 C4.5 12 6 13.5 6 15 C6 17 5.5 20.5 8 20.5 M16 3.5 C18.5 3.5 18 7 18 9 C18 10.5 19.5 12 20.5 12 C19.5 12 18 13.5 18 15 C18 17 18.5 20.5 16 20.5" stroke="#0B63CE" stroke-width="2" stroke-linecap="round"/><circle cx="12" cy="12" r="1.6" fill="#0B63CE"/></svg>`],
  ['YAML guideline', si('m0 .97 4.111 6.453v4.09h2.638v-4.09L11.053.969H8.214L5.58 5.125 2.965.969Zm12.093.024-4.47 10.544h2.114l.97-2.345h4.775l.804 2.345h2.26L14.255.994Zm1.133 2.225 1.463 3.87h-3.096zm3.06 9.475v10.29H24v-2.199h-5.454v-8.091zm-12.175.002v10.335h2.217v-7.129l2.32 4.792h1.746l2.4-4.96v7.295h2.127V12.696h-2.904L9.44 17.37l-2.455-4.674Z', '#CB171E')],
  ['CI gate', `<svg viewBox="0 0 24 24" fill="none"><circle cx="5" cy="5" r="3.2" stroke="#2088FF" stroke-width="1.6"/><path d="M5 8.2 V16 a3 3 0 0 0 3 3 H9" stroke="#2088FF" stroke-width="1.6"/><circle cx="12" cy="19" r="3" stroke="#2088FF" stroke-width="1.6"/><circle cx="12" cy="12" r="3" stroke="#2088FF" stroke-width="1.6"/><circle cx="20" cy="12" r="3" stroke="#2088FF" stroke-width="1.6"/><path d="M5 12 H9 M15 12 H17" stroke="#2088FF" stroke-width="1.6"/><path d="M10.7 12.1 L11.6 13 L13.4 11.2" stroke="#2088FF" stroke-width="1.2" stroke-linecap="round"/></svg>`],
  ['Box Critic', `<svg viewBox="0 0 48 48" fill="none"><path d="M22 10 L34 17 L22 24 L10 17 Z M10 17 V31 L22 38 L34 31 V17 M22 24 V38" stroke="#0B63CE" stroke-width="3" stroke-linejoin="round"/><circle cx="22" cy="38" r="4" fill="#4C9AFF"/><path d="M40 4 L42 10 L48 12 L42 14 L40 20 L38 14 L32 12 L38 10 Z" fill="#F0A54A"/></svg>`],
];
const cube = '<svg width="16" height="16"><use href="#cube"/></svg>';
const ruleHtml = RULES.map(r => `<span class="rule-chip">${cube}${r}</span>`).join('');
const logoHtml = LOGOS.map(([n, s]) => `<span class="logo-chip">${s}${n}</span>`).join('');
$('#rulesTrack').innerHTML = ruleHtml + ruleHtml;   // nhân đôi để chạy vô tận
$('#logosTrack').innerHTML = logoHtml + logoHtml;
$$('#rulesTrack > :nth-child(n+17), #logosTrack > :nth-child(n+11)').forEach(el => el.setAttribute('aria-hidden', 'true'));

// ---------- features ----------
const ICON = {
  floating: '<path d="M6 50 H50" stroke="#A9B4C2" stroke-width="2" stroke-linecap="round"/><path d="M28 6 L42 14 L28 22 L14 14 Z M14 14 V30 L28 38 L42 30 V14 M28 22 V38" stroke="#F87171" stroke-width="2.5" stroke-linejoin="round"/><path d="M28 40 V49" stroke="#F87171" stroke-width="2" stroke-dasharray="2 3"/>',
  size: '<path d="M28 10 L42 18 L28 26 L14 18 Z M14 18 V34 L28 42 L42 34 V18 M28 26 V42" stroke="currentColor" stroke-width="2.5" stroke-linejoin="round"/><path d="M8 46 L22 54 M34 54 L48 46" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  track: '<path d="M6 18 L13 14 L20 18 L13 22 Z M6 18 V26 L13 30 L20 26 V18" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M20 30 L27 26 L34 30 L27 34 Z M20 30 V38 L27 42 L34 38 V30" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M36 12 L43 8 L50 12 L43 16 Z M36 12 V20 L43 24 L50 20 V12" stroke="#F87171" stroke-width="2.5" stroke-linejoin="round"/><path d="M34 32 L42 26" stroke="#F87171" stroke-width="1.5" stroke-dasharray="2 3"/>',
  heading: '<path d="M24 12 L38 20 L24 28 L10 20 Z M10 20 V36 L24 44 L38 36 V20 M24 28 V44" stroke="currentColor" stroke-width="2.5" stroke-linejoin="round"/><path d="M44 30 C 48 22 46 14 40 10 M40 10 L40 16 M40 10 L46 11" stroke="#F87171" stroke-width="2.5" stroke-linecap="round"/>',
  fit: '<path d="M22 12 L36 20 L22 28 L8 20 Z M8 20 V36 L22 44 L36 36 V20 M22 28 V44" stroke="currentColor" stroke-width="2.5" stroke-linejoin="round"/><circle cx="42" cy="30" r="2.2" fill="#F87171"/><circle cx="47" cy="36" r="2.2" fill="#F87171"/><circle cx="44" cy="42" r="2.2" fill="#F87171"/><circle cx="50" cy="28" r="2.2" fill="#F87171"/><circle cx="22" cy="34" r="2" fill="currentColor"/><circle cx="17" cy="30" r="2" fill="currentColor"/>',
  missing: '<path d="M28 8 L44 17 L28 26 L12 17 Z M12 17 V35 L28 44 L44 35 V17 M28 26 V44" stroke="#F87171" stroke-width="2" stroke-linejoin="round" stroke-dasharray="3 3"/><circle cx="22" cy="30" r="2.2" fill="currentColor"/><circle cx="28" cy="34" r="2.2" fill="currentColor"/><circle cx="34" cy="29" r="2.2" fill="currentColor"/><circle cx="26" cy="24" r="2.2" fill="currentColor"/><circle cx="32" cy="38" r="2.2" fill="currentColor"/><circle cx="20" cy="36" r="2.2" fill="currentColor"/>',
  spec: '<rect x="10" y="8" width="36" height="42" rx="6" stroke="currentColor" stroke-width="2.5"/><path d="M17 20 L20 23 L26 17 M17 32 L20 35 L26 29" stroke="#4CC38A" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M31 20 H39 M31 32 H39 M17 43 H39" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  repair: '<path d="M22 14 L36 22 L22 30 L8 22 Z M8 22 V38 L22 46 L36 38 V22 M22 30 V46" stroke="#4CC38A" stroke-width="2.5" stroke-linejoin="round"/><path d="M28 4 L42 12 L28 20 L14 12 Z" stroke="#F87171" stroke-width="2" stroke-linejoin="round" stroke-dasharray="3 3"/><path d="M46 14 V30 M41 25 L46 30 L51 25" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>',
  verifier: '<path d="M24 12 L38 20 L24 28 L10 20 Z M10 20 V36 L24 44 L38 36 V20 M24 28 V44" stroke="currentColor" stroke-width="2.5" stroke-linejoin="round"/><circle cx="24" cy="44" r="4" fill="#4C9AFF"/><path d="M44 6 L46 12 L52 14 L46 16 L44 22 L42 16 L36 14 L42 12 Z" fill="#F0A54A"/>',
};
const FEATS = [
  ['floating', 'Lơ lửng / lún', 'Đáy box so với mặt đất cục bộ quanh box và các frame khác của track.', 'floating', 'Đáy box cách mặt đất 26 cm', true],
  ['size', 'Sai kích thước', 'Ngoài khoảng của class, hoặc lệch trung vị kích thước của cả track.', 'size.class_range', 'Dài 7.80 m — lớn bất thường cho car'],
  ['repair', 'Sửa tay có thước trực tiếp', 'Chọn lỗi, kéo bằng CVAT và xem tọa độ, kích thước, góc thay đổi trên cả bốn góc nhìn.', 'manual', 'Kéo → kiểm lại → Save trong CVAT'],
  ['heading', 'Sai hướng', 'Lật hướng, ngược chiều chạy, lệch trục cụm điểm.', 'heading.flip', 'Ngược chiều 178°'],
  ['fit', 'Box lệch khỏi vật', 'Điểm của vật nằm ngoài box, box dư, box rỗng, vẽ trùng.', 'fit.outside', '40/60 điểm nằm ngoài box'],
  ['missing', 'Sót đối tượng', 'Cụm LiDAR cỡ xe / người di chuyển mà không có box; camera thấy vật mà không có box.', 'lidar.missing', 'Cụm cỡ xe đi 15.9 m không box'],
  ['spec', 'Spec gán nhãn VN', 'Thuộc tính bắt buộc, người trong xe, người lái gán hai lần — theo spec giao thông VN.', 'spec.inside', 'Pedestrian nằm trong Vehicle'],
  ['verifier', 'Box Verifier', 'Đối chiếu box với ảnh camera và Box Critic theo các luật bạn bật. Kiểm tra model trước khi quét.', 'critic.box', 'Gợi ý dời (+0.32, −0.05) m', true],
];
$('#bento').innerHTML = FEATS.map(([ic, t, d, rule, ex, big], i) => `
  <article class="card reveal${big ? ' card--big' : ''}" style="--d:${(i % 4) * 80}ms">
    <span class="card__icon" style="color:var(--primary)"><svg width="56" height="56" viewBox="0 0 56 56" fill="none">${ICON[ic]}</svg></span>
    <h3>${t}</h3><p>${d}</p>
    <div class="card__ex"><b>${rule}</b>${ex}</div>
  </article>`).join('');

// ---------- reveal + counters ----------
const countUp = (el) => {
  const to = +el.dataset.count, suffix = el.dataset.suffix || '', t0 = performance.now(), dur = 1200;
  const tick = (now) => { const p = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - p, 3);
    el.textContent = Math.round(to * e) + suffix; if (p < 1) requestAnimationFrame(tick); };
  reduceMotion ? (el.textContent = to + suffix) : requestAnimationFrame(tick);
};
const io = new IntersectionObserver((entries) => {
  for (const en of entries) if (en.isIntersecting) {
    en.target.classList.add('is-in');
    $$('[data-count]', en.target).forEach(countUp);
    if (en.target.matches('[data-count]')) countUp(en.target);
    io.unobserve(en.target);
  }
}, { threshold: .18, rootMargin: '0px 0px -40px 0px' });
$$('.reveal').forEach((el, i) => { if (!el.style.getPropertyValue('--d') && el.parentElement.children.length > 1) el.style.setProperty('--d', `${(i % 4) * 70}ms`); io.observe(el); });

// ---------- feature card 3D tilt + magnetic buttons + cursor glow ----------
if (!reduceMotion && matchMedia('(pointer: fine)').matches) {
  $$('.card').forEach(card => {
    card.addEventListener('pointermove', (e) => { const r = card.getBoundingClientRect(); const x = (e.clientX - r.left) / r.width - .5, y = (e.clientY - r.top) / r.height - .5;
      card.style.transform = `perspective(900px) rotateY(${x * 10}deg) rotateX(${-y * 10}deg) translateY(-6px)`; });
    card.addEventListener('pointerleave', () => { card.style.transform = ''; });
  });
  $$('.magnetic').forEach(b => {
    b.addEventListener('pointermove', (e) => { const r = b.getBoundingClientRect(); b.style.transform = `translate(${(e.clientX - r.left - r.width / 2) * .22}px, ${(e.clientY - r.top - r.height / 2) * .3}px)`; });
    b.addEventListener('pointerleave', () => { b.style.transform = ''; });
  });
  const glow = $('.cursor-glow');
  addEventListener('pointermove', (e) => { glow.style.setProperty('--mx', e.clientX + 'px'); glow.style.setProperty('--my', e.clientY + 'px'); }, { passive: true });
}

// ---------- nav active link + timeline beam ----------
const links = $$('.nav__links a');
const sections = links.map(a => $(a.getAttribute('href')));
const timeline = $('#timeline'), steps = $$('.step', timeline), beam = $('#beamFill');
const onScroll = () => {
  const y = scrollY + innerHeight * .35;
  let cur = -1; sections.forEach((s, i) => { if (s && s.offsetTop <= y) cur = i; });
  links.forEach((a, i) => a.classList.toggle('is-active', i === cur));
  const r = timeline.getBoundingClientRect();
  const p = Math.max(0, Math.min(1, (innerHeight * .75 - r.top) / (r.height + innerHeight * .2)));
  beam.style.setProperty('--p', (p * 100).toFixed(1) + '%');
  steps.forEach((s, i) => s.classList.toggle('is-on', p >= i / (steps.length - 1) - .02));
};
addEventListener('scroll', onScroll, { passive: true }); onScroll();

// ---------- usage tabs + terminal typing ----------
const showcase = $('.showcase');
const TERM = [
  ['<span class="p">$</span> ', 'pointsnap scan --job 12 --flag'],
  ['<span class="ok">', '✓ 214 box · 40 frame · 9.8 s', '</span>'],
  ['<span class="er">', '✗ 3 Lỗi  ⚠ 5 Cảnh báo · đã gắn cờ', '</span>'],
  ['<span class="p">$</span> ', 'pointsnap gate --job 12'],
  ['<span class="wa">', 'KHÔNG ĐẠT · exit 1', '</span>'],
];
const termEl = $('#termText'); let typing = 0;
const typeTerminal = async () => {
  const run = ++typing; let html = '';
  for (const [pre, text, post = ''] of TERM) {
    for (let i = 1; i <= text.length; i++) { if (run !== typing) return;
      termEl.innerHTML = html + pre + text.slice(0, i) + post + '<span class="caret"></span>';
      await new Promise(r => setTimeout(r, reduceMotion ? 0 : (pre.includes('$') ? 28 : 8))); }
    html += pre + text + post + '\n'; await new Promise(r => setTimeout(r, reduceMotion ? 0 : 260));
  }
  termEl.innerHTML = html + '<span class="p">$</span> <span class="caret"></span>';
};
const tabs = $$('.tabs [role="tab"]');
tabs.forEach(t => t.addEventListener('click', () => {
  tabs.forEach(x => x.setAttribute('aria-selected', String(x === t)));
  showcase.dataset.active = t.dataset.tab;
  if (t.dataset.tab === 'cli') typeTerminal();
}));
new IntersectionObserver((en, obs) => { if (en[0].isIntersecting) { typeTerminal(); obs.disconnect(); } }, { threshold: .3 }).observe(showcase);

// ---------- copy ----------
$$('.copy').forEach(b => b.addEventListener('click', async () => {
  try { await navigator.clipboard.writeText(b.dataset.copy); b.textContent = 'Đã chép ✓'; } catch (e) { b.textContent = 'Không chép được'; }
  setTimeout(() => (b.textContent = 'Sao chép'), 1600);
}));

// ---------- team ring (coverflow 3D) ----------
const TEAM = [
  { name: 'Khúc Việt Anh', tag: 'SẢN PHẨM', role: 'CVAT, adapter, web, extension, Box Verifier', skills: ['CVAT', 'Web', 'Extension', 'Box Verifier'], img: 'viet-anh.jpg' },
  { name: 'Nhữ Đình Chiến', tag: 'KIỂM THỬ', role: 'Test quy trình & video demo', skills: ['QA', 'Video demo'], img: 'chien.jpg' },
  { name: 'Nguyễn Văn Hân', tag: 'CHẤT LƯỢNG', role: 'Xem tay cảnh báo & bảng chỉ số', skills: ['Review', 'Chỉ số'], img: 'han.jpg' },
  { name: '??? ???', tag: '? ? ?', role: 'Vai trò: ??? · Nhiệm vụ: ???', skills: ['?', '???', '??'], img: 'bi-an.jpg', mystery: true },
  { name: 'Vũ Bảo Khánh', tag: 'BÁO CÁO', role: 'Báo cáo & slide', skills: ['Báo cáo dự án', 'Slide'], img: 'khanh.jpg' },
  { name: 'Đặng Văn Huy', tag: 'SẢN PHẨM', role: 'Mặt đất, bộ phát hiện, đánh giá', skills: ['Ground', 'Detector', 'Eval'], img: 'huy.jpg' },
];
const ring = $('#teamRing'), dotsEl = $('#ringDots');
const cards = TEAM.map((m, i) => {
  const el = document.createElement('article');
  el.className = 'member' + (m.mystery ? ' member--mystery' : '');
  el.innerHTML = `<div class="member__photo"><img src="assets/team/${m.img}" alt="${m.mystery ? 'Thành viên bí ẩn' : m.name}" loading="lazy" draggable="false"></div>
    <span class="member__tag">${m.tag}</span><h3>${m.name}</h3><p>${m.role}</p>
    <div class="member__skills">${m.skills.map(s => `<span>${s}</span>`).join('')}</div>`;
  el.addEventListener('click', () => { if (!dragMoved) goTo(i); });
  ring.appendChild(el);
  const d = document.createElement('button'); d.type = 'button'; d.setAttribute('aria-label', `Xem ${m.mystery ? 'thành viên bí ẩn' : m.name}`); d.addEventListener('click', () => goTo(i)); dotsEl.appendChild(d);
  return el;
});
const N = TEAM.length, STEP = 360 / N;
let angle = 0, target = 0, dragMoved = false;
const layoutRing = () => {
  const w = ring.clientWidth, compact = w < 760;
  const Rx = compact ? w * .3 : Math.min(345, w * .27), lift = compact ? 120 : 300;
  cards.forEach((el, i) => {
    let th = ((i * STEP - angle) % 360 + 540) % 360 - 180;          // -180..180, 0 = phía trước
    const r = th * Math.PI / 180, c = Math.cos(r), s = Math.sin(r), u = (1 - c) / 2;
    const x = Rx * s * (0.6 + 1.6 * u);
    const y = -(120 * u + lift * 15 * Math.max(0, u - .8) ** 2);
    const sc = .62 + .38 * (1 - u);
    el.style.transform = `translateX(${x.toFixed(1)}px) translateY(${(y * (compact ? .6 : 1)).toFixed(1)}px) scale(${sc.toFixed(3)})`;
    el.style.opacity = (.42 + .58 * (1 - u)).toFixed(3);
    el.style.zIndex = String(Math.round((1 - u) * 100));
    el.classList.toggle('is-front', Math.abs(th) < STEP / 2);
  });
  const front = ((Math.round(angle / STEP) % N) + N) % N;
  [...dotsEl.children].forEach((d, i) => d.setAttribute('aria-current', String(i === front)));
};
const goTo = (i) => { const cur = Math.round(target / STEP); const diff = ((i - cur) % N + N + N / 2) % N - N / 2; target = (cur + diff) * STEP; kick(); };
$('#ringPrev').addEventListener('click', () => { target = Math.round(target / STEP) * STEP - STEP; kick(); });
$('#ringNext').addEventListener('click', () => { target = Math.round(target / STEP) * STEP + STEP; kick(); });
let raf = 0, lastInteract = performance.now();
const kick = () => { lastInteract = performance.now(); if (!raf) raf = requestAnimationFrame(animate); };
const animate = () => { raf = 0; const d = target - angle; angle += d * (reduceMotion ? 1 : .12); layoutRing(); if (Math.abs(d) > .05) raf = requestAnimationFrame(animate); else { angle = target; layoutRing(); } };
// kéo để xoay
let dragX = null, dragStart = 0;
ring.addEventListener('pointerdown', (e) => { dragX = e.clientX; dragStart = target; dragMoved = false; ring.setPointerCapture(e.pointerId); });
ring.addEventListener('pointermove', (e) => { if (dragX === null) return; const dx = e.clientX - dragX; if (Math.abs(dx) > 4) dragMoved = true; target = dragStart - dx * .35; angle = target; layoutRing(); lastInteract = performance.now(); });
const endDrag = () => { if (dragX === null) return; dragX = null; target = Math.round(target / STEP) * STEP; kick(); };
ring.addEventListener('pointerup', endDrag); ring.addEventListener('pointercancel', endDrag);
ring.addEventListener('keydown', (e) => { if (e.key === 'ArrowLeft') $('#ringPrev').click(); if (e.key === 'ArrowRight') $('#ringNext').click(); });
// tự xoay khi không ai chạm, chỉ khi đang nhìn thấy
let ringVisible = false;
new IntersectionObserver((en) => { ringVisible = en[0].isIntersecting; }, { threshold: .3 }).observe(ring);
if (!reduceMotion) setInterval(() => { if (ringVisible && dragX === null && performance.now() - lastInteract > 4200) { target += STEP; kick(); lastInteract = performance.now() - 1200; } }, 500);
addEventListener('resize', layoutRing);
layoutRing();

// ---------- 3D ----------
import('./scenes.js').then(m => m.init()).catch(err => {
  console.warn('Không nạp được cảnh 3D:', err);
  $$('.scene, .vf8').forEach(el => el.classList.add('no-3d'));
});

// ---------- chạy local trong PointSnap hay trang tĩnh (Vercel) ----------
// Mở từ `pointsnap ui` (127.0.0.1:8765): nút chính vào thẳng ứng dụng ở /app, Enter cũng vào.
// Mở từ nơi không có máy chủ PointSnap: nút chính dẫn tới hướng dẫn cài.
const INSTALL_URL = 'https://github.com/AI20K-Build-Phase-Cohort-4A/P-029/blob/main/source-tool/pointsnap-3d/CAI-DAT.md';
const useStaticMode = () => {
  $$('[data-app-link]').forEach(a => {
    a.href = INSTALL_URL; a.target = '_blank'; a.rel = 'noopener';
    a.innerHTML = 'Hướng dẫn cài đặt <span aria-hidden="true">→</span>';
  });
  $('#startTitle').textContent = 'Cài trong 1 phút.';
  $('#startNote').textContent = 'Cài xong, chạy pointsnap ui rồi mở 127.0.0.1:8765 để vào ứng dụng.';
};
fetch('/api/projects', { headers: { Accept: 'application/json' } })
  .then(res => (res.ok && (res.headers.get('Content-Type') || '').includes('json') ? res.json() : Promise.reject(new Error('static'))))
  .then(projects => {
    const n = Array.isArray(projects) ? projects.length : 0;
    $('#serverPill span').textContent = n ? `PointSnap đang chạy trên máy bạn · ${n} dự án` : 'PointSnap đang chạy trên máy bạn · chưa có dự án';
    $('#enterHint').hidden = false;
    $('#startNote').textContent = n
      ? `Bạn đang có ${n} dự án. Mở ứng dụng để quét job và xem kết quả mới nhất.`
      : 'Lần đầu: tạo dự án (URL CVAT + token) → quét một job → mở job trên CVAT để sửa bằng extension.';
    addEventListener('keydown', (e) => {
      if (e.key !== 'Enter' || e.ctrlKey || e.metaKey || e.altKey || e.shiftKey) return;
      if (e.target.closest && e.target.closest('a, button, input, textarea, select, summary, [contenteditable="true"]')) return;
      location.href = '/app';
    });
  })
  .catch(useStaticMode);
