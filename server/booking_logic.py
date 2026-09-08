"""Đặt lịch hẹn online (bốc số theo khung giờ).

Người dân đặt: chi nhánh + dịch vụ + ngày + khung giờ -> nhận mã hẹn `code` + `token`.
Đến kiosk nhập `code` (hoặc quét QR mở /lich-hen/<token>) -> đổi lấy phiếu số thật,
số này đi vào hàng chờ như khách vãng lai (nguồn = 'online').
"""
import os
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

import db
import queue_logic as ql

TURNSTILE_SECRET = os.environ.get("TURNSTILE_SECRET", "")
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

# Bảng chữ mã hẹn: bỏ ký tự dễ nhầm (0/O, 1/I, ...)
_CODE_ALPHABET = "ACDEFGHJKLMNPQRSTUVWXYZ2345679"


class BookingError(Exception):
    """Lỗi nghiệp vụ đặt lịch, thông điệp hiển thị được cho người dùng."""


# --------------------------------------------------------------------- helpers
def _hhmm_to_min(s):
    h, m = str(s).split(":")
    return int(h) * 60 + int(m)


def _min_to_hhmm(x):
    return f"{x // 60:02d}:{x % 60:02d}"


def _capacity(cfg, prefix):
    caps = cfg.get("capacity_per_slot") or {}
    return int(caps.get(prefix, caps.get("_default", 4)))


def _gen_code(conn, branch_id):
    import secrets
    for _ in range(20):
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))
        code = code[:4] + "-" + code[4:]
        hit = conn.execute(
            "SELECT 1 FROM appointments WHERE branch_id=? AND code=?", (branch_id, code)
        ).fetchone()
        if not hit:
            return code
    raise BookingError("Không tạo được mã hẹn, thử lại.")


# --------------------------------------------------------------- danh sách slot
def list_slots(branch_id, slot_date, prefix):
    """Trả về danh sách khung giờ còn chỗ cho (ngày, dịch vụ)."""
    cfg = db.get_booking_config(branch_id)
    if not cfg.get("enabled"):
        raise BookingError("Chi nhánh chưa mở đặt lịch online.")

    services = db.get_json_config("services", {}, branch_id) or {}
    if prefix not in services or not services[prefix].get("active", True):
        raise BookingError("Dịch vụ không hợp lệ.")

    try:
        d = datetime.strptime(slot_date, "%Y-%m-%d").date()
    except ValueError:
        raise BookingError("Ngày không hợp lệ.")
    today = date.today()
    if d < today or d > today + timedelta(days=int(cfg.get("open_days_ahead", 3))):
        raise BookingError("Ngày ngoài phạm vi cho phép đặt.")

    step = int(cfg.get("slot_minutes", 30))
    cap = _capacity(cfg, prefix)
    now_min = datetime.now().hour * 60 + datetime.now().minute

    with db.get_conn() as conn:
        taken = {
            r["slot_start"]: r["c"]
            for r in conn.execute(
                "SELECT slot_start, COUNT(*) c FROM appointments "
                "WHERE branch_id=? AND slot_date=? AND prefix=? AND status IN ('booked','checked_in') "
                "GROUP BY slot_start",
                (branch_id, slot_date, prefix),
            )
        }

    slots = []
    for win in cfg.get("windows") or []:
        a, b = _hhmm_to_min(win["start"]), _hhmm_to_min(win["end"])
        t = a
        while t + step <= b:
            start, end = _min_to_hhmm(t), _min_to_hhmm(t + step)
            used = taken.get(start, 0)
            remaining = max(0, cap - used)
            is_past = (d == today and t + step <= now_min)
            if not is_past:
                slots.append({
                    "start": start, "end": end,
                    "remaining": remaining, "capacity": cap,
                    "full": remaining <= 0,
                })
            t += step
    return slots


