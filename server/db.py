"""Truy cập CSDL SQLite cho hệ thống bốc số / gọi số — bản ĐA CHI NHÁNH.

CSDL mới (`hethong_v2.db`), không dùng lại dữ liệu bản 1 chi nhánh.
Mọi dữ liệu nghiệp vụ (queue, counters_status, config, visitor_stats,
appointments) đều gắn `branch_id`. `config.branch_id = 0` là cấu hình toàn cục
(hiện chỉ có `admin_password`).
"""
import json
import os
import secrets
import sqlite3
import threading
from datetime import datetime

# hethong_v2.db nằm ở thư mục gốc dự án (cha của thư mục server/)
DB_PATH = os.environ.get(
    "GOISO_DB",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hethong_v2.db"),
)

# SQLite ghi tuần tự; khoá này bảo vệ các thao tác đọc-sửa-ghi phức hợp
LOCK = threading.RLock()

GLOBAL = 0  # branch_id cho cấu hình toàn cục


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=8000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _column_names(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def init_db():
    """Tạo bảng nếu chưa có. An toàn khi gọi nhiều lần."""
    with LOCK, get_conn() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS branches
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  code TEXT UNIQUE NOT NULL,
                  name TEXT NOT NULL,
                  full_name TEXT NOT NULL,
                  address TEXT DEFAULT '',
                  active INTEGER DEFAULT 1,
                  display_order INTEGER DEFAULT 99,
                  api_key TEXT NOT NULL,
                  display_token TEXT NOT NULL,
                  created_at TEXT)"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS queue
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  branch_id INTEGER NOT NULL,
                  prefix TEXT, number INTEGER,
                  status TEXT, counter TEXT DEFAULT '', staff_name TEXT DEFAULT '',
                  date_record TEXT,
                  time_issue TEXT, time_start TEXT, time_done TEXT,
                  fullname TEXT DEFAULT '', cccd TEXT DEFAULT '', phone TEXT DEFAULT '',
                  session TEXT DEFAULT '',
                  source TEXT DEFAULT 'kiosk',
                  priority INTEGER DEFAULT 0,
                  appointment_id INTEGER)"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS counters_status
                 (branch_id INTEGER NOT NULL,
                  counter_id TEXT NOT NULL,
                  staff_name TEXT DEFAULT '', status TEXT DEFAULT 'offline',
                  last_num TEXT DEFAULT '', last_update TEXT,
                  PRIMARY KEY (branch_id, counter_id))"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS config
                 (branch_id INTEGER NOT NULL DEFAULT 0,
                  key TEXT NOT NULL, value TEXT,
                  PRIMARY KEY (branch_id, key))"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS visitor_stats
                 (branch_id INTEGER NOT NULL, date_record TEXT NOT NULL,
                  count INTEGER DEFAULT 0,
                  PRIMARY KEY (branch_id, date_record))"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS appointments
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  branch_id INTEGER NOT NULL,
                  prefix TEXT NOT NULL,
                  slot_date TEXT NOT NULL, slot_start TEXT NOT NULL, slot_end TEXT NOT NULL,
                  code TEXT NOT NULL, token TEXT NOT NULL UNIQUE,
                  citizen_name TEXT DEFAULT '', cccd TEXT DEFAULT '', phone TEXT DEFAULT '',
                  status TEXT DEFAULT 'booked',
                  created_at TEXT, checkin_at TEXT,
                  queue_id INTEGER, ip TEXT DEFAULT '')"""
        )

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_queue_main "
            "ON queue(branch_id, date_record, prefix, status, number)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_queue_counter "
            "ON queue(branch_id, date_record, counter, status)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_appt_slot "
            "ON appointments(branch_id, slot_date, prefix, status)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_appt_code ON appointments(branch_id, code)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_appt_cccd ON appointments(branch_id, cccd, status)"
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  full_name TEXT NOT NULL,
                  password_hash TEXT NOT NULL,
                  role TEXT NOT NULL DEFAULT 'staff',    -- 'staff' | 'admin'
                  branch_id INTEGER,                     -- NULL với admin
                  active INTEGER DEFAULT 1,
                  created_at TEXT)"""
        )

        existing = {row[0] for row in conn.execute(
            "SELECT key FROM config WHERE branch_id=0"
        )}
        if "admin_password" not in existing:
            conn.execute("INSERT INTO config(branch_id, key, value) VALUES(0, 'admin_password', ?)",
                         (DEFAULT_ADMIN_PW,))
        # Seed tài khoản admin 'admin' dùng chính mật khẩu quản trị hiện có.
        if not conn.execute("SELECT 1 FROM users WHERE role='admin'").fetchone():
            pw = conn.execute(
                "SELECT value FROM config WHERE branch_id=0 AND key='admin_password'"
            ).fetchone()
            conn.execute(
                "INSERT INTO users(username, full_name, password_hash, role, branch_id, created_at) "
                "VALUES('admin', 'Quản trị hệ thống', ?, 'admin', NULL, ?)",
                (pw[0] if pw else DEFAULT_ADMIN_PW, now_str()),
            )
    _invalidate_branch_cache()


