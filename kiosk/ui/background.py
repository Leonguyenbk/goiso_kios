"""Ảnh nền trang trí — DÙNG CHUNG cho cả 24 chi nhánh (không có chữ chi nhánh).

- Nếu có sẵn `assets/background.png` thì dùng (thu/phóng theo vùng thẻ).
- Nếu không, tự dựng bằng Pillow: trời gradient xanh rất nhạt, hoạ tiết vòng
  tròn kiểu trống đồng rất mờ, các lớp núi + đường phố + cây + cầu dây văng
  ở chân, một dải nước nhạt phía dưới. Dựng trực tiếp, không ghi ra đĩa.
"""
import os

from PIL import Image, ImageDraw, ImageFilter

from config.settings import COLORS

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(os.path.dirname(HERE), "assets")
BG_PATH = os.path.join(ASSETS_DIR, "background.png")
NATIVE = (1920, 1080)


def _hex(c):
    c = str(c).lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _vgradient(size, top, bottom):
    w, h = size
    base = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        base.putpixel((0, y), tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return base.resize((w, h))


def _hill(draw, size, baseline, height, color, alpha, seed):
    """Một dải đồi/núi mềm (ImageDraw ở mode RGBA sẽ tự alpha-blend)."""
    import math
    w, h = size
    pts = [(0, h)]
    n = 7
    for i in range(n + 1):
        x = w * i / n
        y = baseline - height * (0.55 + 0.45 * math.sin(seed + i * 1.7))
        pts.append((x, y))
    pts.append((w, h))
    draw.polygon(pts, fill=color + (alpha,))


def build(width=NATIVE[0], height=NATIVE[1]):
    w, h = int(width), int(height)
    img = _vgradient((w, h), _hex(COLORS["bg_top"]), _hex(COLORS["bg_bottom"])).convert("RGBA")
    d = ImageDraw.Draw(img, "RGBA")

    # --- hoạ tiết vòng tròn kiểu trống đồng, RẤT mờ, phía dưới-trái
    cx, cy = int(w * 0.08), int(h * 0.74)
    for r in range(36, 250, 40):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=_hex(COLORS["blue"]) + (6,), width=3)
    for k in range(16):
        import math
        a = k * math.pi / 8
        d.line([(cx + 90 * math.cos(a), cy + 90 * math.sin(a)),
                (cx + 210 * math.cos(a), cy + 210 * math.sin(a))],
               fill=_hex(COLORS["blue"]) + (4,), width=2)

    # --- vòng tròn mờ góc phải
    r2 = int(h * 0.55)
    d.ellipse([w - r2, h - r2, w + r2 // 2, h + r2 // 2], outline=_hex(COLORS["blue"]) + (6,), width=4)

    # --- các lớp núi/đồi ở chân
    base = int(h * 0.88)
    _hill(d, (w, h), base + 10, h * 0.10, _hex("#9FC6EA"), 60, 0.4)
    _hill(d, (w, h), base + 30, h * 0.16, _hex("#7FB2E4"), 70, 2.1)

    # --- silhouette phố + cầu dây văng (rất nhạt)
    city = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    cd = ImageDraw.Draw(city)
    col = _hex("#6AA6DE") + (70,)
    xs = int(w * 0.30)
    for i, bw in enumerate((34, 22, 46, 28, 60, 24, 40, 30, 52)):
        bx = xs + i * int(w * 0.045)
        bh = int(h * (0.10 + 0.09 * ((i * 37) % 5) / 5.0))
        cd.rectangle([bx, base - bh, bx + bw, base], fill=col)
    # trụ cầu + dây
    px_ = int(w * 0.62)
    cd.line([(px_, base), (px_, base - int(h * 0.20))], fill=col, width=6)
    for dx in range(-140, 150, 26):
        cd.line([(px_, base - int(h * 0.20)), (px_ + dx, base)], fill=_hex("#6AA6DE") + (45,), width=2)
    cd.line([(int(w * 0.42), base), (int(w * 0.82), base)], fill=col, width=5)
    img.alpha_composite(city)

    # --- cây (đốm tròn) rải rác chân màn hình
    for i in range(18):
        tx = int((i * 113 + 40) % w)
        ty = base + (i % 3) * 6
        tr = 12 + (i * 7) % 16
        d.ellipse([tx - tr, ty - tr * 2, tx + tr, ty], fill=_hex("#8FBEE6") + (55,))
        d.line([(tx, ty), (tx, ty + 10)], fill=_hex("#8FBEE6") + (55,), width=3)

    # --- dải nước phía dưới
    d.rectangle([0, int(h * 0.945), w, h], fill=_hex("#BFDDF4") + (150,))
    d.rectangle([0, int(h * 0.965), w, h], fill=_hex("#A9D0F0") + (170,))

    img = img.filter(ImageFilter.GaussianBlur(0.6))

    return img.convert("RGB")


def get(width, height):
    """Ảnh nền đúng kích thước vùng thẻ.

    Ưu tiên `assets/background.png` do chi nhánh tự đặt (dùng chung 24 chi nhánh,
    KHÔNG chứa chữ chi nhánh). Không có thì tự dựng theo đúng tỉ lệ hiện tại.
    """
    try:
        if os.path.isfile(BG_PATH):
            return Image.open(BG_PATH).convert("RGB").resize(
                (int(width), int(height)), Image.LANCZOS)
    except Exception as e:  # noqa: BLE001
        print(f"[background] Lỗi đọc {BG_PATH}: {e} — tự dựng nền.")
    return build(width, height)
