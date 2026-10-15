# TEST_INFRA.md — Comprehensive 4-Tier E2E Testing Infrastructure

**Project**: PointSnap 3D Quality Acceptance & Assisted 3D Box Repair  
**Target Environment**: Windows PowerShell / Python 3.11  
**Project Root**: `D:/Vin_uni/P-029/P-029`  
**Test Suite Root**: `D:/Vin_uni/P-029/P-029/source-tool/pointsnap-3d/e2e_tests/`  
**Framework**: `pytest` & standalone runner `run_e2e.py`

---

## 1. Executive Summary & Testing Philosophy

This test infrastructure implements a comprehensive, opaque-box, requirement-driven 4-tier testing methodology covering all **17 features** defined in `PROJECT.md § Feature Inventory`.

In accordance with the Project Pattern:
1. **Opaque-Box Verification**: Tests interact with modules and subsystems strictly via public APIs, CLI entry points, REST endpoints, and defined interface contracts.
2. **Authoritative Expected Output Derivation**: Every test case derives its expected values directly from:
   - Reference programs/oracles (e.g., closed-form mathematical equations from `PROJECT.md § Interface Contracts`).
   - Ground-truth specifications in `PROJECT.md` and `ORIGINAL_REQUEST.md`.
   - Local dataset invariants (`nuScenes v1.0-mini` in `D:/Vin_uni/data/nuscenes`).
3. **Four-Tier Hierarchy**:
   - **Tier 1 (Feature Coverage)**: At least 5 isolated tests per feature (17 features $\times \ge 5 = \ge 85$ tests), covering representative happy paths and functional requirements.
   - **Tier 2 (Boundary & Corner Cases)**: At least 5 boundary/edge tests per feature (17 features $\times \ge 5 = \ge 85$ tests), covering extremes: empty clusters, zero clearance, 180° yaw flip, corrupt coordinates, high altitudes, null tracks.
   - **Tier 3 (Cross-Feature Interactions)**: Pairwise and multi-feature interaction tests ($\ge 15$ tests), ensuring no regression or unexpected coupling (e.g. Floating + Yaw Flip, Repair + CVAT Update + Rollback, OCC Concurrency).
   - **Tier 4 (Real-World Application Scenarios)**: End-to-end full workflow scenarios ($\ge 5$ scenarios) exercising the complete lifecycle from held-out scanner findings to preview delta, 1-click apply, re-scan verification, and rollback.

---

## 2. Feature-to-Tier Mapping Matrix (Features F1 to F17)

