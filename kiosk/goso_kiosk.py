"""GoSoKiosk — điểm vào lúc chạy thật.

- Bảo đảm thư mục dữ liệu + di trú config cũ.
- Chưa cấu hình -> mở GoSoConfig rồi thoát.
- Đã cấu hình -> chạy giao diện kiosk (app.KioskApp) với callback bốc số THẬT,
  chạy nền: health marker, heartbeat, kiểm tra bản mới -> tự cập nhật.

Dev vẫn chạy được:  python kiosk/goso_kiosk.py
"""
import os
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    if sys.platform == "win32":
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:  # noqa: BLE001
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:  # noqa: BLE001
                pass
except Exception:  # noqa: BLE001
    pass

from goso import appconfig, paths, updater, version  # noqa: E402
from goso.device import get_or_create  # noqa: E402
from goso.logs import get_logger  # noqa: E402
from goso.serverclient import ServerClient  # noqa: E402

_log = get_logger("kiosk")
HEARTBEAT_EVERY_S = 60
UPDATE_CHECK_EVERY_S = 30 * 60


def _run_configurator():
    here = os.path.dirname(os.path.abspath(__file__))
    if getattr(sys, "frozen", False):
        exe = os.path.join(os.path.dirname(sys.executable), "GoSoConfig.exe")
        cmd = [exe] if os.path.isfile(exe) else None
    else:
        cmd = [sys.executable, os.path.join(here, "goso_config.py")]
    if cmd:
        try:
            subprocess.Popen(cmd, cwd=here, close_fds=True)
        except OSError as e:  # noqa: BLE001
            _log.error("Không mở được Configurator: %s", e)


def _background(app, client, cfg, dev):
    ver = version.get_version()

    def heartbeat_loop():
        while True:
            try:
                res = client.heartbeat(
                    device_id=dev["device_id"], name=dev.get("name", ""),
                    version=ver, printer=cfg.get("printer_name", ""),
                    paper_mm=int(cfg.get("paper_width_mm", 80)), status="online")
                rel = (res or {}).get("release")
                if rel:
                    _maybe_update(app, client, rel, ver)
            except Exception as e:  # noqa: BLE001
                _log.debug("heartbeat lỗi (bỏ qua): %s", e)
            time.sleep(HEARTBEAT_EVERY_S)

    def update_loop():
        time.sleep(20)
        while True:
            try:
                _maybe_update(app, client, client.kiosk_version(), ver)
            except Exception as e:  # noqa: BLE001
                _log.debug("check version lỗi (bỏ qua): %s", e)
            time.sleep(UPDATE_CHECK_EVERY_S)

    for fn in (heartbeat_loop, update_loop):
        threading.Thread(target=fn, daemon=True).start()


_updating = threading.Event()


def _maybe_update(app, client, release, current_ver):
    if _updating.is_set():
        return
    plan = updater.check(release or {}, current_ver)
    if not plan:
        return
    _log.info("Có bản mới %s (force=%s). Đang tải...", plan["version"], plan["force"])
    try:
        pkg = updater.download(plan["download_url"], plan["sha256"])
    except RuntimeError as e:  # noqa: BLE001
        _log.error("Tải bản mới thất bại: %s — vẫn chạy bản hiện tại.", e)
        return
    _updating.set()
    app.after(0, lambda: _launch_updater_and_exit(app, pkg, plan["version"]))


def _launch_updater_and_exit(app, pkg, target):
    app_dir = paths.app_dir()
    if getattr(sys, "frozen", False):
        upd = os.path.join(app_dir, "GoSoUpdater.exe")
        kiosk_exe = os.path.join(app_dir, "GoSoKiosk.exe")
        cmd = [upd, "--package", pkg, "--target", target, "--app-dir", app_dir,
               "--kiosk-exe", kiosk_exe, "--pid", str(os.getpid()),
               "--current", version.get_version()]
    else:
        cmd = [sys.executable, os.path.join(app_dir, "goso_updater.py"),
               "--package", pkg, "--target", target, "--app-dir", app_dir,
               "--kiosk-exe", os.path.join(app_dir, "goso_kiosk.py"),
               "--pid", str(os.getpid()), "--current", version.get_version()]
    try:
        subprocess.Popen(cmd, cwd=app_dir, close_fds=True)
        _log.info("Đã khởi chạy GoSoUpdater -> thoát kiosk để thay bản mới.")
    except OSError as e:  # noqa: BLE001
        _log.error("Không chạy được updater: %s", e)
        _updating.clear()
        return
    try:
        app.destroy()
    except Exception:  # noqa: BLE001
        os._exit(0)


def main():
    paths.ensure_dirs()
    appconfig.migrate_if_needed()
    cfg = appconfig.load()

    if not appconfig.is_configured(cfg):
        _log.warning("Chưa cấu hình -> mở GoSoConfig.")
        _run_configurator()
        return

    dev = get_or_create(cfg.get("branch_code", ""), cfg.get("device_name", ""))
    client = ServerClient(cfg["server_url"], cfg["branch_code"], cfg["api_key"])

    import app as kiosk_ui
    flow = _make_flow(client, cfg)
    callbacks = {
        "on_land_procedure":     lambda: flow.take("A"),
        "on_secured_transaction": lambda: flow.take("B"),
        "on_result_return":      lambda: flow.take("C"),
        "on_online_appointment": lambda: flow.checkin_dialog(),
    }
    gui = kiosk_ui.KioskApp(callbacks=callbacks)
    flow.bind_app(gui)

    def ready():
        updater.write_health(version.get_version())
        _background(gui, client, cfg, dev)

    gui.after(3000, ready)
    _log.info("Kiosk khởi động: chi nhánh=%s device=%s version=%s",
              cfg["branch_code"], dev["device_id"], version.get_version())
    gui.mainloop()


class _LazyFlow:
    """Tạo TicketFlow sau khi có app (bind_app)."""
    def __init__(self, client, cfg):
        self.client, self.cfg, self._impl = client, cfg, None

    def bind_app(self, app):
        from goso.ticketflow import TicketFlow
        self._impl = TicketFlow(app, self.client, self.cfg)

    def take(self, p):
        if self._impl:
            self._impl.take(p)

    def checkin_dialog(self):
        if self._impl:
            self._impl.checkin_dialog()


def _make_flow(client, cfg):
    return _LazyFlow(client, cfg)


if __name__ == "__main__":
    main()
