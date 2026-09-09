# Hệ thống bốc số & gọi số một cửa — **nhiều chi nhánh** + đặt lịch online

Một **máy chủ Flask + SQLite** duy nhất phục vụ **nhiều chi nhánh** (tối đa vài chục),
mỗi chi nhánh có mã `code` riêng (`bmt`, `buondon`…). Toàn bộ dữ liệu (số thứ tự,
quầy, cấu hình, lịch hẹn) tách theo `branch_id` — các chi nhánh không thấy dữ liệu
của nhau.

| Thành phần | Vị trí | Mở tại |
|---|---|---|
| **Máy chủ** | `server/` | `http://<máy-chủ>:5050` (thật: sau Cloudflare Tunnel) |
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

Lần đầu `run_server.bat` tự tạo CSDL `hethong_v2.db` + một chi nhánh mẫu `bmt` (Buôn Ma Thuột).
Chạy như production (waitress) trừ khi đặt `GOISO_DEBUG=1` (Flask dev + reload).

### Biến môi trường

| Biến | Ý nghĩa |
|---|---|
| `GOISO_SECRET` | **bắt buộc khi triển khai thật** — khoá ký session Flask |
| `GOISO_PORT` | cổng máy chủ (mặc định `5050`) |
| `GOISO_DB` | đường dẫn file `.db` khác |
| `GOISO_DEBUG=1` | bật Flask dev server + tắt kiểm tra `X-Branch-Key` |
| `GOISO_BASE_URL` | URL gốc công khai, ví dụ `https://goiso.kh2959bmt.xyz` (dựng link/QR) |
| `TURNSTILE_SITE_KEY` / `TURNSTILE_SECRET` | Cloudflare Turnstile cho trang đặt lịch |

### Lệnh quản lý (`server/manage.py`)

```bat
cd server
python manage.py init                              :: tạo CSDL (+ chi nhánh mẫu nếu trống)
python manage.py set-admin-pw <mật khẩu>           :: mật khẩu trang /admin (toàn hệ thống)
python manage.py add-branch bmt "Buôn Ma Thuột" "CHI NHÁNH KHU VỰC BUÔN MA THUỘT" "địa chỉ"
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
| `server_url` | URL máy chủ, ví dụ `https://goiso.kh2959bmt.xyz` |
| `branch_code` | **mã chi nhánh** của máy kiosk này, ví dụ `bmt` |
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

## 4. Tài khoản & máy gọi số — `/b/<mã>/counter`

Máy gọi số **bắt buộc đăng nhập** (`/login`). Hai vai trò:

| Vai trò | Quyền |
|---|---|
| **admin** | Xem/sửa toàn hệ thống (`/admin`), quản lý người dùng |
| **staff** | Chỉ vào được `/b/<chi-nhánh-của-mình>/counter`; chi nhánh khác → 403 |

Tài khoản `admin` được tạo sẵn khi khởi tạo CSDL (mật khẩu = mật khẩu quản trị
mặc định `admin123` — đổi ngay trong `/admin` → tab **Người dùng**).

Tạo tài khoản nhân viên: `/admin` → **Người dùng** → *+ Thêm người dùng*
(tên đăng nhập, họ tên, mật khẩu, chi nhánh). Hoặc dòng lệnh:
```
python manage.py add-user nvhoan "Nguyễn Văn Hoàn" MatKhau123 bmt
python manage.py list-users
python manage.py set-user-pw nvhoan MatKhauMoi
```

Nhân viên đăng nhập → tự vào trang quầy chi nhánh mình → **chọn quầy đang ngồi** →
*Vào ca* (họ tên lấy từ tài khoản). Thao tác: **GỌI TIẾP** (`Space`) · **Gọi lại**
(`R`) · **Hoàn thành** (`D`) · **Vắng** · **Tạm dừng** · **Gọi số cụ thể** (`A-25`).

> Trang **màn hình TV** (`/b/<mã>/display`) và **đặt lịch** (`/dat-lich`) không yêu
> cầu đăng nhập (màn hình là thiết bị đặt tại chỗ; đặt lịch là trang công dân).

---

## 5. Màn hình hiển thị — `/b/<mã>/display`

Mở toàn màn hình trên TV. Lần đầu **chạm/nhấn phím** để bật âm thanh + toàn màn hình.