| Feature ID | Feature Name | Tier 1 (Coverage $\ge 5$) | Tier 2 (Boundaries $\ge 5$) | Tier 3 (Interactions) | Tier 4 (Scenarios) |
|---|---|---|---|---|---|
| **F1** | Held-out Quality Evaluation | `test_f1_01_scene_split`<br>`test_f1_02_synthetic_faults`<br>`test_f1_03_jump_detection_rate`<br>`test_f1_04_flip_detection_rate`<br>`test_f1_05_size_detection_rate` | `test_f1_b01_zero_boxes`<br>`test_f1_b02_extreme_jump_offset`<br>`test_f1_b03_single_point_cloud`<br>`test_f1_b04_all_outside_cuboids`<br>`test_f1_b05_corrupt_points_shape` | Cross-eval with F7 (Re-scan Clearance) | S1: Held-out scene finding resolution |
| **F2** | Human Precision $\ge 70\%$ | `test_f2_01_csv_verdict_format`<br>`test_f2_02_floating_precision_gte_70`<br>`test_f2_03_precision_formula_accuracy`<br>`test_f2_04_verdict_mapping_classes`<br>`test_f2_05_deduplication_tracks` | `test_f2_b01_empty_verdict_csv`<br>`test_f2_b02_conflicting_verdicts_error`<br>`test_f2_b03_all_unknown_unreviewed`<br>`test_f2_b04_whitespace_verdicts`<br>`test_f2_b05_unicode_verdict_parsing` | Cross-eval with F1 (Held-out Human vs Proxy) | S5: Human in the loop review flow |
| **F3** | CVAT Spec-VN Task & Gate | `test_f3_01_spec_vn_5_classes`<br>`test_f3_02_spec_vn_mandatory_attributes`<br>`test_f3_03_to_cvat_taxonomy_export`<br>`test_f3_04_gate_zero_coverage_gaps`<br>`test_f3_05_gate_threshold_evaluation` | `test_f3_b01_unknown_class_rejection`<br>`test_f3_b02_empty_job_gate_pass`<br>`test_f3_b03_missing_frame_source`<br>`test_f3_b04_negative_track_ids`<br>`test_f3_b05_extreme_box_count` | Cross-eval with F9 (CVAT Track Update) | S3: Spec-VN batch repair workflow |
| **F4** | Ground Delta Calculation | `test_f4_01_floating_positive_delta`<br>`test_f4_02_underground_negative_delta`<br>`test_f4_03_track_median_clearance`<br>`test_f4_04_isolated_box_ground_snap`<br>`test_f4_05_sloped_ground_contact` | `test_f4_b01_zero_clearance_ground`<br>`test_f4_b02_extreme_altitude_box`<br>`test_f4_b03_sparse_ground_ring_points`<br>`test_f4_b04_flat_point_plane_nan_robust`<br>`test_f4_b05_vertical_cliff_ground` | Cross-eval with F5 (Floating + Yaw) | S1, S2: Ground restoration |
| **F5** | Heading/Yaw Delta Calculation | `test_f5_01_heading_flip_180`<br>`test_f5_02_heading_motion_reversal`<br>`test_f5_03_heading_points_closeness`<br>`test_f5_04_yaw_normalization_range`<br>`test_f5_05_confidence_scoring` | `test_f5_b01_exact_pi_yaw_flip`<br>`test_f5_b02_symmetric_square_l_shape`<br>`test_f5_b03_collinear_points_heading`<br>`test_f5_b04_boundary_yaw_pi_neg_pi`<br>`test_f5_b05_empty_cluster_heading` | Cross-eval with F4 (Floating + Yaw) | S1, S3: Vehicle orientation fix |
| **F6** | Dimension & Center Delta Calculation | `test_f6_01_fit_outside_expansion`<br>`test_f6_02_size_in_track_contraction`<br>`test_f6_03_percentile_p1_p99_robustness`<br>`test_f6_04_center_xy_shift`<br>`test_f6_05_preserve_z_dimension` | `test_f6_b01_single_isolated_point`<br>`test_f6_b02_extreme_oversized_cluster`<br>`test_f6_b03_zero_margin_containment`<br>`test_f6_b04_identical_coincident_points`<br>`test_f6_b05_point_cloud_at_infinity` | Cross-eval with F7 (Rescan Size & Fit) | S1, S3: Geometric boundary repair |
| **F7** | Scanner Re-scan Clearance | `test_f7_01_floating_rescan_clearance`<br>`test_f7_02_heading_rescan_clearance`<br>`test_f7_03_fit_outside_rescan_clearance`<br>`test_f7_04_size_rescan_clearance`<br>`test_f7_05_no_regression_other_rules` | `test_f7_b01_rescan_dense_cluster`<br>`test_f7_b02_rescan_track_boundary_frames`<br>`test_f7_b03_rescan_zero_point_frame`<br>`test_f7_b04_rescan_occluded_box`<br>`test_f7_b05_rescan_multi_box_overlap` | Cross-eval with F4, F5, F6, F8 | S1, S2, S3: Zero gate error pass |
| **F8** | Backend REST Repair API | `test_f8_01_get_repair_endpoint`<br>`test_f8_02_post_apply_repair_endpoint`<br>`test_f8_03_post_rollback_endpoint`<br>`test_f8_04_api_json_response_schema`<br>`test_f8_05_invalid_track_404_error` | `test_f8_b01_malformed_json_body_422`<br>`test_f8_b02_missing_query_parameters`<br>`test_f8_b03_non_integer_job_track_id`<br>`test_f8_b04_huge_payload_handling`<br>`test_f8_b05_unsupported_repair_rule` | Cross-eval with F9, F10 (REST+Safe+Rollback) | S1, S4: REST client interaction |
| **F9** | CVAT API Safe Update | `test_f9_01_all_keyframes_preserved`<br>`test_f9_02_attributes_verbatim_intact`<br>`test_f9_03_points_16_floats_format`<br>`test_f9_04_occ_precheck_matching_etag`<br>`test_f9_05_occ_conflict_rejection` | `test_f9_b01_single_keyframe_track`<br>`test_f9_b02_100_keyframes_long_track`<br>`test_f9_b03_track_with_complex_attributes`<br>`test_f9_b04_stale_etag_occ_mismatch`<br>`test_f9_b05_network_retry_idempotence` | Cross-eval with F10 (Rollback Integrity) | S2: Non-targeted keyframe test |
| **F10** | Rollback & History Persistence | `test_f10_01_snapshot_file_creation`<br>`test_f10_02_snapshot_json_schema`<br>`test_f10_03_history_restore_integrity`<br>`test_f10_04_multiple_history_entries`<br>`test_f10_05_snapshot_directory_structure` | `test_f10_b01_missing_history_id_404`<br>`test_f10_b02_corrupted_history_json`<br>`test_f10_b03_nonexistent_job_history_dir`<br>`test_f10_b04_read_only_history_snapshot`<br>`test_f10_b05_concurrent_history_writes` | Cross-eval with F8, F9 (Full Lifecycle) | S1, S2, S4: Instant Undo |
| **F11** | Web UI 3-View Preview Overlay | `test_f11_01_top_view_canvas_transform`<br>`test_f11_02_side_view_ground_line`<br>`test_f11_03_front_view_center_dot`<br>`test_f11_04_dashed_contrast_repair_box`<br>`test_f11_05_delta_metrics_rendering` | `test_f11_b01_zero_point_preview`<br>`test_f11_b02_extreme_zoom_scale`<br>`test_f11_b03_large_canvas_aspect_ratio`<br>`test_f11_b04_nan_coordinate_preview`<br>`test_f11_b05_multiple_overlapping_boxes` | Cross-eval with F12 (Preview to Apply) | S1: Visual verification |
| **F12** | Web UI 1-Click Apply & Rollback | `test_f12_01_apply_button_post_request`<br>`test_f12_02_confirmation_popover_flow`<br>`test_f12_03_rollback_button_post_request`<br>`test_f12_04_ui_status_update_on_apply`<br>`test_f12_05_double_click_debounce` | `test_f12_b01_apply_during_active_request`<br>`test_f12_b02_rollback_empty_history`<br>`test_f12_b03_dismissed_popover_no_patch`<br>`test_f12_b04_rapid_sequential_rollbacks`<br>`test_f12_b05_network_timeout_ui_error` | Cross-eval with F8, F11 | S1: User confirmation loop |
| **F13** | Extension UI Repair Card | `test_f13_01_shadow_dom_card_creation`<br>`test_f13_02_delta_metrics_display`<br>`test_f13_03_action_buttons_render`<br>`test_f13_04_card_state_transitions`<br>`test_f13_05_theme_compatibility` | `test_f13_b01_zero_delta_repair_card`<br>`test_f13_b02_missing_optional_metrics`<br>`test_f13_b03_disconnected_shadow_root`<br>`test_f13_b04_long_reason_text_wrap`<br>`test_f13_b05_rapid_finding_switch` | Cross-eval with F14 (Security Bridge) | S1: Extension card approval |
| **F14** | Extension Security Whitelisting | `test_f14_01_whitelist_repair_route`<br>`test_f14_02_whitelist_apply_route`<br>`test_f14_03_whitelist_rollback_route`<br>`test_f14_04_block_path_traversal`<br>`test_f14_05_block_query_smuggling` | `test_f14_b01_encoded_dot_dot_traversal`<br>`test_f14_b02_hash_fragment_injection`<br>`test_f14_b03_invalid_http_verb`<br>`test_f14_b04_disallowed_origin_header`<br>`test_f14_b05_excessive_url_length` | Cross-eval with F8, F13 | S1: Secure extension communication |
| **F15** | Full Regression Testing | `test_f15_01_pytest_baseline_suite`<br>`test_f15_02_node_extension_suite`<br>`test_f15_03_zero_error_count`<br>`test_f15_04_clean_label_proxy_stability`<br>`test_f15_05_geometry_transform_integrity` | `test_f15_b01_regression_missing_env`<br>`test_f15_b02_regression_corrupt_config`<br>`test_f15_b03_regression_empty_cache`<br>`test_f15_b04_regression_parallel_execution`<br>`test_f15_b05_regression_virtualenv_isolation` | Cross-eval across all core modules | Comprehensive regression gate |
| **F16** | E2E Test Suite Pass | `test_f16_01_tier1_all_pass`<br>`test_f16_02_tier2_all_pass`<br>`test_f16_03_tier3_all_pass`<br>`test_f16_04_tier4_all_pass`<br>`test_f16_05_runner_exit_code_zero` | `test_f16_b01_runner_empty_suite_handling`<br>`test_f16_b02_runner_interrupted_run`<br>`test_f16_b03_runner_json_summary_output`<br>`test_f16_b04_runner_custom_filter`<br>`test_f16_b05_runner_verbose_mode` | Meta-test validating entire suite | S1..S5 Orchestration |
| **F17** | Adversarial Hardening | `test_f17_01_nan_inf_cuboid_handling`<br>`test_f17_02_zero_volume_box_rejection`<br>`test_f17_03_massive_cloud_stress_100k`<br>`test_f17_04_concurrent_occ_race_condition`<br>`test_f17_05_corrupt_history_file_tampering` | `test_f17_b01_interleaved_negative_frames`<br>`test_f17_b02_collinear_coplanar_points`<br>`test_f17_b03_conflicting_track_labels`<br>`test_f17_b04_extreme_quaternion_gimbal_lock`<br>`test_f17_b05_unwritable_history_directory` | Stress testing under adversarial conditions | S4: High concurrency stress |

