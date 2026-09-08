"""Truy cập CSDL SQLite cho hệ thống bốc số / gọi số một cửa.

Dùng lại nguyên schema có sẵn trong hethong_goiso.db, chỉ bổ sung thêm 2 cột
time_issue / time_done cho bảng queue (migration không phá dữ liệu cũ).
"""
import json
import os
import sqlite3
import threading
from datetime import datetime

# hethong_goiso.db nằm ở thư mục gốc dự án (cha của thư mục server/)
DB_PATH = os.environ.get(
    "GOISO_DB",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hethong_goiso.db"),
)

# SQLite ghi tuần tự; khoá này bảo vệ các thao tác đọc-sửa-ghi phức hợp
LOCK = threading.RLock()


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=8000")
    return conn


def _column_names(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def init_db():
    """Tạo bảng nếu chưa có + bổ sung cột mới. An toàn khi gọi nhiều lần."""
    with LOCK, get_conn() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS queue
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, prefix TEXT, number INTEGER,
                  status TEXT, counter TEXT, staff_name TEXT, agency TEXT, time_start TEXT, date_record TEXT,
                  fullname TEXT, cccd TEXT, session TEXT, phone TEXT, file_path TEXT, file_name TEXT,
                  file_path2 TEXT, file_name2 TEXT)"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS counters_status
                 (counter_id TEXT PRIMARY KEY, staff_name TEXT, status TEXT, last_num TEXT, last_update TEXT)"""
        )
        conn.execute("CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS visitor_stats (date_record TEXT PRIMARY KEY, count INTEGER DEFAULT 0)"
        )

        cols = _column_names(conn, "queue")
        if "time_issue" not in cols:
            conn.execute("ALTER TABLE queue ADD COLUMN time_issue TEXT")
        if "time_done" not in cols:
            conn.execute("ALTER TABLE queue ADD COLUMN time_done TEXT")

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_queue_day ON queue(date_record, prefix, status, number)"
        )

        _seed_defaults(conn)


DEFAULT_COUNTERS = {
    "Quầy số 01": {"active": True, "staff": "", "prefix": "A", "display_order": 1},
    "Quầy số 02": {"active": True, "staff": "", "prefix": "B", "display_order": 2},
    "Quầy số 03": {"active": True, "staff": "", "prefix": "C", "display_order": 3},
    "Quầy số 04": {"active": True, "staff": "", "prefix": "D", "display_order": 4},
    "Quầy số 05": {"active": True, "staff": "", "prefix": "E", "display_order": 5},
    "Quầy số 06": {"active": True, "staff": "", "prefix": "F", "display_order": 6},
}

DEFAULT_SERVICES = {
    "A": {"name": "TRẢ KẾT QUẢ GIẢI QUYẾT THỦ TỤC HÀNH CHÍNH", "short": "Trả kết quả",
          "color": "#27ae60", "daily_limit": 200, "current_count": 0, "active": True},
    "B": {"name": "ĐĂNG KÝ BIẾN ĐỘNG ĐẤT ĐAI", "short": "Biến động đất đai",
          "color": "#3498db", "daily_limit": 150, "current_count": 0, "active": True},
}

DEFAULT_EXTRA = {
    "ten_co_quan": "VĂN PHÒNG ĐĂNG KÝ ĐẤT ĐAI",
    "ten_chi_nhanh": "CHI NHÁNH KHU VỰC EA KAR",
    "link_qr": "https://eakartoday.vn",
    "logo_path": "",
    "qr_enabled": False,
    "background_color": "#f5f7fa",
    "lock_time_enabled": True,
    "time_slots": [
        {"start_hour": 6, "start_minute": 15, "end_hour": 11, "end_minute": 15},
        {"start_hour": 13, "start_minute": 15, "end_hour": 15, "end_minute": 30},
    ],
    "lock_message": "Hiện tại chưa đến giờ lấy số hoặc đã hết giờ!\nVui lòng quay lại trong khung giờ Sáng 6:15-11:15, Chiều 13:15-15:30.",
    "allow_saturday": False,
    "allow_sunday": False,
    "voice_rate": 0.95,
    "voice_repeat": 2,
    # Mẫu câu đọc; {so} = A không hai lăm, {quay} = một
    "voice_template": "Mời số {so}, đến quầy số {quay}",
    "spotlight_seconds": 20,
    "recent_count": 8,
}

# Mật khẩu quản trị mặc định: "admin123" (sha256). Đổi trong trang /admin.
DEFAULT_ADMIN_PW = "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9"


def _seed_defaults(conn):
    existing = {row[0] for row in conn.execute("SELECT key FROM config")}
    if "counters" not in existing:
        conn.execute("INSERT INTO config VALUES ('counters', ?)",
                     (json.dumps(DEFAULT_COUNTERS, ensure_ascii=False),))
    if "services" not in existing:
        conn.execute("INSERT INTO config VALUES ('services', ?)",
                     (json.dumps(DEFAULT_SERVICES, ensure_ascii=False),))
    if "extra" not in existing:
        conn.execute("INSERT INTO config VALUES ('extra', ?)",
                     (json.dumps(DEFAULT_EXTRA, ensure_ascii=False),))
    if "admin_password" not in existing:
        conn.execute("INSERT INTO config VALUES ('admin_password', ?)", (DEFAULT_ADMIN_PW,))


# ---------------------------------------------------------------- config helpers
def get_config(key, default=None):
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
    if row is None:
        return default
    return row[0]


def get_json_config(key, default=None):
    raw = get_config(key)
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return default


def set_json_config(key, obj):
    with LOCK, get_conn() as conn:
        conn.execute(
            "INSERT INTO config(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(obj, ensure_ascii=False)),
        )


def set_config(key, value):
    with LOCK, get_conn() as conn:
        conn.execute(
            "INSERT INTO config(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def get_extra():
    data = dict(DEFAULT_EXTRA)
    data.update(get_json_config("extra", {}) or {})
    return data


# ---------------------------------------------------------------- domain helpers
def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def session_now():
    """'Sáng' trước 12h, 'Chiều' từ 12h."""
    return "Sáng" if datetime.now().hour < 12 else "Chiều"


def full_no(prefix, number):
    return f"{prefix}-{int(number):03d}"


def short_label(svc, code=""):
    """Nhãn rút gọn cho thẻ quầy / màn hình. Ưu tiên 'short', nếu không có thì
    cắt phần trước dấu '(' của tên và giới hạn độ dài."""
    if not svc:
        return code
    s = (svc.get("short") or "").strip()
    if s:
        return s
    name = (svc.get("name") or code or "").strip()
    head = name.split("(")[0].strip(" ,;-")
    if len(head) > 30:
        head = head[:29].rstrip() + "…"
    return head or code
