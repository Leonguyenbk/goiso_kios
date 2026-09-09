"""Nạp tài nguyên hình ảnh, luôn có phương án dự phòng.

- `logo(px)`            -> CTkImage logo cơ quan (assets/logo.png) hoặc huy hiệu vẽ sẵn.
- `card_icon(...)`      -> CTkImage icon cho thẻ dịch vụ:
      * CÓ file assets/icons/<name>.png  -> hiện NGUYÊN TRẠNG (giữ vòng tròn,
        gradient, chi tiết) qua imaging.load_ctk_image — không recolor/mask/crop tròn.
      * KHÔNG có file -> vẽ dự phòng: đĩa trắng + hình đơn sắc.
- `plain_icon(...)`     -> CTkImage icon đơn (footer / mũi tên).
- `ctk_image(pil, px)`  -> bọc PIL.Image thành CTkImage vuông.
"""
import os

import customtkinter as ctk
from PIL import Image, ImageDraw

from . import icons, imaging

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(os.path.dirname(HERE), "assets")
ICONS_DIR = os.path.join(ASSETS_DIR, "icons")
LOGO_PATH = os.path.join(ASSETS_DIR, "logo.png")


def icon_file(name):
    """Đường dẫn PNG icon do người dùng đặt (hoặc None nếu chưa có)."""
    p = os.path.join(ICONS_DIR, f"{name}.png")
    return p if os.path.isfile(p) else None


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
    """Nạp assets/logo.png (nếu có) hoặc vẽ huy hiệu tạm — không ghi ra đĩa."""
    px = max(8, int(px))
    try:
        if os.path.isfile(LOGO_PATH):
            im = Image.open(LOGO_PATH).convert("RGBA")
            im.thumbnail((px, px), Image.LANCZOS)
            canvas = Image.new("RGBA", (px, px), (0, 0, 0, 0))
            canvas.paste(im, ((px - im.width) // 2, (px - im.height) // 2), im)
            return ctk_image(canvas, px)
    except Exception as e:  # noqa: BLE001
        print(f"[assets] Lỗi đọc logo {LOGO_PATH}: {e} — dùng huy hiệu vẽ sẵn.")
    return ctk_image(_draw_emblem(px), px)


# --------------------------------------------------------------------- icon thẻ
def has_card_icon(name):
    return icon_file(name) is not None


def card_icon(name, size_px, card_color, *, pad_ratio=0.06, glyph_ratio=0.56):
    """CTkImage icon cho thẻ dịch vụ.

    - Có file PNG  -> imaging.load_ctk_image: giữ NGUYÊN ảnh gốc (vòng tròn +
      gradient + chi tiết), không recolor, không mask, chỉ 1 lần resize LANCZOS,
      nguồn để ở độ phân giải cao cho màn DPI cao.
    - Không có file -> đĩa trắng + hình đơn sắc màu `card_color` (dự phòng).
    """
    size_px = max(8, int(size_px))
    path = icon_file(name)
    if path:
        img = imaging.load_ctk_image(path, size_px, pad_ratio=pad_ratio)
        if img is not None:
            return img
    # dự phòng
    box = size_px
    canvas = Image.new("RGBA", (box, box), (0, 0, 0, 0))
    ImageDraw.Draw(canvas).ellipse([0, 0, box - 1, box - 1], fill=(255, 255, 255, 235))
    glyph = icons.render(name, max(8, int(box * glyph_ratio)), card_color)
    canvas.alpha_composite(glyph, ((box - glyph.width) // 2, (box - glyph.height) // 2))
    return ctk_image(canvas, box)


def plain_icon(name, px, color="#FFFFFF"):
    """Icon đơn sắc cho footer (không cần chất lượng cao như icon thẻ)."""
    path = icon_file(name)
    if path:
        img = imaging.load_ctk_image(path, int(px))
        if img is not None:
            return img
    return ctk_image(icons.render(name, int(px), color), px)


def arrow_button_image(px, color="#FFFFFF"):
    """Nút 'đi tiếp' ở đáy thẻ. Có assets/icons/arrow.png -> dùng nguyên trạng;
    không thì vẽ vòng tròn viền + mũi tên."""
    box = int(px)
    path = icon_file("arrow")
    if path:
        img = imaging.load_ctk_image(path, box)
        if img is not None:
            return img
    canvas = Image.new("RGBA", (box, box), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    d.ellipse([2, 2, box - 3, box - 3], outline=_hex(color) + (235,), width=max(2, box // 22))
    ic = icons.render("arrow", int(box * 0.5), color)
    canvas.alpha_composite(ic, ((box - ic.width) // 2, (box - ic.height) // 2))
    return ctk_image(canvas, box)
