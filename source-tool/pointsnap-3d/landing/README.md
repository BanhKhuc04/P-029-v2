# Landing page PointSnap 3D

Trang giới thiệu tĩnh (HTML / CSS / JS, không cần build). Cảnh 3D dùng Three.js nạp từ CDN.

## Sửa ở đâu

| Muốn sửa | File |
|---|---|
| Chữ, link, thứ tự section | `index.html` |
| Màu, font, khoảng cách, giao diện sáng / tối (token ở đầu file) | `styles.css` |
| Danh sách luật chạy ngang, logo công nghệ, 8 thẻ tính năng, thành viên đội ngũ, lệnh terminal | `main.js` (các mảng `RULES`, `LOGOS`, `FEATS`, `TEAM`, `TERM`) |
| Cảnh point cloud ở hero, mô hình xe VF8 | `scenes.js` |
| Ảnh giao diện, ảnh thành viên | `assets/` (thay file cùng tên là xong) |

## Chạy trên máy

`pointsnap ui` (cài bằng `pip install -e .`) tự phục vụ trang này ở `http://127.0.0.1:8765/`. Khi chạy trong PointSnap,
các nút **Mở PointSnap** dẫn vào ứng dụng ở `/app` và phím Enter cũng vào; mở từ nơi khác (Vercel, `http.server`) thì các
nút đó thành **Hướng dẫn cài đặt**. Trang không tải gì từ mạng ngoài: font IBM Plex lấy ở `/static/fonts/` của PointSnap,
Three.js r160 nằm trong `vendor/three/` (giấy phép MIT, `vendor/three/LICENSE`).

Chỉ xem trang tĩnh, không cần PointSnap:

```bash
python -m http.server 8790 --directory source-tool/pointsnap-3d/landing
```

Mở http://localhost:8790 (cách này thiếu font IBM Plex vì font nằm ở `pointsnap/web/static/fonts/`). Không mở thẳng
`index.html` bằng nhấp đúp — trình duyệt chặn module JS khi mở từ ổ đĩa.

## Đưa lên mạng (Vercel)

Link: https://pointsnap-3d.vercel.app (project `pointsnap-3d`, tài khoản Vercel của Việt Anh).

Lần đầu trên máy mới: `npx vercel login`. Mỗi lần sửa xong, trong PowerShell ở thư mục `landing/`:

```powershell
.\deploy.ps1
```

Link giữ nguyên. Script chép thêm font từ `pointsnap/web/static/fonts/` vào `static/fonts/` của bản deploy. Script deploy từ một bản sao ngoài git, vì Vercel gói Hobby chặn deploy khi commit
gần nhất của repo là của thành viên khác (lỗi "commit author doesn't have permission"). Vercel phát trang qua CDN nên vài trăm người vào cùng lúc không ảnh hưởng.
`vercel.json` đặt cache: ảnh 1 ngày, JS / CSS luôn kiểm tra bản mới để chỗ sửa hiện ngay.
