"""Chạy E2E trình duyệt: landing + web /app và extension thật trong Chromium, trên dữ liệu demo.

    pip install playwright pillow && python -m playwright install chromium
    python auto-tests/browser/run_browser_e2e.py [--out out/browser-e2e] [--only web|extension]

Dùng cổng 8765 (PointSnap demo) và 8080 (CVAT giả) — đúng địa chỉ mặc định của extension, nên tắt `pointsnap ui`
và CVAT thật trước khi chạy. Dữ liệu demo nằm trong thư mục tạm, không đụng ~/.pointsnap hay CVAT thật.
Biến POINTSNAP_CHROMIUM chọn file chạy Chromium khác bản Playwright tải về.
Extension cần Chromium hỗ trợ `--headless=new`.
"""
from __future__ import annotations

import argparse
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent


def port_free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def wait_http(url: str, seconds: float = 30) -> bool:
    end = time.time() + seconds
    while time.time() < end:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            time.sleep(0.3)
    return False


def start(args: list[str], log: Path) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, *args], stdout=log.open("w"), stderr=subprocess.STDOUT)


def run_suite(name: str, args: list[str], home: Path, out: Path, with_cvat: bool) -> int:
    for port in (8765, 8080) if with_cvat else (8765,):
        if not port_free(port):
            print(f"Cổng {port} đang bận — tắt pointsnap ui / CVAT thật rồi chạy lại.", file=sys.stderr)
            return 2
    procs = [start([str(HERE / "demo_server.py"), str(home), "8765"], out / f"{name}-demo.log")]
    if with_cvat:
        procs.append(start([str(HERE / "fake_cvat.py")], out / f"{name}-cvat.log"))
    try:
        if not wait_http("http://127.0.0.1:8765/api/projects") or (with_cvat and not wait_http("http://localhost:8080/tasks/2/jobs/2")):
            print(f"Không khởi động được máy chủ demo; xem log trong {out}", file=sys.stderr)
            return 2
        print(f"\n=== {name} ===", flush=True)
        return subprocess.call([sys.executable, *args])
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", default="out/browser-e2e", help="thư mục log và ảnh chụp")
    parser.add_argument("--only", choices=["web", "extension"], help="chỉ chạy một bộ")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    codes = {}
    for name in ("web", "extension"):
        if args.only and args.only != name:
            continue
        home = Path(tempfile.mkdtemp(prefix=f"pointsnap-e2e-{name}-"))
        try:
            if name == "web":
                codes[name] = run_suite(name, [str(HERE / "e2e_web.py"), "http://127.0.0.1:8765"], home, out, False)
            else:
                codes[name] = run_suite(name, [str(HERE / "e2e_extension.py"), str(out)], home, out, True)
        finally:
            shutil.rmtree(home, ignore_errors=True)
    print("\n" + " · ".join(f"{k}: {'PASS' if v == 0 else 'FAIL'}" for k, v in codes.items()))
    return 0 if codes and all(v == 0 for v in codes.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
