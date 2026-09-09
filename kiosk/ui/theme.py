"""Font & tiện ích co giãn theo kích thước màn hình.

╔══════════════════════════════════════════════════════════════════════════╗
║  SỬA CỠ CHỮ / LOGO Ở ĐÂY                                                 ║
║  - Đổi số trong FONT_SIZES  -> cỡ chữ các thành phần                     ║
║  - Đổi số trong PX_SIZES    -> cỡ logo (và vài kích thước điểm ảnh khác) ║
║  Số ghi ở đây là cỡ chuẩn tại màn hình 1920×1080; màn nhỏ hơn tự thu     ║
║  lại theo tỉ lệ. Sửa xong chạy lại `python app.py` là thấy ngay.         ║
╚══════════════════════════════════════════════════════════════════════════╝
"""
import customtkinter as ctk

from config.settings import FONT_FAMILY, FONT_FAMILY_FALLBACKS

_FAMILY = None


def font_family():
    """Chọn font sans-serif có sẵn đầu tiên trên máy."""
    global _FAMILY
    if _FAMILY:
        return _FAMILY
    try:
        import tkinter.font as tkfont
        avail = set(tkfont.families())
        for name in FONT_FAMILY_FALLBACKS:
            if name in avail:
                _FAMILY = name
                return name
    except Exception:  # noqa: BLE001
        pass
    _FAMILY = FONT_FAMILY
    return _FAMILY


# --------------------------------------------------------------------- CỠ CHỮ
# (điểm ảnh, ở màn hình chuẩn 1920×1080)
FONT_SIZES = {
    "org":         36,   # "VĂN PHÒNG ĐĂNG KÝ ĐẤT ĐAI"
    "branch":      26,   # "CHI NHÁNH KHU VỰC ..."
    "slogan":      14,   # slogan trái
    "right_slo":   14,   # slogan phải
    "hero":        62,   # "KÍNH CHÀO QUÝ KHÁCH"
    "hero_sub":    25,   # "Vui lòng chọn dịch vụ để lấy số thứ tự"
    "card_title":  32,   # tiêu đề trên thẻ
    "card_desc":   16,   # mô tả trên thẻ
    "footer_1":    22,   # dòng "PHÒNG DỮ LIỆU - THÔNG TIN ĐẤT ĐAI"
    "footer_2":    18,   # dòng "TỔ ỨNG DỤNG VÀ PHÁT TRIỂN CÔNG NGHỆ"
    "footer_date": 17,   # "Thứ Tư, 09/09/2026"
    "footer_clock": 35,  # đồng hồ "07:52"
}

# --------------------------------------------------------- CỠ LOGO & ĐIỂM ẢNH
PX_SIZES = {
    "logo": 100,          # cạnh ô logo ở header (px, tại 1920×1080)
    "footer_height": 116,  # chiều cao thanh footer (px)
}


class Scaler:
    """Quản lý một bộ CTkFont và co giãn chúng theo màn hình."""

    def __init__(self):
        fam = font_family()
        self.factor = 1.0
        self._fonts = {}
        weights = {
            "org": "bold", "hero": "bold", "card_title": "bold",
            "footer_1": "bold", "footer_clock": "bold", "branch": "bold",
        }
        for key, size in FONT_SIZES.items():
            self._fonts[key] = ctk.CTkFont(
                family=fam, size=size, weight=weights.get(key, "normal"))

    def font(self, key):
        return self._fonts[key]

    def update(self, width, height):
        """Tính hệ số từ kích thước hiện tại và áp lại cỡ chữ."""
        factor = min(width / 1920.0, height / 1080.0)
        factor = max(0.60, min(1.35, factor))
        if abs(factor - self.factor) < 0.02:
            return False
        self.factor = factor
        for key, size in FONT_SIZES.items():
            self._fonts[key].configure(size=max(9, round(size * factor)))
        return True

    def px(self, key):
        """Kích thước điểm ảnh (từ PX_SIZES) đã co theo màn hình."""
        return max(8, round(PX_SIZES[key] * self.factor))

    def s(self, px):
        """Co giãn một số pixel bất kỳ (padding, kích thước icon...)."""
        return max(1, round(px * self.factor))
