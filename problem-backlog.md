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
