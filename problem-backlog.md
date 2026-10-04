# Problem backlog

Những chỗ gặp trong lúc gán nhãn mà **guideline chưa trả lời được**, cộng các pain point về công cụ.

Ghi ngay khi gặp, kể cả lúc chưa biết xử lý thế nào. Một edge case không được ghi lại thì
mỗi người sẽ tự xử lý theo một kiểu — và đó là nguồn lớn nhất của nhãn không nhất quán.

## Danh sách

| Mã | Tóm tắt | Loại | Mục guideline | Trạng thái | Kết quả |
|---|---|---|---|---|---|
| [P-001](#p-001) | Quy ước gán nhãn đường đi bộ: kẻ từng vạch sọc dọc hay chỉ kẻ các đường ngang giới hạn | Guideline chưa nói tới | LANE/CROSSWALK | ✅ Đã chốt | [QĐ-001](so-quyet-dinh.md#qđ-001) |
| [P-002](#p-002) | Quy cách vẽ Polygon Drivable Area: gộp/tách làn và việc bao trùm vật thể trên đường | Guideline chưa nói tới | §4.1, §4.2 | ✅ Đã chốt | [QĐ-002](so-quyet-dinh.md#qđ-002) |
| [P-003](#p-003) | Quy ước gán nhãn vạch xương cá (chevron): xử lý Drivable Area và class Polyline | Guideline chưa nói tới | §2, §4 | ✅ Đã chốt | [QĐ-003](so-quyet-dinh.md#qđ-003) |
| [P-004](#p-004) | Chưa đồng nhất gán nhãn `area/alternative` giữa các job | Guideline mơ hồ | §2, §4.1 | ✅ Đã chốt | [QĐ-004](so-quyet-dinh.md#qđ-004) |
| [P-005](#p-005) | Ranh giới `road` vs `sidewalk` tại các đoạn hạ vỉa hè / lối xe ra vào (curb cut / ramp) | Guideline mơ hồ | §4 (road vs sidewalk) | ✅ Đã chốt | [QĐ-005](so-quyet-dinh.md#qđ-005) |
| [P-006](#p-006) | Phân định `vegetation` vs `terrain` tại thảm cỏ thấp xen kẽ gốc cây và bồn cây | Guideline mơ hồ | §4 (vegetation vs terrain) | ✅ Đã chốt | [QĐ-006](so-quyet-dinh.md#qđ-006) |
| [P-007](#p-007) | Phân loại `person` vs `rider` trong tình huống người đi bộ dắt xe hai bánh | Guideline mơ hồ | §4 (person vs rider) | ✅ Đã chốt | [QĐ-007](so-quyet-dinh.md#qđ-007) |
| [P-008](#p-008) | Quy ước hệ tọa độ local và hướng của 3D Cuboid (trục X, Y, Z local vs global) | Guideline chưa nói tới | §4.3 (Hướng / yaw) | ✅ Đã chốt | [QĐ-008](so-quyet-dinh.md#qđ-008) |
| [P-009](#p-009) | Ngưỡng tối thiểu điểm LiDAR (Min points) để gán vật thể & giới hạn khoảng cách (Range cut-off) | Guideline chưa nói tới | §4.2, §4.4 | 🔴 Mở | Chờ thảo luận / Hỏi BTC |
| [P-010](#p-010) | Khó phân biệt mặt đường trong 3D Point Cloud để căn đáy cuboid sát mặt đất (Ground Alignment) | Pain point công cụ | §4.2 (Vị trí / Z-grounding) | 🛠️ Làm tool | [Chi tiết](#p-010) |
| [P-011](#p-011) | Thiếu pipeline Auto-QA tiền kiểm tra: lỗi 3D phát hiện muộn ở khâu review gây rework lớn | Pain point công cụ | §4 (Quy chuẩn 3D & QA) | 🛠️ Làm tool | [Chi tiết](#p-011) |
| [P-012](#p-012) | Quá tải thị giác và sót/lặp kiểm tra khi frame có mật độ box dày đặc (Scene Clutter & Verification) | Pain point công cụ | §5 (Quy trình kiểm tra) | 🛠️ Làm tool | [Chi tiết](#p-012) |

**Loại**

| Loại | Nghĩa là |
|---|---|
| Guideline chưa nói tới | Tình huống không có trong guideline |
| Guideline mơ hồ | Đọc guideline ra được hai cách hiểu trở lên |
| Guideline mâu thuẫn | Hai mục trong guideline nói ngược nhau |
| Pain point công cụ | Guideline rõ, nhưng làm trên CVAT chậm hoặc dễ sai |

**Trạng thái:** 🔴 Mở · 🗣️ Đang bàn · ↗️ Hỏi BTC · ✅ Đã chốt (trỏ sang QĐ) · 🛠️ Làm tool (trỏ sang `source-tool/`) · ⚪ Bỏ (ghi lý do)

---

## P-001

**Quy ước gán nhãn đường đi bộ (crosswalk): kẻ từng vạch sọc hay chỉ kẻ các đường ngang giới hạn**

- **Loại:** Guideline chưa nói tới
- **Mục guideline:** LANE / CROSSWALK (vạch kẻ đường cho người đi bộ)
- **Người phát hiện:** @Đặng Văn Huy · 16/09/2026
- **Link CVAT:**
  - https://cvat.note.transformerlabs.ai/tasks/148/jobs/1444?frame=54 — Frame 54 (Job #1444): Kẻ chi tiết từng line dọc theo từng vạch sơn sọc trắng của đường đi bộ kèm đường bao.
  - https://cvat.note.transformerlabs.ai/tasks/148/jobs/1445?frame=79 — Frame 79 (Job #1445): Chỉ kẻ các đường thẳng nằm ngang (transverse lines) đánh dấu ranh giới mép trên/dưới khu vực đường đi bộ, không kẻ từng vạch sọc.
- **Mô tả:** Guideline chưa làm rõ quy cách vẽ polyline/line cho vạch sang đường cho người đi bộ dạng sọc (zebra crossing), dẫn đến hai annotator ở hai job làm theo hai quy ước khác nhau:
  - Tại frame 54 (Job #1444): Annotator vẽ các đường line chạy dọc theo từng vạch sơn trắng riêng lẻ của đường đi bộ, đồng thời kẻ đường bao ngang.
  - Tại frame 79 (Job #1445): Annotator không kẻ theo từng vạch sơn đơn lẻ mà chỉ vẽ các đường thẳng nằm ngang cắt ngang mặt đường để phân định vùng đường đi bộ.
- **Các cách hiểu:**
  1. *Cách 1 (như Frame 54):* Kẻ dọc theo từng vạch sọc trắng riêng lẻ. Ưu điểm: dữ liệu hình học chi tiết từng dải sơn. Nhược điểm: tốn nhiều công sức, thời gian gán nhãn tăng cao.
  2. *Cách 2 (như Frame 79):* Chỉ kẻ các đường ngang giới hạn biên vùng đường đi bộ (ranh giới trước/sau). Ưu điểm: nhanh, gọn gàng. Nhược điểm: không thể hiện cấu trúc các sọc trắng bên trong.
- **Xử lý tạm trong lúc chờ:** Tạm giữ nguyên hiện trạng
- **Kết quả:** ✅ [QĐ-001](so-quyet-dinh.md#qđ-001)

## P-002

**Quy cách vẽ Polygon cho Drivable Area: gộp hay tách làn, và việc bao trùm các vật thể trên đường**

- **Loại:** Guideline chưa nói tới
- **Mục guideline:** §4.1 — Polygon (Drivable Area), §4.2 — Polyline (Lane Marking) & §2 — Taxonomy (`area/drivable`, `area/alternative`)
- **Người phát hiện:** @Nhữ Đình Chiến · 17/09/2026
- **Link CVAT:**
  - https://cvat.note.transformerlabs.ai/tasks/148/jobs/1444?frame=58 — Đường nhiều làn cùng chiều và ngược chiều (phân tách bởi vạch `lane/double yellow`), có nhiều ô tô đang lưu thông và đỗ bên đường.
- **Mô tả:** Khi gán nhãn vùng di chuyển (Drivable Area) bằng Polygon theo §4.1, tài liệu chưa quy định cụ thể các vấn đề thực tế:
  1. *Phân chia Polygon theo làn đường:* Khi có nhiều làn xe, nên vẽ 1 polygon bao trùm toàn bộ các làn cùng chiều, hay phải vẽ riêng từng làn?
  2. *Polygon đường đi có được bao trùm các vật thể trên đường không:* Khi vẽ polygon vùng đường xe chạy (`area/drivable`), có được vẽ bao trùm xuyên qua các vật thể đang có trên mặt đường (ô tô, xe máy, người đi bộ...) hay phải "né" (khoét đường viền lượn vòng quanh vật thể)?
  3. *Sự khác biệt giữa Polygon vùng đường và Polyline vạch kẻ làn:* Cần làm rõ quy ước để tránh nhầm lẫn giữa việc vẽ Polygon mặt đường (cho phép bao trùm xe) và vẽ Polyline vạch sơn (bị xe che thì phải ngắt theo §4.2).
- **Các cách hiểu:**
  - **Vấn đề 1 — Gộp hay tách làn:**
    - *Cách 1.1 (Tách từng làn đơn lẻ):* Mỗi làn xe vẽ một polygon riêng biệt. (Nhược điểm: rất tốn công, không đúng bản chất vùng di chuyển tự do vì xe có thể chuyển làn).
    - *Cách 1.2 (Theo chuẩn BDD100K - Đề xuất):* Gộp toàn bộ các làn cùng chiều mà xe ego có quyền đi thành 1 polygon mang nhãn `area/drivable`. Riêng phần đường ngược chiều (phía bên kia vạch `double yellow`) thì vẽ thành một polygon riêng mang nhãn `area/alternative`.
  - **Vấn đề 2 — Polygon có bao trùm các vật thể (ô tô, xe máy, người...) trên đường không:**
    - *Cách 2.1 (Né / khoét quanh vật thể):* Vẽ polygon lượn viền quanh từng ô tô hoặc người trên đường. (Nhược điểm: polygon cực kỳ phức tạp, nhiều đỉnh thừa, dễ lỗi self-intersection).
    - *Cách 2.2 (Bao trùm vật thể - Đề xuất theo chuẩn BDD100K):* **Được và nên bao trùm**. Polygon drivable bám sát biên thực tế của mặt đường, đi thẳng qua vị trí đáy/bánh xe của các phương tiện và người.
- **Xử lý tạm trong lúc chờ:** Thảo luận nội bộ đội và tham khảo quy chuẩn BDD100K.
- **Kết quả:** ✅ [QĐ-002](so-quyet-dinh.md#qđ-002)

## P-003

**Quy ước gán nhãn vạch xương cá (chevron marking): xác định Drivable Area và class Polyline**

- **Loại:** Guideline chưa nói tới
- **Mục guideline:** §2 — Taxonomy & §4 — Quy tắc Polygon và Polyline
- **Người phát hiện:** @Khúc Việt Anh · 17/09/2026
- **Link CVAT:** https://cvat.note.transformerlabs.ai/tasks/148/jobs/1442?frame=0 — vạch xương cá (chevron/gore area) bên phải đường phân tách làn, có tag `UNCERTAIN_BOUNDARY`
- **Mô tả:** Mặt đường cao tốc xuất hiện khu vực vạch xương cá (chevron marking / gore area / đảo mềm phân tách luồng xe) ở bên phải. Guideline hoàn toàn chưa có quy định cho cả 2 loại shape:
  1. *Về Vùng di chuyển (Drivable Area – Polygon):* Vùng vạch xương cá này có được vẽ Polygon không?
  2. *Về Vạch kẻ đường (Lane Marking – Polyline):* Taxonomy của guideline (§2) không có class `lane/chevron` hay `lane/gore`. Quy cách vẽ là chỉ kẻ đường bao ranh giới hay phải kẻ chi tiết từng vệt sơn chéo bên trong?
- **Các cách hiểu:**
  - **Vấn đề 1 — Drivable Area (Polygon):**
    - *Cách 1.1 (Không vẽ Polygon - Đề xuất theo luật giao thông):* Vạch xương cá là vùng cấm phương tiện lưu thông/chèn vạch. Ranh giới `area/drivable` dừng lại ở mép ngoài vạch sơn bao ngoài (coi là non-drivable).
    - *Cách 1.2 (Vẽ Polygon `area/alternative`):* Coi là vùng có thể tấp vào khi khẩn cấp.
  - **Vấn đề 2 — Lane Marking (Polyline):**
    - *Cách 2.1 (Chỉ kẻ đường viền biên - Đề xuất):* Chỉ dùng Polyline kẻ đường biên ranh giới bao quanh vùng xương cá (dùng `lane/single white` hoặc `lane/double white`). Bỏ qua các vệt sơn chéo bên trong.
    - *Cách 2.2 (Kẻ chi tiết từng vệt chéo):* Kẻ cả đường biên lẫn từng vệt sơn chéo bên trong.
- **Xử lý tạm trong lúc chờ:** Gắn tag `UNCERTAIN_BOUNDARY` tại frame 0 (Job #1442); tạm thời không vẽ polygon đè lên vùng xương cá và chỉ kẻ đường biên ngoài.
- **Kết quả:** ✅ [QĐ-003](so-quyet-dinh.md#qđ-003)

## P-004

**Chưa đồng nhất gán nhãn `area/alternative` giữa các job trong Task #148**

- **Loại:** Guideline mơ hồ
- **Mục guideline:** §2 — Taxonomy & §4.1 — Polygon (Drivable Area)
- **Người phát hiện:** @Khúc Việt Anh · 18/09/2026
- **Link CVAT:** https://cvat.note.transformerlabs.ai/tasks/148/jobs/1442?frame=15 — Job #1442 có 22 polygon `area/alternative`, Job #1445 có 18 polygon, trong khi Job #1443 và #1444 không gán frame nào.
- **Mô tả:** Có sự không đồng nhất giữa các job: Job #1442 và #1445 vẽ polygon `area/alternative` cho làn đường đối diện / nhánh rẽ, còn Job #1443 và #1444 chỉ vẽ `area/drivable` mà bỏ qua phần đường đối diện.
- **Các cách hiểu:**
  1. *Cách 1:* Bắt buộc vẽ cả `area/alternative` cho toàn bộ phần đường xe có thể đi được nhưng thuộc chiều ngược lại hoặc vùng phụ.
  2. *Cách 2:* Chỉ ưu tiên vẽ `area/drivable` của làn xe ego, bỏ qua `area/alternative` nếu không có ranh giới rõ ràng.
- **Xử lý tạm trong lúc chờ:** Đang bàn trong buổi họp nghiệm thu Task #148.
- **Kết quả:** ✅ [QĐ-004](so-quyet-dinh.md#qđ-004)

## P-005

**Ranh giới giữa `road` và `sidewalk` tại các đoạn hạ vỉa hè / lối xe ra vào (Curb Cut / Driveway Ramp)**

- **Loại:** Guideline mơ hồ
- **Mục guideline:** §4 — Các cặp class dễ nhầm (`road vs sidewalk`) & RULE 02
- **Người phát hiện:** @Đặng Văn Huy · 19/09/2026
- **Link CVAT:** https://cvat.note.transformerlabs.ai/tasks/202/jobs/1658?frame=12 — Đoạn vỉa hè vát dốc thoải hạ cốt xuống ngang mặt đường để xe máy leo lên vỉa hè hoặc lối rẽ vào ngõ.
- **Mô tả:** Guideline quy định `road` là phần mặt đường dành cho phương tiện lưu thông, `sidewalk` là lối đi bộ/viền hè tách khỏi mặt đường. Tại các vị trí ram dốc vỉa hè (curb cut / driveway ramp):
  - Bề mặt dốc thoải được đổ bê tông nối liền mặt đường, xe cơ giới có thể di chuyển lên được.
  - Một số annotator vẽ phần ram dốc này thuộc `road` (vì xe chạy lên được), một số khác lại vẽ thuộc `sidewalk` (vì nằm trong ranh giới thẳng của vỉa hè).
- **Các cách hiểu:**
  1. *Cách 1 (Gán `sidewalk` theo tuyến vỉa hè):* Giữ nguyên ranh giới mép đường liên tục (đường viền bó vỉa thẳng); toàn bộ phần dốc nghiêng hạ cốt vẫn thuộc `sidewalk`. Ưu điểm: đảm bảo tính liên tục của vỉa hè hình học.
  2. *Cách 2 (Gán `road` cho phần mặt dốc):* Phần dốc mà phương tiện có thể đi vào được gán nhãn `road`. Nhược điểm: ranh giới vỉa hè bị lõm nham nhở, khó thống nhất độ sâu dốc.
- **Xử lý tạm trong lúc chờ:** Tạm thời gán là `sidewalk` theo đường thẳng mép bó vỉa; gắn cờ `UNCERTAIN_CLASS` tại Frame 12 Job #1658 để họp chốt.
- **Kết quả:** ✅ [QĐ-005](so-quyet-dinh.md#qđ-005)

## P-006

**Phân định ranh giới giữa `vegetation` và `terrain` tại thảm cỏ thấp xen kẽ gốc cây và bồn hoa**

- **Loại:** Guideline mơ hồ
- **Mục guideline:** §4 — Các cặp class dễ nhầm (`vegetation vs terrain`) & §5 — Thao tác khuyến nghị trên CVAT
- **Người phát hiện:** @Nhữ Đình Chiến · 19/09/2026
- **Link CVAT:** https://cvat.note.transformerlabs.ai/tasks/202/jobs/1660?frame=62 — Dải phân cách trồng cỏ thấp bên dưới và các khóm cây bụi/tán lá thấp bên trên, xen lẫn các mảng đất trơ.
- **Mô tả:** Guideline định nghĩa `vegetation` = cây/bụi/lá; `terrain` = đất/cỏ/bề mặt tự nhiên thấp không được xem là vegetation dạng cây/bụi.
  - Khi dùng Brush vẽ vùng dải phân cách hoặc công viên ven đường, phần cỏ thấp mọc lan sát dưới tán cây rất khó tách bạch.
  - Nếu cố gắng bóc tách từng mảng cỏ (`terrain`) ra khỏi tán cây (`vegetation`), annotator để lại hàng chục mẩu mask vụn li ti (fragmented masks) và bị chồng lấn (overlap) đè lên nhau, vi phạm RULE 01.
  - Một số bạn tô gộp toàn bộ khu vực bồn cây xanh là `vegetation`, người khác lại bóc tách nhỏ lẻ.
- **Các cách hiểu:**
  1. *Cách 1 (Gộp theo khu vực chiếm ưu thế):* Với bồn cây có thảm cỏ và cây bụi đan xen phức tạp, gộp toàn bộ thành `vegetation`. Chỉ gán `terrain` khi là bãi đất trống phẳng hoặc thảm cỏ rộng không có cây bụi.
  2. *Cách 2 (Bóc tách mặt đất phẳng và thân cây):* Phần cỏ mọc phẳng sát đất gán `terrain`, phần thân/tán cây nhô lên khỏi mặt đất gán `vegetation`, nhưng yêu cầu vẽ bằng Polygon biên mềm để tránh phát sinh mask vụn.
- **Xử lý tạm trong lúc chờ:** Tạm gán theo Cách 2 nhưng ưu tiên làm mịn biên mask; các thành viên cần tự gom và dọn sạch mask vụn trước khi bàn giao.
- **Kết quả:** ✅ [QĐ-006](so-quyet-dinh.md#qđ-006)

## P-007

**Phân loại `person` vs `rider` trong tình huống người đi bộ dắt xe hai bánh**

- **Loại:** Guideline mơ hồ
- **Mục guideline:** §4 — Các cặp class dễ nhầm (`person vs rider`, `motorcycle vs bicycle`)
- **Người phát hiện:** @Khúc Việt Anh · 19/09/2026
- **Link CVAT:** https://cvat.note.transformerlabs.ai/tasks/202/jobs/1659?frame=31 — Người đi bộ dắt bộ xe máy trên lòng đường.
- **Mô tả:** Guideline quy định: `rider` = người đang cưỡi/điều khiển xe hai bánh hoặc phương tiện tương ứng; `person` = người đi bộ/đứng/ngồi không thuộc rider.
  - Trong trường hợp người đang dắt bộ xe đạp hoặc xe máy: Chân người chạm đất bước đi (đặc trưng của `person`), nhưng tay đang cầm ghi-đông điều khiển phương tiện di chuyển.
  - Hai annotator đang có cách hiểu trái ngược nhau: một người gán là `rider` (vì đang điều khiển xe), người kia gán là `person` (vì không ngồi cưỡi trên xe).
- **Các cách hiểu:**
  1. *Cách 1 (Gán `person`):* Tiêu chí phân biệt là tư thế cưỡi/ngồi trên phương tiện (mounted). Nếu người đi bộ chân bước trên mặt đất để đẩy/dắt xe thì tô pixel người là `person`, thân xe gán riêng là `motorcycle`/`bicycle`.
  2. *Cách 2 (Gán `rider`):* Mọi hành vi tương tác vật lý trực tiếp để điều khiển chuyển động của xe (kể cả dắt bộ) đều tính là `rider`.
- **Xử lý tạm trong lúc chờ:** Tạm thống nhất gán `person` cho người dắt xe, phương tiện gán `motorcycle`/`bicycle` riêng; gắn tag `UNCERTAIN_CLASS` tại Frame 31 Job #1659.
- **Kết quả:** ✅ [QĐ-007](so-quyet-dinh.md#qđ-007)

## P-008

**Quy ước hệ tọa độ local và hướng của 3D Cuboid: phân biệt trục local vs global và hướng xe**

- **Loại:** Guideline chưa nói tới
- **Mục guideline:** §4.3 — Hướng / yaw
- **Người phát hiện:** @Vũ Bảo Khánh · 01/10/2026
- **Link CVAT:** 3D Point Cloud Annotation (Task 3D Cuboid)
- **Mô tả:** Guideline §4.3 chỉ nêu: *"Với phương tiện, đặt trục dài của cuboid theo hướng thân xe"*, chưa quy định cụ thể hệ tọa độ local của box và chiều vector hướng (yaw arrow) khi vẽ trên giao diện CVAT-3D:
  - Point cloud gốc mang hệ tọa độ của thiết bị LiDAR/xe thu thập dữ liệu (đây là hệ tọa độ global của scene trong CVAT).
  - Khi tạo 3D Cuboid cho từng ô tô/vật thể, annotator dễ nhầm lẫn giữa trục tọa độ global của scene với trục local của cuboid, dẫn đến đặt sai trục chiều dài/rộng hoặc xoay ngược hướng 180°.
  - Chưa rõ có cần gán nhãn chiếc xe ego đang đi thu thập dữ liệu hay không.
- **Phản hồi từ BTC:**
  > *"trong phần label cuboid các bạn cần lưu ý: point cloud gốc có hệ tọa độ của LiDAR/xe dùng để thu thập dữ liệu. Các trục X, Y, Z các bạn thấy trên scene là hệ tọa độ global của point cloud trong CVAT, không phải hướng local của cuboid mà mình cần vẽ. (Và các bạn không cần label chiếc xe đang đi thu thập dữ liệu :D)*  
  > *Khi vẽ cuboid cho từng ô tô, hãy đặt X local theo chiều dọc thân xe/hướng chính của xe, Y local theo chiều ngang xe, và Z local hướng lên trên theo chiều cao xe.*  
  > *Để dễ quan sát hướng local của cuboid, các bạn bật “Cuboid Orientation” ở góc dưới bên phải màn hình. Dưới đây là một ví dụ minh họa."*
- **Quy tắc chốt:**
  1. **Trục X local:** Đặt theo chiều dọc thân xe / hướng chính tiến tới của xe (front).
  2. **Trục Y local:** Đặt theo chiều ngang thân xe (width).
  3. **Trục Z local:** Hướng lên trên theo chiều cao xe (height).
  4. Bật chế độ **“Cuboid Orientation”** (góc dưới bên phải màn hình CVAT-3D) để kiểm tra trực quan hướng local của box.
  5. **Không** gán nhãn chiếc xe đang đi thu thập dữ liệu (xe ego).
- **Xử lý tạm trong lúc chờ:** Đã có câu trả lời chính thức từ BTC.
- **Kết quả:** ✅ [QĐ-008](so-quyet-dinh.md#qđ-008)

## P-009

**Ngưỡng tối thiểu điểm LiDAR (Min points) để gán vật thể & giới hạn phạm vi khoảng cách (Range cut-off)**

- **Loại:** Guideline chưa nói tới
- **Mục guideline:** §4.2 — Kích thước & §4.4 — Khi vật thể bị che khuất hoặc point cloud thưa
- **Người phát hiện:** @Vũ Bảo Khánh · 01/10/2026
- **Link CVAT:** 3D Point Cloud Annotation (Task 3D Cuboid)
- **Mô tả:** Guideline quy định: *"Khi vật thể bị che khuất hoặc point cloud thưa... không tạo cuboid chỉ dựa trên ảnh 2D nếu không có cơ sở 3D hợp lý trong point cloud"* và *"kiểm tra kỹ các cone xa vì point cloud thường thưa"*. Tuy nhiên tài liệu không đưa ra con số định lượng cụ thể:
  1. Bao nhiêu điểm (points) LiDAR thì được coi là "đủ cơ sở 3D hợp lý" để tạo cuboid (ví dụ $\ge 3$ điểm hay $\ge 5$ điểm)?
  2. Có giới hạn bán kính khoảng cách tối đa (range cut-off) tính từ tâm LiDAR hay không (ví dụ trong bán kính 50m, 70m hay toàn bộ tầm quét)?
  - Thực tế: Có những vật thể ở rất xa (trên 60m) chỉ xuất hiện 1–2 điểm lác đác trong chùm LiDAR nhưng nhìn thấy lờ mờ trên ảnh camera. Người thì cố tạo box theo 2D, người lại bỏ qua dẫn đến tỷ lệ sót/thừa nhãn không đồng nhất giữa các thành viên.
- **Các cách hiểu / Hướng đang cân nhắc:**
  1. *Cách 1 (Ngưỡng điểm tối thiểu):* Chỉ tạo cuboid khi vật thể có tối thiểu $\ge 5$ điểm LiDAR rõ ràng và đối chiếu được hình khối qua camera. Cụm điểm $< 5$ điểm ở xa coi là nhiễu / không đủ độ tin cậy hình học 3D, bỏ qua.
  2. *Cách 2 (Giới hạn khoảng cách kết hợp ngưỡng điểm):* Quy định bán kính tối đa là 50m. Trong bán kính 50m: vật thể có từ $\ge 3$ điểm và xác định được class qua camera thì gán; ngoài 50m thì bỏ qua nếu không rõ ràng.
- **Xử lý tạm trong lúc chờ:** Ưu tiên gán các vật thể có chùm điểm LiDAR rõ khối ($\ge 5$ điểm) và đối chiếu được trên camera; các case nghi ngờ ở xa dưới 3 điểm gắn cờ/ghi lại frame để xin ý kiến BTC/mentor.
- **Kết quả:** 🔴 Mở

## P-010

**Khó phân biệt mặt đường trong 3D Point Cloud để căn đáy cuboid sát mặt đất (Ground Surface Alignment / Object Grounding)**

- **Loại:** Pain point công cụ
- **Mục guideline:** §4.2 — Kích thước & Vị trí (Z-axis Grounding)
- **Người phát hiện:** @Đặng Văn Huy · 04/10/2026
- **Link CVAT:**
  - https://cvat.note.transformerlabs.ai/jobs/4019?frame=12 — Xe ô tô và xe tải trên đoạn đường có độ dốc nhẹ, đáy box bị lơ lửng (floating) hoặc lún dưới mặt đường (submerged) do mật độ điểm mặt đường thưa và không có mặt phẳng tham chiếu.
  - https://cvat.note.transformerlabs.ai/jobs/4021?frame=45 — Xe đỗ ở mép đường dốc nghiêng; annotator phải xoay 3D perspective nhiều góc để ước lượng đáy box bằng mắt thường.
- **Mô tả & Bằng chứng thực tế (Evidence):**
  - *Vấn đề thực tế:* Dữ liệu LiDAR 3D trên CVAT không có phân tách ground/non-ground plane, cũng không có lưới tham chiếu mặt đất. Tại các đoạn đường dốc, mấp mô hoặc ở cự ly xa (>25m), chùm tia LiDAR quét mặt đường rất thưa thớt hoặc bị tán xạ.
  - *Khó khăn thao tác:* Annotator phải liên tục xoay camera 3D quanh đối tượng và chuyển sang các góc chiếu trực giao (Side/Front View) phóng to cực đại để ước lượng xem đáy cuboid đã chạm đất hay chưa. Việc căn chỉnh thủ công trục Z (tọa độ $z$ và chiều cao $h$) chiếm tới **35% - 40% tổng thời gian chỉnh 1 box**.
  - *Hậu quả sai sót:* Căn chỉnh bằng mắt thường có độ dung sai lớn ($\pm 5 - 15\text{ cm}$). Khi Reviewer kiểm tra ở góc nhìn ngang, phát hiện hàng loạt box bị lỗi "floating" (bay trên không) hoặc "penetrating ground" (lún ngập dưới lòng đường). Đây là loại lỗi hình học phổ biến nhất, chiếm **~30% số ca reject/rework** giữa annotator và reviewer.
- **Hướng đang cân nhắc (Đề xuất công cụ giải quyết):**
  1. *Tool ước lượng mặt đường (Ground Plane Estimation):* Áp dụng thuật toán RANSAC mặt phẳng hoặc Patchwork++/CSF để lọc tập điểm ground points, hiển thị lưới tham chiếu hoặc tô màu riêng biệt cho điểm mặt đất trên giao diện 3D.
  2. *Tool tự động "Snap-to-Ground" / Cảnh báo Z-Grounding:* Viết script tự động tính khoảng cách giữa mặt đáy cuboid ($z_{\min} = z - h/2$) với các điểm ground lân cận ($k$-nearest neighbors) trong bán kính đáy box; tự động snap đáy box sát mặt đường hoặc gắn cờ cảnh báo box bay lệch quá $\pm 5\text{ cm}$.
- **Xử lý tạm trong lúc chờ:** Annotator chuyển sang Side View / Front View ở mức zoom lớn, lấy cụm điểm phản xạ thấp nhất của lốp xe làm mốc đáy; reviewer bắt buộc soi kỹ mặt cắt ngang từng phương tiện trước khi duyệt.
- **Kết quả:** 🛠️ Làm tool (Đề xuất xây module kiểm tra Z-grounding & ước lượng mặt đường trong `source-tool/`)

## P-011

**Nhiều lỗi 3D (cuboid lơ lửng, ID đứt, thiếu attribute...) chỉ phát hiện ở khâu Review thủ công gây rework lớn; thiếu pipeline Auto-QA tiền kiểm tra**

- **Loại:** Pain point công cụ
- **Mục guideline:** §4 — Quy chuẩn gán nhãn 3D Cuboid & Quy trình QA/QC
- **Người phát hiện:** @Vũ Bảo Khánh · 04/10/2026
- **Link CVAT:**
  - https://cvat.note.transformerlabs.ai/jobs/4020?frame=25 — Xe di chuyển qua các frame 20–30 bị đứt track ID giữa chừng (ID 12 biến mất ở frame 25 rồi xuất hiện lại với ID 18 ở frame 26); reviewer phải mở từng frame để đối soát và gán lại tracklet.
  - https://cvat.note.transformerlabs.ai/jobs/4022?frame=60 — Box rỗng điểm LiDAR ở xa nhưng không có tag/comment giải trình, kèm theo thiếu attribute bắt buộc (`state`, `occlusion`).
- **Mô tả & Bằng chứng thực tế (Evidence):**
  - *Vấn đề thực tế:* Quy trình hiện tại phụ thuộc hoàn toàn vào việc Reviewer mở từng frame và kiểm tra thủ công bằng mắt trên CVAT. Trong khi đó, hầu hết các lỗi 3D nghiêm trọng đều tuân theo các quy tắc logic / hình học có thể quét tự động bằng code:
    1. *Cuboid lơ lửng / lún đất:* Đáy box không khớp với cao độ mặt đường lân cận.
    2. *Đứt gãy Track ID / Nhảy vị trí phi lý:* Tracklet ID bị ngắt quãng giữa các frame liền kề, hoặc đối tượng "dịch chuyển tức thời" (teleportation / velocity spike) với vận tốc phi thực tế.
    3. *Kích thước dị thường (Dimension Anomaly):* Box có kích thước vi phạm ngưỡng vật lý của class (ví dụ: xe con dài 9m, người đi bộ cao 3m hoặc rộng 2.5m).
    4. *Yaw jitter / Xoay ngược hướng:* Góc xoay yaw bị đảo 180° hoặc rung lắc đột ngột giữa các frame trong khi quỹ đạo xe đang thẳng.
    5. *Box rỗng điểm (Empty Box):* Bounding box chứa 0 điểm hoặc $<3$ điểm LiDAR nhưng không có ghi chú/tag ngoại lệ.
    6. *Thiếu thuộc tính bắt buộc (Missing Attributes):* Bỏ trống các trường `occluded`, `truncated`, `activity`.
  - *Hậu quả & Đo lường:*
    - Reviewer mất trung bình **3–5 phút cho mỗi frame** để rà soát thủ công toàn bộ các yếu tố trên. Một job 100 frame ngốn 5–8 giờ làm việc của reviewer.
    - Việc phát hiện lỗi muộn ở khâu review thủ công gây lãng phí lớn: annotator phải làm lại (rework), tỷ lệ trả job chiếm **25% – 35% tổng thời lượng dự án**, làm chậm tiến độ giao nộp của toàn đội.
- **Hướng đang cân nhắc (Đề xuất công cụ giải quyết — Pre-Review Auto-QA Pipeline):**
  - Xây dựng một **Pipeline QA tự động chạy độc lập trước khi gửi review (Pre-review Automated QA Pipeline)** gồm 4 khối:
    1. *Khối đọc dữ liệu (Data Ingestion):* Đọc file export nhãn (CVAT XML / OpenPCDet / JSON) kết hợp dữ liệu Point Cloud gốc (`.pcd` / `.bin`).
    2. *Khối luật kiểm tra (Rule Engine):* Thực thi bộ luật kiểm tra tự động gồm:
       - *Rule 1 (Dimensions):* Kiểm tra min/max chiều dài, rộng, cao theo bảng phân phối kích thước chuẩn của từng class taxonomy.
       - *Rule 2 (Density):* Đếm điểm point cloud nằm trong box; cảnh báo box rỗng / box thưa dưới ngưỡng quy định.
       - *Rule 3 (Grounding):* Phân tích khoảng cách cao độ Z đáy box so với mặt phẳng đất.
       - *Rule 4 (Tracking Continuity):* Kiểm tra tính liên tục của Track ID qua chuỗi frame, vận tốc dịch chuyển ($\Delta d / \Delta t$), và độ biến thiên góc xoay ($\Delta \text{yaw}$).
       - *Rule 5 (Attributes):* Kiểm tra tính đầy đủ của các thuộc tính bắt buộc.
    3. *Khối lưu trữ & Tính điểm rủi ro (Data Store & Risk Scoring Engine):*
       - Lưu toàn bộ kết quả kiểm tra vào kho dữ liệu có cấu trúc (SQLite / JSON log).
       - Tính điểm rủi ro (Risk Score: Thấp / Trung bình / Cao) cho từng Job, từng Frame và từng Object dựa trên trọng số lỗi vi phạm.
    4. *Khối xuất báo cáo (QA Dashboard & Priority Report):*
       - Xuất báo cáo trực quan (HTML Dashboard / CSV summary) xếp hạng các frame có điểm rủi ro cao nhất (High Risk Frames).
       - Reviewer và annotator mở trực tiếp danh sách cảnh báo này để ưu tiên kiểm tra và sửa ngay các frame đỏ/vàng, giảm thiểu 70% thời gian duyệt các frame sạch.
- **Xử lý tạm trong lúc chờ:** Reviewer tự tạo checklist kiểm tra bằng mắt kết hợp filter CVAT; yêu cầu annotator tự rà soát Track ID qua thanh Timeline trước khi submit.
- **Kết quả:** 🛠️ Làm tool (Đề xuất xây pipeline `qa-pre-review-pipeline` trong `source-tool/`)

## P-012

**Quá tải thị giác và sót/lặp kiểm tra khi frame có mật độ box dày đặc (Scene Clutter, Review Fatigue & Thiếu trạng thái xác minh từng box)**

- **Loại:** Pain point công cụ
- **Mục guideline:** §5 — Thao tác khuyến nghị trên CVAT & Quy trình kiểm tra chất lượng
- **Người phát hiện:** @Khúc Việt Anh · 04/10/2026
- **Link CVAT:**
  - https://cvat.note.transformerlabs.ai/jobs/4022?frame=42 — Cảnh ngã tư đô thị mật độ cao với hơn 50 cuboids (hỗn hợp xe hơi, xe tải, xe máy, người đi bộ và dải cọc tiêu traffic cone); các box hiển thị chồng chéo trong không gian 3D.
- **Mô tả & Bằng chứng thực tế (Evidence):**
  - *Vấn đề thực tế:* Trong các cảnh giao thông phức tạp (ùn tắc, ngã tư), số lượng cuboid trên một frame rất lớn (từ 40 đến 80+ đối tượng). Mặc định CVAT hiển thị tất cả các bounding box dạng wireframe cùng lúc trên không gian 3D.
  - *Hậu quả & Đo lường:*
    - *Hiện tượng Clutter (Che khuất tầm nhìn):* Các box lớn phía trước che lấp hoàn toàn các box nhỏ (pedestrian, traffic cone, barrier) nằm ở phía sau hoặc xen kẽ giữa các làn.
    - *Hiện tượng Cognitive Fatigue & Bỏ sót (Missed Objects):* Không có dấu hiệu phân biệt giữa box "đã được kiểm tra kỹ" và box "chưa kiểm tra", dẫn đến tỷ lệ bỏ sót lỗi hình khối/yaw ở các box khuất lên tới **15% – 20%**.
    - *Lãng phí thời gian do kiểm tra trùng lặp (Redundant Re-checking):* Reviewer click kiểm tra đi kiểm tra lại một box nhiều lần vì không nhớ mình đã duyệt qua nó chưa. Ước tính mất thêm **25% – 30% thời gian review** cho mỗi frame đông đúc chỉ để định vị đối tượng.
- **Hướng đang cân nhắc (Đề xuất công cụ giải quyết):**
  1. *Cơ chế Verification State Tracking (Đánh dấu tiến độ review từng box):* Bổ sung thuộc tính tạm hoặc script đánh dấu trạng thái `status: verified` / `needs_fix`. Hộp đã kiểm tra được làm mờ (dim/lower opacity) hoặc chuyển màu xanh lá, giúp các box chưa duyệt nổi bật rõ trên màn hình.
  2. *Chế độ Solo / Focus Inspector Mode:* Script hoặc tiện ích hỗ trợ phím tắt (Next / Prev Object) tự động cô lập (isolate) duy nhất 1 box và cụm điểm LiDAR của nó, đồng thời căn camera vào tâm box để annotator/reviewer duyệt tuần tự từ đầu đến cuối danh sách mà không bị phân tâm bởi các box khác.
  3. *Bộ lọc theo cự ly / lớp (Depth Slicing & Class Grouping):* Cho phép ẩn/hiện box theo các lát cắt cự ly (ví dụ: $<20\text{m}$, $20–50\text{m}$, $>50\text{m}$) để kiểm tra từng tầng không gian một cách khoa học.
- **Xử lý tạm trong lúc chờ:** Sử dụng bảng Object List bên phải CVAT để ẩn/hiện thủ công từng nhãn; tuy nhiên thao tác này tốn nhiều lượt click chuột và dễ gây nhầm lẫn.
- **Kết quả:** 🛠️ Làm tool (Đề xuất phát triển tiện ích hỗ trợ review tuần tự và quản lý trạng thái kiểm tra)

---

## Mẫu để copy

```markdown
## P-NNN

**Tóm tắt một dòng**

- **Loại:** Guideline chưa nói tới | Guideline mơ hồ | Guideline mâu thuẫn | Pain point công cụ
- **Mục guideline:** §
- **Người phát hiện:** @ · dd/mm/yyyy
- **Link CVAT:** (bỏ trống nếu không có)
  - https://…/tasks/<id>/jobs/<id>?frame=<n> — frame này có gì
- **Mô tả:**
- **Các cách hiểu:** (với pain point công cụ thì ghi **Hướng đang cân nhắc:**)
  1.
  2.
- **Xử lý tạm trong lúc chờ:**
- **Kết quả:** 🔴 Mở
```

Nhớ thêm một dòng vào bảng **Danh sách** ở đầu file.
