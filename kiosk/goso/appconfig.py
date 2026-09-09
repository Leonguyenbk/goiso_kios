"""Đọc/ghi cấu hình MÁY (config.json) + di trú từ bản cũ đi kèm mã nguồn.

- Ưu tiên: ProgramData\\GoSoKiosk\\config.json
- Lần đầu chưa có nhưng thấy kiosk/config.json cũ hợp lệ  -> copy sang ProgramData.
- Giữ NGUYÊN mọi khoá cũ mà kiosk đang dùng (server_url, printer_name, ...).
- Ghi file kiểu atomic (tmp + os.replace) để không hỏng config khi mất điện.
"""
import json
import os
import shutil

from . import paths
from .logs import get_logger

_log = get_logger("kiosk")

# Khoá kỹ thuật + mặc định an toàn. KHÔNG xoá khoá cũ; chỉ bổ sung khoá thiếu.
DEFAULTS = {
    "server_url":       "http://127.0.0.1:5050",
    "branch_code":      "",
    "branch_id":        None,
    "api_key":          "",
    "printer_name":     "",
    "paper_width_mm":   80,
    "preview_only":     False,
    "fullscreen":       True,
    "columns":          2,
    "refresh_seconds":  20,
    "confirm_seconds":  6,
    "font_family":      "Arial",
    "device_id":        "",
    "device_name":      "",
    "autostart":        False,
}

# Khoá tối thiểu để coi 1 config là "đã cấu hình xong" (đủ chạy kiosk).
REQUIRED = ("server_url", "branch_code", "api_key")


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, OSError) as e:  # noqa: BLE001
        _log.warning("config.json lỗi (%s): %s — bỏ qua, KHÔNG ghi đè.", path, e)
        return {}


def migrate_if_needed():
    """Copy config cũ (kiosk/config.json) sang ProgramData nếu chưa có bản mới."""
    try:
        paths.ensure_dirs()
    except RuntimeError as e:
        _log.error("%s", e)
        return
    dst = paths.config_path()
    if os.path.isfile(dst):
        return
    legacy = paths.legacy_config_path()
    old = _read_json(legacy)
    if old:
        try:
            shutil.copy2(legacy, dst)
            _log.info("Đã di trú config cũ: %s -> %s", legacy, dst)
        except OSError as e:  # noqa: BLE001
            _log.error("Không di trú được config: %s", e)


def load():
    """Trả về dict cấu hình đầy đủ (DEFAULTS <- file)."""
    migrate_if_needed()
    data = _read_json(paths.config_path()) or {}
    merged = dict(DEFAULTS)
    merged.update(data)
    return merged


def save(cfg):
    """Ghi atomic vào ProgramData\\GoSoKiosk\\config.json."""
    paths.ensure_dirs()
    dst = paths.config_path()
    tmp = dst + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, dst)
    _log.info("Đã lưu config: %s", dst)


def is_configured(cfg=None):
    cfg = cfg or load()
    return all(str(cfg.get(k) or "").strip() for k in REQUIRED)


def update(**fields):
    cfg = load()
    cfg.update({k: v for k, v in fields.items() if v is not None})
    save(cfg)
    return cfg
