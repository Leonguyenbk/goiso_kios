"""Luồng bốc số thật cho giao diện kiosk mới — TÁI SỬ DỤNG printer.py + ServerClient.

Không thay đổi nghiệp vụ server: vẫn gọi POST /api/b/<mã>/ticket và /checkin.
Chỉ ghép: bấm thẻ -> gọi server -> in phiếu -> hiện màn xác nhận (overlay).
"""
import threading

import customtkinter as ctk

import printer
from .logs import get_logger

_log = get_logger("kiosk")
NAVY = "#0b5fa5"


class TicketFlow:
    def __init__(self, app, client, cfg):
        self.app = app
        self.client = client
        self.cfg = cfg
        self.busy = False
        self._overlay = None
        self._extra = {"ten_co_quan": "VĂN PHÒNG ĐĂNG KÝ ĐẤT ĐAI",
                       "ten_chi_nhanh": cfg.get("branch_name", "")}

    # -------------------------------------------------- công khai
    def take(self, prefix):
        if self.busy:
            return
        self.busy = True

        def work():
            try:
                ticket = self.client.take_ticket(prefix)
                self.app.after(0, lambda: self._on_ticket(ticket))
            except Exception as e:  # noqa: BLE001
                self.app.after(0, lambda: self._toast(str(e), error=True))
            finally:
                self.app.after(0, lambda: setattr(self, "busy", False))

        threading.Thread(target=work, daemon=True).start()

    def checkin_dialog(self):
        if self.busy:
            return
        self._clear()
        ov = ctk.CTkFrame(self.app, fg_color=NAVY, corner_radius=0)
        ov.place(relx=0, rely=0, relwidth=1, relheight=1)
        ctk.CTkLabel(ov, text="NHẬP MÃ LỊCH HẸN", font=("Arial", 40, "bold"),
                     text_color="white").pack(pady=(200, 6))
        ctk.CTkLabel(ov, text="Mã 8 ký tự nhận khi đặt lịch online (VD: ABCD-2345)",
                     font=("Arial", 20), text_color="#d6e6f5").pack(pady=(0, 18))
        ent = ctk.CTkEntry(ov, font=("Arial", 40, "bold"), width=520, height=88, justify="center")
        ent.pack(); ent.focus_set()
        msg = ctk.CTkLabel(ov, text="", font=("Arial", 20), text_color="#fecaca"); msg.pack(pady=12)

        def submit():
            code = ent.get().strip()
            if not code or self.busy:
                return
            self.busy = True
            msg.configure(text="Đang kiểm tra...", text_color="#d6e6f5")

            def work():
                try:
                    t = self.client.checkin(code)
                    self.app.after(0, lambda: (self._clear(), self._on_ticket(t)))
                except Exception as e:  # noqa: BLE001
                    self.app.after(0, lambda: msg.configure(text=str(e), text_color="#fecaca"))
                finally:
                    self.app.after(0, lambda: setattr(self, "busy", False))

            threading.Thread(target=work, daemon=True).start()

        ent.bind("<Return>", lambda e: submit())
        row = ctk.CTkFrame(ov, fg_color="transparent"); row.pack(pady=18)
        ctk.CTkButton(row, text="XÁC NHẬN", font=("Arial", 24, "bold"), height=66, width=220,
                      fg_color="#16a34a", command=submit).pack(side="left", padx=10)
        ctk.CTkButton(row, text="ĐÓNG", font=("Arial", 24, "bold"), height=66, width=180,
                      fg_color="#334155", command=self._clear).pack(side="left", padx=10)
        self._overlay = ov

    # -------------------------------------------------- nội bộ
    def _on_ticket(self, ticket):
        if not isinstance(ticket, dict) or "full_no" not in ticket:
            self._toast("Máy chủ trả dữ liệu không hợp lệ.", error=True)
            return
        threading.Thread(target=self._print, args=(ticket,), daemon=True).start()
        self._show_confirm(ticket)

    def _print(self, ticket):
        try:
            img = printer.render_ticket(ticket, self._extra, self.cfg.get("paper_width_mm", 80))
        except Exception as e:  # noqa: BLE001
            _log.error("render_ticket lỗi: %s", e)
            return
        if self.cfg.get("preview_only") or not _safe(printer.has_win_print):
            self.app.after(0, lambda: _safe(lambda: printer.show_preview(img, self.app)))
            return
        try:
            printer.print_image(img, self.cfg.get("printer_name", ""))
        except Exception as e:  # noqa: BLE001
            _log.error("print_image lỗi: %s", e)
            self.app.after(0, lambda: _safe(lambda: printer.show_preview(img, self.app)))

    def _show_confirm(self, ticket):
        self._clear()
        ov = ctk.CTkFrame(self.app, fg_color=NAVY, corner_radius=0)
        ov.place(relx=0, rely=0, relwidth=1, relheight=1)
        ctk.CTkLabel(ov, text="SỐ THỨ TỰ CỦA QUÝ KHÁCH", font=("Arial", 34, "bold"),
                     text_color="white").pack(pady=(170, 10))
        ctk.CTkLabel(ov, text=ticket["full_no"], font=("Arial", 200, "bold"),
                     text_color="white").pack()
        ctk.CTkLabel(ov, text=ticket.get("service_name", ""), font=("Arial", 26),
                     text_color="#d6e6f5", wraplength=900).pack(pady=10)
        ctk.CTkLabel(ov, text=f"Còn {ticket.get('waiting_ahead', 0)} khách chờ trước quý khách",
                     font=("Arial", 28, "bold"), text_color="white").pack(pady=18)
        ctk.CTkLabel(ov, text="Vui lòng giữ phiếu và chờ gọi số",
                     font=("Arial", 22), text_color="#d6e6f5").pack()
        self._overlay = ov
        self.app.after(int(self.cfg.get("confirm_seconds", 6)) * 1000, self._clear)

    def _clear(self, *_):
        if self._overlay is not None:
            try:
                self._overlay.destroy()
            except Exception:  # noqa: BLE001
                pass
            self._overlay = None

    def _toast(self, text, error=False):
        t = ctk.CTkLabel(self.app, text=text, font=("Arial", 22, "bold"),
                         fg_color="#b91c1c" if error else NAVY, text_color="white",
                         corner_radius=12, padx=24, pady=14)
        t.place(relx=0.5, rely=0.88, anchor="center")
        self.app.after(3800, t.destroy)


def _safe(fn):
    try:
        return fn()
    except Exception:  # noqa: BLE001
        return None
