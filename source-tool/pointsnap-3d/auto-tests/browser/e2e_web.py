"""E2E trình duyệt cho landing + /app trên máy chủ demo. python e2e_web.py BASE"""
import json
import os
import sys
import urllib.request

from playwright.sync_api import sync_playwright

BASE = sys.argv[1]
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail and not cond else ""))


def api(method, path, body=None):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("POINTSNAP_CHROMIUM") or None)
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))

    # 1. Landing → ứng dụng
    pg.goto(BASE + "/")
    pg.wait_for_timeout(1200)
    cta = pg.locator(".hero [data-app-link]").first
    check("landing: CTA trỏ /app khi chạy local", cta.get_attribute("href") == "/app")
    check("landing: không còn nút tải về", pg.locator("text=Tải miễn phí").count() == 0 and pg.locator("#tai-ve").count() == 0)
    check("landing: pill trạng thái máy chủ", "đang chạy trên máy bạn" in pg.locator("#serverPill").inner_text())
    check("landing: cảnh 3D đã nạp (không no-3d)", pg.locator(".scene.no-3d").count() == 0)
    cta.click()
    pg.wait_for_url("**/app**")
    pg.wait_for_selector("#system-continue:not([disabled])")
    check("mở app: kiểm tra môi trường trước phiên cũ",pg.locator("#tab-system").is_visible())
    pg.locator("#system-continue").click()
    pg.wait_for_selector("#findings-table-body tr")
    check("landing → /app bằng nút Mở PointSnap", "/app" in pg.url)
    pg.goto(BASE + "/")
    pg.wait_for_timeout(800)
    pg.keyboard.press("Enter")
    pg.wait_for_url("**/app**", timeout=5000)
    if pg.locator("#tab-system").is_visible(): pg.locator("#system-continue:not([disabled])").click()
    check("landing: phím Enter vào ứng dụng", "/app" in pg.url)

    # 2. Kết quả: phím tắt, lọc, kết luận
    pg.wait_for_selector("#findings-table-body tr.selected")
    check("kết quả: track.* bị lọc", pg.locator("#findings-table-body", has_text="track cũ").count() == 0)
    c0 = pg.locator("#quick-nav-counter").inner_text()
    pg.keyboard.press("j")
    pg.wait_for_timeout(300)
    check("kết quả: J chuyển mục", pg.locator("#quick-nav-counter").inner_text() != c0, pg.locator("#quick-nav-counter").inner_text())
    pg.keyboard.press("k")
    pg.wait_for_timeout(300)
    pg.keyboard.press("1")
    pg.wait_for_timeout(800)
    check("kết quả: phím 1 ghi Đúng là lỗi", pg.locator("#findings-table-body .review-mark.ok").count() >= 1)
    pg.click("#sev-tab-error")
    pg.wait_for_timeout(200)
    sevs = pg.locator("#findings-table-body .pill-badge").all_inner_texts()
    check("kết quả: lọc mức Lỗi", sevs and all(s in ("Lỗi", "ĐÃ GHI CVAT") for s in sevs), str(sevs))
    pg.click("#sev-tab-all")
    pg.keyboard.press("/")
    check("kết quả: phím / vào ô tìm", pg.evaluate("document.activeElement.id") == "filter-search-box")
    pg.keyboard.type("lơ lửng")
    pg.wait_for_timeout(300)
    check("kết quả: tìm kiếm lọc bảng", pg.locator("#findings-table-body tr").count() == 1)
    pg.fill("#filter-search-box", "")
    pg.locator("#findings-table-body").click(position={"x": 5, "y": 5})
    pg.keyboard.press("?")
    check("trợ giúp: phím ? mở bảng phím tắt", pg.locator("#modal-help.open").count() == 1)
    pg.keyboard.press("Escape")
    check("trợ giúp: Esc đóng", pg.locator("#modal-help.open").count() == 0)

    # v2: guidance is read-only, old write controls and APIs are retired.
    pg.locator('#findings-table-body tr', has_text='Box lơ lửng so với mặt đất').click()
    check('sửa tay: không còn nút áp dụng/hoàn tác tự động', pg.locator('#btn-open-apply-repair, #btn-rollback-repair').count() == 0)
    run_id = api('GET', '/api/projects/demo/scans')[0]['run_id']
    guide = api('GET', f'/api/projects/demo/scans/{run_id}/findings/0/guide')
    check('hướng dẫn: hợp đồng GuideContext v1', guide.get('schema_version') == 1)
    check('hướng dẫn: đúng frame và ID', guide['identity']['frame'] == 18 and guide['identity']['server_id'] == 12)
    import urllib.error
    try:
        api('POST', '/api/jobs/2/tracks/12/apply-repair', {'frame': 18, 'repair': {}})
        check('API tự sửa đã ngừng', False)
    except urllib.error.HTTPError as exc:
        check('API tự sửa đã ngừng', exc.code == 410)

    # 5. Guideline
    pg.goto(BASE + "/app#guideline")
    if pg.locator("#tab-system").is_visible(): pg.locator("#system-continue:not([disabled])").click()
    pg.wait_for_selector("#rule-fit-loose")
    pg.wait_for_timeout(800)
    check("guideline: nút Lưu tắt khi chưa đổi", pg.locator("#btn-save-guideline").is_disabled())
    before = pg.locator("#rules-enabled-count").inner_text()
    pg.click("#rule-fit-loose")
    check("guideline: bật luật → dirty + Lưu bật", pg.locator("#btn-save-guideline").is_enabled()
          and "chưa lưu" in pg.locator("#guideline-dirty-note").inner_text())
    check("guideline: bộ đếm luật cập nhật", pg.locator("#rules-enabled-count").inner_text() != before)
    pg.fill("#rules-search", "camera")
    pg.wait_for_timeout(200)
    visible = pg.locator(".rule-row:visible").count()
    check("guideline: tìm luật", 0 < visible < 8, str(visible))
    pg.fill("#rules-search", "")
    pg.fill("#new-size-class-name", "van")
    pg.press("#new-size-class-name", "Enter")
    check("guideline: thêm class ngay trong bảng", pg.locator("#size-classes-table-body td.cls-name", has_text="van").count() == 1)
    row = pg.locator("#size-classes-table-body tr", has_text="van")
    row.locator(".size-input[data-dim='length'][data-i='0']").fill("9")
    pg.click("#btn-save-guideline")
    pg.wait_for_timeout(500)
    check("guideline: chặn min > max", any("min lớn hơn max" in t for t in pg.locator(".toast").all_inner_texts()))
    row.locator(".size-input[data-dim='length'][data-i='0']").fill("3.5")
    pg.click("#btn-save-guideline")
    pg.wait_for_timeout(1200)
    check("guideline: lưu thành công", pg.locator("#btn-save-guideline").is_disabled())
    cfg = api("GET", "/api/projects/demo/guideline")["config"]
    check("guideline: lưu đúng lên máy chủ", cfg["rules"]["fit_loose"] is True and cfg["size"]["manual_ranges"]["van"]["length"][0] == 3.5)
    check("guideline: luật track vẫn tắt", not any(v for k, v in cfg["rules"].items() if k.startswith("track_")))
    pg.click("#rule-fit-loose")
    pg.click("#btn-save-guideline")
    pg.wait_for_timeout(800)
    pg.click("#btn-mode-yaml")
    check("guideline: chuyển YAML", pg.locator("#guideline-yaml-view").is_visible() and "fit_loose" in pg.locator("#guideline-yaml-textarea").input_value())
    pg.click("#btn-mode-form")

    # 6. Quét job: tóm tắt guideline
    pg.goto(BASE + "/app#scan")
    if pg.locator("#tab-system").is_visible(): pg.locator("#system-continue:not([disabled])").click()
    pg.wait_for_timeout(1500)
    check("quét: hiện số luật đang bật", "luật đang bật" in pg.locator("#scan-guideline-summary").inner_text())
    check("quét: báo lý do không tải được task", any("Token" in t or "token" in t for t in pg.locator(".toast").all_inner_texts()))

    # 7. Màn hẹp: không tràn ngang
    for w in (390, 768, 1024):
        pg.set_viewport_size({"width": w, "height": 860})
        for tab in ("results", "guideline", "scan", "connection", "history"):
            pg.goto(f"{BASE}/app#{tab}")
            if pg.locator("#tab-system").is_visible(): pg.locator("#system-continue:not([disabled])").click()
            pg.wait_for_timeout(500)
            over = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            check(f"responsive {w}px {tab}: không tràn ngang", over <= 1, f"tràn {over}px")
    pg.set_viewport_size({"width": 390, "height": 860})
    pg.goto(BASE + "/")
    pg.wait_for_timeout(800)
    over = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    check("responsive 390px landing: không tràn ngang", over <= 1, f"tràn {over}px")

    check("không có lỗi JavaScript trên trang", not errors, "; ".join(errors))
    b.close()

failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)}/{len(results)} PASS")
sys.exit(1 if failed else 0)
