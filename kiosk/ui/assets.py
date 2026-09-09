"""Nạp tài nguyên hình ảnh, luôn có phương án dự phòng.

- `logo(px)`            -> CTkImage logo cơ quan (assets/logo.png) hoặc huy hiệu vẽ sẵn.
- `icon_badge(...)`     -> CTkImage: đĩa trắng bán trong suốt + icon ở giữa (cho thẻ).
- `plain_icon(...)`     -> CTkImage icon đơn (cho footer / mũi tên).
- `ctk_image(pil, px)`  -> bọc PIL.Image thành CTkImage vuông.
"""
import os

import customtkinter as ctk
from PIL import Image, ImageDraw

from . import icons

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(os.path.dirname(HERE), "assets")
LOGO_PATH = os.path.join(ASSETS_DIR, "logo.png")


def _hex(c):
    c = str(c).lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def ctk_image(pil_img, px):
    return ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(int(px), int(px)))


# --------------------------------------------------------------------- logo
def _draw_emblem(px):
    """Huy hiệu tròn đơn giản: nền xanh, ngọn núi trắng, vòng cung xanh lá."""
    S = 4
    img = Image.new("RGBA", (px * S, px * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([2*S, 2*S, (px - 2)*S, (px - 2)*S], fill=_hex("#1E6FBF"), outline=_hex("#123B72"), width=3*S)
    d.polygon([(px*0.5*S, px*0.24*S), (px*0.78*S, px*0.60*S), (px*0.22*S, px*0.60*S)], fill="white")
    d.polygon([(px*0.60*S, px*0.40*S), (px*0.72*S, px*0.56*S), (px*0.50*S, px*0.56*S)], fill=_hex("#DCEAF8"))
    d.arc([px*0.16*S, px*0.50*S, px*0.84*S, px*0.92*S], 12, 168, fill=_hex("#13A861"), width=int(px*0.10*S))
    return img.resize((px, px), Image.LANCZOS)


def logo(px):
    try:
        if os.path.isfile(LOGO_PATH):
            im = Image.open(LOGO_PATH).convert("RGBA")
            im.thumbnail((px, px), Image.LANCZOS)
            canvas = Image.new("RGBA", (px, px), (0, 0, 0, 0))
            canvas.paste(im, ((px - im.width) // 2, (px - im.height) // 2), im)
            return ctk_image(canvas, px)
    except Exception as e:  # noqa: BLE001
        print(f"[assets] Lỗi đọc logo {LOGO_PATH}: {e} — dùng huy hiệu vẽ sẵn.")
    emblem = _draw_emblem(px)
    try:
        os.makedirs(ASSETS_DIR, exist_ok=True)
        if not os.path.isfile(LOGO_PATH):
            _draw_emblem(256).save(LOGO_PATH)
    except Exception:  # noqa: BLE001
        pass
    return ctk_image(emblem, px)


# --------------------------------------------------------------------- icon
def icon_badge(name, box_px, icon_color, disc_rgba=(255, 255, 255, 235)):
    """Đĩa tròn trắng bán trong suốt + icon `name` màu `icon_color` ở giữa."""
    box = int(box_px)
    img = Image.new("RGBA", (box, box), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([0, 0, box - 1, box - 1], fill=disc_rgba)
    ic = icons.load(name, int(box * 0.56), icon_color)
    img.alpha_composite(ic, ((box - ic.width) // 2, (box - ic.height) // 2))
    return ctk_image(img, box)


def plain_icon(name, px, color="#FFFFFF"):
    return ctk_image(icons.load(name, int(px), color), px)


def arrow_button_image(px, color="#FFFFFF"):
    """Vòng tròn viền trắng + mũi tên — nút 'đi tiếp' trên thẻ."""
    box = int(px)
    img = Image.new("RGBA", (box, box), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([2, 2, box - 3, box - 3], outline=_hex(color) + (235,), width=max(2, box // 22))
    ic = icons.load("arrow", int(box * 0.5), color)
    img.alpha_composite(ic, ((box - ic.width) // 2, (box - ic.height) // 2))
    return ctk_image(img, box)