# --------------------------------------------------------------------- đặt lịch
def create_appointment(branch_id, prefix, slot_date, slot_start,
                       citizen_name, cccd, phone, ip=""):
    cfg = db.get_booking_config(branch_id)
    if not cfg.get("enabled"):
        raise BookingError("Chi nhánh chưa mở đặt lịch online.")

    citizen_name = (citizen_name or "").strip()
    cccd = "".join(ch for ch in (cccd or "") if ch.isdigit())
    phone = "".join(ch for ch in (phone or "") if ch.isdigit())
    if len(citizen_name) < 2:
        raise BookingError("Vui lòng nhập họ tên.")
    if not (9 <= len(cccd) <= 12):
        raise BookingError("Số CCCD/CMND không hợp lệ (9–12 chữ số).")
    if not (9 <= len(phone) <= 11):
        raise BookingError("Số điện thoại không hợp lệ.")

    # slot phải nằm trong danh sách còn chỗ
    avail = {s["start"]: s for s in list_slots(branch_id, slot_date, prefix)}
    slot = avail.get(slot_start)
    if slot is None:
        raise BookingError("Khung giờ không còn hợp lệ, vui lòng chọn lại.")

    max_active = int(cfg.get("max_active_per_cccd", 1))

    with db.LOCK, db.get_conn() as conn:
        used = conn.execute(
            "SELECT COUNT(*) FROM appointments WHERE branch_id=? AND slot_date=? AND prefix=? "
            "AND slot_start=? AND status IN ('booked','checked_in')",
            (branch_id, slot_date, prefix, slot_start),
        ).fetchone()[0]
        if used >= slot["capacity"]:
            raise BookingError("Khung giờ vừa hết chỗ, vui lòng chọn khung khác.")

        if max_active:
            open_cnt = conn.execute(
                "SELECT COUNT(*) FROM appointments WHERE branch_id=? AND cccd=? AND status='booked'",
                (branch_id, cccd),
            ).fetchone()[0]
            if open_cnt >= max_active:
                raise BookingError(
                    f"Mỗi CCCD chỉ được giữ {max_active} lịch hẹn đang chờ. "
                    "Vui lòng dùng lịch cũ hoặc huỷ trước khi đặt mới.")

        code = _gen_code(conn, branch_id)
        token = db.gen_token(24)
        cur = conn.execute(
            """INSERT INTO appointments
                 (branch_id, prefix, slot_date, slot_start, slot_end, code, token,
                  citizen_name, cccd, phone, status, created_at, ip)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'booked', ?, ?)""",
            (branch_id, prefix, slot_date, slot_start, slot["end"], code, token,
             citizen_name, cccd, phone, db.now_str(), ip),
        )
        appt_id = cur.lastrowid

    return appointment_view(token)


# --------------------------------------------------------------------- tra cứu
def appointment_view(token):
    with db.get_conn() as conn:
        r = conn.execute("SELECT * FROM appointments WHERE token=?", (token,)).fetchone()
    if r is None:
        raise BookingError("Không tìm thấy lịch hẹn.")
    branch = db.get_branch_by_id(r["branch_id"])
    services = db.get_json_config("services", {}, r["branch_id"]) or {}
    svc = services.get(r["prefix"], {})
    q_no = None
    if r["queue_id"]:
        with db.get_conn() as conn:
            qr = conn.execute("SELECT prefix, number FROM queue WHERE id=?", (r["queue_id"],)).fetchone()
        if qr:
            q_no = db.full_no(qr["prefix"], qr["number"])
    return {
        "token": r["token"], "code": r["code"], "status": r["status"],
        "branch_code": branch["code"] if branch else None,
        "branch_name": branch["full_name"] if branch else "",
        "prefix": r["prefix"],
        "service_name": svc.get("name", r["prefix"]),
        "service_short": db.short_label(svc, r["prefix"]),
        "slot_date": r["slot_date"], "slot_start": r["slot_start"], "slot_end": r["slot_end"],
        "citizen_name": r["citizen_name"], "phone": r["phone"],
        "created_at": r["created_at"], "checkin_at": r["checkin_at"],
        "queue_no": q_no,
    }


def cancel(token):
    with db.LOCK, db.get_conn() as conn:
        r = conn.execute("SELECT status FROM appointments WHERE token=?", (token,)).fetchone()
        if r is None:
            raise BookingError("Không tìm thấy lịch hẹn.")
        if r["status"] != "booked":
            raise BookingError("Lịch hẹn không ở trạng thái có thể huỷ.")
        conn.execute("UPDATE appointments SET status='cancelled' WHERE token=?", (token,))
    return {"ok": True}


