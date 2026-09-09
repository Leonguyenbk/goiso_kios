"""Tự khởi động cùng Windows — dùng khoá Run của NGƯỜI DÙNG HIỆN TẠI (HKCU).

- Không cần quyền Administrator.
- Bật/tắt idempotent (không tạo entry trùng).
- Trỏ tới đường dẫn hiện tại của chương trình (đúng sau khi cài vào Program Files;
  cũng đúng khi chạy dev — trỏ tới python + script).
"""
import os
import sys

from .logs import get_logger

_log = get_logger("kiosk")
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_NAME = "GoSoKiosk"


def _target_command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    # dev: python <thư mục kiosk>/goso_kiosk.py
    script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "goso_kiosk.py")
    return f'"{sys.executable}" "{script}"'


def is_enabled():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as k:
            winreg.QueryValueEx(k, _NAME)
        return True
    except (OSError, ImportError):
        return False


def enable():
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as k:
            winreg.SetValueEx(k, _NAME, 0, winreg.REG_SZ, _target_command())
        _log.info("Đã bật tự khởi động: %s", _target_command())
        return True
    except (OSError, ImportError) as e:  # noqa: BLE001
        _log.error("Không bật được tự khởi động: %s", e)
        return False


def disable():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, _NAME)
        _log.info("Đã tắt tự khởi động.")
    except FileNotFoundError:
        pass
    except (OSError, ImportError) as e:  # noqa: BLE001
        _log.error("Không tắt được tự khởi động: %s", e)
    return True


def apply(enabled):
    return enable() if enabled else disable()
