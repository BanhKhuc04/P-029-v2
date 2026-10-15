"""CVAT giả tối thiểu cho E2E extension (localhost:8080): trang job có các phần tử extension đọc + API nhãn / annotations."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>CVAT job 2</title>
<style>body{margin:0;font:14px system-ui;background:#1e1e1e;color:#ddd}.bar{padding:8px;background:#333}
.canvas{height:640px;background:#000}.cvat-objects-sidebar{position:fixed;right:0;top:40px;width:260px;bottom:0;background:#2a2a2a}</style>
</head><body>
<div class="bar"><span class="cvat-player-frame-selector"><input value="18"></span>
<span class="cvat-player-slider"><span role="slider" aria-valuenow="18"></span></span>
<button class="cvat-annotation-header-filters-button">Filters</button></div>
<div class="canvas" id="cvat-canvas3d-wrapper"></div>
<div class="cvat-objects-sidebar"></div>
<script>
// Gõ số frame + Enter: đổi thanh trượt như CVAT thật.
const input = document.querySelector('.cvat-player-frame-selector input');
const slider = document.querySelector('[role=slider]');
input.addEventListener('keydown', (e) => { if (e.key === 'Enter') slider.setAttribute('aria-valuenow', input.value); });
input.addEventListener('change', () => slider.setAttribute('aria-valuenow', input.value));
</script></body></html>"""

LABELS = {"results": [{"id": 1, "name": "car", "attributes": [{"id": 11, "name": "pointsnap_error", "input_type": "text"}]},
                      {"id": 2, "name": "truck", "attributes": [{"id": 12, "name": "pointsnap_error", "input_type": "text"}]}],
          "next": None}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, kind):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path.startswith("/api/labels"):
            return self.send(200, json.dumps(LABELS), "application/json")
        if path == "/api/jobs/2/annotations":
            return self.send(200, json.dumps({"version": 1, "tags": [], "shapes": [], "tracks": []}), "application/json")
        if path == "/api/jobs/2":
            return self.send(200, json.dumps({"id": 2, "task_id": 2}), "application/json")
        if path.startswith("/tasks/"):
            return self.send(200, PAGE, "text/html; charset=utf-8")
        return self.send(404, "{}", "application/json")


ThreadingHTTPServer(("127.0.0.1", 8080), H).serve_forever()