**Giọng đọc số:** mặc định `tts_mode = "server"` — **máy chủ tạo giọng tiếng Việt**
(thư viện `edge-tts`, giọng `vi-VN-HoaiMyNeural` / `vi-VN-NamMinhNeural`) rồi gửi âm
thanh cho TV phát, nên **không cần cài giọng đọc trên từng máy nối TV**. Máy chủ cần
có mạng ra Internet; câu đọc được lưu đệm ở `server/tts_cache/`.
Đổi giọng nam/nữ hoặc chuyển về giọng trình duyệt (`tts_mode = "browser"`) trong
`/admin` → tab **Cấu hình chung** (`tts_voice`, `tts_mode`).

**Bật tiếng:** trình duyệt chặn tự phát âm thanh nên lần đầu phải **chạm/nhấn phím**
để lớp "Chạm để bắt đầu" biến mất — ô ở chân màn hình chuyển **🔊 Đã bật tiếng**
(xanh). Máy nối TV không có chuột/bàn phím thì mở trình duyệt kèm cờ
`--autoplay-policy=no-user-gesture-required` rồi vào `…/display?autoplay=1` để bỏ
qua bước này. Nút **🔊 Thử tiếng** ở chân màn hình để kiểm tra nhanh.

Biến thể: `?nocursor=1` · `?counters=1,3,5` · `?autoplay=1` · `/b/<mã>/display/simple`.

---

## 6. Triển khai thật qua Cloudflare Tunnel

Máy chủ chỉ nghe `127.0.0.1:<GOISO_PORT>` (mặc định **5050** — đổi nếu cổng bận);
Cloudflare Tunnel đưa ra Internet, không cần mở cổng vào máy.

### 6.1a. Nếu đã có Tunnel quản lý trên dashboard (khuyên dùng — máy này đang có sẵn)

Máy này đã chạy sẵn `cloudflared` dạng service với **token** (Tunnel tạo từ
Cloudflare Zero Trust). Không cần `login` / `create` / `config.yml`. Chỉ cần thêm
**Public Hostname**:

1. Cloudflare **Zero Trust → Networks → Tunnels →** chọn tunnel đang chạy →
   tab **Public Hostname → Add a public hostname**.
2. Subdomain `goiso` · Domain `kh2959bmt.xyz` · Type **HTTP** · URL `localhost:5050`.
3. **Save** — DNS `goiso.kh2959bmt.xyz` được tạo tự động.
4. Mở `https://goiso.kh2959bmt.xyz/` sau ~30 giây.

> Tunnel này có thể đang phục vụ ứng dụng khác ở `localhost:5000` (vd `qlns_vpdk`).
> Cứ thêm public hostname mới trỏ `localhost:5050` cho hệ thống gọi số — hai bên
> chạy song song trên cùng một tunnel.

### 6.1b. Hoặc tạo Tunnel cục bộ mới (nếu chưa có gì)

```bat
winget install --id Cloudflare.cloudflared
cloudflared tunnel login
cloudflared tunnel create goiso
```

`C:\Users\<user>\.cloudflared\config.yml`:

```yaml
tunnel: goiso
credentials-file: C:\Users\<user>\.cloudflared\<UUID>.json
ingress:
  - hostname: goiso.kh2959bmt.xyz
    service: http://localhost:5050
    originRequest:
      connectTimeout: 30s
  - service: http_status:404
```

```bat
cloudflared tunnel route dns goiso goiso.kh2959bmt.xyz
cloudflared service install
```

Sau khi có hostname: đặt `GOISO_BASE_URL=https://goiso.kh2959bmt.xyz` và
`GOISO_SECRET=<chuỗi ngẫu nhiên cố định>` ở đầu `run_server.bat` (đã có sẵn), rồi
khởi động lại máy chủ.

### 6.2. Cloudflare Access (Zero Trust) — chặn quầy & quản trị

Đặt **Access Application** cho các đường dẫn nội bộ, chỉ cho email cán bộ:

- `goiso.kh2959bmt.xyz/admin*`
- `goiso.kh2959bmt.xyz/b/*/counter*`

**Không** đặt Access cho: `/`, `/b/*/display*`, `/api/b/*/stream`,
`/api/b/*/config/public`, `/dat-lich`, `/lich-hen/*`, `/api/booking/*`
(màn hình sảnh và trang người dân phải mở).

