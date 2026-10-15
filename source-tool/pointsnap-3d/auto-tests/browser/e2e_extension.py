"""E2E extension thật trong Chromium: popup, Tùy chọn, bảng trong CVAT giả, đồng bộ 2 chiều với web demo.

Cần demo_server.py ở 127.0.0.1:8765 và fake_cvat.py ở localhost:8080 (địa chỉ mặc định của extension).
python e2e_extension.py OUT_DIR
"""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import urllib.request

from playwright.sync_api import sync_playwright

EXT = str(Path(__file__).resolve().parents[2] / "extension")
SP = sys.argv[1] if len(sys.argv) > 1 else "."
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail and not cond else ""))


def api(method, path, body=None):
    req = urllib.request.Request("http://127.0.0.1:8765" + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


profile = tempfile.mkdtemp()
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(profile, executable_path=os.environ.get("POINTSNAP_CHROMIUM") or None, headless=False, viewport={"width": 1400, "height": 860},
                                               args=["--headless=new", f"--disable-extensions-except={EXT}", f"--load-extension={EXT}"])
    errors = []
    sw = ctx.service_workers[0] if ctx.service_workers else ctx.wait_for_event("serviceworker", timeout=15000)
    ext_id = sw.url.split("/")[2]
    check("extension: service worker chạy", bool(ext_id))

    pop = ctx.new_page()
    pop.on("pageerror", lambda e: errors.append("popup: " + str(e)))
    pop.goto(f"chrome-extension://{ext_id}/popup.html")
    pop.wait_for_function("document.getElementById('server').classList.contains('ok') || document.getElementById('server').classList.contains('err')", timeout=10000)
    check("popup: thấy PointSnap đang chạy", "đang chạy" in pop.locator("#server-text").inner_text(), pop.locator("#server-text").inner_text())
    pop.set_viewport_size({"width": 340, "height": 420})
    pop.screenshot(path=f"{SP}/ext-popup.png")
    pop.close()

    opt = ctx.new_page()
    opt.on("pageerror", lambda e: errors.append("options: " + str(e)))
    opt.goto(f"chrome-extension://{ext_id}/options.html")
    opt.wait_for_function("document.getElementById('conn').classList.contains('ok') || document.getElementById('conn').classList.contains('err')", timeout=10000)
    check("tùy chọn: tự kiểm tra kết nối", "đang chạy" in opt.locator("#conn-text").inner_text(), opt.locator("#conn-text").inner_text())
    check("tùy chọn: nạp giá trị đã lưu", opt.locator("#pointsnap-url").input_value() == "http://127.0.0.1:8765")
    opt.screenshot(path=f"{SP}/ext-options.png", full_page=True)
    opt.close()

    # Web PointSnap và trang job CVAT giả
    web = ctx.new_page()
    web.on("pageerror", lambda e: errors.append("web: " + str(e)))
    web.goto("http://127.0.0.1:8765/app#results")
    web.wait_for_selector("#findings-table-body tr.selected")

    cv = ctx.new_page()
    cv.on("pageerror", lambda e: errors.append("cvat: " + str(e)))
    cv.goto("http://localhost:8080/tasks/2/jobs/2")
    cv.wait_for_selector("#pointsnap-cvat-panel", state="attached", timeout=15000)
    panel = cv.locator("#pointsnap-cvat-panel")
    cv.wait_for_function("""() => { const r = document.querySelector('#pointsnap-cvat-panel').shadowRoot;
        return r && r.querySelector('.card-title'); }""", timeout=20000)
    check("bảng CVAT: hiện thẻ lỗi frame 18", "Lơ lửng" in panel.locator(".card-title").inner_text(), panel.locator(".card-title").inner_text())
    check("bảng CVAT: chấm PointSnap đang chạy", panel.locator(".dot.on").count() == 1)
    check("bảng CVAT: có nút mở web", panel.locator("[data-action=open-web]").count() == 1)

    web.wait_for_function("document.getElementById('ext-status-text').textContent.includes('đang mở job')", timeout=10000)
    check("web: nhận ra extension đang mở job", True)

    # Extension áp dụng sửa → web cập nhật không F5
    cv.wait_for_function("""() => document.querySelector('#pointsnap-cvat-panel').shadowRoot.querySelector('[data-action=repair-apply-start]')""", timeout=15000)
    cv.screenshot(path=f"{SP}/ext-panel.png", clip={"x": 40, "y": 80, "width": 380, "height": 720})
    panel.locator("[data-action=repair-apply-start]").click()
    panel.locator("[data-action=repair-apply-confirm]").click()
    cv.wait_for_function("""() => document.querySelector('#pointsnap-cvat-panel').shadowRoot.querySelector('[data-action=repair-rollback]')""", timeout=10000)
    check("bảng CVAT: áp dụng sửa đã xác nhận", "ĐÃ GHI" in panel.locator(".repair-success-box").inner_text())
    web.wait_for_function("document.getElementById('detail-sev-badge').textContent === 'ĐÃ GHI CVAT'", timeout=10000)
    check("đồng bộ extension → web không F5", True)
    check("web: có nút Hoàn tác cho sửa từ extension", web.locator("#btn-rollback-repair").is_visible())

    # Web hoàn tác → extension cập nhật
    web.click("#btn-rollback-repair")
    cv.wait_for_function("""() => !document.querySelector('#pointsnap-cvat-panel').shadowRoot.querySelector('[data-action=repair-rollback]')""", timeout=10000)
    check("đồng bộ web → extension: hoàn tác hiện ngay trong CVAT", True)

    # Web áp dụng → extension hiện đã ghi
    web.wait_for_selector("#btn-open-apply-repair:not([disabled])", timeout=10000)
    web.wait_for_timeout(700)
    web.click("#btn-open-apply-repair")
    web.click("#btn-modal-repair-confirm")
    cv.wait_for_function("""() => document.querySelector('#pointsnap-cvat-panel').shadowRoot.querySelector('[data-action=repair-rollback]')""", timeout=10000)
    check("đồng bộ web → extension: sửa từ web hiện ngay trong CVAT", True)
    notice = panel.locator(".note").all_inner_texts()
    check("bảng CVAT: nhắc tải lại để thấy box mới", any("Tải lại" in n or "tải lại" in n for n in notice), str(notice))

    # Kết luận xem tay hai chiều
    panel.locator("[data-action=review-fp]").click()
    web.wait_for_function("document.querySelectorAll('#findings-table-body .review-mark.fp').length >= 1", timeout=10000)
    check("đồng bộ kết luận extension → web", True)

    # Web chọn mục khác → CVAT chuyển frame
    web.locator("#findings-table-body tr", has_text="Hướng box lệch 178°").click()
    cv.wait_for_function("document.querySelector('[role=slider]').getAttribute('aria-valuenow') === '23'", timeout=10000)
    check("web chọn mục → CVAT tự chuyển frame 23", True)

    check("không có lỗi JavaScript", not errors, "; ".join(errors))
    ctx.close()
shutil.rmtree(profile, ignore_errors=True)
failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)}/{len(results)} PASS")
sys.exit(1 if failed else 0)
