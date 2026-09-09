"""GoSoConfig — cấu hình kiosk cho một máy (chạy sau khi cài, hoặc mở lại để đổi).

Không cần Python/terminal/JSON. Tái sử dụng: goso.serverclient, printer.py,
goso.appconfig, goso.device, goso.autostart.
"""
import os
import subprocess
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    if sys.platform == "win32":
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:  # noqa: BLE001
            pass
except Exception:  # noqa: BLE001
    pass

import customtkinter as ctk  # noqa: E402

import printer  # noqa: E402  (module có sẵn trong kiosk/)
from goso import appconfig, autostart, device, version  # noqa: E402
from goso.logs import get_logger  # noqa: E402
from goso.serverclient import ServerClient, ServerError  # noqa: E402

_log = get_logger("configurator")
ctk.set_appearance_mode("light")
NAVY = "#123B72"


class ConfigApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"GoSo Kiosk — Cấu hình  (v{version.get_version()})")
        self.geometry("640x760")
        self.minsize(560, 640)

        self.cfg = appconfig.load()
        self.branches = []               # [{code,name,full_name}]
        self._branch_by_label = {}       # "full_name  ·  code" -> branch dict
        self.server_ok = False

        root = ctk.CTkScrollableFrame(self, fg_color="transparent")
        root.pack(fill="both", expand=True, padx=18, pady=14)
        root.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(root, text="CẤU HÌNH MÁY KIOSK", font=("Segoe UI", 20, "bold"),
                     text_color=NAVY).grid(sticky="w", pady=(0, 8))

        # 1 — MÁY CHỦ
        self._section(root, "1. Máy chủ")
        self.e_server = self._entry(root, self.cfg.get("server_url", ""))
        row = ctk.CTkFrame(root, fg_color="transparent"); row.grid(sticky="ew", pady=(2, 2))
        ctk.CTkButton(row, text="KIỂM TRA KẾT NỐI", command=self._check_server).pack(side="left")
        self.lbl_server = ctk.CTkLabel(row, text="", anchor="w"); self.lbl_server.pack(side="left", padx=10)

        # 2 — CHI NHÁNH
        self._section(root, "2. Chi nhánh")
        self.cb_branch = ctk.CTkComboBox(root, values=["— kiểm tra máy chủ trước —"],
                                         state="disabled", command=self._refresh_summary)
        self.cb_branch.grid(sticky="ew", pady=(2, 4))
        ctk.CTkLabel(root, text="API key chi nhánh (X-Branch-Key) — lấy ở trang quản trị:",
                     text_color="#64748b", font=("Segoe UI", 11)).grid(sticky="w")
        self.e_apikey = self._entry(root, self.cfg.get("api_key", ""))
        akrow = ctk.CTkFrame(root, fg_color="transparent"); akrow.grid(sticky="ew", pady=(0, 2))
        ctk.CTkButton(akrow, text="KIỂM TRA KEY", width=120,
                      command=self._check_key).pack(side="left")
        self.lbl_key = ctk.CTkLabel(akrow, text="", anchor="w"); self.lbl_key.pack(side="left", padx=10)

        # 3 — MÁY IN
        self._section(root, "3. Máy in")
        pr = list(_safe(printer.list_printers)) or []
        self.cb_printer = ctk.CTkComboBox(root, values=pr or ["(không tìm thấy máy in)"])
        self.cb_printer.grid(sticky="ew", pady=(2, 4))
        if self.cfg.get("printer_name") and self.cfg["printer_name"] in pr:
            self.cb_printer.set(self.cfg["printer_name"])
        elif pr:
            self.cb_printer.set(pr[0])
        self.paper = ctk.StringVar(value=str(self.cfg.get("paper_width_mm", 80)))
        prow = ctk.CTkFrame(root, fg_color="transparent"); prow.grid(sticky="w", pady=(0, 2))
        ctk.CTkRadioButton(prow, text="58 mm", variable=self.paper, value="58").pack(side="left", padx=(0, 16))
        ctk.CTkRadioButton(prow, text="80 mm", variable=self.paper, value="80").pack(side="left")
        self.v_preview = ctk.BooleanVar(value=bool(self.cfg.get("preview_only", False)))
        ctk.CTkCheckBox(root, text="Chỉ xem trước, không in", variable=self.v_preview).grid(sticky="w", pady=(4, 2))
        trow = ctk.CTkFrame(root, fg_color="transparent"); trow.grid(sticky="ew", pady=(2, 2))
        ctk.CTkButton(trow, text="IN THỬ", command=self._test_print).pack(side="left")
        self.lbl_print = ctk.CTkLabel(trow, text="", anchor="w"); self.lbl_print.pack(side="left", padx=10)

        # 4 — KIOSK
        self._section(root, "4. Cấu hình kiosk")
        self.v_full = ctk.BooleanVar(value=bool(self.cfg.get("fullscreen", True)))
        self.v_auto = ctk.BooleanVar(value=bool(self.cfg.get("autostart", autostart.is_enabled())))
        ctk.CTkCheckBox(root, text="Toàn màn hình", variable=self.v_full).grid(sticky="w", pady=2)
        ctk.CTkCheckBox(root, text="Tự chạy khi Windows khởi động", variable=self.v_auto).grid(sticky="w", pady=2)
        adv = ctk.CTkFrame(root, fg_color="transparent"); adv.grid(sticky="ew", pady=(6, 0))
        ctk.CTkLabel(adv, text="Cài đặt nâng cao:", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        self.e_cols = self._mini(adv, "Số cột nút dịch vụ", self.cfg.get("columns", 2))
        self.e_refresh = self._mini(adv, "Làm mới cấu hình (giây)", self.cfg.get("refresh_seconds", 20))
        self.e_confirm = self._mini(adv, "Hiện màn xác nhận (giây)", self.cfg.get("confirm_seconds", 6))
        self.e_font = self._mini(adv, "Font", self.cfg.get("font_family", "Arial"), width=140)

        # 5 — THIẾT BỊ
        self._section(root, "5. Mã thiết bị (Device ID)")
        dev = device.current() or {}
        self.e_device = self._entry(root, dev.get("device_id", self.cfg.get("device_id", "")))
        ctk.CTkLabel(root, text="Không đổi khi cập nhật. Nên đặt duy nhất, vd BMT-KIOSK-01.",
                     text_color="#64748b", font=("Segoe UI", 11)).grid(sticky="w")

        # 6 — LƯU
        self._section(root, "6. Hoàn tất")
        self.lbl_summary = ctk.CTkLabel(root, text="", justify="left", anchor="w",
                                        font=("Segoe UI", 12)); self.lbl_summary.grid(sticky="w", pady=(0, 6))
        self.lbl_msg = ctk.CTkLabel(root, text="", anchor="w"); self.lbl_msg.grid(sticky="w")
        ctk.CTkButton(root, text="LƯU VÀ CHẠY KIOSK", height=44, font=("Segoe UI", 15, "bold"),
                      command=self._save_and_run).grid(sticky="ew", pady=(6, 4))
        ctk.CTkButton(root, text="Chỉ lưu (không chạy)", fg_color="#94a3b8",
                      command=lambda: self._save_and_run(run=False)).grid(sticky="ew")

        self._refresh_summary()
        if self.cfg.get("server_url"):
            self.after(200, self._check_server)

    # ---------------------------------------------------------------- helpers UI
    def _section(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=("Segoe UI", 14, "bold"),
                     text_color=NAVY).grid(sticky="w", pady=(14, 2))

    def _entry(self, parent, value=""):
        e = ctk.CTkEntry(parent); e.grid(sticky="ew", pady=(2, 2)); e.insert(0, str(value or ""))
        return e

    def _mini(self, parent, label, value, width=90):
        r = ctk.CTkFrame(parent, fg_color="transparent"); r.pack(anchor="w", pady=1)
        ctk.CTkLabel(r, text=label + ":", width=200, anchor="w").pack(side="left")
        e = ctk.CTkEntry(r, width=width); e.pack(side="left"); e.insert(0, str(value))
        return e

    def _msg(self, text, ok=True):
        self.lbl_msg.configure(text=text, text_color="#15803d" if ok else "#b91c1c")

    # ---------------------------------------------------------------- actions
    def _check_server(self):
        # Đọc widget Ở LUỒNG CHÍNH rồi mới sang luồng phụ (tkinter không thread-safe).
        url = self.e_server.get().strip()
        api_key = self.cfg.get("api_key", "")
        self.lbl_server.configure(text="Đang kiểm tra...", text_color="#64748b")
        self.server_ok = False

        def work():
            try:
                cli = ServerClient(url, "", api_key)
                info = cli.ping()
                self.after(0, lambda: self._server_done(
                    True, f"✓ Kết nối OK (server v{info.get('server_version','?')})"))
                brs = cli.branches()
                self.after(0, lambda: self._fill_branches(brs))
            except ServerError as e:
                self.after(0, lambda: self._server_done(False, f"✗ {e}"))

        threading.Thread(target=work, daemon=True).start()

    def _server_done(self, ok, text):
        self.server_ok = ok
        self.lbl_server.configure(text=text, text_color="#15803d" if ok else "#b91c1c")
        self._refresh_summary()

    def _check_key(self):
        b = self._selected_branch()
        url = self.e_server.get().strip()
        key = self.e_apikey.get().strip()
        dev_id = self.e_device.get().strip() or "GOSOCONFIG"
        if not b:
            self.lbl_key.configure(text="Chọn chi nhánh trước.", text_color="#b91c1c"); return
        self.lbl_key.configure(text="Đang kiểm tra...", text_color="#64748b")

        def work():
            state, msg = ServerClient(url, b["code"], key).verify_branch_key(dev_id)
            color = {"ok": "#15803d", "bad": "#b91c1c"}.get(state, "#a16207")
            self.after(0, lambda: self.lbl_key.configure(text=msg, text_color=color))

        threading.Thread(target=work, daemon=True).start()

    PLACEHOLDER = "— chọn chi nhánh —"

    def _fill_branches(self, brs):
        self.branches = brs or []
        if not brs:
            self._branch_by_label = {}
            self.cb_branch.configure(values=["(máy chủ chưa có chi nhánh)"], state="readonly")
            self.cb_branch.set("(máy chủ chưa có chi nhánh)")
            return
        labels = [f"{b['full_name']}  ·  {b['code']}" for b in brs]
        self._branch_by_label = dict(zip(labels, brs))
        self.cb_branch.configure(values=[self.PLACEHOLDER] + labels, state="readonly")
        # Giữ nguyên lựa chọn đang có nếu hợp lệ; nếu chưa có thì theo branch_code đã lưu.
        keep = self.cb_branch.get()
        if keep in self._branch_by_label:
            self.cb_branch.set(keep)
        else:
            cur = (self.cfg.get("branch_code") or "").lower()
            match = next((l for l, b in zip(labels, brs) if b["code"].lower() == cur), None)
            self.cb_branch.set(match or self.PLACEHOLDER)
        self._refresh_summary()

    def _selected_branch(self):
        return self._branch_by_label.get(self.cb_branch.get())

    def _test_print(self):
        name = self.cb_printer.get().strip()
        paper = int(self.paper.get())
        ticket = {"full_no": "A-001", "prefix": "A", "number": 1,
                  "service_name": "PHIẾU IN THỬ — KIỂM TRA MÁY IN", "waiting_ahead": 0,
                  "date_record": "", "session": ""}
        extra = {"ten_co_quan": "VĂN PHÒNG ĐĂNG KÝ ĐẤT ĐAI",
                 "ten_chi_nhanh": (self._selected_branch() or {}).get("full_name", "IN THỬ")}
        try:
            img = printer.render_ticket(ticket, extra, paper)
        except Exception as e:  # noqa: BLE001
            self.lbl_print.configure(text=f"✗ Lỗi tạo phiếu: {e}", text_color="#b91c1c"); return
        if self.v_preview.get() or not _safe(printer.has_win_print):
            _safe(lambda: printer.show_preview(img, self))
            self.lbl_print.configure(text="Đã mở cửa sổ xem trước.", text_color="#64748b"); return
        try:
            printer.print_image(img, name)
            self.lbl_print.configure(text="✓ Đã gửi lệnh in. Kiểm tra phiếu.", text_color="#15803d")
        except Exception as e:  # noqa: BLE001
            self.lbl_print.configure(text=f"✗ Không in được: {e}", text_color="#b91c1c")

    def _refresh_summary(self, *_):
        b = self._selected_branch()
        self.lbl_summary.configure(text=(
            f"Chi nhánh : {b['full_name'] if b else '(chưa chọn)'}\n"
            f"Máy chủ   : {self.e_server.get().strip()}\n"
            f"Device ID : {self.e_device.get().strip() or '(tự sinh)'}\n"
            f"Máy in    : {self.cb_printer.get()}   |   Khổ giấy: {self.paper.get()} mm\n"
            f"Phiên bản : {version.get_version()}"))

    def _save_and_run(self, run=True):
        self._refresh_summary()
        server = self.e_server.get().strip()
        b = self._selected_branch()
        key = self.e_apikey.get().strip()
        if not server:
            return self._msg("Chưa nhập địa chỉ máy chủ.", False)
        if not self.server_ok:
            return self._msg("Chưa kiểm tra kết nối máy chủ thành công.", False)
        if not b:
            return self._msg("Chưa chọn chi nhánh.", False)
        if not key:
            return self._msg("Chưa nhập API key chi nhánh (X-Branch-Key).", False)
        if not self.v_preview.get() and self.cb_printer.get().startswith("("):
            return self._msg("Chưa chọn máy in (hoặc bật 'Chỉ xem trước').", False)

        dev = device.set_device_id(self.e_device.get().strip() or
                                   device.get_or_create(b["code"])["device_id"])
        state, kmsg = ServerClient(server, b["code"], key).verify_branch_key(dev["device_id"])
        if state == "bad":
            return self._msg(kmsg + " — kiểm tra lại ở trang quản trị.", False)
        try:
            cfg = appconfig.load()
            cfg.update({
                "server_url": server,
                "branch_code": b["code"], "branch_id": b["id"],
                "api_key": key,
                "printer_name": "" if self.cb_printer.get().startswith("(") else self.cb_printer.get().strip(),
                "paper_width_mm": int(self.paper.get()),
                "preview_only": bool(self.v_preview.get()),
                "fullscreen": bool(self.v_full.get()),
                "autostart": bool(self.v_auto.get()),
                "columns": _int(self.e_cols.get(), 2),
                "refresh_seconds": _int(self.e_refresh.get(), 20),
                "confirm_seconds": _int(self.e_confirm.get(), 6),
                "font_family": self.e_font.get().strip() or "Arial",
                "device_id": dev["device_id"],
                "device_name": dev.get("name", dev["device_id"]),
                # đồng bộ các chữ hiển thị theo chi nhánh cho giao diện kiosk
                "branch_name": b["full_name"],
            })
            appconfig.save(cfg)
            autostart.apply(bool(self.v_auto.get()))
        except Exception as e:  # noqa: BLE001
            _log.exception("Lưu cấu hình lỗi")
            return self._msg(f"Lưu lỗi: {e}", False)

        self._msg("✓ Đã lưu cấu hình.", True)
        _log.info("Đã lưu cấu hình cho chi nhánh %s, device %s", b["code"], dev["device_id"])
        if run:
            self.after(400, self._launch_kiosk)

    def _launch_kiosk(self):
        here = os.path.dirname(os.path.abspath(__file__))
        if getattr(sys, "frozen", False):
            exe = os.path.join(os.path.dirname(sys.executable), "GoSoKiosk.exe")
            cmd = [exe] if os.path.isfile(exe) else None
        else:
            cmd = [sys.executable, os.path.join(here, "goso_kiosk.py")]
        try:
            if cmd:
                subprocess.Popen(cmd, cwd=here, close_fds=True)
                self.destroy()
        except OSError as e:  # noqa: BLE001
            self._msg(f"Không chạy được kiosk: {e}", False)


def _safe(fn):
    try:
        return fn()
    except Exception:  # noqa: BLE001
        return None


def _int(s, default):
    try:
        return int(str(s).strip())
    except (ValueError, TypeError):
        return default


def main():
    appconfig.migrate_if_needed()
    ConfigApp().mainloop()


if __name__ == "__main__":
    main()
