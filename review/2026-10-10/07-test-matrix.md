# Ma trận yêu cầu → test → bằng chứng

| Phạm vi | Tests thực tế | Evidence /giới hạn |
|---|---|---|
| Config/schema/security | test_config, test_web, test_security_review | Full490; không authLAN |
| Geometry/pose/yaw/points | test_geometry/model, review02/03 regressions, test_real_nuscenes | Independent transforms/point counts;4datasetca runner |
| Detectors floating/size/track/heading/fit/spec | detector tests vàreview02 regressions | Threshold/empty/outside/rule; quality ởnuScenes riêng |
| CVAT read/write/attributes/snapshot | test_cvat_client/reader/writer, test_live_cvat | Mock +3livetask tự dọn; GET→PATCH race còn |
| Runner/CLI/reports/pathscope | test_backend_review_regressions, test_cli, test_report_api, test_web_a14/a15 | HTTP/TestClient vàserverlocal;thao tácGUI khácunit |
| Web/extension identity/state/worker | extension/tests/{core,review05,security06}.test.js |36Node; chưaChrome/EdgeMV3thật |
| Eval | test_evaluation_review21ca,test_metrics3ca,test_synthetic | TPs/FNs known,seed0,rate0,null/scope/logguards |
| Coverage quality | eval5tuning+5test,10rounds,all,seed0 | Config/dataset hashes;348testinjections;precisionmanual0 |
| Auto checklist | auto-tests/test_runner.py6ca +map41case |34codepass7manual;fullmanualfalse |
| Performance | benchmark2scene0/4sweeps3repeat +controlledreportHTTP | CPU/peakRAM/I/O/reportserial;notLANcapacity |
| Package/cleanCI/runtime/rollback | Phụ trách08 | không lấyeditabletests làm bằng chứngwheel |

CI hiện có testsPython vàextension; suitekhông tựbậtCVAT-write. CI runtime matrix/packaged smoke chuyển08. Mọi snapshot lịch sử vàUI ảnh05 có nguồn ngày/commit, không được tính là test củawheel08.
