"""Vẽ icon bằng Pillow (dự phòng khi không có file trong assets/icons/).

Ưu tiên nạp `assets/icons/<name>.png`. Nếu thiếu, tự vẽ một icon nét mảnh
sạch sẽ theo `name` và lưu lại vào assets/icons/ để lần sau dùng luôn.

Toạ độ trong các hàm _draw_* nằm trên khung 100x100 rồi nhân hệ số S (siêu lấy
mẫu) cho nét mượt; cuối cùng thu nhỏ về đúng kích thước yêu cầu.
Icon nào cũng trả về ảnh RGBA đúng `size`, màu `color` (mặc định trắng).
"""
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ICONS_DIR = os.path.join(os.path.dirname(HERE), "assets", "icons")

KNOWN = ("land", "secured", "result", "appointment", "arrow", "database")
_SCALE = 4  # siêu lấy mẫu


def _hex(c):
    c = str(c).lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _canvas():
    img = Image.new("RGBA", (100 * _SCALE, 100 * _SCALE), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img), _SCALE


def _draw_land(d, S, col, w):
    d.line([(18*S, 54*S), (18*S, 86*S)], fill=col, width=w)
    d.line([(82*S, 54*S), (82*S, 86*S)], fill=col, width=w)
    d.line([(12*S, 56*S), (50*S, 22*S), (88*S, 56*S)], fill=col, width=w, joint="curve")
    d.line([(18*S, 86*S), (82*S, 86*S)], fill=col, width=w)
    d.rounded_rectangle([(42*S, 60*S), (58*S, 86*S)], radius=3*S, outline=col, width=w)
    d.arc([(50*S, 18*S), (80*S, 48*S)], 95, 215, fill=col, width=w)
    d.line([(60*S, 40*S), (74*S, 24*S)], fill=col, width=max(2, w * 2 // 3))


def _draw_secured(d, S, col, w):
    d.rounded_rectangle([(18*S, 12*S), (64*S, 76*S)], radius=6*S, outline=col, width=w)
    for y in (28, 39, 50):
        d.line([(28*S, y*S), (54*S, y*S)], fill=col, width=max(2, w * 2 // 3))
    d.polygon([(62*S, 42*S), (88*S, 51*S), (88*S, 70*S), (62*S, 88*S),
               (36*S, 70*S), (36*S, 51*S)], outline=col, width=w)
    d.line([(48*S, 66*S), (58*S, 76*S), (78*S, 52*S)], fill=col, width=w, joint="curve")


def _draw_result(d, S, col, w):
    d.line([(14*S, 40*S), (14*S, 84*S), (86*S, 84*S), (86*S, 40*S)],
           fill=col, width=w, joint="curve")
    d.line([(14*S, 58*S), (34*S, 58*S), (40*S, 66*S), (60*S, 66*S), (66*S, 58*S), (86*S, 58*S)],
           fill=col, width=w, joint="curve")
    d.rounded_rectangle([(30*S, 14*S), (70*S, 46*S)], radius=5*S, outline=col, width=w)
    d.line([(40*S, 30*S), (47*S, 38*S), (62*S, 22*S)], fill=col, width=w, joint="curve")


def _draw_appointment(d, S, col, w):
    d.rounded_rectangle([(12*S, 20*S), (74*S, 80*S)], radius=6*S, outline=col, width=w)
    d.line([(12*S, 37*S), (74*S, 37*S)], fill=col, width=w)
    d.line([(28*S, 12*S), (28*S, 26*S)], fill=col, width=w)
    d.line([(58*S, 12*S), (58*S, 26*S)], fill=col, width=w)
    d.ellipse([(56*S, 50*S), (90*S, 84*S)], outline=col, width=w)
    d.line([(73*S, 57*S), (73*S, 68*S), (82*S, 68*S)], fill=col, width=w, joint="curve")


def _draw_arrow(d, S, col, w):
    d.line([(40*S, 24*S), (66*S, 50*S), (40*S, 76*S)], fill=col, width=int(w * 1.15), joint="curve")


def _draw_database(d, S, col, w):
    d.ellipse([(18*S, 12*S), (82*S, 32*S)], outline=col, width=w)
    d.line([(18*S, 22*S), (18*S, 78*S)], fill=col, width=w)
    d.line([(82*S, 22*S), (82*S, 78*S)], fill=col, width=w)
    for dy in (22, 44):
        d.arc([(18*S, (12 + dy)*S), (82*S, (32 + dy)*S)], 8, 172, fill=col, width=w)
    d.arc([(18*S, 68*S), (82*S, 88*S)], 8, 172, fill=col, width=w)


_DRAW = {
    "land": _draw_land, "secured": _draw_secured, "result": _draw_result,
    "appointment": _draw_appointment, "arrow": _draw_arrow, "database": _draw_database,
}


def render(name, px, color="#FFFFFF"):
    """Trả về PIL.Image RGBA kích thước (px, px)."""
    img, d, S = _canvas()
    _DRAW.get(name, _draw_arrow)(d, S, _hex(color) + (255,), 6 * S)
    return img.resize((max(1, int(px)), max(1, int(px))), Image.LANCZOS)


def load(name, px, color="#FFFFFF"):
    """Nạp assets/icons/<name>.png (nếu bạn có đặt) hoặc tự vẽ trong bộ nhớ.

    - PNG có nền TRONG SUỐT (hình nằm ở kênh alpha): tô lại theo `color`
      (icon trắng/đơn sắc trên thẻ, đúng phong cách ảnh mẫu).
    - PNG KHÔNG có nền trong suốt (icon nhiều màu, nền đặc): GIỮ NGUYÊN màu gốc,
      chỉ thu về `px` — để icon bạn gửi hiển thị đúng, không bị biến thành ô đặc.
    - Không có file: tự vẽ (không ghi ra đĩa).
    """
    px = max(8, int(px))
    path = os.path.join(ICONS_DIR, f"{name}.png")
    try:
        if os.path.isfile(path):
            base = Image.open(path).convert("RGBA").resize((px, px), Image.LANCZOS)
            alpha = base.getchannel("A")
            if alpha.getextrema()[0] >= 250:     # gần như đục hoàn toàn -> giữ màu gốc
                return base
            solid = Image.new("RGBA", base.size, _hex(color) + (255,))
            solid.putalpha(alpha)
            return solid
    except Exception as e:  # noqa: BLE001
        print(f"[icons] Lỗi đọc {path}: {e} — dùng icon vẽ sẵn.")
    return render(name, px, color)
