"""Danh tính thiết bị ổn định — device.json ở ProgramData.

- device_id KHÔNG đổi khi update / khởi động lại.
- Định dạng dễ đọc: <BRANCHCODE>-KIOSK-NN  (NN từ 4 ký tự đầu của uuid ổn định).
- Nếu người cài đặt tên riêng thì tôn trọng.
- Giữ được khi uninstall/reinstall nếu người dùng chọn giữ ProgramData.
"""
import json
import os
import re
import uuid

from . import paths
from .logs import get_logger

_log = get_logger("kiosk")


def _read():
    try:
        with open(paths.device_path(), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _write(d):
    paths.ensure_dirs()
    tmp = paths.device_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(tmp, paths.device_path())


def _slug(s):
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())[:12] or "KIOSK"


def get_or_create(branch_code="", suggested_name=""):
    """Trả về dict {device_id, name, uuid, branch_code}. Tạo mới nếu chưa có."""
    d = _read()
    if not d.get("uuid"):
        d["uuid"] = str(uuid.uuid4())
    if not d.get("device_id"):
        base = _slug(branch_code) or "KIOSK"
        suffix = d["uuid"].split("-")[0][:4].upper()
        d["device_id"] = suggested_name.strip() or f"{base}-KIOSK-{suffix}"
    if branch_code:
        d["branch_code"] = branch_code
    d.setdefault("name", d["device_id"])
    _write(d)
    return d


def set_device_id(device_id, name=None):
    d = _read()
    d.setdefault("uuid", str(uuid.uuid4()))
    d["device_id"] = device_id.strip()
    d["name"] = (name or device_id).strip()
    _write(d)
    return d


def current():
    return _read()
