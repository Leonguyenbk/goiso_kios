# Hệ thống bốc số & gọi số một cửa — **nhiều chi nhánh** + đặt lịch online

Một **máy chủ Flask + SQLite** duy nhất phục vụ **nhiều chi nhánh** (tối đa vài chục),
mỗi chi nhánh có mã `code` riêng (`eakar`, `buondon`…). Toàn bộ dữ liệu (số thứ tự,
quầy, cấu hình, lịch hẹn) tách theo `branch_id` — các chi nhánh không thấy dữ liệu
của nhau.

| Thành phần | Vị trí | Mở tại |
|---|---|---|
| **Máy chủ** | `server/` | `http://<máy-chủ>:5000` (thật: sau Cloudflare Tunnel) |
| **Trang chủ** (chọn chi nhánh) | trình duyệt | `…/` |
| **Máy bốc số** (kiosk cảm ứng) | `kiosk/` | chạy trên máy đặt ở sảnh từng chi nhánh |
| **Máy gọi số** (bàn cán bộ) | trình duyệt | `…/b/<mã>/counter` |
| **Màn hình hiển thị** (TV sảnh) | trình duyệt | `…/b/<mã>/display` · `…/b/<mã>/display/simple` |
| **Quản trị tổng** | trình duyệt | `…/admin` |
| **Đặt lịch hẹn online** (người dân) | trình duyệt | `…/dat-lich` · tra cứu `…/lich-hen/<token>` |

- Realtime **màn hình hiển thị** dùng **SSE** (`/api/b/<mã>/stream`).
- **Bàn gọi số** và **kiosk** dùng **polling** (3 s / 20 s) — nhẹ khi có nhiều quầy.

---

## 1. Cài đặt & chạy máy chủ

Yêu cầu: Python 3.10+.

```bat
run_server.bat
```

Lần đầu `run_server.bat` tự tạo CSDL `hethong_v2.db` + một chi nhánh mẫu `eakar`.
Chạy như production (waitress) trừ khi đặt `GOISO_DEBUG=1` (Flask dev + reload).

### Biến môi trường

| Biến | Ý nghĩa |
|---|---|
| `GOISO_SECRET` | **bắt buộc khi triển khai thật** — khoá ký session Flask |
| `GOISO_PORT` | cổng (mặc định `5000`, chỉ dùng ở chế độ dev) |
| `GOISO_DB` | đường dẫn file `.db` khác |
| `GOISO_DEBUG=1` | bật Flask dev server + tắt kiểm tra `X-Branch-Key` |
| `GOISO_BASE_URL` | URL gốc công khai, ví dụ `https://goiso.tentinh.vn` (dựng link/QR) |
| `TURNSTILE_SITE_KEY` / `TURNSTILE_SECRET` | Cloudflare Turnstile cho trang đặt lịch |

### Lệnh quản lý (`server/manage.py`)

```bat
cd server
python manage.py init                              :: tạo CSDL (+ chi nhánh mẫu nếu trống)
python manage.py set-admin-pw <mật khẩu>           :: mật khẩu trang /admin (toàn hệ thống)
python manage.py add-branch eakar "Ea Kar" "CHI NHÁNH KHU VỰC EA KAR" "địa chỉ"
python manage.py seed-branches ..\branches.csv     :: tạo hàng loạt từ CSV (code,name,full_name,address)
python manage.py list-branches                     :: xem chi nhánh + api_key + display_token
python manage.py regen-key <mã>                    :: tạo lại API key kiosk
python manage.py regen-display-token <mã>
python manage.py reset-today [<mã>|all]            :: xoá số đã cấp hôm nay
python manage.py show-config <mã>                  :: in cấu hình 1 chi nhánh
```

> File mẫu `branches.csv` ở thư mục gốc có sẵn 24 dòng — sửa lại `name`/`full_name`
> cho đúng rồi chạy `seed-branches`.

Mật khẩu `/admin` mặc định trên CSDL mới: `admin123` — **đổi ngay**.

---

## 2. Mỗi chi nhánh cần cấu hình gì

Vào `/admin` → tab **Chi nhánh**:

- Thêm/sửa chi nhánh: **mã** (dùng trong URL, chỉ chữ thường/số/gạch), tên ngắn,
  tên đầy đủ (hiện trên màn hình), địa chỉ, thứ tự, bật/tắt.
