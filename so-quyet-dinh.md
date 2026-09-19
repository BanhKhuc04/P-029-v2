# Sổ quyết định

Ghi lại những gì đội đã chốt, và **vì sao**. Ba tuần sau không ai còn nhớ vì sao box lại vẽ
kiểu này — người mới vào đội lại càng không.

**Quyết định đã ghi thì không sửa nội dung.** Đổi ý thì ghi một quyết định mới, và chuyển
trạng thái quyết định cũ thành *Bị thay bởi QĐ-xxx*. Nhờ vậy vẫn truy được vì sao các job
cũ được gán theo cách cũ.

## Danh sách

| Mã | Quyết định | Ngày | Xuất phát từ | Trạng thái |
|---|---|---|---|---|
| [QĐ-001](#qđ-001) | Vạch kẻ đường đi bộ (crosswalk): chỉ kẻ các đường ngang giới hạn biên | 18/09/2026 | [P-001](problem-backlog.md#p-001) | Hiệu lực |
| [QĐ-002](#qđ-002) | Polygon Drivable Area gộp các làn cùng chiều và bao trùm vật thể trên đường | 18/09/2026 | [P-002](problem-backlog.md#p-002) | Hiệu lực |
| [QĐ-003](#qđ-003) | Vạch xương cá (chevron): không vẽ Polygon Drivable, chỉ kẻ Polyline đường biên | 18/09/2026 | [P-003](problem-backlog.md#p-003) | Hiệu lực |

**Trạng thái:** Hiệu lực · Bị thay bởi QĐ-xxx · Huỷ (ghi lý do)

---

## QĐ-001

**Vạch kẻ đường đi bộ (crosswalk): chỉ kẻ các đường ngang giới hạn biên**

- **Ngày:** 18/09/2026
- **Người tham gia:** @Đặng Văn Huy (chốt), @Khúc Việt Anh, @Nguyễn Văn Hân, @Nhữ Đình Chiến, @Vũ Bảo Khánh
- **Xuất phát từ:** [P-001](problem-backlog.md#p-001)
- **Bối cảnh:** Vạch sang đường cho người đi bộ dạng sọc (zebra) chưa rõ quy cách vẽ polyline, dẫn đến Job #1444 kẻ từng vạch sọc dọc còn Job #1445 chỉ kẻ đường ngang giới hạn vùng.
- **Các phương án đã cân nhắc:**
  1. *Kẻ dọc theo từng vạch sọc trắng* — chi tiết nhưng tốn quá nhiều thời gian gán nhãn, dễ gây sai lệch vị trí polyline khi vạch bị mờ. Loại.
  2. *Chỉ kẻ các đường ngang (transverse lines) giới hạn biên vùng đi bộ* — nhanh gọn, thể hiện rõ ranh giới khu vực ưu tiên người đi bộ trên mặt đường. **Chọn.**
- **Quyết định:** Khi gặp vạch sang đường cho người đi bộ, chỉ dùng Polyline `lane/crosswalk` kẻ 2 đường ngang giới hạn mép trên và mép dưới của khu vực đi bộ. Không kẻ chi tiết từng vạch sọc trắng bên trong.
- **Việc phải làm theo:**
  - [ ] Rà lại Frame 54 (Job #1444) để xóa các polyline sọc dọc thừa, chỉ giữ đường ngang biên (@Nhữ Đình Chiến)
- **Trạng thái:** Hiệu lực

## QĐ-002

**Polygon Drivable Area gộp các làn cùng chiều và bao trùm vật thể trên đường**

- **Ngày:** 18/09/2026
- **Người tham gia:** @Đặng Văn Huy (chốt), @Khúc Việt Anh, @Nguyễn Văn Hân, @Nhữ Đình Chiến, @Vũ Bảo Khánh
- **Xuất phát từ:** [P-002](problem-backlog.md#p-002)
- **Bối cảnh:** Chưa rõ quy cách vẽ Polygon cho Drivable Area: có tách từng làn đơn lẻ không, và đường polygon có được vẽ bao trùm xuyên qua ô tô/người trên mặt đường không.
- **Các phương án đã cân nhắc:**
  1. *Tách từng làn đơn lẻ & khoét/né viền quanh từng xe* — polygon cực kỳ phức tạp, nhiều đỉnh, dễ lỗi tự cắt (self-intersection) và mất nhiều thời gian. Loại.
  2. *Gộp các làn cùng chiều & bao trùm vật thể (theo chuẩn BDD100K)* — mặt đường là nền (background), xe/người là đối tượng độc lập (foreground) đã có bounding box riêng; polygon bám sát biên mép đường/vỉa hè đi thẳng qua đáy xe. **Chọn.**
- **Quyết định:** 
  1. Gộp toàn bộ các làn xe cùng chiều mà xe ego có thể đi thành 1 polygon `area/drivable`. Phần đường ngược chiều (bên kia vạch vàng kép) vẽ polygon `area/alternative`.
  2. Polygon `area/drivable` được bao trùm xuyên qua các vật thể (ô tô, xe máy, người) trên đường, không lượn viền khoét quanh vật thể.
  3. Riêng Polyline vạch kẻ làn (`lane/*`) nếu bị xe che khuất thì phải ngắt theo §4.2.
- **Việc phải làm theo:**
  - [x] Thống nhất áp dụng cho toàn bộ 4 job khi vẽ polygon drivable (@Cả đội)
- **Trạng thái:** Hiệu lực

## QĐ-003

**Vạch xương cá (chevron): không vẽ Polygon Drivable, chỉ kẻ Polyline đường biên**

- **Ngày:** 18/09/2026
- **Người tham gia:** @Đặng Văn Huy (chốt), @Khúc Việt Anh, @Nguyễn Văn Hân, @Nhữ Đình Chiến, @Vũ Bảo Khánh
- **Xuất phát từ:** [P-003](problem-backlog.md#p-003)
- **Bối cảnh:** Vạch xương cá (đảo mềm phân tách luồng xe) trên cao tốc chưa có quy định cho Polygon và Polyline.
- **Các phương án đã cân nhắc:**
  1. *Vẽ Polygon `area/alternative` & kẻ từng vạch chéo* — sai bản chất phân luồng an toàn giao thông và tốn công vẽ từng nét. Loại.
  2. *Không vẽ Polygon (non-drivable) & chỉ kẻ Polyline viền ranh giới bao quanh* — chuẩn theo luật giao thông (vùng cấm đè vạch), tiết kiệm thời gian. **Chọn.**
- **Quyết định:**
  1. Về Drivable Area: Không vẽ polygon lên vùng vạch xương cá (xem là non-drivable, biên polygon `area/drivable` dừng lại ở mép ngoài của vạch biên).
  2. Về Lane Marking: Chỉ kẻ Polyline bám theo đường biên bao quanh vùng xương cá (dùng `lane/single white` hoặc `lane/double white` tùy thực tế). Không kẻ các vạch sơn chéo bên trong.
- **Việc phải làm theo:**
  - [x] Bỏ tag `UNCERTAIN_BOUNDARY` tại Frame 0 Job #1442 sau khi chuẩn hóa theo quyết định (@Khúc Việt Anh)
- **Trạng thái:** Hiệu lực

---

## Mẫu để copy

```markdown
## QĐ-NNN

**Quyết định trong một dòng**

- **Ngày:** dd/mm/yyyy
- **Người tham gia:** @ (chốt), @, @
- **Xuất phát từ:** [P-NNN](problem-backlog.md#p-nnn) | Họp tuần NN | …
- **Bối cảnh:** vì sao phải quyết định
- **Các phương án đã cân nhắc:**
  1. *Phương án* — ưu / nhược. Loại hoặc **Chọn.**
  2. *Phương án* — ưu / nhược. Loại hoặc **Chọn.**
- **Quyết định:** đủ rõ để người không dự họp vẫn làm đúng
- **Việc phải làm theo:**
  - [ ] việc (@người phụ trách)
- **Trạng thái:** Hiệu lực
```

Nhớ thêm một dòng vào bảng **Danh sách** ở đầu file, và đóng mục P-xxx tương ứng trong backlog.