Kiosk gọi API kèm `X-Branch-Key` nên không cần qua Access; giữ nguyên đường
`/api/b/<mã>/ticket`, `/api/b/<mã>/checkin` mở (đã có khoá riêng).

### 6.3. Turnstile cho trang đặt lịch

Tạo site Turnstile (domain `goiso.kh2959bmt.xyz`), lấy **Site key** + **Secret key**,
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
                        MÁY CHỦ  server/app.py  (127.0.0.1:5050, waitress)
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

---

## 10. Bộ cài Windows Kiosk & tự cập nhật (GoSo Kiosk)

Một bộ cài `GoSoKiosk_Setup_x.y.z.exe` dùng cho **mọi chi nhánh**. Máy triển khai
KHÔNG cần Python / terminal / pip / sửa JSON.

### Kiến trúc Windows

| Nơi | Nội dung |
|---|---|
| `C:\Program Files\GoSo Kiosk\` | `GoSoKiosk.exe`, `GoSoConfig.exe`, `GoSoUpdater.exe`, `assets\`, `VERSION` — **bị thay khi update** |
| `C:\ProgramData\GoSoKiosk\` | `config.json`, `device.json`, `logs\`, `updates\`, `backup\`, `state\` — **KHÔNG bị update ghi đè** |

Nhờ tách 2 vùng: cập nhật ứng dụng **không mất** chi nhánh / device / server / máy in / cấu hình / log.

Mã nguồn: `kiosk/goso/` (thư viện dùng chung), `kiosk/goso_kiosk.py` (runtime),
`kiosk/goso_config.py` (Configurator), `kiosk/goso_updater.py` (Updater), `kiosk/app.py` (giao diện).

### Development (không cần build exe)

```bat
cd kiosk
pip install -r requirements.txt
python goso_kiosk.py        :: chưa cấu hình -> tự mở Configurator
python goso_config.py       :: mở Configurator
```

Dev lưu dữ liệu ở `kiosk\.godata\` (thay cho ProgramData). Ép nơi khác bằng
biến môi trường `GOSO_DATA_DIR`. Config cũ `kiosk/config.json` được **tự di trú**
sang đó ở lần chạy đầu.

### Configurator (`GoSoConfig.exe`)

Chạy sau khi cài (hoặc mở lại bất kỳ lúc nào). Các mục:
1. **Máy chủ** — nhập URL, bấm *Kiểm tra kết nối* (gọi `/api/ping`, xác nhận đúng GoSo Server).
2. **Chi nhánh** — combobox nạp từ `GET /api/branches` (không hard-code).
3. **Máy in** — chọn từ máy in Windows (`win32print`), khổ `58/80` mm, *Chỉ xem trước*, **In thử**.
4. **Cấu hình kiosk** — Toàn màn hình, Tự chạy cùng Windows; *Cài đặt nâng cao* (`columns`, `refresh_seconds`, `confirm_seconds`, `font`).
5. **Device ID** — vd `BMT-KIOSK-01` (ổn định, không đổi khi update).
6. **Lưu và chạy kiosk** — validate → tạo `ProgramData\GoSoKiosk\` → lưu config + device → bật auto-start → chạy `GoSoKiosk.exe`.

### Build

```powershell
.\scripts\build.ps1              # dist\GoSoKiosk\ + GoSoKiosk_Update_<ver>.zip + version.json
.\scripts\build.ps1 -Installer   # + dist\GoSoKiosk_Setup_<ver>.exe  (cần Inno Setup)
```

`GoSoKiosk.spec` là định nghĩa build (PyInstaller onedir, `--windowed`, gộp assets +
`VERSION`, xử lý resource path khi frozen). Phiên bản lấy từ **1 nguồn**: file `VERSION` ở gốc.

### Installer (`installer\GoSoKiosk.iss`)

- Cài vào `Program Files\GoSo Kiosk\`, tạo `ProgramData\GoSoKiosk\` (không xoá khi uninstall).
- Start Menu + Desktop shortcut (tuỳ chọn).
- Lần cài **mới** (chưa có `config.json`) → tự chạy `GoSoConfig.exe`. **Upgrade** → không hỏi lại.
- Uninstall chỉ gỡ binary, **giữ** cấu hình ở ProgramData.

### Cài một kiosk mới

1. Chạy `GoSoKiosk_Setup_x.y.z.exe`.
2. Configurator tự mở → nhập máy chủ → *Kiểm tra kết nối* → chọn chi nhánh → chọn máy in → *In thử* → *Lưu và chạy kiosk*.
3. Xong. Kiosk tự chạy; các lần Windows khởi động sau tự chạy lại (nếu đã bật).

### Đổi máy in / chi nhánh

Mở **GoSo Kiosk - Cấu hình** (Start Menu) → đổi mục cần đổi → *Lưu và chạy kiosk*.
Device ID và các cấu hình khác giữ nguyên.

### Auto Start

Configurator ghi khoá `HKCU\...\Run\GoSoKiosk` (không cần quyền Admin). Bỏ chọn thì
xoá khoá. Trỏ tới `GoSoKiosk.exe` trong Program Files (đúng sau update).

### Auto Update

- Server là lớp điều phối: `GET /api/kiosk/version` trả
  `{version, download_url, sha256, mandatory, release_notes, min_supported_version}`.
  Đặt bằng: `python server/manage.py kiosk-release <ver> <url> <sha256> [true]`
  hoặc `POST /api/admin/kiosk-release`.
- Kiosk hỏi server (khi heartbeat + mỗi 30 phút). Nếu có bản mới hơn:
  tải vào `ProgramData\GoSoKiosk\updates\` (file `.tmp` → đổi tên khi xong) →
  kiểm **SHA256** → chạy `GoSoUpdater.exe` (tiến trình riêng, tham số cố định) →
  kiosk thoát.
- Updater: chờ kiosk thoát → **sao lưu** `backup\<version cũ>\` → giải nén đè
  (chống **ZIP path traversal** / absolute path) → chạy bản mới → chờ **health
  marker** (`state\health.json`, version khớp) ≤ 90 s.
- Không cập nhật giữa lúc đang cấp/in số (cờ `_updating`), không nhúng token GitHub
  (mọi phối hợp qua GoSo Server).

### Release version mới

```bash
# sửa file VERSION nếu cần, rồi:
git tag v1.0.7
git push origin v1.0.7
```

GitHub Actions (`.github/workflows/release.yml`): build 3 exe → gói
`GoSoKiosk_Update_1.0.7.zip` + SHA256 + `version.json` → Inno Setup →
tạo GitHub Release + upload `Setup.exe`, `Update.zip`, `version.json`.

Sau khi Release có URL, trỏ server tới bản đó:
```bat
python server/manage.py kiosk-release 1.0.7 ^
  https://github.com/<owner>/<repo>/releases/download/v1.0.7/GoSoKiosk_Update_1.0.7.zip ^
  <sha256-từ-version.json>
