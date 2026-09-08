"""Máy bốc số — giao diện cảm ứng toàn màn hình (CustomTkinter).

Chạy:  python kiosk.py
Thoát: Ctrl+Shift+Q   |   Bật/tắt toàn màn hình: F11
Cấu hình: kiosk/config.json  (địa chỉ máy chủ, máy in, khổ giấy...)
"""
import json
import os
import threading
import tkinter as tk
from datetime import datetime

import customtkinter as ctk

from api_client import ApiClient, ApiError
import printer

HERE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(HERE, "config.json"), encoding="utf-8") as f:
    CFG = json.load(f)

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

FONT = CFG.get("font_family", "Arial")


class KioskApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.api = ApiClient(CFG["server_url"], CFG.get("branch_code", ""),
                             CFG.get("api_key", ""))
        self.services = {}
        self.extra = {}
        self.time_open = True
        self.busy = False
        self.online = False

        self.title("Bốc số thứ tự")
        self.configure(fg_color="#eef2f7")
        if CFG.get("fullscreen", True):
            self.attributes("-fullscreen", True)
        self.geometry("1080x1920")
        self.bind("<Control-Shift-Q>", lambda e: self.destroy())
        self.bind("<F11>", lambda e: self.attributes("-fullscreen", not self.attributes("-fullscreen")))
        self.bind("<Escape>", lambda e: None)

        self._build_header()
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=28, pady=(0, 6))

        self.lbl_credit = ctk.CTkLabel(
            self, text="Phòng Dữ liệu - Thông tin đất đai\nTổ Ứng dụng và Phát triển công nghệ",
            font=(FONT, 15), text_color="#94a3b8", justify="center")
        self.lbl_credit.pack(side="bottom", pady=(0, 8))

        self.overlay = None
        self._tick_clock()
        self.refresh_config(initial=True)

    # ---------------------------------------------------------------- header
    def _build_header(self):
        head = ctk.CTkFrame(self, fg_color="#0b5fa5", corner_radius=0)
        head.pack(fill="x")
        self.lbl_org = ctk.CTkLabel(head, text="", font=(FONT, 26, "bold"), text_color="white")
        self.lbl_org.pack(pady=(18, 0))
        self.lbl_branch = ctk.CTkLabel(head, text="", font=(FONT, 40, "bold"), text_color="white")
        self.lbl_branch.pack()
        self.lbl_hint = ctk.CTkLabel(head, text="Chạm vào ô dịch vụ để lấy số thứ tự",
                                     font=(FONT, 20), text_color="#d6e6f5")
        self.lbl_hint.pack(pady=(4, 6))
        self.btn_checkin = ctk.CTkButton(
            head, text="TÔI CÓ LỊCH HẸN — nhập mã", font=(FONT, 20, "bold"),
            height=52, corner_radius=14, fg_color="#0a4c85", hover_color="#083b68",
            command=self._open_checkin)
        self.btn_checkin.pack(pady=(2, 8))
        self.lbl_clock = ctk.CTkLabel(head, text="", font=(FONT, 22, "bold"), text_color="#d6e6f5")
        self.lbl_clock.pack(pady=(0, 14))

    def _tick_clock(self):
        wd = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ nhật"]
        now = datetime.now()
        self.lbl_clock.configure(
            text=f"{wd[now.weekday()]}, {now:%d/%m/%Y}   —   {now:%H:%M:%S}")
        self.after(1000, self._tick_clock)

    # ---------------------------------------------------------------- config
    def refresh_config(self, initial=False):
        def work():
            try:
                data = self.api.public_config()
                self.after(0, lambda: self._apply_config(data))
            except ApiError as e:
                self.after(0, lambda: self._show_offline(str(e)))
        threading.Thread(target=work, daemon=True).start()
        self.after(int(CFG.get("refresh_seconds", 20)) * 1000, self.refresh_config)

    def _apply_config(self, data):
        self.online = True
        self.services = data.get("services", {})
        self.extra = data.get("extra", {})
        self.time_open = data.get("time_open", True)
        self.lbl_org.configure(text=self.extra.get("ten_co_quan", ""))
        self.lbl_branch.configure(text=self.extra.get("ten_chi_nhanh", ""))
        if self.extra.get("footer_credit"):
            self.lbl_credit.configure(text=self.extra["footer_credit"])
        if self.overlay and getattr(self, "_overlay_kind", "") in ("offline", "lock"):
            self._clear_overlay()
        if not self.time_open:
            self._show_lock()
        else:
            self._render_services()

    # ---------------------------------------------------------------- lưới dịch vụ
    def _render_services(self):
        for w in self.body.winfo_children():
            w.destroy()
        cols = int(CFG.get("columns", 2))
        for c in range(cols):
            self.body.grid_columnconfigure(c, weight=1, uniform="col")

        items = [(k, v) for k, v in sorted(self.services.items())]
        rows = (len(items) + cols - 1) // cols
        for r in range(rows):
            self.body.grid_rowconfigure(r, weight=1, uniform="row")

        for i, (code, svc) in enumerate(items):
            r, c = divmod(i, cols)
            self._service_button(code, svc).grid(
                row=r, column=c, sticky="nsew", padx=12, pady=12)

    def _service_button(self, code, svc):
        color = svc.get("color", "#0b5fa5")
        sold = svc.get("sold_out")
        card = ctk.CTkFrame(self.body, fg_color="white", corner_radius=20,
                            border_width=2, border_color="#e2e8f0")
        card.grid_propagate(False)

        badge = ctk.CTkLabel(card, text=code, font=(FONT, 54, "bold"),
                             text_color="white", fg_color=color, corner_radius=16,
                             width=96, height=96)
        badge.pack(pady=(26, 10))
        name = ctk.CTkLabel(card, text=svc.get("short") or svc.get("name", code),
                            font=(FONT, 26, "bold"), text_color="#16202b",
                            wraplength=360, justify="center")
        name.pack(padx=20)

        if sold:
            state_lbl = ctk.CTkLabel(card, text="ĐÃ HẾT LƯỢT HÔM NAY",
                                     font=(FONT, 20, "bold"), text_color="#b91c1c")
            state_lbl.pack(pady=16)
            card.configure(border_color="#fca5a5")
        else:
            btn = ctk.CTkButton(card, text="LẤY SỐ", font=(FONT, 26, "bold"),
                                height=68, corner_radius=14, fg_color=color,
                                hover_color=_darken(color),
                                command=lambda: self.take(code))
            btn.pack(pady=20, padx=24, fill="x")
            for widget in (card, badge, name):
                widget.bind("<Button-1>", lambda e, cc=code: self.take(cc))
        return card

    # ---------------------------------------------------------------- lấy số
    def take(self, code):
        if self.busy or not self.time_open:
            return
        self.busy = True

        def work():
            try:
                ticket = self.api.take_ticket(code)
                self.after(0, lambda: self._on_ticket(ticket))
            except ApiError as e:
                self.after(0, lambda: self._toast(str(e), error=True))
            finally:
                self.after(0, lambda: setattr(self, "busy", False))

        threading.Thread(target=work, daemon=True).start()

    def _on_ticket(self, ticket):
        if not isinstance(ticket, dict) or "full_no" not in ticket:
            self._toast("Máy chủ trả về dữ liệu không hợp lệ — kiểm tra 'server_url' "
                        "và 'api_key' trong config.json.", error=True)
            return
        threading.Thread(target=self._print_ticket, args=(ticket,), daemon=True).start()
        self._show_confirm(ticket)

    # ---------------------------------------------------------------- check-in lịch hẹn
    def _open_checkin(self):
        if self.busy:
            return
        self._clear_overlay()
        self._overlay_kind = "checkin"
        ov = ctk.CTkFrame(self, fg_color="#0b5fa5", corner_radius=0)
        ov.place(relx=0, rely=0, relwidth=1, relheight=1)
        ctk.CTkLabel(ov, text="NHẬP MÃ LỊCH HẸN", font=(FONT, 40, "bold"),
                     text_color="white").pack(pady=(220, 6))
        ctk.CTkLabel(ov, text="Mã gồm 8 ký tự đã nhận khi đặt lịch online (VD: ABCD-2345)",
                     font=(FONT, 20), text_color="#d6e6f5").pack(pady=(0, 20))
        ent = ctk.CTkEntry(ov, font=(FONT, 40, "bold"), width=520, height=90,
                           justify="center")
        ent.pack()
        ent.focus_set()
        msg = ctk.CTkLabel(ov, text="", font=(FONT, 22), text_color="#fecaca")
        msg.pack(pady=14)

        def submit():
            code = ent.get().strip()
            if not code:
                return
            self.busy = True
            msg.configure(text="Đang kiểm tra...", text_color="#d6e6f5")

            def work():
                try:
                    ticket = self.api.checkin(code)
                    self.after(0, lambda: (self._clear_overlay(), self._on_ticket(ticket)))
                except ApiError as e:
                    self.after(0, lambda: msg.configure(text=str(e), text_color="#fecaca"))
                finally:
                    self.after(0, lambda: setattr(self, "busy", False))

            threading.Thread(target=work, daemon=True).start()

        ent.bind("<Return>", lambda e: submit())
        row = ctk.CTkFrame(ov, fg_color="transparent")
        row.pack(pady=20)
        ctk.CTkButton(row, text="XÁC NHẬN", font=(FONT, 26, "bold"), height=70, width=240,
                      fg_color="#16a34a", hover_color="#15803d", command=submit).pack(side="left", padx=10)
        ctk.CTkButton(row, text="ĐÓNG", font=(FONT, 26, "bold"), height=70, width=200,
                      fg_color="#334155", hover_color="#1e293b",
                      command=self._clear_overlay).pack(side="left", padx=10)
        self.overlay = ov

    def _print_ticket(self, ticket):
        try:
            img = printer.render_ticket(ticket, self.extra, CFG.get("paper_width_mm", 80))
        except Exception as e:  # noqa: BLE001
            self.after(0, lambda: self._toast(f"Lỗi tạo phiếu: {e}", error=True))
            return
        if CFG.get("preview_only") or not printer.has_win_print():
            self.after(0, lambda: printer.show_preview(img, self))
            return
        try:
            printer.print_image(img, CFG.get("printer_name", ""))
        except Exception as e:  # noqa: BLE001
            self.after(0, lambda: (self._toast(f"Không in được: {e}", error=True),
                                   printer.show_preview(img, self)))

    # ---------------------------------------------------------------- overlays
    def _show_confirm(self, ticket):
        self._clear_overlay()
        self._overlay_kind = "confirm"
        ov = ctk.CTkFrame(self, fg_color="#0b5fa5", corner_radius=0)
        ov.place(relx=0, rely=0, relwidth=1, relheight=1)
        ctk.CTkLabel(ov, text="SỐ THỨ TỰ CỦA QUÝ KHÁCH",
                     font=(FONT, 34, "bold"), text_color="white").pack(pady=(180, 10))
        ctk.CTkLabel(ov, text=ticket["full_no"], font=(FONT, 200, "bold"),
                     text_color="white").pack()
        ctk.CTkLabel(ov, text=ticket.get("service_name", ""), font=(FONT, 26),
                     text_color="#d6e6f5", wraplength=800).pack(pady=10)
        ctk.CTkLabel(ov, text=f"Còn {ticket.get('waiting_ahead', 0)} khách chờ trước quý khách",
                     font=(FONT, 28, "bold"), text_color="white").pack(pady=20)
        ctk.CTkLabel(ov, text="Vui lòng giữ phiếu và chờ gọi số",
                     font=(FONT, 22), text_color="#d6e6f5").pack()
        self.overlay = ov
        self.after(int(CFG.get("confirm_seconds", 6)) * 1000, self._clear_overlay)

    def _show_lock(self):
        self._clear_overlay()
        self._overlay_kind = "lock"
        ov = ctk.CTkFrame(self, fg_color="#334155", corner_radius=0)
        ov.place(relx=0, rely=0, relwidth=1, relheight=1)
        ctk.CTkLabel(ov, text="⏰", font=(FONT, 90)).pack(pady=(200, 10))
        ctk.CTkLabel(ov, text="NGOÀI GIỜ LẤY SỐ", font=(FONT, 40, "bold"),
                     text_color="white").pack(pady=10)
        ctk.CTkLabel(ov, text=self.extra.get("lock_message", "Vui lòng quay lại trong giờ làm việc."),
                     font=(FONT, 24), text_color="#e2e8f0", wraplength=800, justify="center").pack(pady=20)
        self.overlay = ov

    def _show_offline(self, msg):
        self.online = False
        if self.overlay and getattr(self, "_overlay_kind", "") == "confirm":
            return
        self._clear_overlay()
        self._overlay_kind = "offline"
        ov = ctk.CTkFrame(self, fg_color="#7f1d1d", corner_radius=0)
        ov.place(relx=0, rely=0, relwidth=1, relheight=1)
        ctk.CTkLabel(ov, text="⚠", font=(FONT, 90), text_color="white").pack(pady=(220, 10))
        ctk.CTkLabel(ov, text="MẤT KẾT NỐI MÁY CHỦ", font=(FONT, 38, "bold"),
                     text_color="white").pack(pady=10)
        ctk.CTkLabel(ov, text=msg, font=(FONT, 20), text_color="#fecaca",
                     wraplength=800, justify="center").pack(pady=16)
        ctk.CTkLabel(ov, text="Hệ thống sẽ tự kết nối lại...", font=(FONT, 20),
                     text_color="#fecaca").pack()
        self.overlay = ov

    def _clear_overlay(self):
        if self.overlay is not None:
            self.overlay.destroy()
            self.overlay = None
        self._overlay_kind = ""

    def _toast(self, text, error=False):
        t = ctk.CTkLabel(self, text=text, font=(FONT, 22, "bold"),
                         fg_color="#b91c1c" if error else "#0b5fa5",
                         text_color="white", corner_radius=12, padx=24, pady=14)
        t.place(relx=0.5, rely=0.9, anchor="center")
        self.after(3500, t.destroy)


def _darken(hex_color, f=0.82):
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02x%02x%02x" % (int(r * f), int(g * f), int(b * f))


if __name__ == "__main__":
    KioskApp().mainloop()