# --------------------------------------------------------------- mẫu cấu hình
DEFAULT_COUNTERS = {
    "Quầy số 01": {"active": True, "staff": "", "prefix": "A", "display_order": 1},
    "Quầy số 02": {"active": True, "staff": "", "prefix": "A", "display_order": 2},
    "Quầy số 03": {"active": True, "staff": "", "prefix": "B", "display_order": 3},
    "Quầy số 04": {"active": True, "staff": "", "prefix": "C", "display_order": 4},
    "Quầy số 05": {"active": True, "staff": "", "prefix": "A,B,C", "display_order": 5},
}

DEFAULT_SERVICES = {
    "A": {"name": "ĐĂNG KÝ ĐẤT ĐAI", "short": "Đăng ký đất đai",
          "color": "#3498db", "daily_limit": 200, "active": True},
    "B": {"name": "GIAO DỊCH BẢO ĐẢM", "short": "Giao dịch bảo đảm",
          "color": "#e67e22", "daily_limit": 200, "active": True},
    "C": {"name": "TRẢ KẾT QUẢ", "short": "Trả kết quả",
          "color": "#27ae60", "daily_limit": 300, "active": True},
}

DEFAULT_EXTRA = {
    "ten_co_quan": "VĂN PHÒNG ĐĂNG KÝ ĐẤT ĐAI",
    "link_qr": "",
    "logo_path": "",
    "qr_enabled": False,
    "background_color": "#f5f7fa",
    "counter_pin": "",  # PIN "Vào ca" cho /counter; "" = không yêu cầu
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
    "voice_template": "Xin mời số thứ tự {so}, đến quầy số {quay}",
    # Đọc số: "server" = máy chủ tạo giọng tiếng Việt (không cần cài gì trên TV);
    # "browser" = dùng giọng của trình duyệt/Windows.
    "tts_mode": "server",
    "tts_voice": "vi-VN-HoaiMyNeural",  # hoặc vi-VN-NamMinhNeural (giọng nam)
    "spotlight_seconds": 20,
    "recent_count": 8,
    # Dòng ghi công ở chân mọi giao diện (2 dòng, ngăn bằng \n).
    "footer_credit": "Phòng Dữ liệu - Thông tin đất đai\nTổ Ứng dụng và Phát triển công nghệ",
}

DEFAULT_BOOKING = {
    "enabled": False,
    "open_days_ahead": 3,
    "slot_minutes": 30,
    "windows": [
        {"start": "07:30", "end": "11:00"},
        {"start": "13:30", "end": "16:00"},
    ],
    "capacity_per_slot": {"_default": 4},
    "max_active_per_cccd": 1,
    "checkin_grace_minutes": 15,
    "online_priority": False,
    "turnstile": True,
}

