"""Kiosk bốc số thứ tự — màn hình chính (giao diện mới).

Chạy:
    cd kiosk
    pip install -r requirements.txt
    python app.py

Phím tắt khi phát triển:
    ESC  -> thoát toàn màn hình
    F11  -> bật / tắt toàn màn hình
    Ctrl+Shift+Q -> thoát ứng dụng

Các callback dưới đây hiện chỉ in ra console. Sau này thay bằng luồng bấm số
thật (gọi api_client + in phiếu) — xem kiosk/api_client.py, kiosk/printer.py.
"""
import os
import sys

# cho phép `python app.py` chạy trực tiếp trong thư mục kiosk/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- DPI aware (Windows) trước khi tạo cửa sổ ---
try:
    if sys.platform == "win32":
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)   # PER_MONITOR_AWARE_V2
        except Exception:  # noqa: BLE001
            ctypes.windll.user32.SetProcessDPIAware()
except Exception:  # noqa: BLE001
    pass

import customtkinter as ctk  # noqa: E402

from config.settings import APP_CONFIG, COLORS  # noqa: E402
from ui.main_screen import MainScreen  # noqa: E402

ctk.set_appearance_mode("light")


# --------------------------------------------------------------------- callbacks
def on_land_procedure():
    print("Land procedure")


def on_secured_transaction():
    print("Secured transaction")


def on_result_return():
    print("Result return")


def on_online_appointment():
    print("Online appointment")


CALLBACKS = {
    "on_land_procedure": on_land_procedure,
    "on_secured_transaction": on_secured_transaction,
    "on_result_return": on_result_return,
    "on_online_appointment": on_online_appointment,
}


class KioskApp(ctk.CTk):
    def __init__(self):
        super().__init__(fg_color=COLORS["bg"])
        self.title("Kiosk bốc số thứ tự")
        self._fullscreen = bool(APP_CONFIG.get("fullscreen", True))

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{sw}x{sh}+0+0")
        self.minsize(1024, 600)
        try:
            self.attributes("-fullscreen", self._fullscreen)
        except Exception:  # noqa: BLE001
            self.state("zoomed")

        self.bind("<Escape>", self._exit_fullscreen)
        self.bind("<F11>", self._toggle_fullscreen)
        self.bind("<Control-Shift-Q>", lambda e: self.destroy())
        self.bind("<Control-Shift-q>", lambda e: self.destroy())

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.screen = MainScreen(self, CALLBACKS)
        self.screen.grid(row=0, column=0, sticky="nsew")

    def _toggle_fullscreen(self, _=None):
        self._fullscreen = not self._fullscreen
        self.attributes("-fullscreen", self._fullscreen)

    def _exit_fullscreen(self, _=None):
        self._fullscreen = False
        self.attributes("-fullscreen", False)


def main():
    KioskApp().mainloop()


if __name__ == "__main__":
    main()