---

## 3. Detailed Specification of the 4 Tiers

### Tier 1: Feature Coverage ($\ge 85$ tests, $\ge 5$ per feature)
- **Goal**: Confirm baseline functional behavior of each feature in isolation.
- **Contract Adherence**: Checks method signatures, return dataclasses, HTTP response status codes (`200 OK`), JSON bodies, and error codes.
- **Derivation**: Derived from requirements in `PROJECT.md` and `ORIGINAL_REQUEST.md`.

### Tier 2: Boundary & Corner Cases ($\ge 85$ tests, $\ge 5$ per feature)
- **Goal**: Ensure the system does not crash or corrupt data when subjected to extreme, non-standard, or degenerate inputs.
- **Inputs Tested**: Empty point clouds, extreme heights ($> 100$ m, $< -100$ m), zero clearances, 180° yaw flips, $\pm\pi$ boundary wraps, single-point clouds, massive clouds ($10^5$ points), duplicate/conflicting verdicts, path traversals (`..%2f`), and OCC version mismatches.

### Tier 3: Cross-Feature Interactions ($\ge 15$ tests)
- **Goal**: Ensure modules interact correctly in pairwise and multi-module pipelines without regressions.
- **Key Pairs**:
  - `F4 + F5`: Floating ground delta combined with 180° yaw flip.
  - `F4 + F7`: Ground delta repair followed by immediate scanner re-scan (verifying 0 errors).
  - `F5 + F7`: Yaw delta repair followed by immediate scanner re-scan.
  - `F6 + F7`: Dimension delta repair followed by immediate scanner re-scan.
  - `F8 + F9`: REST API `/apply-repair` invoking CVAT safe track update with OCC.
  - `F8 + F10`: REST API `/rollback` restoring persistent snapshot.
  - `F9 + F10`: Concurrency race condition triggering OCC reject and keeping history intact.
  - `F11 + F12`: Web 3-view preview calculation feeding 1-Click apply confirmation.
  - `F13 + F14`: Chrome Extension UI card requesting repair through background security whitelist.
  - `F1 + F7`: Held-out synthetic error scan, repairing identified faults, and verifying re-scan gate PASS.

