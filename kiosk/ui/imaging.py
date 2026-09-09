"""Nạp ảnh PNG chất lượng cao thành CTkImage — dùng cho icon thẻ dịch vụ.

Nguyên tắc (theo yêu cầu):
- KHÔNG sửa / ghi đè file PNG gốc. File gốc giữ nguyên trong assets/icons/.
- Mở bằng Pillow, `convert("RGBA")`, GIỮ NGUYÊN alpha suốt quá trình.
- KHÔNG recolor, KHÔNG tạo nền trắng/đen, KHÔNG mask tròn, KHÔNG quantize/
  posterize/threshold alpha.
- Chỉ resize MỘT lần, TRỰC TIẾP từ ảnh gốc, bằng Image.Resampling.LANCZOS
  (ảnh gốc -> kích thước đích, không resize bắc cầu).
- Nguồn đưa cho CTkImage để ở độ phân giải cao (>= ~3x cỡ hiển thị) cho màn
  DPI cao; CTkImage khai báo size=(display, display) để CustomTkinter tự lo
  DPI scaling.
- Cache CTkImage theo (đường dẫn tuyệt đối, mtime, cỡ, tham số) + giữ tham
  chiếu chống bị thu gom rác.
"""
import os

import customtkinter as ctk
from PIL import Image

try:
    _LANCZOS = Image.Resampling.LANCZOS
except AttributeError:  # Pillow cũ
    _LANCZOS = Image.LANCZOS

_CACHE = {}     # key -> CTkImage
_KEEP = []      # giữ tham chiếu CTkImage (chống GC)
_PIL_KEEP = []  # giữ tham chiếu ảnh nguồn PIL


def _fit_square(img, side):
    """Đưa ảnh về khung vuông `side` x `side`, GIỮ TỈ LỆ (contain), nền trong suốt.
    Đúng một phép resize LANCZOS từ ảnh truyền vào."""
    side = max(1, int(side))
    w, h = img.size
    if w == h:
        return img if w == side else img.resize((side, side), _LANCZOS)
    scale = side / float(max(w, h))
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    resized = img.resize((nw, nh), _LANCZOS)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(resized, ((side - nw) // 2, (side - nh) // 2), resized)
    return canvas


def _autocrop_pad(img, pad_ratio):
    """Nếu có viền trong suốt THỪA quanh ảnh thì cắt theo bbox alpha rồi chèn lại
    padding `pad_ratio` (mặc định ~6%). Không cắt sát icon, không đụng phần đục
    (vòng tròn màu bên ngoài vẫn còn vì nó không trong suốt)."""
    try:
        bbox = img.getchannel("A").getbbox()
    except Exception:  # noqa: BLE001
        return img
    if not bbox:
        return img
    w, h = img.size
    margin = min(bbox[0], bbox[1], w - bbox[2], h - bbox[3])
    if margin <= 0.03 * max(w, h):          # viền trong suốt không đáng kể -> để yên
        return img
    cropped = img.crop(bbox)
    cw, ch = cropped.size
    side = int(round(max(cw, ch) * (1.0 + 2.0 * pad_ratio)))
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(cropped, ((side - cw) // 2, (side - ch) // 2), cropped)
    return canvas


def load_ctk_image(path, display_size, *, autocrop=True, pad_ratio=0.06):
    """Trả về CTkImage vuông (display_size x display_size) từ PNG gốc `path`.
    Không đổi file gốc. Có cache."""
    path = os.path.abspath(path)
    disp = max(8, int(display_size))
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None
    key = (path, mtime, disp, autocrop, round(pad_ratio, 3))
    if key in _CACHE:
        return _CACHE[key]

    try:
        original = Image.open(path)
        original.load()
        original = original.convert("RGBA")   # RGBA, không convert RGB
    except Exception as e:  # noqa: BLE001
        print(f"[imaging] Không đọc được {path}: {e}")
        return None

    work = _autocrop_pad(original, pad_ratio) if autocrop else original

    # Nguồn độ phân giải cao cho CTkImage (>= 3x cỡ hiển thị, tối thiểu 320),
    # nhưng không phóng vượt quá kích thước gốc. Đúng MỘT phép resize từ `work`.
    target = max(disp * 3, 320)
    src_side = min(target, max(work.size))
    src = _fit_square(work, src_side) if (work.size[0] != work.size[1]
                                         or max(work.size) != src_side) else work

    img = ctk.CTkImage(light_image=src, dark_image=src, size=(disp, disp))
    _CACHE[key] = img
    _KEEP.append(img)
    _PIL_KEEP.append(src)
    return img


def probe(path):
    """Thông tin nhanh để kiểm tra chất lượng icon (dùng khi debug)."""
    im = Image.open(path)
    im.load()
    im = im.convert("RGBA")
    a = im.getchannel("A")
    return {
        "size": im.size,
        "mode": im.mode,
        "alpha_extrema": a.getextrema(),
        "alpha_bbox": a.getbbox(),
        "has_transparency": a.getextrema()[0] < 255,
    }