# Mật khẩu quản trị mặc định: "admin123" (sha256). Đổi trong trang /admin.
DEFAULT_ADMIN_PW = "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9"


# ---------------------------------------------------------------- config helpers
def get_config(key, default=None, branch_id=GLOBAL):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT value FROM config WHERE branch_id=? AND key=?", (branch_id, key)
        ).fetchone()
    return default if row is None else row[0]


def get_json_config(key, default=None, branch_id=GLOBAL):
    raw = get_config(key, None, branch_id)
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return default


def set_json_config(key, obj, branch_id=GLOBAL):
    set_config(key, json.dumps(obj, ensure_ascii=False), branch_id)


def set_config(key, value, branch_id=GLOBAL):
    with LOCK, get_conn() as conn:
        conn.execute(
            "INSERT INTO config(branch_id, key, value) VALUES(?, ?, ?) "
            "ON CONFLICT(branch_id, key) DO UPDATE SET value=excluded.value",
            (branch_id, key, value),
        )


def get_extra(branch_id):
    data = dict(DEFAULT_EXTRA)
    data.update(get_json_config("extra", {}, branch_id) or {})
    return data


def get_booking_config(branch_id):
    data = dict(DEFAULT_BOOKING)
    data.update(get_json_config("booking", {}, branch_id) or {})
    return data


# ---------------------------------------------------------------- branch helpers
_branch_cache = {}          # code -> dict
_branch_cache_by_id = {}    # id   -> dict
_branch_cache_lock = threading.Lock()


def _invalidate_branch_cache():
    with _branch_cache_lock:
        _branch_cache.clear()
        _branch_cache_by_id.clear()


def _row_to_branch(row):
    return {
        "id": row["id"], "code": row["code"], "name": row["name"],
        "full_name": row["full_name"], "address": row["address"] or "",
        "active": bool(row["active"]), "display_order": row["display_order"],
        "api_key": row["api_key"], "display_token": row["display_token"],
        "created_at": row["created_at"],
    }


def get_branch(code):
    code = (code or "").strip().lower()
    if not code:
        return None
    with _branch_cache_lock:
        if code in _branch_cache:
            return _branch_cache[code]
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM branches WHERE code=?", (code,)).fetchone()
    b = _row_to_branch(row) if row else None
    with _branch_cache_lock:
        _branch_cache[code] = b
        if b:
            _branch_cache_by_id[b["id"]] = b
    return b


def get_branch_by_id(branch_id):
    with _branch_cache_lock:
        if branch_id in _branch_cache_by_id:
            return _branch_cache_by_id[branch_id]
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM branches WHERE id=?", (branch_id,)).fetchone()
    b = _row_to_branch(row) if row else None
    if b:
        with _branch_cache_lock:
            _branch_cache_by_id[branch_id] = b
            _branch_cache[b["code"]] = b
    return b


def list_branches(active_only=False):
    q = "SELECT * FROM branches"
    if active_only:
        q += " WHERE active=1"
    q += " ORDER BY display_order, code"
    with get_conn() as conn:
        return [_row_to_branch(r) for r in conn.execute(q)]


def gen_token(nbytes=24):
    return secrets.token_urlsafe(nbytes)


