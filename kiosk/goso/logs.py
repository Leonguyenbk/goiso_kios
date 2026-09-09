"""Log xoay vòng cho từng thành phần, ghi vào ProgramData\\GoSoKiosk\\logs.

Không ghi secret/token. Console handler chỉ bật khi chạy từ source (dev).
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from . import paths

_CONFIGURED = set()
_FMT = "%(asctime)s %(levelname)-7s [%(name)s] %(message)s"


def get_logger(component="kiosk", *, to_console=None):
    """component: 'kiosk' | 'configurator' | 'updater'."""
    name = f"goso.{component}"
    logger = logging.getLogger(name)
    if name in _CONFIGURED:
        return logger
    logger.setLevel(logging.INFO)
    try:
        os.makedirs(paths.logs_dir(), exist_ok=True)
        fh = RotatingFileHandler(
            os.path.join(paths.logs_dir(), f"{component}.log"),
            maxBytes=1_000_000, backupCount=5, encoding="utf-8")
        fh.setFormatter(logging.Formatter(_FMT))
        logger.addHandler(fh)
    except OSError as e:  # noqa: BLE001
        print(f"[logs] Không mở được file log: {e}", file=sys.stderr)
    if to_console is None:
        to_console = not paths.FROZEN
    if to_console:
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter(_FMT))
        logger.addHandler(ch)
    logger.propagate = False
    _CONFIGURED.add(name)
    return logger