- Mỗi chi nhánh tự sinh 2 khoá:
  - **`api_key`** — kiosk của chi nhánh gửi kèm header `X-Branch-Key` khi lấy số.
  - **`display_token`** — (tuỳ chọn) khoá mềm cho URL màn hình.

Chọn chi nhánh ở thanh trên rồi chỉnh **Dịch vụ / Quầy / Cấu hình chung / Đặt lịch
online** cho *riêng chi nhánh đó*. Tab **Thống kê** chọn "Tất cả" để xem bảng tổng
hợp mọi chi nhánh.

**Cấu hình chung** có thêm ô **Mã PIN quầy**: nếu đặt, màn hình "Vào ca" của
`/b/<mã>/counter` sẽ yêu cầu PIN này (lớp chặn ứng dụng — vẫn nên dùng kèm
Cloudflare Access, xem mục 6).

---

## 3. Máy bốc số (kiosk)

```bat
run_kiosk.bat
```

`kiosk/config.json`:

| Khoá | Ý nghĩa |
|---|---|
| `server_url` | URL máy chủ, ví dụ `https://goiso.tentinh.vn` |
| `branch_code` | **mã chi nhánh** của máy kiosk này, ví dụ `eakar` |
| `api_key` | khoá `api_key` của chi nhánh (lấy từ `list-branches` hoặc trang /admin) |
| `printer_name` | tên máy in nhiệt Windows; `""` = máy in mặc định |
| `paper_width_mm` | `80` hoặc `58` |
| `preview_only` | `true` = chỉ xem trước, không in |
| `fullscreen`, `columns`, `confirm_seconds` | như cũ |

Kiosk tự: ẩn dịch vụ tắt/hết lượt, chặn ngoài giờ, báo mất kết nối & tự nối lại.
Nút **“TÔI CÓ LỊCH HẸN”** trên đầu màn hình: người dân nhập mã hẹn online → in phiếu
số ngay (nếu đang trong khung giờ hẹn).

Phím tắt: `F11` toàn màn hình · `Ctrl+Shift+Q` thoát.

---

## 4. Máy gọi số — `/b/<mã>/counter`

1. Chọn **quầy** + nhập **tên cán bộ** (+ **PIN** nếu chi nhánh bật) → *Vào ca*.
   (Ghi nhớ trên máy đó.)
2. **GỌI TIẾP** (`Space`) · **Gọi lại** (`R`) · **Hoàn thành** (`D`) · **Vắng** ·
   **Tạm dừng** · **Gọi số cụ thể** (`A-25`).
3. Bảng phải: đang phục vụ, hàng chờ (số online có nhãn **HẸN**), lịch sử.

---

## 5. Màn hình hiển thị — `/b/<mã>/display`

Mở toàn màn hình trên TV. Lần đầu **chạm/nhấn phím** để bật âm thanh + toàn màn hình.
Cần cài **giọng tiếng Việt của Windows** để đọc số.

Biến thể: `?nocursor=1` · `?counters=1,3,5` · `/b/<mã>/display/simple` (một số cực lớn).

---

## 6. Triển khai thật qua Cloudflare Tunnel

Máy chủ chỉ nghe `127.0.0.1:5000`; Cloudflare Tunnel đưa ra Internet, không cần mở
cổng vào máy.

### 6.1. cloudflared

```bat
:: cài (winget) rồi đăng nhập
winget install --id Cloudflare.cloudflared
cloudflared tunnel login
cloudflared tunnel create goiso
```

`C:\Users\<user>\.cloudflared\config.yml`:

```yaml
tunnel: goiso
credentials-file: C:\Users\<user>\.cloudflared\<UUID>.json
ingress:
  - hostname: goiso.tentinh.vn
    service: http://localhost:5000
    originRequest:
      # SSE: giữ kết nối stream lâu
      disableChunkedEncoding: false
      connectTimeout: 30s
  - service: http_status:404
```

```bat
cloudflared tunnel route dns goiso goiso.tentinh.vn
cloudflared service install      :: chạy nền như Windows service
```

Đặt `GOISO_BASE_URL=https://goiso.tentinh.vn` và `GOISO_SECRET=<chuỗi ngẫu nhiên>`
(vào **System Properties → Environment Variables**, hoặc đầu `run_server.bat`).

### 6.2. Cloudflare Access (Zero Trust) — chặn quầy & quản trị

Đặt **Access Application** cho các đường dẫn nội bộ, chỉ cho email cán bộ:

