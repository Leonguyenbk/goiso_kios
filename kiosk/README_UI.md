# Giao diện Kiosk bốc số (giao diện mới)

Màn hình chọn dịch vụ full-screen, cảm ứng, dùng chung cho **24 chi nhánh**
(không nhúng tên chi nhánh vào ảnh nền / trang trí).

## Chạy

```bat
cd kiosk
pip install -r requirements.txt
python app.py
```

Phím tắt khi phát triển:

| Phím | Tác dụng |
|---|---|
| `ESC` | Thoát toàn màn hình |
| `F11` | Bật/tắt toàn màn hình |
| `Ctrl+Shift+Q` | Thoát ứng dụng |

## Cấu trúc

```
kiosk/
  app.py                     KioskApp(ctk.CTk) — cửa sổ, phím tắt, callback
  config/settings.py         APP_CONFIG (mọi chữ hiển thị) + COLORS
  ui/
    theme.py                 font + co giãn cỡ chữ theo màn hình
    icons.py                 vẽ icon bằng Pillow (dự phòng khi thiếu file)
    background.py            dựng ảnh nền trang trí (hoặc dùng assets/background.png)
    assets.py                nạp logo / icon, luôn có fallback
    main_screen.py           MainScreen(ctk.CTkFrame) — ghép header/hero/thẻ/footer
    widgets/
      service_card.py        ServiceCard(ctk.CTkFrame) — thẻ chức năng bấm được
      footer.py              Footer(ctk.CTkFrame) — đơn vị + đồng hồ thời gian thực
  assets/
    logo.png                 (tuỳ chọn) logo cơ quan — thiếu thì tự vẽ huy hiệu
    background.png            (tuỳ chọn) ảnh nền chung — thiếu thì tự dựng
    icons/                    land/secured/result/appointment/arrow/database .png
                             — thiếu thì tự vẽ và lưu lại
```

## Cấu hình theo TỪNG chi nhánh — KHÔNG sửa code

Header hiển thị **2 dòng**:

```
VĂN PHÒNG ĐĂNG KÝ ĐẤT ĐAI          ← organization_name (chung 24 chi nhánh)
CHI NHÁNH KHU VỰC ...              ← branch_name (đặt riêng mỗi máy)
CÔNG KHAI - MINH BẠCH - ...        ← left_slogan
```

Chỉnh trong `kiosk/config.json` của **máy kiosk đó** (file này đã có sẵn — thêm
các khoá bên dưới vào cùng cấp với `server_url`, `branch_code`...):

```json
{
  "server_url": "https://goiso.kh2959bmt.xyz",
  "branch_code": "bmt",
  "api_key": "...",

  "branch_name": "CHI NHÁNH KHU VỰC BUÔN MA THUỘT",
  "organization_name": "VĂN PHÒNG ĐĂNG KÝ ĐẤT ĐAI",
  "left_slogan": "CÔNG KHAI - MINH BẠCH - CHUYÊN NGHIỆP - VÌ NGƯỜI DÂN",
  "right_slogan_lines": ["ĐỒNG HÀNH CÙNG NGƯỜI DÂN", "VÌ QUẢN LÝ ĐẤT ĐAI HIỆU QUẢ"],
  "footer_department": "PHÒNG DỮ LIỆU - THÔNG TIN ĐẤT ĐAI",
  "footer_team": "TỔ ỨNG DỤNG VÀ PHÁT TRIỂN CÔNG NGHỆ",
  "fullscreen": true
}
```

- Chỉ **bắt buộc** đặt `branch_name`. Các khoá khác đã có mặc định đúng, để trống cũng được.
- Cách khác: đặt biến môi trường `KIOSK_BRANCH_NAME="CHI NHÁNH KHU VỰC ..."`.
- `branch_name` để trống ("") → header chỉ còn 1 dòng tên Văn phòng.

## Thay LOGO

- Chép file **`kiosk/assets/logo.png`** — PNG **nền trong suốt**, hình vuông là
  đẹp nhất (vd 512×512). Cỡ bất kỳ, chương trình tự thu về vừa header.
- Không có file này → tự vẽ huy hiệu tạm (tròn xanh + núi trắng + vòng cung lá).
- Logo dùng chung 24 chi nhánh (logo cơ quan), **không** để logo riêng từng chi nhánh.

## Thay ẢNH NỀN

- Chép file **`kiosk/assets/background.png`** — khuyến nghị **1920×1080**,
  **KHÔNG chứa chữ / tên chi nhánh** (dùng chung 24 chi nhánh).
- Ảnh được **phủ kín, không kéo méo** (phóng theo cạnh lớn rồi cắt giữa) vào vùng
  4 thẻ. Nên là ảnh nhẹ, tông xanh nhạt để chữ trên thẻ vẫn rõ.
