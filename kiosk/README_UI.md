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

## Cấu hình theo chi nhánh — KHÔNG sửa code

Đặt trong `kiosk/config.json` (đã có sẵn file này):

```json
{
  "branch_name": "CHI NHÁNH KHU VỰC BUÔN MA THUỘT",
  "organization_name": "VĂN PHÒNG ĐĂNG KÝ ĐẤT ĐAI",
  "footer_department": "PHÒNG DỮ LIỆU - THÔNG TIN ĐẤT ĐAI",
  "footer_team": "TỔ ỨNG DỤNG VÀ PHÁT TRIỂN CÔNG NGHỆ",
  "fullscreen": true
}
```

Hoặc biến môi trường: `KIOSK_BRANCH_NAME`.
`branch_name` chỉ hiển thị dạng dòng nhỏ dưới tên Văn phòng; để trống = ẩn.

## Thay logo / ảnh nền

- Bỏ file `assets/logo.png` (nền trong suốt) → dùng ngay.
- Bỏ file `assets/background.png` (khuyến nghị 1920×1080, **không chữ chi nhánh**)
  → thay cho ảnh nền tự dựng.
- Bỏ icon riêng vào `assets/icons/<tên>.png` (nét trắng, nền trong suốt) → tự
  tô lại màu theo thẻ.

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
