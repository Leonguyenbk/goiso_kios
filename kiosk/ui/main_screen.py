"""MainScreen — màn hình chính của Kiosk: header + lời chào + 4 thẻ + footer.

Bố cục dùng grid (weight) cho 4 dải ngang. Riêng vùng 4 thẻ ("stage") có một
ảnh nền trang trí (cảnh vật + hoạ tiết mờ) dùng chung 24 chi nhánh; các thẻ được
`.place()` lên trên theo tỉ lệ nên tự giãn khi đổi kích thước.
"""
import customtkinter as ctk

from config.settings import APP_CONFIG, COLORS
from ui import assets, background
from ui.theme import Scaler
from ui.widgets.footer import Footer
from ui.widgets.service_card import ServiceCard


def _hx(rgb):
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def _avg_hex(pil_img, top=0.0, bottom=0.72):
    """Màu trung bình của DẢI ngang [top..bottom] của ảnh."""
    try:
        im = pil_img.convert("RGB")
        w, h = im.size
        band = im.crop((0, int(h * top), w, max(int(h * top) + 1, int(h * bottom))))
        return _hx(band.resize((1, 1)).getpixel((0, 0)))
    except Exception:  # noqa: BLE001
        return COLORS["bg"]


def _border_hex(rgb_img, w, h, rect):
    """Màu trung bình của VIỀN ngay bên ngoài một thẻ (rect = relx,rely,relw,relh).
    Lấy 4 dải mảnh sát 4 cạnh thẻ -> khớp màu góc bo tốt nhất có thể."""
    try:
        rx, ry, rw, rh = rect
        x0, y0 = int(rx * w), int(ry * h)
        x1, y1 = int((rx + rw) * w), int((ry + rh) * h)
        m = max(6, int(0.02 * w))  # bề dày dải viền
        strips = [
            rgb_img.crop((max(0, x0 - m), y0, x0, y1)),                     # trái
            rgb_img.crop((x1, y0, min(w, x1 + m), y1)),                     # phải
            rgb_img.crop((x0, max(0, y0 - m), x1, y0)),                     # trên
            rgb_img.crop((x0, y1, x1, min(h, y1 + m))),                     # dưới
        ]
        acc, n = [0, 0, 0], 0
        for s in strips:
            if s.width < 1 or s.height < 1:
                continue
            px = s.resize((1, 1)).getpixel((0, 0))
            acc = [acc[i] + px[i] for i in range(3)]
            n += 1
        if not n:
            return _avg_hex(rgb_img)
        return _hx([round(v / n) for v in acc])
    except Exception:  # noqa: BLE001
        return _avg_hex(rgb_img)


