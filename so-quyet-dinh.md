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
| [QĐ-004](#qđ-004) | Đồng nhất gán nhãn `area/alternative`: bắt buộc vẽ cho phần đường ngược chiều / nhánh phụ | 20/09/2026 | [P-004](problem-backlog.md#p-004) | Hiệu lực |
| [QĐ-005](#qđ-005) | Ram dốc hạ cốt vỉa hè (Curb Cut / Driveway Ramp) gán nhãn `sidewalk` | 20/09/2026 | [P-005](problem-backlog.md#p-005) | Hiệu lực |
| [QĐ-006](#qđ-006) | Phân định `vegetation` vs `terrain`: gộp bồn cây tán phủ dày, phân tầng nền cho dải cỏ lớn | 20/09/2026 | [P-006](problem-backlog.md#p-006) | Hiệu lực |
| [QĐ-007](#qđ-007) | Người đi bộ dắt xe hai bánh gán nhãn `person`, xe gán class phương tiện riêng | 20/09/2026 | [P-007](problem-backlog.md#p-007) | Hiệu lực |

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

## QĐ-004

**Đồng nhất gán nhãn `area/alternative`: bắt buộc vẽ cho phần đường xe chạy ngược chiều hoặc nhánh phụ**

- **Ngày:** 20/09/2026
- **Người tham gia:** @Khúc Việt Anh (chốt), @Đặng Văn Huy, @Nguyễn Văn Hân, @Nhữ Đình Chiến, @Vũ Bảo Khánh
- **Xuất phát từ:** [P-004](problem-backlog.md#p-004)
- **Bối cảnh:** Sự không đồng nhất giữa các job: Job #1442 và #1445 vẽ `area/alternative` cho làn đường đối diện / ngã ba, còn Job #1443 và #1444 chỉ vẽ `area/drivable` mà bỏ qua chiều ngược lại.
- **Các phương án đã cân nhắc:**
  1. *Chỉ vẽ duy nhất `area/drivable` và bỏ qua phần đường đối diện* — tiết kiệm thao tác nhưng làm mất dữ liệu không gian lưu thông mở rộng, sai lệch chuẩn BDD100K. Loại.
  2. *Bắt buộc vẽ `area/alternative` cho phần đường ngược chiều và nhánh phụ (theo chuẩn BDD100K)* — đảm bảo dữ liệu toàn diện cho hệ thống tự lái nhận diện không gian di chuyển dự phòng. **Chọn.**
- **Quyết định:** 
  1. Mọi phần mặt đường xe cơ giới có thể di chuyển được thuộc làn đối diện (phía bên kia vạch phân cách nét đứt hoặc vạch vàng đôi) hoặc nhánh rẽ phụ bắt buộc phải gán polygon `area/alternative`.
  2. Trường hợp đường có dải phân cách cứng (con lươn bê tông, rào chắn tách biệt hoàn toàn hai chiều) thì phần đường phía bên kia dải phân cách cứng không vẽ polygon.
- **Việc phải làm theo:**
  - [x] Rà soát và bổ sung các polygon `area/alternative` cho Job #1443 (@Nguyễn Văn Hân) và Job #1444 (@Nhữ Đình Chiến)
- **Trạng thái:** Hiệu lực

## QĐ-005

**Ram dốc hạ cốt vỉa hè (Curb Cut / Driveway Ramp) gán nhãn `sidewalk`**

- **Ngày:** 20/09/2026
- **Người tham gia:** @Khúc Việt Anh (chốt), @Đặng Văn Huy, @Nguyễn Văn Hân, @Nhữ Đình Chiến, @Vũ Bảo Khánh
- **Xuất phát từ:** [P-005](problem-backlog.md#p-005)
- **Bối cảnh:** Vỉa hè vát nghiêng hạ cốt xuống bằng mặt đường (lối dắt xe vào nhà, lối lên vỉa hè, ram dốc người khuyết tật). Có sự không đồng nhất giữa việc gán `road` hay `sidewalk`.
- **Các phương án đã cân nhắc:**
  1. *Gán `road` cho toàn bộ phần mặt dốc bê tông* — làm ranh giới vỉa hè bị thụt lõm nham nhở, khó thống nhất điểm kết thúc dốc, xe tự lái có thể hiểu nhầm là lòng đường xe chạy. Loại.
  2. *Gán toàn bộ phần ram dốc hạ cốt là `sidewalk` (chuẩn Cityscapes)* — giữ đường viền vỉa hè thẳng, liên tục theo mép lòng đường nhựa, giúp nhận diện rõ ranh giới an toàn cho người đi bộ. **Chọn.**
- **Quyết định:** 
  1. Toàn bộ ram dốc vát hạ cốt của vỉa hè (curb cut / driveway ramp) được gán nhãn `sidewalk`.
  2. Ranh giới giữa `road` và `sidewalk` bám theo đường chân mép dốc tiếp giáp với mặt phẳng lòng đường xe chạy. Chỉ gán `road` khi là lối rẽ vào ngõ/đường phụ công cộng có lòng đường riêng biệt.
- **Việc phải làm theo:**
  - [x] Tháo tag `UNCERTAIN_CLASS` tại Frame 12 Job #1658 và chuẩn hóa thành `sidewalk` (@Đặng Văn Huy)
- **Trạng thái:** Hiệu lực

## QĐ-006

**Phân định `vegetation` vs `terrain`: gộp bồn cây có tán phủ dày, phân tầng nền cho dải cỏ lớn**

- **Ngày:** 20/09/2026
- **Người tham gia:** @Khúc Việt Anh (chốt), @Đặng Văn Huy, @Nguyễn Văn Hân, @Nhữ Đình Chiến, @Vũ Bảo Khánh
- **Xuất phát từ:** [P-006](problem-backlog.md#p-006)
- **Bối cảnh:** Cỏ thấp mọc xen kẽ cây bụi trong bồn cây hoặc dải phân cách. Bóc tách nhỏ lẻ bằng cọ Brush gây ra hàng chục mask vụn li ti và vi phạm Rule 01 (chồng lấn pixel).
- **Các phương án đã cân nhắc:**
  1. *Bóc tách chi tiết từng cụm cỏ sát đất thành `terrain` bằng Brush* — tốn cực nhiều thời gian, phát sinh mask vụn li ti (<10 pixel) và đè lem viền. Loại.
  2. *Quy tắc phân cấp theo vùng chiếm ưu thế & cấu trúc 2.5D* — gộp các bồn cây rậm rạp; với bãi cỏ lớn thì vẽ nền phẳng `terrain` trước rồi vẽ tán cây `vegetation` lên trên bằng polygon/brush mịn, cấm để mask vụn. **Chọn.**
- **Quyết định:**
  1. Đối với bồn hoa, dải phân cách hẹp hoặc gốc cây có mật độ cành lá/bụi cây che phủ trên 60% diện tích: Gộp toàn bộ vùng đó thành `vegetation`.
  2. Đối với bãi cỏ rộng, công viên hoặc dải phân cách lớn có phân tầng rõ rệt: Phần mặt đất/thảm cỏ phẳng sát đất gán `terrain`; phần thân cây, cành lá nhô cao gán `vegetation`.
  3. Quy tắc kỹ thuật: Tuyệt đối không dùng cọ Brush chấm vụn các đốm pixel dưới 10 pixel; vẽ phủ nền phẳng trước, sau đó chỉnh biên class cây phía trên để đảm bảo Rule 01 (không chồng lấn).
- **Việc phải làm theo:**
  - [x] Làm sạch và gộp các mask cỏ vụn tại Frame 62 Job #1660 và các frame tương tự (@Nhữ Đình Chiến)
- **Trạng thái:** Hiệu lực

## QĐ-007

**Người đi bộ dắt xe hai bánh gán nhãn `person`, xe gán class phương tiện riêng**

- **Ngày:** 20/09/2026
- **Người tham gia:** @Khúc Việt Anh (chốt), @Đặng Văn Huy, @Nguyễn Văn Hân, @Nhữ Đình Chiến, @Vũ Bảo Khánh
- **Xuất phát từ:** [P-007](problem-backlog.md#p-007)
- **Bối cảnh:** Trường hợp người đi bộ dắt bộ xe đạp hoặc xe máy trên lòng đường (chân chạm đất bước đi, tay cầm ghi-đông điều khiển).
- **Các phương án đã cân nhắc:**
  1. *Gán `rider` cho người dắt xe* — không phản ánh đúng cơ chế vận động và tốc độ di chuyển (người dắt bộ có động học giống người đi bộ), dễ gây nhiễu nhãn khi người chỉ đứng tựa xe. Loại.
  2. *Gán `person` cho người dắt xe, phương tiện gán riêng theo đúng loại (theo chuẩn Cityscapes & BDD100K)* — chuẩn xác về ngữ nghĩa; `rider` chỉ dành cho người đang ngồi/cưỡi trên yên phương tiện. **Chọn.**
- **Quyết định:**
  1. Mask người đi bộ dắt/đẩy xe hai bánh (chân tiếp đất bước đi, không ngồi trên yên) được gán nhãn `person`.
  2. Phương tiện được dắt kèm gán nhãn riêng theo đúng chủng loại (`motorcycle` hoặc `bicycle`).
  3. Nhãn `rider` chỉ áp dụng khi người đó đang ngồi/cưỡi trên xe (kể cả trường hợp dừng đèn đỏ chống chân).
- **Việc phải làm theo:**
  - [x] Tháo tag `UNCERTAIN_CLASS` tại Frame 31 Job #1659 và xác nhận gán `person` cho người dắt xe (@Nguyễn Văn Hân)
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
