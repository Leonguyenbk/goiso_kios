# Hệ thống bốc số & gọi số một cửa — Chi nhánh khu vực Ea Kar

Văn phòng Đăng ký đất đai — Chi nhánh khu vực Ea Kar.

Gồm 3 phần chạy quanh **một máy chủ Flask + SQLite** (`hethong_goiso.db`):

| Phần | Vị trí | Công nghệ | Mở tại |
|---|---|---|---|
| **Máy chủ** | `server/` | Flask + SQLite + SSE | `http://<ip-máy-chủ>:5000` |
| **Máy bốc số** (kiosk cảm ứng) | `kiosk/` | CustomTkinter + Pillow + in nhiệt 80mm | chạy trực tiếp trên máy đặt ở sảnh |
| **Máy gọi số** (bàn cán bộ) | trình duyệt | trang web Tailwind | `…:5000/counter` |
| **Màn hình hiển thị** (TV sảnh) | trình duyệt | trang web + đọc tiếng Việt (Web Speech) | `…:5000/display` |
| **Quản trị** | trình duyệt | trang web | `…:5000/admin` |

Realtime giữa các phần dùng **SSE** (`/api/stream`) — không cần F5.

---

## 1. Cài đặt & chạy máy chủ

Yêu cầu: Python 3.10+.

```bat
:: Windows — nhấp đúp hoặc chạy trong CMD
run_server.bat
```

Hoặc thủ công:

```bat
cd server
python -m pip install -r requirements.txt
python app.py
```

Biến môi trường tuỳ chọn:

- `GOISO_PORT` — cổng (mặc định `5000`)
- `GOISO_DB` — đường dẫn file `.db` khác
- `GOISO_SECRET` — khoá phiên Flask (nên đặt khi triển khai thật)
- `GOISO_DEBUG=1` — bật chế độ debug

Máy chủ tự tạo/di trú bảng khi khởi động (thêm 2 cột `time_issue`, `time_done`
vào bảng `queue` — **không đụng dữ liệu cũ**).

### Lệnh quản lý (`server/manage.py`)

```bat
cd server
python manage.py set-admin-pw MatKhauMoi   :: đặt lại mật khẩu trang /admin
python manage.py reset-today                :: xoá toàn bộ số đã cấp trong ngày
python manage.py show-config                :: xem cấu hình hiện tại
python manage.py init                       :: chỉ tạo/di trú bảng
```

> File `hethong_goiso.db` sẵn có đã chứa mật khẩu quản trị cũ. Chạy
> `python manage.py set-admin-pw <mật khẩu>` **một lần** để đặt mật khẩu bạn biết.
> (Trên CSDL mới hoàn toàn, mật khẩu mặc định là `admin123`.)

---

## 2. Máy bốc số (kiosk)

```bat
run_kiosk.bat
```

Hoặc:

```bat
cd kiosk
python -m pip install -r requirements.txt
python kiosk.py
```

Cấu hình tại `kiosk/config.json`:

| Khoá | Ý nghĩa |
|---|---|
| `server_url` | địa chỉ máy chủ, ví dụ `http://192.168.1.10:5000` |
| `printer_name` | tên máy in nhiệt trong Windows; để `""` = máy in mặc định |
| `paper_width_mm` | `80` hoặc `58` |
| `preview_only` | `true` = chỉ hiện cửa sổ xem trước, không in (dùng khi chưa nối máy in) |
| `fullscreen` | `true` = toàn màn hình |
| `columns` | số cột lưới nút dịch vụ |
| `confirm_seconds` | thời gian hiện màn hình xác nhận số |

Phím tắt: `F11` bật/tắt toàn màn hình · `Ctrl+Shift+Q` thoát.

Kiosk tự động:

- Ẩn dịch vụ đã tắt / đã hết lượt trong ngày.
- Chặn lấy số ngoài khung giờ (theo cấu hình `lock_time_enabled` + `time_slots`).
- Hiện thông báo khi mất kết nối máy chủ và tự kết nối lại.

Nếu thiếu `pywin32` hoặc bật `preview_only`, phiếu sẽ hiện ở **cửa sổ xem trước**
thay vì in ra giấy.

---

## 3. Máy gọi số (bàn cán bộ) — `/counter`

Mở `http://<ip-máy-chủ>:5000/counter` trên máy tính mỗi quầy.

1. Chọn **quầy** + nhập **tên cán bộ** → *Vào ca*. (Ghi nhớ trên máy đó,
   lần sau vào thẳng.)
2. Thao tác:
   - **GỌI TIẾP** (phím `Space`) — kết thúc số đang phục vụ và gọi số kế tiếp.
   - **Gọi lại** (`R`) — phát lại thông báo số hiện tại lên màn hình + loa.
   - **Hoàn thành** (`D`) — đánh dấu xong (không gọi số mới).
   - **Vắng** — đánh dấu khách không có mặt.
   - **Tạm dừng / Tiếp tục** — quầy nghỉ tạm.
   - **Gọi số cụ thể** — nhập `A-25` để gọi đúng số đó.
3. Bảng phải: số đang chờ của quầy, đã xử lý, hàng chờ chi tiết, lịch sử.