# --------------------------------------------------------------------- check-in
def checkin(branch_id, code_or_token):
    key = (code_or_token or "").strip()
    if not key:
        raise BookingError("Thiếu mã lịch hẹn.")
    key_code = key.upper().replace(" ", "")
    if len(key_code) == 8 and "-" not in key_code:
        key_code = key_code[:4] + "-" + key_code[4:]

    cfg = db.get_booking_config(branch_id)
    grace = int(cfg.get("checkin_grace_minutes", 15))
    prio = 1 if cfg.get("online_priority") else 0
    today = db.today_str()

    with db.LOCK, db.get_conn() as conn:
        r = conn.execute(
            "SELECT * FROM appointments WHERE branch_id=? AND (code=? OR token=?)",
            (branch_id, key_code, key),
        ).fetchone()
        if r is None:
            raise BookingError("Không tìm thấy lịch hẹn ở chi nhánh này.")
        if r["status"] == "checked_in":
            raise BookingError("Lịch hẹn này đã được check-in.")
        if r["status"] != "booked":
            raise BookingError("Lịch hẹn đã bị huỷ hoặc hết hạn.")
        if r["slot_date"] != today:
            raise BookingError(f"Lịch hẹn của quý khách là ngày {r['slot_date']}, chưa phải hôm nay.")

        now = datetime.now()
        cur_min = now.hour * 60 + now.minute
        s_min = _hhmm_to_min(r["slot_start"])
        e_min = _hhmm_to_min(r["slot_end"])
        if cur_min < s_min - grace:
            raise BookingError(f"Chưa đến giờ hẹn ({r['slot_start']}). Vui lòng quay lại gần giờ hẹn.")
        if cur_min > e_min + grace:
            raise BookingError("Đã quá giờ hẹn. Vui lòng lấy số trực tiếp tại kiosk.")

        appt_id = r["id"]

    # cấp phiếu số thật (ngoài lock để issue_ticket tự quản lý lock của nó)
    ticket = ql.issue_ticket(
        branch_id, r["prefix"], fullname=r["citizen_name"], cccd=r["cccd"],
        phone=r["phone"], source="online", priority=prio, appointment_id=appt_id,
    )
    with db.LOCK, db.get_conn() as conn:
        conn.execute(
            "UPDATE appointments SET status='checked_in', checkin_at=?, queue_id=? WHERE id=?",
            (db.now_str(), ticket["id"], appt_id),
        )
    ticket["appointment_code"] = r["code"]
    return ticket


# --------------------------------------------------------------------- dọn hạn
def expire_stale():
    """Đổi 'booked' -> 'expired' cho lịch hẹn đã qua khung giờ + ân hạn."""
    for b in db.list_branches():
        grace = int(db.get_booking_config(b["id"]).get("checkin_grace_minutes", 15))
        with db.LOCK, db.get_conn() as conn:
            conn.execute(
                """UPDATE appointments SET status='expired'
                   WHERE branch_id=? AND status='booked'
                     AND datetime(slot_date || ' ' || slot_end, ?) < datetime('now','localtime')""",
                (b["id"], f"+{grace} minutes"),
            )


# --------------------------------------------------------------------- Turnstile
def verify_turnstile(branch_id, token, ip=""):
    if not db.get_booking_config(branch_id).get("turnstile"):
        return True
    if not TURNSTILE_SECRET:
        return True  # chưa cấu hình secret -> bỏ qua (chỉ nên dùng khi chạy thử)
    data = urllib.parse.urlencode({
        "secret": TURNSTILE_SECRET, "response": token or "", "remoteip": ip,
    }).encode()
    try:
        with urllib.request.urlopen(TURNSTILE_VERIFY_URL, data=data, timeout=6) as resp:
            import json
            return bool(json.loads(resp.read()).get("success"))
    except Exception:  # noqa: BLE001
        return False


# --------------------------------------------------------------------- rate limit
_rl = {}  # ip -> [timestamps]
_RL_MAX = 6
_RL_WINDOW = 3600


def rate_limit_ok(ip):
    now = time.time()
    xs = [t for t in _rl.get(ip, []) if now - t < _RL_WINDOW]
    if len(xs) >= _RL_MAX:
        _rl[ip] = xs
        return False
    xs.append(now)
    _rl[ip] = xs
    return True


# --------------------------------------------------------------- danh sách công khai
def public_branches():
    out = []
    for b in db.list_branches(active_only=True):
        cfg = db.get_booking_config(b["id"])
        if not cfg.get("enabled"):
            continue
        services = db.get_json_config("services", {}, b["id"]) or {}
        out.append({
            "code": b["code"], "name": b["name"], "full_name": b["full_name"],
            "address": b["address"],
            "open_days_ahead": int(cfg.get("open_days_ahead", 3)),
            "services": [
                {"prefix": k, "name": v.get("name", k), "short": db.short_label(v, k),
                 "color": v.get("color", "#0b5fa5")}
                for k, v in sorted(services.items()) if v.get("active", True)
            ],
        })
    return out
