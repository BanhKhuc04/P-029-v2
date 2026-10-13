# Evidence 08

12/10/2026, Asia/Saigon. Production source `94dac32a64fa91d3ebe6211db2c1f84716044f81`,
test dataset isolation `79849b4fd73f80f697cf228fd5a7222fdc79c0ac`.
Raw logs/artifacts/dataset/annotations ở tool/out ignored. Bản này chỉ metadata,
counts/hashes/check results; không PAT thật hay payload nhãn.

| Mã | Ca / loại | File | Kết quả / lệnh / giới hạn |
|---|---|---|---|
| EV-08-001 | Package/Windows real runtime | [package-tests](package-tests.json),[artifact-smoke](artifact-smoke.json) | Build→installwheel→pipcheck→smokeoutside; exits0;90files/27static/21font |
| EV-08-002 | Windows full suites | [package-tests](package-tests.json) | pytest493pass,0skip/fail/error,51,84s;Node36pass;1deprecationwarning |
| EV-08-003 | Live CVAT/API | [before](api-before.json),[after](api-after.json) | GET3formats/PATmissing/PATfake/health; cloudfalse→true; geometry payload digest giữ |
| EV-08-004 | Traefik/restart live | [router](api-router.json),[restart](api-restart.json),[docker](docker.json) | Router Hostfixture riêngpriority100;restartownedAPI;reports/auth/links200/401 đúng |
| EV-08-005 | Filesystem operation fixture | [operations](operations.json) | FakePATonly,11files,byteequal,done/queued/bridge;rollbackreader04+currentdeps |
| EV-08-006 | Launcher Windows fixture | [launcher](launcher.json) | cwd khác;APIprojects200;portoccupiedrejected;ownPIDstop;noexecutionpolicychange |
| EV-08-007 | Linux source/installed runtime | [linux-tests](linux-tests.json),[linux-smoke](linux-smoke.json),[linux312](linux312-runtime.json) | 486pass/7skip;installedpackage7HTTP200;CLI/config3.12;PyPIretryrecorded |
| EV-08-008 | Cleanup live | [cleanup](cleanup.json) | Task/job79HTTP404,ownedcontainer/PIDsremoved;worktasks/imagesuntouched |
| EV-08-009 | Inventory/docs | [inventory](inventory-summary.json),[docs-check](docs-check.json) | baseline184/currentindexcoverage/Markdownlocalpaths;notanchororvisualQA |

## Lệnh thực tế (cwd tool root trừ khi ghi khác)

```powershell
git archive --format=zip --output=out/review08-final-clean.zip 94dac32
Expand-Archive out/review08-final-clean.zip out/review08-final-clean
./out/build-env/Scripts/python.exe -m build ./out/review08-final-clean --outdir ./out/review08-final-dist
./out/artifact-env/Scripts/python.exe -m pip install --force-reinstall --no-deps ./out/review08-final-dist/pointsnap-0.1.0-py3-none-any.whl
./out/artifact-env/Scripts/python.exe -m pip check
# cwd out/review08-final-dist; Python/script absolute paths:
# artifact-env/Scripts/python.exe <tool-root>/scripts/smoke_package.py
node --test extension/tests/core.test.js extension/tests/review05.test.js extension/tests/security06.test.js
docker compose config --quiet
docker build -t pointsnap-review:94dac32 ./out/review08-final-clean
docker build --build-arg POINTSNAP_BASE_IMAGE=pointsnap-review:94dac32 -f ./out/review08-final-clean/Dockerfile.api -t pointsnap-api-review:94dac32 ./out/review08-final-clean
```

FullWindows gọi pytest bằng runpy để nạp workspace .venv/Lib/site-packages của
bundled runtime: flags `-q -p no:cacheprovider --basetemp out/r08-final-<unique>
--tb=line -ra --junitxml=out/review08-final.xml`; POINTSNAP_HOME riêng,
NUSCENES_ROOT mini local, POINTSNAP_LIVE_CVAT=1. Client fixture tự tạo/dọn3task.

Linux3.11 firstbuild theo Dockerfile gốc thất bại pipReadTimeoutError lúc tảiNumPy.
Retry dùng file tạm cùng Dockerfile với `pip install --timeout 120 --retries 3`,
ARG PYTHON_VERSION=3.11; package source không đổi. Mount readonly archive79849b4
vào /src,copy vào /tmp container,--user0 để pipinstall-e.[dev]/pytest;--rm khi xong.
Package smoke chạy container riêng userpointsnap từ /work,importsitedpackage.
Không mount dataset/.env/PAT hoặc mởopt-in live trongLinux nên7skip có lý do.

APIfixture mount export/datasetRO,read-onlyrootfs/tmpfs,UID1000,bind127.0.0.1:8881,
networkcvat_cvat;PATcaller nạp .env trong helpermemorykhông xuấtgiátrị. Helpers GET
JSON/HTML/CSV,missing/fakePAT/health,digestannotations. Routertest Host
pointsnap-review.local tới127.0.0.1:8080,các label router/service riêng. Giữ no-store
và linksWebURL; counts/coverage không chứng nhậnqualitydetector. Test helpercleanup
ban đầu giả định CvatError.status_code; task đãxóa, follow-up kiểmstatusHTTP404.

Các tên/range đã được kiểm tra; không commit rawCVATpayload/token. Khác runtime
patchversion/dependency và các hạn chế chưa kiểm được ghi trongma trận/báocáo08.
