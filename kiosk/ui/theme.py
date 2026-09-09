"""Font & tiện ích co giãn theo kích thước màn hình.

Thiết kế gốc chuẩn ở 1920x1080 (hệ số 1.0). Ở độ phân giải khác, gọi
`Scaler.update(width, height)` để tính lại hệ số; các `CTkFont` đã đăng ký sẽ
tự đổi cỡ chữ. Bố cục dùng grid + weight nên tự giãn, phần này chỉ lo cỡ chữ.
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


# Cỡ chữ "gốc" (ở màn hình 1920x1080)
BASE_SIZES = {
    "org":        37,
    "slogan":     15,
    "branch":     16,
    "right_slo":  14,
    "hero":       62,
    "hero_sub":   25,
    "card_title": 32,
    "card_desc":  16,
    "footer_1":   18,
    "footer_2":   15,
    "footer_date": 16,
    "footer_clock": 33,
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
        for key, size in BASE_SIZES.items():
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
        for key, size in BASE_SIZES.items():
            self._fonts[key].configure(size=max(9, round(size * factor)))
        return True

    def s(self, px):
        """Co giãn một số pixel bất kỳ (padding, kích thước icon...)."""
        return max(1, round(px * self.factor))
