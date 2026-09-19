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
| [P-004](#p-004) | Chưa đồng nhất gán nhãn `area/alternative` giữa các job | Guideline mơ hồ | §2, §4.1 | 🗣️ Đang bàn | — |
| [P-005](#p-005) | Ranh giới `road` vs `sidewalk` tại các đoạn hạ vỉa hè / lối xe ra vào (curb cut / ramp) | Guideline mơ hồ | §4 (road vs sidewalk) | 🗣️ Đang bàn | — |
| [P-006](#p-006) | Phân định `vegetation` vs `terrain` tại thảm cỏ thấp xen kẽ gốc cây và bồn cây | Guideline mơ hồ | §4 (vegetation vs terrain) | 🗣️ Đang bàn | — |
| [P-007](#p-007) | Phân loại `person` vs `rider` trong tình huống người đi bộ dắt xe hai bánh | Guideline mơ hồ | §4 (person vs rider) | 🗣️ Đang bàn | — |

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
- **Kết quả:** 🗣️ Đang bàn

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
- **Kết quả:** 🗣️ Đang bàn

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
- **Kết quả:** 🗣️ Đang bàn

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
- **Kết quả:** 🗣️ Đang bàn

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
