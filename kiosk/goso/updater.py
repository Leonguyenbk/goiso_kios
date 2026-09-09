"""Tự cập nhật an toàn: tải -> kiểm SHA256 -> sao lưu -> thay -> chạy lại ->
health check -> rollback nếu hỏng. Chống ZIP path traversal & vòng lặp update.

Program Files = binaries (được thay).  ProgramData = config/device/logs (KHÔNG đụng).

Dùng ở 2 nơi:
- goso_kiosk.py : gọi check()/download() ; khi sẵn sàng thì spawn GoSoUpdater.
- goso_updater.py : gọi apply_package() trong tiến trình RIÊNG.
"""
import hashlib
import json
import os
import shutil
import time
import zipfile

import requests

from . import paths, version
from .logs import get_logger

_log = get_logger("updater")

HEALTH_TIMEOUT_S = 90        # chờ bản mới tạo health marker
DOWNLOAD_TIMEOUT_S = 60
MAX_ATTEMPTS_PER_VERSION = 2  # sau đó coi version đó là "hỏng", không thử lại


# --------------------------------------------------------------- loop guard
def _attempts_path():
    return os.path.join(paths.state_dir(), "update_attempts.json")


def _load_attempts():
    try:
        with open(_attempts_path(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_attempts(d):
    paths.ensure_dirs()
    tmp = _attempts_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _attempts_path())


def mark_attempt(ver, result):
    d = _load_attempts()
    e = d.get(ver, {"attempts": 0})
    e["attempts"] = int(e.get("attempts", 0)) + (1 if result == "start" else 0)
    e["last"] = time.strftime("%Y-%m-%d %H:%M:%S")
    e["result"] = result
    d[ver] = e
    _save_attempts(d)


def _blocked(ver):
    e = _load_attempts().get(ver, {})
    if e.get("result") == "failed" and int(e.get("attempts", 0)) >= MAX_ATTEMPTS_PER_VERSION:
        return True
    return False


# --------------------------------------------------------------- check
def check(release: dict, current_version: str):
    """release = dict từ /api/kiosk/version. Trả về release (đã bổ sung 'force')
    nếu NÊN cập nhật, ngược lại None."""
    latest = (release or {}).get("version", "").strip()
    if not latest or not release.get("download_url") or not release.get("sha256"):
        return None
    if not version.is_newer(latest, current_version):
        return None
    minv = (release.get("min_supported_version") or "").strip()
    force = bool(release.get("mandatory")) or (
        minv and version.cmp(current_version, minv) < 0)
    if _blocked(latest) and not force:
        _log.warning("Bỏ qua bản %s: đã thất bại nhiều lần (loop guard).", latest)
        return None
    out = dict(release)
    out["force"] = force
    return out


# --------------------------------------------------------------- download
def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url, expected_sha256, dest_dir=None):
    """Tải .tmp -> đổi tên khi xong -> kiểm SHA256. Trả về đường dẫn zip đã xác minh.
    Ném RuntimeError nếu bất kỳ bước nào lỗi (KHÔNG cập nhật)."""
    dest_dir = dest_dir or paths.updates_dir()
    os.makedirs(dest_dir, exist_ok=True)
    name = os.path.basename(url.split("?")[0]) or "update.zip"
    if not name.lower().endswith(".zip"):
        name += ".zip"
    tmp = os.path.join(dest_dir, name + ".tmp")
    final = os.path.join(dest_dir, name)
    for p in (tmp, final):
        try:
            os.remove(p)
        except OSError:
            pass
    try:
        with requests.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT_S) as r:
            r.raise_for_status()
            clen = int(r.headers.get("Content-Length") or 0)
            got = 0
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(1 << 16):
                    if chunk:
                        f.write(chunk)
                        got += len(chunk)
        if clen and got != clen:
            raise RuntimeError(f"Tải thiếu: {got}/{clen} byte")
        if not os.path.isfile(tmp) or os.path.getsize(tmp) == 0:
            raise RuntimeError("File tải về rỗng")
        actual = _sha256(tmp)
        if actual.lower() != str(expected_sha256).lower():
            raise RuntimeError(f"SHA256 sai (mong đợi {expected_sha256}, nhận {actual})")
        os.replace(tmp, final)
        _log.info("Đã tải & xác minh: %s (%d byte)", final, os.path.getsize(final))
        return final
    except Exception as e:  # noqa: BLE001
        for p in (tmp, final):
            try:
                os.remove(p)
            except OSError:
                pass
        _log.error("Tải update lỗi: %s", e)
        raise RuntimeError(str(e)) from e


# --------------------------------------------------------------- safe extract
def _safe_members(zf, root):
    root = os.path.realpath(root)
    for m in zf.infolist():
        n = m.filename.replace("\\", "/")
        if n.startswith("/") or ".." in n.split("/") or (len(n) > 1 and n[1] == ":"):
            raise RuntimeError(f"ZIP chứa đường dẫn không hợp lệ: {m.filename!r}")
        target = os.path.realpath(os.path.join(root, n))
        if target != root and not target.startswith(root + os.sep):
            raise RuntimeError(f"ZIP cố ghi ra ngoài thư mục: {m.filename!r}")
        yield m