```
(Có thể rollout dần: sau này thêm override `kiosk_release` theo chi nhánh — schema đã sẵn.)

### Rollback

Trước khi thay, Updater sao lưu bản đang chạy vào `ProgramData\GoSoKiosk\backup\<ver>\`.
Nếu bản mới không tạo health marker đúng hạn / crash → Updater **khôi phục** bản cũ
và chạy lại. Version lỗi bị ghi vào `state\update_attempts.json`; sau
2 lần thất bại, kiosk **không thử lại** version đó (chống loop) cho tới khi server
đổi sang version khác.

### Logs

`C:\ProgramData\GoSoKiosk\logs\` — `kiosk.log`, `configurator.log`, `updater.log`
(xoay vòng 1 MB × 5). Không ghi secret/token.

### Troubleshooting

| Triệu chứng | Xử lý |
|---|---|
| Kiosk mở ra Configurator | `config.json` thiếu `server_url`/`branch_code`/`api_key` — điền lại. |
| "Địa chỉ này không phải GoSo Server" | Sai URL, hoặc server chưa chạy. |
| In thử không ra | Sai máy in, hoặc máy in đổi tên → mở Configurator chọn lại; hoặc bật *Chỉ xem trước*. |
| Không tự chạy khi khởi động | Mở Configurator, bật *Tự chạy cùng Windows*, Lưu. |
| Update mãi không lên | Xem `updater.log`; kiểm `sha256` trong `manage.py show-kiosk-release` khớp file. |
| `ProgramData` không ghi được | Chạy Configurator bằng quyền phù hợp; kiểm quyền thư mục `C:\ProgramData\GoSoKiosk`. |
