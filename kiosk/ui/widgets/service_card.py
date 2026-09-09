"""ServiceCard — thẻ chức năng lớn, bấm được, có hiệu ứng hover/nhấn.

Tái sử dụng cho cả 4 dịch vụ. Toàn bộ vùng thẻ đều click được. Icon và mũi tên
tự vẽ lại theo chiều cao thẻ khi cửa sổ đổi kích thước (debounce).
"""
import os

import customtkinter as ctk

from config.settings import CARD_ICON, CARD_RADIUS
from ui import assets


def _hex(c):
    c = str(c).lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _mix(hex_color, other, t):
    a, b = _hex(hex_color), _hex(other)
    return "#%02x%02x%02x" % tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def lighten(hex_color, t=0.12):
    return _mix(hex_color, "#FFFFFF", t)


def darken(hex_color, t=0.10):
    return _mix(hex_color, "#000000", t)


class ServiceCard(ctk.CTkFrame):
    def __init__(self, master, title, description, icon_path, bg_color, command,
                 title_font=None, desc_font=None, **kwargs):
        super().__init__(master, fg_color=bg_color, corner_radius=CARD_RADIUS,
                         border_width=0, **kwargs)
        self._base = bg_color
        self._hover = lighten(bg_color, 0.12)
        self._press = darken(bg_color, 0.10)
        self._command = command
        self._icon_name = os.path.splitext(os.path.basename(str(icon_path)))[0] or "arrow"
        self._pressed = False
        self._img_job = None
        self._badge_img = None
        self._arrow_img = None
        self._last_h = 0

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)   # icon
        self.grid_rowconfigure(1, weight=0)   # cụm chữ (title + desc)
        self.grid_rowconfigure(2, weight=1)   # spacer -> đẩy mũi tên xuống
        self.grid_rowconfigure(3, weight=0)   # arrow

        self._icon = ctk.CTkLabel(self, text="", fg_color="transparent")
        self._icon.grid(row=0, column=0, pady=(30, 6))

        block = ctk.CTkFrame(self, fg_color="transparent")
        block.grid(row=1, column=0, sticky="ew", padx=14)
        block.grid_columnconfigure(0, weight=1)
        self._title = ctk.CTkLabel(
            block, text=title, font=title_font, text_color="#FFFFFF",
            fg_color="transparent", justify="center")
        self._title.grid(row=0, column=0, pady=(2, 6))
        self._desc = ctk.CTkLabel(
            block, text=description, font=desc_font, text_color="#EDF5FF",
            fg_color="transparent", justify="center")
        self._desc.grid(row=1, column=0)

        self._arrow = ctk.CTkLabel(self, text="", fg_color="transparent")
        self._arrow.grid(row=3, column=0, pady=(8, 24))

        self._bind_all_recursive(self)
        self.bind("<Configure>", self._on_configure)

    # ------------------------------------------------------------- tương tác
    def _bind_all_recursive(self, w):
        w.configure(cursor="hand2")
        w.bind("<Button-1>", self._on_press, add="+")
        w.bind("<ButtonRelease-1>", self._on_release, add="+")
        w.bind("<Enter>", self._on_enter, add="+")
        w.bind("<Leave>", self._on_leave, add="+")
        for child in w.winfo_children():
            self._bind_all_recursive(child)

    def _set_color(self, color):
        try:
            self.configure(fg_color=color)
        except Exception:  # noqa: BLE001
            pass

    def _on_enter(self, _=None):
        if not self._pressed:
            self._set_color(self._hover)

    def _on_leave(self, _=None):
        self._pressed = False
        self._set_color(self._base)

    def _on_press(self, _=None):
        self._pressed = True
        self._set_color(self._press)

    def _on_release(self, event=None):
        was = self._pressed
        self._pressed = False
        # chỉ kích hoạt nếu con trỏ vẫn nằm trong thẻ
        inside = True
        if event is not None:
            x, y = event.x_root, event.y_root
            inside = (self.winfo_rootx() <= x <= self.winfo_rootx() + self.winfo_width()
                      and self.winfo_rooty() <= y <= self.winfo_rooty() + self.winfo_height())
        self._set_color(self._hover if inside else self._base)
        if was and inside and callable(self._command):
            self.after(10, self._command)

    # ------------------------------------------------------------- ảnh động
    def _on_configure(self, event):
        if abs(event.height - self._last_h) < 8:
            return
        self._last_h = event.height
        if self._img_job:
            self.after_cancel(self._img_job)
        self._img_job = self.after(90, lambda h=event.height: self._render_images(h))

    def _render_images(self, h):
        self._img_job = None
        c = CARD_ICON
        has_file = assets.has_card_icon(self._icon_name)
        if has_file:
            size = max(c["size_min"], min(c["size_max"], int(h * c["size_ratio"])))
        else:  # dự phòng: đĩa trắng có sẵn -> dùng cỡ đĩa
            size = max(c["size_min"], min(c["size_max"], int(h * c["fallback_disc_ratio"])))
        arrow = max(c["arrow_min"], min(c["arrow_max"], int(h * c["arrow_ratio"])))
        try:
            self._badge_img = assets.card_icon(
                self._icon_name, size, self._base,
                pad_ratio=c["pad_ratio"], glyph_ratio=c["fallback_glyph_ratio"])
            self._icon.configure(image=self._badge_img)
            self._arrow_img = assets.arrow_button_image(arrow, "#FFFFFF")
            self._arrow.configure(image=self._arrow_img)
        except Exception as e:  # noqa: BLE001
            print(f"[ServiceCard] Lỗi dựng icon: {e}")
