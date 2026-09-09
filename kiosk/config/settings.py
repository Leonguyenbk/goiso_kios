"""Cấu hình giao diện Kiosk bốc số.

`APP_CONFIG` là nguồn sự thật cho mọi chữ hiển thị dùng chung 24 chi nhánh.
Khi cài đặt tại từng chi nhánh, chỉ cần đặt `branch_name` (và các khoá khác nếu
muốn) trong `kiosk/config.json` — KHÔNG sửa code.

Thứ tự ưu tiên khi nạp:
    APP_CONFIG mặc định  <  kiosk/config.json  <  biến môi trường KIOSK_BRANCH_NAME
"""
import json
import os

# --------------------------------------------------------------------- màu sắc
COLORS = {
    "navy":        "#123B72",
    "text_navy":   "#173A72",
    "navy_dark":   "#0E2E59",
    "green":       "#13A861",
    "blue":        "#1689E8",
    "orange":      "#F58220",
    "purple":      "#6D45D8",
    "bg":          "#F4F9FE",
    "bg_top":      "#E9F3FD",
    "bg_bottom":   "#D7E9F8",
    "white":       "#FFFFFF",
    "muted":       "#5B7599",
}

CARD_RADIUS = 20   # độ bo góc thẻ (px). Giảm nếu góc bo lộ màu -> đỡ thấy hơn.

# --------------------------------------------------------- CỠ ICON TRÊN THẺ
# Tính theo CHIỀU CAO thẻ (tự co khi đổi kích thước màn hình).
CARD_ICON = {
    # Cỡ ICON hiển thị. PNG bạn cung cấp (đã có sẵn vòng tròn màu) được hiện
    # nguyên trạng ở cỡ này, KHÔNG vẽ thêm đĩa trắng phía sau.
    "size_ratio": 0.30,          # ~170 px ở màn 1920×1080
    "size_min":   96,
    "size_max":   260,
    "pad_ratio":  0.06,          # padding khi tự cắt viền trong suốt thừa (5–8%)

    # CHỈ dùng khi THIẾU file PNG -> vẽ dự phòng: đĩa trắng + hình đơn sắc.
    "fallback_disc_ratio":  0.30,
    "fallback_glyph_ratio": 0.56,

    "arrow_ratio": 0.115,        # nút mũi tên ở đáy thẻ
    "arrow_min":   34,
    "arrow_max":   82,
}

# Font ưu tiên có sẵn trên Windows — không cần cài thêm.
FONT_FAMILY = "Segoe UI"
FONT_FAMILY_FALLBACKS = ("Segoe UI", "Arial", "Tahoma", "sans-serif")

# --------------------------------------------------------------------- nội dung
APP_CONFIG = {
    "organization_name": "VĂN PHÒNG ĐĂNG KÝ ĐẤT ĐAI",
    "branch_name": "",  # để trống = không hiển thị. Cài đặt qua config.json.
    "left_slogan": "CÔNG KHAI - MINH BẠCH - CHUYÊN NGHIỆP - VÌ NGƯỜI DÂN",
    "right_slogan_lines": [
        "ĐỒNG HÀNH CÙNG NGƯỜI DÂN",
        "VÌ QUẢN LÝ ĐẤT ĐAI HIỆU QUẢ",
    ],
    "hero_title": "KÍNH CHÀO QUÝ KHÁCH",
    "hero_subtitle": "Vui lòng chọn dịch vụ để lấy số thứ tự",
    "footer_department": "PHÒNG DỮ LIỆU - THÔNG TIN ĐẤT ĐAI",
    "footer_team": "TỔ ỨNG DỤNG VÀ PHÁT TRIỂN CÔNG NGHỆ",
    "fullscreen": True,

    # 4 thẻ chức năng — thứ tự = thứ tự hiển thị.
    "services": [
        {
            "key": "land",
            "title": "THỦ TỤC\nĐẤT ĐAI",
            "description": "Đăng ký, cấp Giấy chứng nhận,\nchuyển mục đích, tách thửa,\nhợp thửa, ...",
            "icon": "land",
            "color": COLORS["green"],
        },
        {
            "key": "secured",
            "title": "GIAO DỊCH\nBẢO ĐẢM",
            "description": "Đăng ký, xóa đăng ký\ngiao dịch bảo đảm bằng\nquyền sử dụng đất, tài sản gắn liền\nvới đất, ...",
            "icon": "secured",
            "color": COLORS["blue"],
        },
        {
            "key": "result",
            "title": "TRẢ KẾT QUẢ",
            "description": "Nhận kết quả giải quyết\nthủ tục hành chính",
            "icon": "result",
            "color": COLORS["orange"],
        },
        {
            "key": "appointment",
            "title": "LẤY PHIẾU HẸN\nONLINE",
            "description": "Dành cho công dân đã đăng ký\nhồ sơ trực tuyến",
            "icon": "appointment",
            "color": COLORS["purple"],
        },
    ],
}

_HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_JSON = os.path.join(os.path.dirname(_HERE), "config.json")


def _load_overrides(cfg):
    """Nạp đè từ kiosk/config.json (nếu có) rồi tới biến môi trường."""
    try:
        with open(CONFIG_JSON, encoding="utf-8") as f:
            data = json.load(f)
        for k in ("organization_name", "branch_name", "left_slogan",
                  "hero_title", "hero_subtitle", "footer_department",
                  "footer_team", "fullscreen"):
            if k in data and data[k] not in (None, ""):
                cfg[k] = data[k]
        if isinstance(data.get("right_slogan_lines"), list):
            cfg["right_slogan_lines"] = data["right_slogan_lines"]
    except FileNotFoundError:
        pass
    except (json.JSONDecodeError, OSError) as e:  # noqa: BLE001
        print(f"[settings] Bỏ qua config.json lỗi: {e}")

    env_branch = os.environ.get("KIOSK_BRANCH_NAME")
    if env_branch:
        cfg["branch_name"] = env_branch
    return cfg


_load_overrides(APP_CONFIG)
