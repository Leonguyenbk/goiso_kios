"""Footer xanh navy: icon database + 2 dòng đơn vị (trái), ngày + đồng hồ (phải)."""
import customtkinter as ctk

from config.settings import APP_CONFIG, COLORS
from ui import assets
from ui.theme import PX_SIZES

_WD = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]


class Footer(ctk.CTkFrame):
    def __init__(self, master, scaler, **kwargs):
        super().__init__(master, fg_color=COLORS["navy_dark"], corner_radius=0,
                         height=PX_SIZES.get("footer_height", 116), **kwargs)
        self.grid_propagate(False)
        self._scaler = scaler
        self._db_img = None

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0)

        self._db = ctk.CTkLabel(self, text="", fg_color="transparent")
        self._db.grid(row=0, column=0, padx=(28, 16), pady=10)

        left = ctk.CTkFrame(self, fg_color="transparent")
        left.grid(row=0, column=1, sticky="w", pady=10)
        self._l1 = ctk.CTkLabel(left, text=APP_CONFIG["footer_department"],
                                font=scaler.font("footer_1"), text_color="#FFFFFF",
                                fg_color="transparent", anchor="w", justify="left")
        self._l1.pack(anchor="w")
        self._l2 = ctk.CTkLabel(left, text=APP_CONFIG["footer_team"],
                                font=scaler.font("footer_2"), text_color="#CFE0F2",
                                fg_color="transparent", anchor="w", justify="left")
        self._l2.pack(anchor="w")

        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=2, sticky="e", padx=(16, 32), pady=10)
        self._date = ctk.CTkLabel(right, text="", font=scaler.font("footer_date"),
                                  text_color="#CFE0F2", fg_color="transparent", anchor="e")
        self._date.pack(anchor="e")
        self._clock = ctk.CTkLabel(right, text="--:--", font=scaler.font("footer_clock"),
                                   text_color="#FFFFFF", fg_color="transparent", anchor="e")
        self._clock.pack(anchor="e")

        self.bind("<Configure>", self._resize_icon)
        self._tick()

    def _resize_icon(self, event):
        px = max(30, min(52, int(event.height * 0.42)))
        try:
            self._db_img = assets.plain_icon("database", px, "#FFFFFF")
            self._db.configure(image=self._db_img)
        except Exception:  # noqa: BLE001
            pass

    def _tick(self):
        if not self.winfo_exists():
            return
        from datetime import datetime
        now = datetime.now()
        self._date.configure(text=f"{_WD[now.weekday()]}, {now:%d/%m/%Y}")
        self._clock.configure(text=now.strftime("%H:%M"))
        self._job = self.after(1000, self._tick)

    def destroy(self):
        try:
            if getattr(self, "_job", None):
                self.after_cancel(self._job)
        except Exception:  # noqa: BLE001
            pass
        super().destroy()