### Tier 4: Real-World Application Scenarios ($\ge 5$ tests)
- **Goal**: Execute complete, end-to-end real-world user workflows.
- **Scenario 1 (`scenario_heldout_repair_clearance_rollback`)**:
  Scanner flags floating vehicle on held-out scene -> preview computes $\Delta z = -\text{offset}$ -> 1-Click apply patches CVAT track -> re-scan gate passes with 0 errors -> Rollback restores pre-repair state.
- **Scenario 2 (`scenario_multiframe_track_integrity`)**:
  5-frame vehicle track with frame 2 yaw-flipped and frame 3 floating. Targeted repairs applied to frame 2 and 3 sequentially. Verify frames 0, 1, 4 remain strictly bit-for-bit identical, attributes preserved, re-scan clean.
- **Scenario 3 (`scenario_spec_vn_batch_repair`)**:
  Spec-VN task containing Vehicle, Two-wheels, and Pedestrian. Batch repair computes distinct class-specific deltas (rider pose, ground contact, pedestrian bounding box). Gate command passes with 0 coverage gaps.
- **Scenario 4 (`scenario_high_concurrency_occ_safety`)**:
  Two annotators inspect the same track. Annotator A applies repair; Annotator B attempts stale repair -> rejected by OCC pre-check with HTTP 409 Conflict. History preserves intact snapshot of Annotator A's action.
- **Scenario 5 (`scenario_full_synthetic_pipeline_to_clean_verdict`)**:
  Full cycle: synthetic error injection on held-out scene -> scanner generates findings -> automated repair engine computes deltas -> simulated annotator approval -> patch -> re-scan gate PASS -> quality metrics report generated.

---

## 4. Test Execution & Orchestration

The E2E test suite can be run using either standard `pytest` or the standalone runner `run_e2e.py`.

```powershell
# 1. Run all E2E tiers via standalone runner:
python e2e_tests/run_e2e.py --all

# 2. Run specific tiers:
python e2e_tests/run_e2e.py --tier 1
python e2e_tests/run_e2e.py --tier 2
python e2e_tests/run_e2e.py --tier 3
python e2e_tests/run_e2e.py --tier 4

# 3. Run via pytest directly:
pytest e2e_tests/ -v
pytest e2e_tests/test_tier1_features.py -v
pytest e2e_tests/test_tier2_boundaries.py -v
pytest e2e_tests/test_tier3_interactions.py -v
pytest e2e_tests/test_tier4_scenarios.py -v
```
