/*
 * Kiểu dáng bảng PointSnap trên trang CVAT. Nằm trong Shadow DOM nên không ảnh hưởng giao diện CVAT
 * và không bị CSS của CVAT ảnh hưởng. Cùng bộ màu xanh nước biển với giao diện web PointSnap.
 */
globalThis.PointSnapPanelCss = `
:host { all: initial; }
.ps {
  --bg: #FFFFFF; --soft: #F4F6F9; --border: #DDE2E8; --text: #161B22; --muted: #5B6573;
  --primary: #0B63CE; --on-primary: #FFFFFF; --primary-soft: #E8F1FC; --primary-text: #0A57B5;
  --error: #B42318; --error-soft: #FDEEEE; --warn: #A35200; --warn-soft: #FFF3E3;
  --info: #4A5563; --info-soft: #EEF1F5; --success: #157A4A; --success-soft: #EBF8F1;
  --head: #0F2A47; --dot: #4C9AFF;
  position: fixed; z-index: 2147483000; width: 340px; max-height: calc(100vh - 120px);
  display: flex; flex-direction: column;
  font: 13px/1.45 "Segoe UI", system-ui, -apple-system, sans-serif; color: var(--text);
  background: var(--bg); border: 1px solid var(--border); border-radius: 8px;
  box-shadow: 0 8px 24px rgba(15, 42, 71, .18); overflow: hidden;
}
@media (prefers-color-scheme: dark) {
  .ps {
    --bg: #151B23; --soft: #0D1117; --border: #2A333F; --text: #E6EAF0; --muted: #9AA5B4;
    --primary: #4C9AFF; --on-primary: #04162E; --primary-soft: #14284A; --primary-text: #7DB4FF;
    --error: #F38B85; --error-soft: #2E1718; --warn: #F0A54A; --warn-soft: #33260F;
    --info: #A9B4C2; --info-soft: #222A35; --success: #5FD39A; --success-soft: #12291D; --head: #0A0F15;
  }
}
.ps * { box-sizing: border-box; }
.ps button { font: inherit; cursor: pointer; }
.ps button:focus-visible { outline: 2px solid var(--primary); outline-offset: 1px; }

.head {
  display: flex; align-items: center; gap: 8px; padding: 8px 10px; background: var(--head); color: #fff;
  cursor: grab; user-select: none;
}
.head:active { cursor: grabbing; }
.brand { font-weight: 600; letter-spacing: .2px; }
.status { margin-left: auto; display: flex; align-items: center; gap: 6px; font-size: 11px; color: #B8C6D8; }
.status i { width: 7px; height: 7px; border-radius: 50%; background: #6B7785; display: inline-block; }
.status.on i { background: #3FCF8E; }
.icon-btn {
  border: 0; background: transparent; color: #fff; width: 26px; height: 26px; border-radius: 4px;
  display: grid; place-items: center; padding: 0;
}
.icon-btn:hover { background: rgba(255,255,255,.12); }

.body { overflow-y: auto; padding: 10px; display: flex; flex-direction: column; gap: 10px; }
.ps.collapsed { width: auto; }
.ps.collapsed .body { display: none; }

.nav { display: grid; grid-template-columns: auto 1fr auto; gap: 8px; align-items: center; }
.nav .where { text-align: center; }
.nav .where b { display: block; font-size: 15px; }
.nav .where span { color: var(--muted); font-size: 11px; }
.btn {
  height: 32px; padding: 0 12px; border-radius: 6px; border: 1px solid var(--border);
  background: var(--bg); color: var(--text); white-space: nowrap;
}
.btn:hover:not(:disabled) { border-color: var(--primary); color: var(--primary-text); }
.btn:disabled { opacity: .45; cursor: default; }
.btn.primary { background: var(--primary); border-color: var(--primary); color: var(--on-primary); }
.btn.primary:hover:not(:disabled) { color: var(--on-primary); filter: brightness(1.08); }
.btn.small { height: 26px; padding: 0 8px; font-size: 12px; }
.btn.on { background: var(--primary-soft); border-color: var(--primary); color: var(--primary-text); }
.kbd { font: 11px ui-monospace, Consolas, monospace; padding: 0 4px; border: 1px solid var(--border); border-radius: 3px; color: var(--muted); }

.row { display: flex; align-items: center; gap: 8px; }
.row .grow { flex: 1; min-width: 0; }
.muted { color: var(--muted); }
.small { font-size: 12px; }
.section-title {
  font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .5px; color: var(--muted);
  display: flex; align-items: center; gap: 6px;
}

.note {
  padding: 8px 10px; border-radius: 6px; background: var(--primary-soft); color: var(--text); font-size: 12px;
}
.note.warn { background: var(--warn-soft); }
.note.error { background: var(--error-soft); }
.note .actions { margin-top: 6px; display: flex; gap: 6px; flex-wrap: wrap; }

.card { border: 1px solid var(--border); border-radius: 6px; padding: 8px 10px; background: var(--bg); }
.card.active { border-color: var(--primary); box-shadow: 0 0 0 1px var(--primary) inset; }
.card .top { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.card .label { font-weight: 600; }
.msg { margin: 2px 0; }
.tip { margin-top: 4px; font-size: 12px; color: var(--muted); }
.tip b { color: var(--text); font-weight: 600; }
.card .actions { display: flex; gap: 6px; margin-top: 6px; flex-wrap: wrap; }

.sev { font-size: 11px; font-weight: 600; padding: 1px 6px; border-radius: 10px; white-space: nowrap; }
.sev.error { background: var(--error-soft); color: var(--error); }
.sev.warning { background: var(--warn-soft); color: var(--warn); }
.sev.info { background: var(--info-soft); color: var(--info); }

.chips { display: flex; gap: 4px; margin-left: auto; }
.chip {
  height: 22px; padding: 0 8px; border-radius: 11px; border: 1px solid var(--border); background: var(--bg);
  color: var(--muted); font-size: 11px;
}
.chip.on { background: var(--primary-soft); border-color: var(--primary); color: var(--primary-text); }

.list { display: flex; flex-direction: column; border: 1px solid var(--border); border-radius: 6px; max-height: 240px; overflow-y: auto; }
.item {
  display: grid; grid-template-columns: 38px 1fr auto; gap: 6px; align-items: center; text-align: left;
  padding: 6px 8px; border: 0; border-bottom: 1px solid var(--border); background: var(--bg); color: var(--text);
}
.item:last-child { border-bottom: 0; }
.item:hover { background: var(--soft); }
.item.current { background: var(--primary-soft); }
.item .f { font: 12px ui-monospace, Consolas, monospace; color: var(--muted); }
.item .t { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; }
.item .t b { font-weight: 600; }
.verdict { font-size: 11px; color: var(--muted); }
.verdict.ok { color: var(--success); }
.verdict.fp { color: var(--error); }

.foot { border-top: 1px solid var(--border); padding: 8px 10px; display: flex; flex-direction: column; gap: 6px; background: var(--soft); }
.foot .row { flex-wrap: wrap; }
.progress { height: 4px; border-radius: 2px; background: var(--border); overflow: hidden; }
.progress i { display: block; height: 100%; background: var(--primary); transition: width .3s; }
.empty { padding: 10px; text-align: center; color: var(--muted); font-size: 12px; }
`;
