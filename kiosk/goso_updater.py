"""GoSoUpdater — tiến trình RIÊNG thực hiện thay bản mới.

GoSoKiosk gọi:
    GoSoUpdater.exe --package <zip> --target 1.0.7 --app-dir "<Program Files\\GoSo Kiosk>"
                    --kiosk-exe "<...\\GoSoKiosk.exe>" --pid <kiosk_pid> [--current 1.0.6]

Chỉ nhận tham số CỐ ĐỊNH ở trên — KHÔNG chạy lệnh tuỳ ý do server truyền vào.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from goso import updater, version  # noqa: E402
from goso.logs import get_logger  # noqa: E402

_log = get_logger("updater")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="GoSoUpdater", add_help=True)
    ap.add_argument("--package", required=True, help="đường dẫn file .zip đã tải & xác minh")
    ap.add_argument("--target", required=True, help="version đích, vd 1.0.7")
    ap.add_argument("--app-dir", required=True, help="thư mục cài đặt (Program Files)")
    ap.add_argument("--kiosk-exe", required=True, help="đường dẫn GoSoKiosk.exe")
    ap.add_argument("--pid", type=int, default=0, help="PID kiosk đang chạy (để chờ thoát)")
    ap.add_argument("--current", default="", help="version hiện tại")
    a = ap.parse_args(argv)

    for p, label in ((a.package, "package"), (a.app_dir, "app-dir"),
                     (os.path.dirname(a.kiosk_exe), "kiosk-exe dir")):
        if not os.path.exists(p):
            _log.error("Không tồn tại %s: %s", label, p)
            return 2

    rc = updater.apply_package(
        package_zip=os.path.abspath(a.package),
        target_version=a.target,
        app_dir=os.path.abspath(a.app_dir),
        kiosk_exe=os.path.abspath(a.kiosk_exe),
        kiosk_pid=a.pid or None,
        current_version=a.current or version.get_version(),
    )
    _log.info("GoSoUpdater kết thúc, mã %s", rc)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
