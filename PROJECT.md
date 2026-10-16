# Project: PointSnap 3D — Manual Repair v2

Current implementation: detector/model findings remain enabled; geometry repair is exclusively manual in CVAT.
Extension 0.2.0 reads live cuboids/cameras and overlays measurements on all four views. PointSnap geometry-writing
APIs return HTTP 410; no snapping, quick leveling or automatic apply remains in the extension.
See [v2 usage and contracts](source-tool/pointsnap-3d/docs/manual-repair.md).

The sections below record the **historical v1** architecture and milestones, not the active v2 repair workflow.

## Architecture
The PointSnap 3D platform is an annotation QA, assisted repair, and bidirectional synchronization system for autonomous vehicle LiDAR 3D bounding boxes.
- **Backend / Core Engine (`pointsnap.core`)**: Python library providing 3D cuboid models, geometry calculations, point cloud slicing, ground estimation, rule scanners (floating, heading, fit, size), and synthetic error injection. Track discontinuity rules (`track.*`) are disabled across config, scanner, and coordinators.
- **Assisted 3D Box Repair Engine (`pointsnap.core.repair`)**: Closed-form mathematical delta engine computing proposed adjustments ($\Delta z$, $\Delta \text{yaw}$, $\Delta \text{dims}$) to resolve scanner findings and ensure re-scan passes quality gates.
- **Real-Time Bidirectional Synchronization Layer (`pointsnap.web`, `pointsnap.adapters.cvat.writer`, `extension/`)**:
  - Live link syncing findings, reviews, and repair history between CVAT Chrome Extension and Web UI.
  - OCC ETag SHA-256 conflict protection rejecting stale updates with HTTP 409 Conflict.
  - Offline CVAT detection returning HTTP 503 and locking apply buttons (`applicable: false`, `disabled: true`).
  - Zero-F5 bidirectional event propagation via `history_rev` and `reviews_rev` polling/signals.
- **Ghost Target & Telemetry HUD Engine (`extension/src/ghost-engine.js`, `cvat-3d-hook.js`, `telemetry-hud.js`)**: Real-time 60 FPS live HUD, magnet snapping (8 cm / 4°), quick leveling hotkey (L / Shift+S), and green target lock (≤ 2 cm / 2°).
- **Web UI & REST API (`pointsnap.web`)**: FastAPI backend serving interactive 3-view orthogonal LiDAR canvas (`drawPreview`) with proposed repair bounding box overlay and 1-Click Apply / Rollback actions.
- **Visual Analytics & Reporting Engine (`tools/generate_analytics_report.py`)**: Automated Python measurement script generating 3+ publication-ready PNG charts and embedding them into a comprehensive Markdown analytics report.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | F1: Track Discontinuity Config Switch Off | Set default `track_jump: false`, `track_split_id: false`, `track_long_interpolation: false`, `track_reuse_id: false`, `track_occluded_long: false`, `track_id_swap: false`, `track_static_shift: false` in `config.yaml` and `RulesConfig` | M1 | ORIGINAL_REQUEST 2026-10-15T05:04:04Z §R1 |
| 2 | F2: Scanner Track Bypass & 0 Findings | Add guard in `check_track`, `scan_cuboids`, `is_rule_enabled`, and `scan_coverage_gaps` ensuring 0 track findings on any scan | M1 | ORIGINAL_REQUEST 2026-10-15T05:04:04Z §R1 |
| 3 | F3: 3D Geometric Rules Integrity | Preserve 100% functionality and precision for `floating`, `fit.*`, `heading.*`, `size.*` rules with 0 regression | M1 | ORIGINAL_REQUEST 2026-10-15T05:04:04Z §R1 |
| 4 | F4: Bidirectional Findings & Repair Sync | Real-time findings synchronization, ghost target guides & preview matching across Extension and Web UI | M2 | ORIGINAL_REQUEST 2026-10-15T05:04:04Z §R2 |
| 5 | F5: Zero-F5 Extension ⟷ Web Live Updates | Expose `history_rev` in `/api/extension/status` and handle in Web UI `pollCvatLink` so repair apply/rollback updates instantly in Web UI | M2 | ORIGINAL_REQUEST 2026-10-15T05:04:04Z §R2 |
| 6 | F6: OCC ETag 409 Conflict Protection | Enforce SHA-256 ETag pre-check rejecting stale writes with HTTP 409 Conflict across Extension and Web UI | M2 | ORIGINAL_REQUEST 2026-10-15T05:04:04Z §R2 |
| 7 | F7: CVAT Offline 503 Protection | Return HTTP 503 with exact Vietnamese message and lock apply buttons (`applicable: false`, `disabled: true`) when CVAT offline | M2 | ORIGINAL_REQUEST 2026-10-15T05:04:04Z §R2 |
| 8 | F8: Analytics PNG 1 - Error Distribution | Python script generating `error_distribution.png` showing error counts by rule category with 0 track findings | M3 | ORIGINAL_REQUEST 2026-10-15T05:04:04Z §R4 |
| 9 | F9: Analytics PNG 2 - Residual Distribution | Python script generating `residuals_distribution.png` boxplot and histogram for $\Delta z$ and $\Delta \text{yaw}$ with tolerance lines | M3 | ORIGINAL_REQUEST 2026-10-15T05:04:04Z §R4 |
| 10 | F10: Analytics PNG 3 - Performance Metrics | Python script generating `performance_metrics.png` for API latency and scan HUD 60 FPS frame time | M3 | ORIGINAL_REQUEST 2026-10-15T05:04:04Z §R4 |
| 11 | F11: Visual Analytics Markdown Report | Produce comprehensive Markdown report (`ANALYTICS_REPORT.md`) embedding all 3 PNGs with metrics and verification data | M3 | ORIGINAL_REQUEST 2026-10-15T05:04:04Z §R4 |
| 12 | F12: Full Python Pytest Suite Regression Pass | 100% of runnable tests in `tests/`, `e2e_tests/`, and `auto-tests/` pass with 0 failures | M4 | ORIGINAL_REQUEST 2026-10-15T05:04:04Z §R3 |
| 13 | F13: Full Extension JS Test Suite Pass | 100% of tests in `extension/tests/*.test.js` pass with 0 failures | M4 | ORIGINAL_REQUEST 2026-10-15T05:04:04Z §R3 |
| 14 | F14: REST API Endpoints Verification | Verify all 35 REST API endpoints in backend with healthy status codes and expected contracts | M4 | ORIGINAL_REQUEST 2026-10-15T05:04:04Z §R3 |
| 15 | F15: nuScenes Mini Evaluation & Precision Acceptance | Execute `check_quality.py` and `manual_precision.py` on 5 held-out scenes confirming 0 track findings and human precision $\ge 70\%$ | M4 | ORIGINAL_REQUEST 2026-10-15T05:04:04Z §R3 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | M1: Disable All Track Discontinuity Rules | Features F1, F2, F3: Config switch off, scanner bypass, 0 track findings, preserve 3D geometry rules | none | PLANNED |
| 2 | M2: Real-Time Bidirectional Synchronization | Features F4, F5, F6, F7: Zero-F5 live sync, OCC 409 Conflict, CVAT offline 503 | M1 | PLANNED |
| 3 | M3: Visual Analytics Report & Artifacts | Features F8, F9, F10, F11: Python report script, 3 publication-ready PNGs, Markdown report | M1, M2 | PLANNED |
| 4 | M4: Full E2E Audit, Regression & nuScenes Precision | Features F12, F13, F14, F15: 100% pytest pass, 100% extension test pass, 35 endpoints check, nuScenes precision | M1, M2, M3 | PLANNED |

