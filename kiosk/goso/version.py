"""Phiên bản — MỘT nguồn duy nhất (file VERSION ở gốc repo, đóng gói kèm exe).

GitHub Actions ghi đè file này từ tag `vX.Y.Z` trước khi build.
"""
import re

from . import paths

_CACHE = None


def get_version():
    global _CACHE
    if _CACHE:
        return _CACHE
    try:
        with open(paths.version_file(), encoding="utf-8") as f:
            v = f.read().strip()
        _CACHE = v or "0.0.0"
    except OSError:
        _CACHE = "0.0.0"
    return _CACHE


def parse(v):
    """'1.2.3' -> (1, 2, 3). Chấp nhận tiền tố 'v' và hậu tố -rc..."""
    m = re.match(r"v?(\d+)\.(\d+)\.(\d+)", str(v or "0.0.0"))
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)


def cmp(a, b):
    """-1 nếu a<b, 0 bằng, 1 nếu a>b (chỉ so major.minor.patch)."""
    pa, pb = parse(a), parse(b)
    return (pa > pb) - (pa < pb)


def is_newer(candidate, current):
    return cmp(candidate, current) > 0