- Không có file này → tự dựng nền (trời gradient + hoạ tiết trống đồng mờ + núi +
  phố + cây + dải nước).
- Vùng header và lời chào luôn giữ nền sáng phẳng để dễ đọc — ảnh nền hiển thị ở
  khu vực 4 thẻ trở xuống.

## Chỉnh CỠ CHỮ và CỠ LOGO

Mở **`kiosk/ui/theme.py`** — tất cả nằm ở đầu file:

```python
FONT_SIZES = {
    "org":         36,   # "VĂN PHÒNG ĐĂNG KÝ ĐẤT ĐAI"
    "branch":      21,   # "CHI NHÁNH KHU VỰC ..."
    "slogan":      14,   # slogan trái
    "right_slo":   14,   # slogan phải
    "hero":        62,   # "KÍNH CHÀO QUÝ KHÁCH"
    "hero_sub":    25,   # dòng mô tả dưới lời chào
    "card_title":  32,   # tiêu đề trên thẻ
    "card_desc":   16,   # mô tả trên thẻ
    "footer_1":    18,   # "PHÒNG DỮ LIỆU - ..."
    "footer_2":    15,   # "TỔ ỨNG DỤNG - ..."
    "footer_date": 16,   # ngày ở footer
    "footer_clock": 33,  # đồng hồ
}

PX_SIZES = {
    "logo": 80,          # cạnh ô logo ở header
}
```

- Số là **cỡ ở màn hình 1920×1080**; màn nhỏ hơn tự thu theo tỉ lệ.
- Muốn logo to hơn: tăng `"logo"` (vd `80` → `110`).
- Sửa xong lưu file rồi chạy lại `python app.py`.

## Thay ICON thẻ

Chép PNG vào **`kiosk/assets/icons/`** với đúng tên:
`land.png` (Thủ tục đất đai), `secured.png` (Giao dịch bảo đảm),
`result.png` (Trả kết quả), `appointment.png` (Lấy phiếu hẹn online),
`arrow.png`, `database.png`. Thiếu file nào thì tự vẽ.

Hai kiểu file đều dùng được:

| File icon | Cách hiển thị |
|---|---|
| **PNG nền TRONG SUỐT** (nét icon nằm ở kênh alpha) | Chương trình **tô lại theo màu thẻ** — icon đơn sắc trên đĩa trắng, đúng phong cách ảnh mẫu. **Khuyến nghị.** |
| **PNG nền ĐẶC** (icon nhiều màu, có nền) | **Giữ nguyên màu gốc**, chỉ thu nhỏ. Dùng khi bạn muốn icon màu riêng. |

> Nếu icon "biến mất" / thành ô đặc: file bạn gửi là PNG nền đặc **màu trắng/sáng**
> nhưng lại **có chút alpha** → bị tô thành khối. Hãy xuất lại PNG **nền trong
> suốt thật sự** (transparent), hoặc PNG **hoàn toàn không có alpha**.

### Chỉnh CỠ icon trên thẻ

Mở **`kiosk/config/settings.py`** → sửa `CARD_ICON` (tính theo % chiều cao thẻ,
tự co theo màn hình):

```python
CARD_ICON = {
    "disc_ratio":  0.28,   # to/nhỏ đĩa tròn trắng chứa icon  (tăng = icon to hơn)
    "disc_min": 70, "disc_max": 210,
    "glyph_ratio": 0.56,   # hình icon bên trong đĩa
    "arrow_ratio": 0.115,  # nút mũi tên ở đáy thẻ
    "arrow_min": 34, "arrow_max": 82,
}
```

## Tại sao file trong `assets/` bị "mờ / ẩn" trong VS Code?

Trước đây `assets/logo.png`, `assets/icons/*.png` bị đưa vào `.gitignore` nên
VS Code hiển thị mờ. **Đã bỏ** — nay logo / ảnh nền / icon bạn đặt vào đều
hiện bình thường và commit được. Ảnh tự vẽ (khi thiếu file) **không còn ghi ra
đĩa**, chỉ dựng trong bộ nhớ.

## Nối logic bốc số thật

`kiosk/app.py` có sẵn 4 callback, hiện chỉ `print(...)`:

| Thẻ | Hàm |
|---|---|
| Thủ tục đất đai | `on_land_procedure()` |
| Giao dịch bảo đảm | `on_secured_transaction()` |
| Trả kết quả | `on_result_return()` |
| Lấy phiếu hẹn online | `on_online_appointment()` |

Thay thân hàm bằng lệnh gọi `api_client` + `printer` (đã có trong thư mục này) là
xong. Không đụng tới `kiosk.py` cũ.
