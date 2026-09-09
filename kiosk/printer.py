"""Kết xuất phiếu số thứ tự (Pillow) và in ra máy in nhiệt khổ 80mm trên Windows.

- render_ticket(...)  -> PIL.Image
- print_image(img, printer_name)  -> in ra máy in (mặc định nếu để trống)
- Nếu thiếu pywin32 hoặc preview_only=True, gọi show_preview(img) để xem trước.
"""
import os
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

DPI = 203  # máy in nhiệt phổ thông
WIDTH_PX = {58: 384, 80: 576}

FONT_DIR = os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts")


def _font(name, size):
    for fn in (name, name.lower()):
        p = os.path.join(FONT_DIR, fn)
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    try:
        return ImageFont.truetype(name, size)
    except OSError:
        return ImageFont.load_default()


def _wrap(draw, text, font, max_w):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


def render_ticket(ticket, cfg_extra, paper_mm=80):
    """ticket: dict trả về từ /api/ticket. cfg_extra: khối 'extra' từ /api/config/public."""
    W = WIDTH_PX.get(int(paper_mm), 576)
    pad = 16
    inner = W - pad * 2

    f_org = _font("arialbd.ttf", 24)
    f_branch = _font("arialbd.ttf", 30)
    f_label = _font("arial.ttf", 22)
    f_num = _font("arialbd.ttf", 150)
    f_svc = _font("arialbd.ttf", 26)
    f_small = _font("arial.ttf", 21)

    # dựng nội dung theo dòng để tính chiều cao
    tmp = Image.new("L", (10, 10), 255)
    d = ImageDraw.Draw(tmp)

    blocks = []  # (kind, payload, font, height)

    def add(kind, payload, font, gap=6, h=None):
        if h is None:
            bbox = d.textbbox((0, 0), "Ag", font=font)
            h = bbox[3] - bbox[1]
        blocks.append((kind, payload, font, h + gap))

    for ln in _wrap(d, cfg_extra.get("ten_co_quan", ""), f_org, inner):
        add("center", ln, f_org)
    for ln in _wrap(d, cfg_extra.get("ten_chi_nhanh", ""), f_branch, inner):
        add("center", ln, f_branch)
    add("rule", None, f_label, gap=10, h=2)
    add("center", "PHIẾU SỐ THỨ TỰ", f_label, gap=4)
    add("num", ticket["full_no"], f_num, gap=10, h=150)
    for ln in _wrap(d, ticket.get("service_name", ""), f_svc, inner):
        add("center", ln, f_svc)
    add("rule", None, f_label, gap=10, h=2)
    ahead = ticket.get("waiting_ahead", 0)
    add("left", f"Số người chờ trước: {ahead}", f_small)
    now = datetime.now()
    add("left", f"Thời gian: {now.strftime('%H:%M:%S  %d/%m/%Y')}", f_small)
    add("left", f"Buổi: {ticket.get('session', '')}", f_small)

    qr_img = None
    if cfg_extra.get("qr_enabled") and cfg_extra.get("link_qr"):
        try:
            import qrcode
            qr_img = qrcode.make(cfg_extra["link_qr"]).resize((160, 160))
            blocks.append(("qr", qr_img, None, 172))
        except Exception:
            qr_img = None

    add("rule", None, f_label, gap=8, h=2)
    for ln in _wrap(d, "Vui lòng giữ phiếu và chờ gọi số. Xin cảm ơn!", f_small, inner):
        add("center", ln, f_small)

    total_h = pad * 2 + sum(b[3] for b in blocks)
    img = Image.new("RGB", (W, total_h), "white")
    draw = ImageDraw.Draw(img)

    y = pad
    for kind, payload, font, h in blocks:
        if kind == "rule":
            for x in range(pad, W - pad, 8):
                draw.line([(x, y), (x + 4, y)], fill="black", width=2)
        elif kind == "center":
            w = draw.textlength(payload, font=font)
            draw.text(((W - w) / 2, y), payload, font=font, fill="black")
        elif kind == "left":
            draw.text((pad, y), payload, font=font, fill="black")
        elif kind == "num":
            w = draw.textlength(payload, font=font)
            draw.text(((W - w) / 2, y - 10), payload, font=font, fill="black")
        elif kind == "qr" and payload is not None:
            img.paste(payload, (int((W - payload.width) / 2), y))
        y += h

    return img


# --------------------------------------------------------------- in Windows
def print_image(img, printer_name=""):
    import win32con
    import win32print
    import win32ui
    from PIL import ImageWin

    name = printer_name or win32print.GetDefaultPrinter()
    hDC = win32ui.CreateDC()
    hDC.CreatePrinterDC(name)
    printable_w = hDC.GetDeviceCaps(win32con.HORZRES)
    printable_h = hDC.GetDeviceCaps(win32con.VERTRES)

    ratio = printable_w / img.width
    target_w = printable_w
    target_h = int(img.height * ratio)
    if target_h > printable_h and printable_h > 0:
        target_h = printable_h

    hDC.StartDoc("Phieu so thu tu")
    hDC.StartPage()
    dib = ImageWin.Dib(img)
    dib.draw(hDC.GetHandleOutput(), (0, 0, target_w, target_h))
    hDC.EndPage()
    hDC.EndDoc()
    hDC.DeleteDC()


def has_win_print():
    try:
        import win32print  # noqa: F401
        import win32ui  # noqa: F401
        return True
    except ImportError:
        return False


def list_printers():
    try:
        import win32print
        flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        return [p[2] for p in win32print.EnumPrinters(flags)]
    except Exception:
        return []


def show_preview(img, parent=None):
    """Cửa sổ xem trước phiếu khi chưa có máy in / bật preview_only."""
    import tkinter as tk
    from PIL import ImageTk

    win = tk.Toplevel(parent) if parent else tk.Tk()
    win.title("Xem trước phiếu")
    win.configure(bg="#e5e7eb")
    scale = min(1.0, 560 / img.width)
    disp = img.resize((int(img.width * scale * 1.4), int(img.height * scale * 1.4)))
    photo = ImageTk.PhotoImage(disp)
    lbl = tk.Label(win, image=photo, bg="white", bd=1, relief="solid")
    lbl.image = photo
    lbl.pack(padx=20, pady=20)
    tk.Button(win, text="Đóng", font=("Arial", 14), command=win.destroy,
              bg="#0b5fa5", fg="white", padx=20, pady=8).pack(pady=(0, 20))
    win.after(15000, win.destroy)
    return win


if __name__ == "__main__":
    demo = {
        "full_no": "A-025", "service_name": "TRẢ KẾT QUẢ GIẢI QUYẾT THỦ TỤC HÀNH CHÍNH",
        "waiting_ahead": 12, "session": "Sáng",
    }
    extra = {"ten_co_quan": "VĂN PHÒNG ĐĂNG KÝ ĐẤT ĐAI",
             "ten_chi_nhanh": "CHI NHÁNH KHU VỰC BUÔN MA THUỘT",
             "qr_enabled": False, "link_qr": ""}
    im = render_ticket(demo, extra, 80)
    im.save(os.path.join(os.path.dirname(__file__), "ticket_demo.png"))
    print("Đã lưu ticket_demo.png")