Mỗi lần gọi/gọi lại sẽ đẩy sự kiện tới **mọi màn hình hiển thị** đang mở.

---

## 4. Màn hình hiển thị — `/display`

Mở toàn màn hình trên TV/đầu phát ở sảnh. Lần đầu **chạm/nhấn phím bất kỳ**
để bật âm thanh + toàn màn hình (chính sách trình duyệt).

Bố cục:

```
┌─────────────────────────────────────────────────────────────┐
│ [logo] VĂN PHÒNG ĐĂNG KÝ ĐẤT ĐAI            07:45:27         │
│        CHI NHÁNH KHU VỰC EA KAR             Thứ Ba, 8/9/2026 │
├──────────────────────────┬──────────────────────────────────┤
│  MỜI QUÝ KHÁCH            │  QUẦY 1  ● Đang phục vụ           │
│                          │  A-002  Trả kết quả              │
│      A-002               │  QUẦY 2  ● Đang phục vụ           │
│   xin mời đến             │  B-001  Biến động đất đai        │
│     QUẦY 1               │  QUẦY 3 … QUẦY 6                  │
│  TRẢ KẾT QUẢ …           │  (số hiện tại mỗi quầy, cán bộ)   │
├──────────────────────────┴──────────────────────────────────┤
│ ĐÃ GỌI GẦN ĐÂY  A-001›Q1  A-002›Q1  B-001›Q2 …               │
├─────────────────────────────────────────────────────────────┤
│ ĐANG CHỜ  A:1  B:1  D:0  E:0        Tổng lượt hôm nay: 5     │
└─────────────────────────────────────────────────────────────┘
```

- Khi có lượt gọi: ô **spotlight** bên trái đổi sang số mới (hiệu ứng trượt),
  thẻ quầy tương ứng **nhấp nháy**, phát **chuông** rồi **đọc tiếng Việt**
  (lặp 2 lần): *"Mời số A, không không hai, đến quầy số một"*.
- Cần cài sẵn **giọng tiếng Việt của Windows** (Cài đặt → Thời gian & ngôn ngữ →
  Giọng nói → thêm giọng *Tiếng Việt (Microsoft An / HoaiMy / NamMinh)*).
  Không có giọng Việt thì chỉ có chuông, không đọc.

Biến thể:

- `/display?nocursor=1` — ẩn con trỏ chuột.
- `/display?counters=1,3,5` — chỉ hiện các quầy chỉ định.
- `/display/simple` — chế độ **một số cực lớn** (màn hình nhỏ / phụ).

---

## 5. Trang quản trị — `/admin`

Đăng nhập bằng mật khẩu quản trị (xem mục 1). Các thẻ:

- **Dịch vụ** — mã (A, B…), tên đầy đủ, tên rút gọn (hiển thị trên thẻ quầy),
  màu, giới hạn số/ngày, bật/tắt.
- **Quầy** — tên quầy, mã dịch vụ phục vụ (nhiều mã cách nhau bằng dấu phẩy,
  ví dụ `A,B`), cán bộ mặc định, thứ tự, bật/tắt.
- **Cấu hình chung** — tên cơ quan/chi nhánh, link QR, khoá theo giờ + khung giờ,
  tốc độ/độ lặp giọng đọc, mẫu câu đọc, thời gian giữ spotlight, đổi mật khẩu.
- **Thống kê** — hôm nay theo dịch vụ, thời gian chờ trung bình, lượt khách 30 ngày,
  nút **Reset toàn bộ số hôm nay**.

Nhấn **Lưu cấu hình** để áp dụng (đẩy ngay tới các màn hình đang mở).

---

## Sơ đồ triển khai gợi ý

```
                 ┌───────────────┐
                 │  MÁY CHỦ      │  server/app.py  (LAN, cổng 5000)
                 │  Flask+SQLite │
                 └───┬───┬───┬───┘
        SSE + REST   │   │   │
      ┌──────────────┘   │   └───────────────┐
┌─────┴──────┐   ┌───────┴────────┐   ┌──────┴───────┐
│ KIOSK      │   │ 6 × MÁY GỌI SỐ │   │ TV HIỂN THỊ  │
│ bốc số     │   │ /counter       │   │ /display     │
│ (CustomTk) │   │ (trình duyệt)  │   │ (trình duyệt)│
└────────────┘   └────────────────┘   └──────────────┘
```

- Đặt **cổng tường lửa 5000** cho phép LAN.
- Máy gọi số & TV chỉ cần trình duyệt (Chrome/Edge), trỏ tới IP máy chủ.
- Kiosk cần Python + máy in nhiệt.

## Ghi chú kỹ thuật

- Máy chủ dùng server phát triển của Flask (`threaded=True`) — đủ cho một chi nhánh
  (vài chục kết nối). Muốn chắc chắn hơn có thể chạy sau `waitress`
  (`waitress-serve --threads=8 --call app:create_app` — cần bọc thêm factory)
  hoặc để nguyên nếu tải nhẹ.
- Số thứ tự đánh theo **từng mã dịch vụ, theo ngày** (`A-001`, `A-002`, `B-001`…),
  tự bắt đầu lại từ 1 mỗi ngày.
- Toàn bộ trạng thái nằm trong `hethong_goiso.db` — sao lưu file này là đủ.