class MainScreen(ctk.CTkFrame):
    def __init__(self, master, callbacks: dict):
        super().__init__(master, fg_color=COLORS["bg"], corner_radius=0)
        self.scaler = Scaler()
        self._callbacks = callbacks
        self._logo_img = None
        self._stage_bg_img = None
        self._stage_job = None
        self._resize_job = None
        self._stage_size = (0, 0)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)   # header
        self.grid_rowconfigure(1, weight=0)   # hero
        self.grid_rowconfigure(2, weight=1)   # stage (4 thẻ)
        self.grid_rowconfigure(3, weight=0)   # footer

        self._build_header()
        self._build_hero()
        self._build_stage()
        self._footer = Footer(self, self.scaler)
        self._footer.grid(row=3, column=0, sticky="nsew")

        self.bind("<Configure>", self._on_resize)
        self.after(60, lambda: self._apply_scale(force=True))

    # --------------------------------------------------------------- header
    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        hdr.grid(row=0, column=0, sticky="nsew", padx=44, pady=(26, 6))
        hdr.grid_columnconfigure(1, weight=1)

        self._logo = ctk.CTkLabel(hdr, text="", fg_color="transparent")
        self._logo.grid(row=0, column=0, rowspan=2, padx=(0, 20), sticky="w")

        block = ctk.CTkFrame(hdr, fg_color="transparent")
        block.grid(row=0, column=1, sticky="w")
        self._org = ctk.CTkLabel(block, text=APP_CONFIG["organization_name"],
                                 font=self.scaler.font("org"), text_color=COLORS["text_navy"],
                                 fg_color="transparent", anchor="w", justify="left")
        self._org.pack(anchor="w")
        # Tên chi nhánh — dòng riêng, rõ, ngay dưới tên Văn phòng (theo từng chi nhánh).
        branch = (APP_CONFIG.get("branch_name") or "").strip()
        self._branch = ctk.CTkLabel(block, text=branch, font=self.scaler.font("branch"),
                                    text_color=COLORS["navy"], fg_color="transparent",
                                    anchor="w", justify="left")
        if branch:
            self._branch.pack(anchor="w", pady=(1, 0))
        self._slogan = ctk.CTkLabel(block, text=APP_CONFIG["left_slogan"],
                                    font=self.scaler.font("slogan"), text_color=COLORS["muted"],
                                    fg_color="transparent", anchor="w", justify="left")
        self._slogan.pack(anchor="w", pady=(3, 0))

        right = ctk.CTkFrame(hdr, fg_color="transparent")
        right.grid(row=0, column=2, sticky="e")
        for line in APP_CONFIG.get("right_slogan_lines", []):
            ctk.CTkLabel(right, text=line, font=self.scaler.font("right_slo"),
                         text_color=COLORS["muted"], fg_color="transparent",
                         anchor="e", justify="right").pack(anchor="e")

    # ----------------------------------------------------------------- hero
    def _build_hero(self):
        hero = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        hero.grid(row=1, column=0, sticky="nsew", pady=(2, 4))
        hero.grid_columnconfigure(0, weight=1)
        self._hero = ctk.CTkLabel(hero, text=APP_CONFIG["hero_title"],
                                  font=self.scaler.font("hero"), text_color=COLORS["text_navy"],
                                  fg_color="transparent")
        self._hero.grid(row=0, column=0, pady=(6, 0))
        self._hero_sub = ctk.CTkLabel(hero, text=APP_CONFIG["hero_subtitle"],
                                      font=self.scaler.font("hero_sub"), text_color=COLORS["muted"],
                                      fg_color="transparent")
        self._hero_sub.grid(row=1, column=0, pady=(2, 6))

    # ---------------------------------------------------------------- stage
    def _build_stage(self):
        self._stage = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        self._stage.grid(row=2, column=0, sticky="nsew")
        self._stage.bind("<Configure>", self._on_stage_resize)

        # ảnh nền trang trí (phía sau các thẻ)
        self._stage_bg = ctk.CTkLabel(self._stage, text="", fg_color="transparent")
        self._stage_bg.place(x=0, y=0, relwidth=1, relheight=1)

        svcs = APP_CONFIG["services"][:4]
        cb_map = {
            "land": "on_land_procedure",
            "secured": "on_secured_transaction",
            "result": "on_result_return",
            "appointment": "on_online_appointment",
        }
        self._cards = []
        gap, top, bot = 0.018, 0.05, 0.13
        cw = (1 - gap * 5) / 4
        self._card_rects = []  # (relx, rely, relw, relh) để lấy màu nền quanh từng thẻ
        for i, s in enumerate(svcs):
            cb = self._callbacks.get(cb_map.get(s["key"], ""), lambda: None)
            card = ServiceCard(
                self._stage, title=s["title"], description=s["description"],
                icon_path=s["icon"], bg_color=s["color"], command=cb,
                title_font=self.scaler.font("card_title"),
                desc_font=self.scaler.font("card_desc"))
            rx = gap + i * (cw + gap)
            card.place(relx=rx, rely=top, relwidth=cw, relheight=1 - top - bot)
            self._cards.append(card)
            self._card_rects.append((rx, top, cw, 1 - top - bot))

    def _on_stage_resize(self, event):
        size = (event.width, event.height)
        if abs(size[0] - self._stage_size[0]) < 12 and abs(size[1] - self._stage_size[1]) < 12:
            return
        self._stage_size = size
        if self._stage_job:
            self.after_cancel(self._stage_job)
        self._stage_job = self.after(120, self._redraw_stage_bg)

    def _redraw_stage_bg(self):
        self._stage_job = None
        w, h = self._stage_size
        if w < 40 or h < 40:
            return
        try:
            pil = background.get(w, h)
            self._stage_bg_img = ctk.CTkImage(light_image=pil, dark_image=pil, size=(w, h))
            self._stage_bg.configure(image=self._stage_bg_img)
            # Góc bo của thẻ (CTkFrame) lộ MÀU ĐẶC của khung cha (tkinter không có
            # alpha giữa widget). Lấy màu nền NGAY QUANH từng thẻ gán làm màu góc
            # để mối nối ít lộ nhất.
            rgb = pil.convert("RGB")
            self._stage.configure(fg_color=_avg_hex(pil))
            for card, rect in zip(self._cards, self._card_rects):
                card.configure(bg_color=_border_hex(rgb, w, h, rect))
        except Exception as e:  # noqa: BLE001
            print(f"[MainScreen] Lỗi dựng nền: {e}")

    # --------------------------------------------------------------- resize
    def _on_resize(self, event):
        if event.widget is not self:
            return
        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(140, self._apply_scale)

    def _apply_scale(self, force=False):
        self._resize_job = None
        w = self.winfo_width() or self.winfo_screenwidth()
        h = self.winfo_height() or self.winfo_screenheight()
        changed = self.scaler.update(w, h)
        if changed or force:
            self._logo_img = assets.logo(self.scaler.px("logo"))  # cỡ trong theme.PX_SIZES
            self._logo.configure(image=self._logo_img)