def create_branch(code, name, full_name, address="", display_order=None):
    """Tạo chi nhánh mới + seed cấu hình mặc định cho chi nhánh đó."""
    code = (code or "").strip().lower()
    if not code or not code.replace("-", "").replace("_", "").isalnum():
        raise ValueError("Mã chi nhánh chỉ gồm chữ/số/gạch, ví dụ 'bmt'.")
    with LOCK, get_conn() as conn:
        if conn.execute("SELECT 1 FROM branches WHERE code=?", (code,)).fetchone():
            raise ValueError(f"Chi nhánh '{code}' đã tồn tại.")
        if display_order is None:
            mx = conn.execute("SELECT COALESCE(MAX(display_order), 0) FROM branches").fetchone()[0]
            display_order = mx + 1
        cur = conn.execute(
            """INSERT INTO branches
                 (code, name, full_name, address, active, display_order,
                  api_key, display_token, created_at)
               VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)""",
            (code, name.strip(), full_name.strip(), address.strip(), display_order,
             gen_token(24), gen_token(16), now_str()),
        )
        bid = cur.lastrowid
        for key, obj in (("services", DEFAULT_SERVICES), ("counters", DEFAULT_COUNTERS),
                         ("extra", {}), ("booking", {})):
            conn.execute(
                "INSERT INTO config(branch_id, key, value) VALUES(?, ?, ?)",
                (bid, key, json.dumps(obj, ensure_ascii=False)),
            )
    _invalidate_branch_cache()
    return get_branch(code)


def update_branch(code, **fields):
    allowed = {"name", "full_name", "address", "active", "display_order"}
    sets, vals = [], []
    for k, v in fields.items():
        if k in allowed:
            sets.append(f"{k}=?")
            vals.append(int(v) if k in ("active", "display_order") else str(v).strip())
    if not sets:
        return get_branch(code)
    vals.append((code or "").strip().lower())
    with LOCK, get_conn() as conn:
        conn.execute(f"UPDATE branches SET {', '.join(sets)} WHERE code=?", vals)
    _invalidate_branch_cache()
    return get_branch(code)


def regen_branch_field(code, field):
    if field not in ("api_key", "display_token"):
        raise ValueError("field phải là api_key hoặc display_token.")
    token = gen_token(24 if field == "api_key" else 16)
    with LOCK, get_conn() as conn:
        conn.execute(f"UPDATE branches SET {field}=? WHERE code=?",
                     (token, (code or "").strip().lower()))
    _invalidate_branch_cache()
    return token


def delete_branch(code):
    code = (code or "").strip().lower()
    with LOCK, get_conn() as conn:
        row = conn.execute("SELECT id FROM branches WHERE code=?", (code,)).fetchone()
        if not row:
            return
        bid = row["id"]
        for t in ("queue", "counters_status", "visitor_stats", "appointments"):
            conn.execute(f"DELETE FROM {t} WHERE branch_id=?", (bid,))
        conn.execute("DELETE FROM config WHERE branch_id=?", (bid,))
        conn.execute("DELETE FROM users WHERE branch_id=?", (bid,))
        conn.execute("DELETE FROM branches WHERE id=?", (bid,))
    _invalidate_branch_cache()


# ---------------------------------------------------------------- người dùng
def _pw_hash(pw):
    import hashlib
    return hashlib.sha256((pw or "").encode("utf-8")).hexdigest()


def strip_accents(s):
    """Bỏ dấu tiếng Việt -> ASCII thường (đ/Đ -> d)."""
    import unicodedata
    s = (s or "").replace("Đ", "D").replace("đ", "d")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s


def gen_username(branch_code, full_name):
    """cn<mã>.<tên><chữ-cái-đầu-các-từ-còn-lại>. VD 'Mai Xuân Chiến' @ bmt -> cnbmt.chienmx."""
    words = ["".join(ch for ch in w if ch.isalnum())
             for w in strip_accents(full_name).lower().split()]
    words = [w for w in words if w]
    code = (branch_code or "").strip().lower()
    if not words:
        return f"cn{code}.user"
    ten, initials = words[-1], "".join(w[0] for w in words[:-1])
    return f"cn{code}.{ten}{initials}"


def unique_username(base):
    """Thêm hậu tố số nếu username đã tồn tại."""
    with get_conn() as conn:
        taken = {r[0] for r in conn.execute(
            "SELECT username FROM users WHERE username=? OR username LIKE ?",
            (base, base + "%"),
        )}
    if base not in taken:
        return base
    i = 2
    while f"{base}{i}" in taken:
        i += 1
    return f"{base}{i}"