- `goiso.tentinh.vn/admin*`
- `goiso.tentinh.vn/b/*/counter*`

**Không** đặt Access cho: `/`, `/b/*/display*`, `/api/b/*/stream`,
`/api/b/*/config/public`, `/dat-lich`, `/lich-hen/*`, `/api/booking/*`
(màn hình sảnh và trang người dân phải mở).

Kiosk gọi API kèm `X-Branch-Key` nên không cần qua Access; giữ nguyên đường
`/api/b/<mã>/ticket`, `/api/b/<mã>/checkin` mở (đã có khoá riêng).

### 6.3. Turnstile cho trang đặt lịch

Tạo site Turnstile (domain `goiso.tentinh.vn`), lấy **Site key** + **Secret key**,
đặt vào `TURNSTILE_SITE_KEY` / `TURNSTILE_SECRET`. Bật/tắt theo chi nhánh ở tab
**Đặt lịch online**. Nếu chưa cấu hình secret, máy chủ bỏ qua bước xác thực (chỉ nên
dùng khi chạy thử).

---

## 7. Đặt lịch hẹn online (bốc số theo khung giờ)

Bật ở `/admin` → **Đặt lịch online** cho từng chi nhánh:

- `windows` — các khung nhận đặt trong ngày, `[{"start":"07:30","end":"11:00"}]`
- `slot_minutes` — độ dài mỗi khung (mặc định 30)
- `capacity_per_slot` — sức chứa mỗi khung theo dịch vụ, `{"_default":4,"A":6}`
- `open_days_ahead` — cho đặt trước tối đa mấy ngày (mặc định 3)
- `max_active_per_cccd` — số lịch **đang chờ** tối đa mỗi CCCD (mặc định 1)
- `checkin_grace_minutes` — ân hạn check-in trước/sau khung giờ (mặc định 15)
- `online_priority` — nếu bật, số đã check-in từ lịch hẹn được gọi trước khách vãng lai

**Luồng người dân:** `/dat-lich` → chọn chi nhánh → thủ tục → ngày → khung giờ →
nhập họ tên + CCCD + SĐT (+ Turnstile) → nhận **mã hẹn** + **QR**. Đến kiosk, bấm
**“TÔI CÓ LỊCH HẸN”**, nhập mã (hoặc quét QR mở `/lich-hen/<token>`) trong khoảng
`[giờ bắt đầu − ân hạn, giờ kết thúc + ân hạn]` → in phiếu số thật, số vào hàng chờ
như bình thường (`source = online`).

Lịch hẹn quá giờ mà không check-in sẽ tự chuyển **hết hạn** (tác vụ nền chạy mỗi 5′).
Người dân xem/huỷ tại `/lich-hen/<token>`.

---

## 8. Sơ đồ triển khai

```
                    Internet ──► Cloudflare ──► cloudflared (Windows)
                                   │  (Access chặn /admin, /b/*/counter)
                                   ▼
                        MÁY CHỦ  server/app.py  (127.0.0.1:5000, waitress)
                        Flask + SQLite (hethong_v2.db)
        SSE(display) / polling(counter,kiosk) / REST
   ┌──────────────┬──────────────────────────┬─────────────────────────┐
 24 × KIOSK      24 × TV /b/<mã>/display   nhiều × /b/<mã>/counter    /dat-lich
 (branch_code +   (SSE, đọc TV)             (polling 3s + PIN)        (người dân + Turnstile)
  api_key)
```

---

## 9. Ghi chú kỹ thuật

- Số thứ tự đánh theo **`(chi nhánh, mã dịch vụ, ngày)`** — `A-001`, `A-002`… tự
  bắt đầu lại mỗi ngày, độc lập giữa các chi nhánh.
- Máy chủ chạy dưới **waitress** (`--threads=32`) — đủ cho vài chục chi nhánh với
  tải bốc số thông thường. SSE chỉ dùng cho `/display` nên số kết nối bền ≈ số TV.
- Toàn bộ trạng thái nằm trong `hethong_v2.db` — **sao lưu file này là đủ** (kèm
  `-wal`/`-shm` nếu có). File này không đưa vào git.
- Muốn tải rất lớn / nhiều tiến trình về sau: tách sang PostgreSQL (lớp truy cập
  gói trong `server/db.py`).
- Chưa tích hợp gửi SMS/Zalo cho lịch hẹn — người dân tự lưu mã hẹn / QR.