## Interface Contracts

### 1. Track Rule Disabling Contract
- In `pointsnap/config.yaml`:
  `track_jump: false`, `track_split_id: false`, `track_long_interpolation: false`, `track_reuse_id: false`, `track_occluded_long: false`, `track_id_swap: false`, `track_static_shift: false`, `track.long_interpolation.enabled: false`.
- In `pointsnap/core/config.py`:
  `RulesConfig` default fields for all track discontinuity rules must default to `False`.
- In `pointsnap/core/scanner.py`:
  `check_track` immediately returns `[]` if no track rule is enabled in `config.rules`.
  `scan_cuboids` does not invoke `check_track` when all track rules are `False`.
  `scan_coverage_gaps` skips pose gap checks when all pose rules are disabled.

### 2. Bidirectional Sync & Status Contract
- `GET /api/extension/status?job_id={job_id}&cvat_url={url}`
  - Returns:
    ```json
    {
      "status": "ok",
      "connected": true,
      "reviews_rev": 1,
      "history_rev": 3,
      "latest_run_id": "scan_run_123"
    }
    ```
- Web UI `pollCvatLink` in `app.js` checks both `reviews_rev` and `history_rev`:
  - When `history_rev` increments, reload finding state, active finding preview, and history stack without page reload.
- OCC ETag SHA-256 pre-check:
  - If `client_track_etag != current_etag`, return HTTP 409 Conflict with `detail="Xung đột phiên bản (OCC Conflict): Dữ liệu nhãn trên CVAT đã bị sửa đổi..."`.
- Offline CVAT check:
  - Return HTTP 503 Service Unavailable with `detail="Chỉ có bản xem ngoại tuyến; chưa kết nối CVAT để đồng bộ"`.

### 3. Visual Analytics Report Contract
- Script `tools/generate_analytics_report.py`:
  - Uses `matplotlib` with clean styling (`seaborn-v0_8-whitegrid` or equivalent).
  - Generates:
    - `review/2026-10-15/error_distribution.png`
    - `review/2026-10-15/residuals_distribution.png`
    - `review/2026-10-15/performance_metrics.png`
  - Generates:
    - `review/2026-10-15/ANALYTICS_REPORT.md` (and copied/symlinked to project root `ANALYTICS_REPORT.md`)
    - Complete tables of error counts, precision rates, latency metrics, and verification logs.

## Code Layout
- `source-tool/pointsnap-3d/pointsnap/config.yaml` — Root configuration template
- `source-tool/pointsnap-3d/pointsnap/core/config.py` — Config dataclasses and parser
- `source-tool/pointsnap-3d/pointsnap/core/scanner.py` — Scan coordination and rule filtering
- `source-tool/pointsnap-3d/pointsnap/detectors/track.py` — Track detector implementation
- `source-tool/pointsnap-3d/pointsnap/web/app.py` — REST API endpoints and extension status
- `source-tool/pointsnap-3d/pointsnap/web/static/app.js` — Web UI preview, OCC handling, and pollCvatLink
- `source-tool/pointsnap-3d/extension/src/content.js` — Extension panel, 1-click apply, rollback, and OCC handling
- `source-tool/pointsnap-3d/extension/src/ghost-engine.js` — Ghost target math, magnet snap, leveling, green lock
- `source-tool/pointsnap-3d/tools/generate_analytics_report.py` — Analytics and charting script
- `review/2026-10-15/` — Analytics report and generated PNG charts
- `tests/` — Pytest test suite
- `extension/tests/` — Node.js test suite