def _row_to_user(r):
    if not r:
        return None
    b = get_branch_by_id(r["branch_id"]) if r["branch_id"] else None
    return {
        "id": r["id"], "username": r["username"], "full_name": r["full_name"],
        "role": r["role"], "branch_id": r["branch_id"],
        "branch_code": b["code"] if b else None,
        "branch_name": b["full_name"] if b else None,
        "active": bool(r["active"]), "created_at": r["created_at"],
    }


def get_user_by_username(username):
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM users WHERE username=?",
                         ((username or "").strip().lower(),)).fetchone()
    return _row_to_user(r)


def get_user(uid):
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    return _row_to_user(r)


def verify_login(username, password):
    """Trả về dict user nếu đúng tài khoản + đang bật; ngược lại None."""
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM users WHERE username=?",
                         ((username or "").strip().lower(),)).fetchone()
    if not r or not r["active"]:
        return None
    if _pw_hash(password) != r["password_hash"]:
        return None
    return _row_to_user(r)


def list_users():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM users ORDER BY role DESC, branch_id, username"
        ).fetchall()
    return [_row_to_user(r) for r in rows]


def create_user(username, full_name, password, role="staff", branch_code=None):
    username = (username or "").strip().lower()
    if not username or not username.replace("_", "").replace(".", "").replace("-", "").isalnum():
        raise ValueError("Tên đăng nhập chỉ gồm chữ thường/số/._- .")
    if not (full_name or "").strip():
        raise ValueError("Thiếu họ tên.")
    if not (password or "").strip():
        raise ValueError("Thiếu mật khẩu.")
    role = "admin" if role == "admin" else "staff"
    bid = None
    if role == "staff":
        b = get_branch(branch_code)
        if not b:
            raise ValueError("Nhân viên phải thuộc một chi nhánh hợp lệ.")
        bid = b["id"]
    with LOCK, get_conn() as conn:
        if conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
            raise ValueError(f"Tên đăng nhập '{username}' đã tồn tại.")
        conn.execute(
            "INSERT INTO users(username, full_name, password_hash, role, branch_id, created_at) "
            "VALUES(?, ?, ?, ?, ?, ?)",
            (username, full_name.strip(), _pw_hash(password), role, bid, now_str()),
        )
    return get_user_by_username(username)


def update_user(username, full_name=None, password=None, branch_code=None,
                role=None, active=None):
    username = (username or "").strip().lower()
    sets, vals = [], []
    if full_name is not None and full_name.strip():
        sets.append("full_name=?"); vals.append(full_name.strip())
    if password:
        sets.append("password_hash=?"); vals.append(_pw_hash(password))
    if role in ("staff", "admin"):
        sets.append("role=?"); vals.append(role)
        if role == "admin":
            sets.append("branch_id=NULL")
    if branch_code is not None and (role != "admin"):
        b = get_branch(branch_code)
        if not b:
            raise ValueError("Chi nhánh không hợp lệ.")
        sets.append("branch_id=?"); vals.append(b["id"])
    if active is not None:
        sets.append("active=?"); vals.append(1 if active else 0)
    if not sets:
        return get_user_by_username(username)
    vals.append(username)
    with LOCK, get_conn() as conn:
        conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE username=?", vals)
    return get_user_by_username(username)


def delete_user(username):
    username = (username or "").strip().lower()
    with LOCK, get_conn() as conn:
        n = conn.execute("SELECT COUNT(*) FROM users WHERE role='admin'").fetchone()[0]
        r = conn.execute("SELECT role FROM users WHERE username=?", (username,)).fetchone()
        if r and r["role"] == "admin" and n <= 1:
            raise ValueError("Không thể xoá tài khoản admin cuối cùng.")
        conn.execute("DELETE FROM users WHERE username=?", (username,))


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