def _extract(zip_path, dest_root):
    with zipfile.ZipFile(zip_path) as zf:
        members = list(_safe_members(zf, dest_root))  # xác thực trước khi ghi
        for m in members:
            zf.extract(m, dest_root)


# --------------------------------------------------------------- apply (updater proc)
def _dir_copy(src, dst):
    if os.path.isdir(dst):
        shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(src, dst)


def _wait_pid_gone(pid, timeout=30):
    if not pid:
        return
    end = time.time() + timeout
    while time.time() < end:
        if not _pid_alive(pid):
            return
        time.sleep(0.5)


def _pid_alive(pid):
    try:
        if os.name == "nt":
            import ctypes
            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
            if not h:
                return False
            ctypes.windll.kernel32.CloseHandle(h)
            return True
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError):
        return False


def _read_health():
    try:
        with open(paths.health_marker_path(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def write_health(ver, status="ready"):
    """Kiosk gọi khi đã khởi động tới trạng thái an toàn."""
    paths.ensure_dirs()
    tmp = paths.health_marker_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"version": ver, "status": status,
                   "ts": time.time(), "at": time.strftime("%Y-%m-%d %H:%M:%S")}, f)
    os.replace(tmp, paths.health_marker_path())


def apply_package(package_zip, target_version, app_dir, kiosk_exe,
                  kiosk_pid=None, current_version=None):
    """Chạy TRONG tiến trình updater riêng. Trả 0 nếu OK, khác 0 nếu rollback."""
    import subprocess

    current_version = current_version or version.get_version()
    _log.info("=== UPDATE %s -> %s ===", current_version, target_version)
    _log.info("package=%s app_dir=%s exe=%s", package_zip, app_dir, kiosk_exe)
    paths.ensure_dirs()
    mark_attempt(target_version, "start")

    if not os.path.isfile(package_zip):
        _log.error("Không thấy package: %s", package_zip)
        return 2
    backup = os.path.join(paths.backup_dir(), current_version)

    _wait_pid_gone(kiosk_pid, 40)
    if _pid_alive(kiosk_pid):
        _log.warning("Kiosk (pid %s) chưa thoát — tiếp tục thận trọng.", kiosk_pid)

    try:
        _log.info("Sao lưu %s -> %s", app_dir, backup)
        _dir_copy(app_dir, backup)
    except OSError as e:  # noqa: BLE001
        _log.error("Sao lưu lỗi: %s — HỦY update.", e)
        _start(kiosk_exe)
        mark_attempt(target_version, "failed")
        return 3

    try:
        _log.info("Giải nén đè lên %s", app_dir)
        _extract(package_zip, app_dir)
    except Exception as e:  # noqa: BLE001
        _log.error("Giải nén lỗi: %s — ROLLBACK.", e)
        _rollback(backup, app_dir)
        _start(kiosk_exe)
        mark_attempt(target_version, "failed")
        return 4

    # xoá health cũ rồi chạy bản mới
    try:
        os.remove(paths.health_marker_path())
    except OSError:
        pass
    started_at = time.time()
    _start(kiosk_exe)

    _log.info("Chờ health marker (<= %ds)...", HEALTH_TIMEOUT_S)
    ok = False
    while time.time() - started_at < HEALTH_TIMEOUT_S:
        h = _read_health()
        if (h.get("status") == "ready" and h.get("ts", 0) >= started_at
                and version.parse(h.get("version")) == version.parse(target_version)):
            ok = True
            break
        time.sleep(1.0)

    if ok:
        _log.info("HEALTH OK — update %s thành công.", target_version)
        mark_attempt(target_version, "success")
        try:
            os.remove(package_zip)
        except OSError:
            pass
        return 0

    _log.error("Bản %s KHÔNG health trong %ds — ROLLBACK.", target_version, HEALTH_TIMEOUT_S)
    _kill_kiosk_by_exe(kiosk_exe)
    _rollback(backup, app_dir)
    _start(kiosk_exe)
    mark_attempt(target_version, "failed")
    return 5


def _rollback(backup, app_dir):
    try:
        if os.path.isdir(backup):
            _dir_copy(backup, app_dir)
            _log.info("Đã khôi phục bản trước từ %s", backup)
    except OSError as e:  # noqa: BLE001
        _log.error("Rollback lỗi: %s", e)


def _start(exe):
    import subprocess
    try:
        subprocess.Popen([exe], cwd=os.path.dirname(exe) or None,
                         close_fds=True)
        _log.info("Đã chạy: %s", exe)
    except OSError as e:  # noqa: BLE001
        _log.error("Không chạy được %s: %s", exe, e)


def _kill_kiosk_by_exe(exe):
    if os.name != "nt":
        return
    import subprocess
    try:
        subprocess.run(["taskkill", "/F", "/IM", os.path.basename(exe)],
                       capture_output=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        pass
