# Ma trận tương thích và cài mới

Đối chiếu 12/10/2026; code `94dac32`, test fixture `79849b4`. Chỉ chứng nhận
phạm vi từng dòng. requires-python ≥3.10 không có nghĩa mọi phiên bản đã kiểm.

| Tổ hợp | Cài mới / dependencies | CLI/Web | CVAT/dataset | Extension | Giới hạn |
|---|---|---|---|---|---|
| Windows, Python3.12.14, venv công việc | Editable hiện có; môi trường runtime bundled phải nạp site-packages | Full493 pytest,0skip; 36Node | CVAT2.78.1, mini thật,3live fixtures tự dọn | Node logic, Web thật ở05 | Không phải máy trắng; không MV3 thật |
| Windows, Python3.12.14, wheel venv riêng | Wheel94dac32, pip check đạt; NumPy2.5.4/Pydantic2.14.1 | CLI help/config/spec-vn, Web7routes200 ngoài source | Không dùng PAT/dataset trong smoke | Không | 21font trong wheel, HTTP một font; không mở mọi glyph |
| Linux Docker, Python3.12.15, image CLI→API | Build source archive; NumPy2.5.4/Pydantic2.14.1 | CLIhelp/config; Report API JSON/HTML/CSV | Fixture79 thật trên CVAT2.78.1, cloud có, annotations giữ, router/restart | Không | Image/private container; không redeploy service đang dùng |
| Linux Docker, Python3.11.17 | Build package; editable từ archive79849b4 trong /tmp; pip check đạt | 486pytest đạt,7skip; package Web7routes200 từ /work | Không mount mini/PAT,4dataset+3live skip | Không | Retry build dùng Dockerfile tạm thêm pip timeout120/retries3 sau lỗi mạng |
| GitHub CI dự kiến Ubuntu3.10/3.11,Windows3.12,Node22 | Workflow matrix +artifact job được sửa/đọc cấu trúc | Chưa có run remote cho nhánh review | CI không có CVAT live/dataset | Node job dự kiến | Chỉ cấu hình, không kết quả CI |
| CVAT2.77.0/2.77.1 chuẩn gốc,server BTC | Tài liệu lịch sử; không cài/đo lại | Code/API fixture khác version không suy tương thích | Chưa kiểm mới | Chưa kiểm mới | Cần stack/job thử đúng đích |
| Chrome/Edge MV3 thật | Bề mặt được kết nối chỉ IAB/MCPApps | Chưa Load unpacked/worker/permission mới | Chưa thao tác CVAT3D trong MV3 | Chưa nghiệm thu | Bị chặn môi trường trình duyệt |
| LAN/HTTPS/proxy path/nhiều người | Ngoài mô hình Web local | Chưa có auth người dùng/reverse proxy được nghiệm thu | Không chứng nhận concurrent Save atomic | Proxy path chưa hỗ trợ extension options | Chốt mô hình và kiểm môi trường đích trước rollout |

Docker base `python:3.12-slim` không pin digest; artifact dependency resolution chưa
lock. Ghi image ID và phiên bản trong evidence để tái hiện đúng đợt này. Tag/package
0.1.0 không đủ xác định source commit. Linux3.11 dùng NumPy2.4.6 do compatibility
resolver; không ghi hai runtime có cùng dependencies.

## Cài sạch đã thực hiện

1. `git archive` từ tool root tại94dac32, giải nén vào out riêng; .env/.venv/data/out
   không có trong archive. Build isolated sdist/wheel bằng build-env riêng.
2. Venv artifact Windows tách biệt, cài wheel, pipcheck, chạy script smoke từ ngoài
   working tree. Kiểm package_path trong site-packages, không source import fallback.
3. Build CLI image rồi API image base tag private cùng source. API user pointsnap,
   mount dataset/exportRO, rootfsRO/tmpfs, PAT người gọi mỗi request.
4. Linux3.11 build với PYTHON_VERSION arg, test source archive readonly mount được
   copy vào /tmp container tạm để cài editable/test; không ghi source host.
5. Linux package smoke trong /work dưới user pointsnap từ installed package. Test
   editable và package smoke là hai ca riêng, không coi pytest source là wheel test.

[Bằng chứng](evidence/08/README.md) ghi hashes/image IDs/runtime/skips/commands.
