# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build cho bộ Kiosk Windows: GoSoKiosk / GoSoConfig / GoSoUpdater.

Chạy:  pyinstaller GoSoKiosk.spec --noconfirm
Kết quả:  dist/GoSoKiosk/  (onedir, chứa cả 3 .exe + assets + VERSION)

File .spec này LÀ định nghĩa build — được commit chủ đích.
"""
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = os.path.abspath(os.getcwd())
KIOSK = os.path.join(ROOT, "kiosk")

_datas = [
    (os.path.join(KIOSK, "assets"), "assets"),
    (os.path.join(ROOT, "VERSION"), "."),
]
_datas += collect_data_files("customtkinter")

_hidden = (collect_submodules("customtkinter")
           + ["PIL._tkinter_finder", "win32timezone", "win32print", "win32ui",
              "win32api", "win32con", "win32gui", "requests"])

_ver_txt = os.path.join(ROOT, "build_version_info.txt")
_ver_kw = {"version": _ver_txt} if os.path.isfile(_ver_txt) else {}
_ico = os.path.join(KIOSK, "assets", "app.ico")
_ico_kw = {"icon": _ico} if os.path.isfile(_ico) else {}


def _ana(entry):
    return Analysis(
        [os.path.join(KIOSK, entry)],
        pathex=[KIOSK, ROOT],
        binaries=[],
        datas=_datas,
        hiddenimports=_hidden,
        hookspath=[],
        runtime_hooks=[],
        excludes=["tkinter.test", "test", "pytest"],
        noarchive=False,
    )


a_kiosk = _ana("goso_kiosk.py")
a_config = _ana("goso_config.py")
a_updater = _ana("goso_updater.py")

pyz_k = PYZ(a_kiosk.pure)
pyz_c = PYZ(a_config.pure)
pyz_u = PYZ(a_updater.pure)

exe_kiosk = EXE(pyz_k, a_kiosk.scripts, [], exclude_binaries=True,
                name="GoSoKiosk", console=False, disable_windowed_traceback=False,
                **_ver_kw, **_ico_kw)
exe_config = EXE(pyz_c, a_config.scripts, [], exclude_binaries=True,
                 name="GoSoConfig", console=False, **_ver_kw, **_ico_kw)
exe_updater = EXE(pyz_u, a_updater.scripts, [], exclude_binaries=True,
                  name="GoSoUpdater", console=False, **_ver_kw)

coll = COLLECT(
    exe_kiosk, a_kiosk.binaries, a_kiosk.zipfiles, a_kiosk.datas,
    exe_config, a_config.binaries, a_config.zipfiles, a_config.datas,
    exe_updater, a_updater.binaries, a_updater.zipfiles, a_updater.datas,
    strip=False, upx=False, name="GoSoKiosk",
)
