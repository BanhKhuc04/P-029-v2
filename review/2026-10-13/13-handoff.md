# Bàn giao phần 13

- Nhánh `codex/review-13-missing-objects`, base `699433b`, code **`ae1d579`**; giữ ancestry 09–12. [Báo cáo](13-report.md).
- 9 nhóm sửa, **21 ca mới**; **792 Python + 37 Node PASS**, 3 live-CVAT SKIP, 0 FAIL/ERROR/XFAIL. Coverage missing 96,84%.
- Mini read-only: 20 deleted objects/10 scenes, 12 recovered (baseline cũng 12), 1 clean candidate mỗi split (chưa human verdict). Static/pretrained/GPU chưa nghiệm thu.
- Nhánh được push GitHub; SHA cuối xem HEAD remote. Không mở PR hoặc merge main.

## Chạy lại và phần tiếp theo

Dùng `.venv/Scripts/python.exe`, private `PYTHONPATH=out/review12-runtime;out/review11-runtime` (absolute), DLL handle như phần 12, `NUSCENES_ROOT=C:/Users/Han/Downloads/v1.0-mini`, `HF_HUB_OFFLINE=1`, `POINTSNAP_LIVE_CVAT=0`, OMP/MKL threads=1. Từ tool: `python out/review1314_gate.py 13` là launcher cục bộ của lượt kiểm; trên máy mới chạy `python -m pytest -q` với runtime đã cài. Từ extension: `node --test tests/*.test.js`.

Probe tracked: `review/2026-10-13/evidence/13/missing_probe.py --dataroot <mini> --out <fresh.json>`; optional `--baseline <missing.py snapshot>` để so hai phiên bản. Output/caches ở out ignored.

Phần 14 chọn `codex/review-14-integration`, nhận nhánh 13 bằng fast-forward. Cần kiểm missing coverage trên toàn frame range, no-ID findings, optional camera markers, learned severity không chứng nhận gate sai, config miền giá trị và UI request scope. Missing primary value giờ là displacement m; speed_m_s/duration_s nằm trong details, không dùng cache/model learning cũ như cùng một feature contract mà không kiểm lại.
