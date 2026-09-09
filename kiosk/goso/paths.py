"""Đường dẫn cho cả 2 chế độ: chạy từ source (dev) và đóng gói PyInstaller (frozen).

Nguyên tắc:
  Program Files  = mã chương trình (thay được khi update)
  ProgramData    = dữ liệu riêng của máy (KHÔNG bị update ghi đè)

  APP_DIR   -> nơi chứa .exe / assets  (dev: thư mục kiosk/)
  DATA_DIR  -> C:\\ProgramData\\GoSoKiosk  (dev: kiosk/.godata/)

Không hard-code đường dẫn chỉ đúng khi frozen.
"""
import os
import sys

APP_NAME = "GoSoKiosk"

_THIS = os.path.dirname(os.path.abspath(__file__))          # .../kiosk/goso
_KIOSK_DIR = os.path.dirname(_THIS)                          # .../kiosk
_REPO_DIR = os.path.dirname(_KIOSK_DIR)                      # .../goiso_kios

FROZEN = bool(getattr(sys, "frozen", False))


def app_dir():
    """Thư mục chứa chương trình + assets."""
    if FROZEN:
        # PyInstaller onedir: cạnh .exe. onefile: dùng _MEIPASS cho tài nguyên đọc.
        return os.path.dirname(sys.executable)
    return _KIOSK_DIR


def resource_dir():
    """Thư mục tài nguyên đọc-chỉ (assets). Frozen onefile -> _MEIPASS."""
    if FROZEN and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS  # noqa: SLF001
    return app_dir()


def data_dir():
    """Thư mục dữ liệu máy (đọc/ghi). Có thể ép bằng env GOSO_DATA_DIR."""
    env = os.environ.get("GOSO_DATA_DIR")
    if env:
        return env
    if FROZEN or os.name == "nt" and os.environ.get("PROGRAMDATA"):
        base = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        return os.path.join(base, APP_NAME)
    # dev: giữ trong repo, đã .gitignore
    return os.path.join(_KIOSK_DIR, ".godata")


def _sub(*parts):
    return os.path.join(data_dir(), *parts)


def config_path():
    return _sub("config.json")


def device_path():
    return _sub("device.json")


def logs_dir():
    return _sub("logs")


def updates_dir():
    return _sub("updates")


def backup_dir():
    return _sub("backup")


def state_dir():
    return _sub("state")


def health_marker_path():
    return os.path.join(state_dir(), "health.json")


def legacy_config_path():
    """config.json cũ đi kèm mã nguồn (bản trước khi tách ProgramData)."""
    return os.path.join(_KIOSK_DIR, "config.json")


def version_file():
    """File VERSION 1 nguồn. Frozen: cạnh exe/_MEIPASS. Dev: gốc repo."""
    for p in (os.path.join(resource_dir(), "VERSION"),
              os.path.join(app_dir(), "VERSION"),
              os.path.join(_REPO_DIR, "VERSION")):
        if os.path.isfile(p):
            return p
    return os.path.join(_REPO_DIR, "VERSION")


def assets_dir():
    """Thư mục assets (logo/nền/icon). Ưu tiên bản dữ liệu máy nếu có (chi nhánh
    tự thay), sau đó tới bản đóng gói theo chương trình."""
    data_assets = _sub("assets")
    if os.path.isdir(data_assets):
        return data_assets
    return os.path.join(resource_dir(), "assets")


def ensure_dirs():
    for d in (data_dir(), logs_dir(), updates_dir(), backup_dir(), state_dir()):
        try:
            os.makedirs(d, exist_ok=True)
        except OSError as e:  # noqa: BLE001
            raise RuntimeError(f"Không tạo được thư mục dữ liệu: {d} ({e})") from e
    return data_dir()
