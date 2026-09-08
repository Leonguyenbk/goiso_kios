"""Nghiệp vụ cấp số, gọi số, trạng thái quầy."""
from datetime import datetime

import db


class QueueError(Exception):
    """Lỗi nghiệp vụ, thông điệp hiển thị được cho người dùng."""


# --------------------------------------------------------------------- cấp số
def issue_ticket(prefix, fullname="", cccd="", phone=""):
    """Cấp một số mới cho dịch vụ `prefix`. Trả về dict thông tin phiếu."""
    services = db.get_json_config("services", {}) or {}
    svc = services.get(prefix)
    if not svc or not svc.get("active", True):
        raise QueueError("Dịch vụ không hoạt động.")

    extra = db.get_extra()
    _check_time_lock(extra)

    day = db.today_str()
    with db.LOCK, db.get_conn() as conn:
        limit = int(svc.get("daily_limit") or 0)
        issued_today = conn.execute(
            "SELECT COUNT(*) FROM queue WHERE prefix=? AND date_record=?", (prefix, day)
        ).fetchone()[0]
        if limit and issued_today >= limit:
            raise QueueError("Đã hết lượt cấp số trong ngày cho dịch vụ này.")

        row = conn.execute(
            "SELECT COALESCE(MAX(number), 0) FROM queue WHERE prefix=? AND date_record=?",
            (prefix, day),
        ).fetchone()
        number = int(row[0]) + 1
        now = db.now_str()
        sess = db.session_now()
        cur = conn.execute(
            """INSERT INTO queue
                 (prefix, number, status, counter, staff_name, agency, time_start,
                  date_record, fullname, cccd, session, phone, time_issue)
               VALUES (?, ?, 'waiting', '', '', ?, NULL, ?, ?, ?, ?, ?, ?)""",
            (prefix, number, extra.get("ten_chi_nhanh", ""), day,
             fullname.strip(), cccd.strip(), sess, phone.strip(), now),
        )
        ticket_id = cur.lastrowid

        # cập nhật bộ đếm dịch vụ + lượt khách trong ngày
        svc["current_count"] = int(svc.get("current_count") or 0) + 1
        services[prefix] = svc
        conn.execute("UPDATE config SET value=? WHERE key='services'",
                     (_dumps(services),))
        conn.execute(
            "INSERT INTO visitor_stats(date_record, count) VALUES(?, 1) "
            "ON CONFLICT(date_record) DO UPDATE SET count = count + 1",
            (day,),
        )

        waiting_ahead = conn.execute(
            "SELECT COUNT(*) FROM queue WHERE prefix=? AND date_record=? AND status='waiting' AND number<?",
            (prefix, day, number),
        ).fetchone()[0]

    return {
        "id": ticket_id,
        "prefix": prefix,
        "number": number,
        "full_no": db.full_no(prefix, number),
        "service_name": svc.get("name", prefix),
        "service_short": db.short_label(svc, prefix),
        "service_color": svc.get("color", "#0b5fa5"),
        "waiting_ahead": waiting_ahead,
        "session": sess,
        "time_issue": now,
        "date_record": day,
    }


def _check_time_lock(extra):
    if not extra.get("lock_time_enabled"):
        return
    now = datetime.now()
    wd = now.weekday()  # 5=Bảy, 6=CN
    if wd == 5 and not extra.get("allow_saturday"):
        raise QueueError(extra.get("lock_message", "Ngoài giờ làm việc."))
    if wd == 6 and not extra.get("allow_sunday"):
        raise QueueError(extra.get("lock_message", "Ngoài giờ làm việc."))
    slots = extra.get("time_slots") or []
    if not slots:
        return
    minutes = now.hour * 60 + now.minute
    for s in slots:
        start = int(s.get("start_hour", 0)) * 60 + int(s.get("start_minute", 0))
        end = int(s.get("end_hour", 23)) * 60 + int(s.get("end_minute", 59))
        if start <= minutes <= end:
            return
    raise QueueError(extra.get("lock_message", "Ngoài giờ làm việc."))


def within_time_lock():
    """True nếu ĐANG trong giờ cho phép lấy số (hoặc không khoá giờ)."""
    try:
        _check_time_lock(db.get_extra())
        return True
    except QueueError:
        return False


# ------------------------------------------------------- prefix mà quầy phục vụ
def counter_prefixes(counter_id):
    counters = db.get_json_config("counters", {}) or {}
    conf = counters.get(counter_id) or {}
    raw = str(conf.get("prefix", "")).strip()
    return [p.strip() for p in raw.split(",") if p.strip()]


def _counter_number(counter_id):
    """'Quầy số 03' -> '3' (đọc TTS); fallback là chính chuỗi."""
    digits = "".join(ch for ch in counter_id if ch.isdigit())
    return str(int(digits)) if digits else counter_id


# --------------------------------------------------------------------- gọi số
def call_next(counter_id, staff_name=""):
    prefixes = counter_prefixes(counter_id)
    if not prefixes:
        raise QueueError(f"{counter_id} chưa gán dịch vụ.")
    day = db.today_str()
    now = db.now_str()
    with db.LOCK, db.get_conn() as conn:
        # kết thúc số đang phục vụ ở quầy này (nếu có)
        conn.execute(
            "UPDATE queue SET status='done', time_done=? "
            "WHERE counter=? AND date_record=? AND status='serving'",
            (now, counter_id, day),
        )
        placeholders = ",".join("?" * len(prefixes))
        nxt = conn.execute(
            f"""SELECT * FROM queue
                WHERE date_record=? AND status='waiting' AND prefix IN ({placeholders})
                ORDER BY id ASC LIMIT 1""",
            [day, *prefixes],
        ).fetchone()
        if nxt is None:
            raise QueueError("Không còn số nào đang chờ.")
        conn.execute(
            "UPDATE queue SET status='serving', counter=?, staff_name=?, time_start=? WHERE id=?",
            (counter_id, staff_name, now, nxt["id"]),
        )
        fno = db.full_no(nxt["prefix"], nxt["number"])
        _touch_counter(conn, counter_id, staff_name, fno, status="active")
        called = _row_to_call(conn, nxt["id"])
    return called


def recall(counter_id):
    day = db.today_str()
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM queue WHERE counter=? AND date_record=? AND status='serving' "
            "ORDER BY time_start DESC LIMIT 1",
            (counter_id, day),
        ).fetchone()
        if row is None:
            raise QueueError("Quầy chưa gọi số nào để gọi lại.")
        return _row_to_call(conn, row["id"], is_recall=True)


def finish_current(counter_id):
    day = db.today_str()
    now = db.now_str()
    with db.LOCK, db.get_conn() as conn:
        n = conn.execute(
            "UPDATE queue SET status='done', time_done=? "
            "WHERE counter=? AND date_record=? AND status='serving'",
            (now, counter_id, day),
        ).rowcount
    if not n:
        raise QueueError("Không có số nào đang phục vụ.")
    return {"ok": True}


def mark_missed(counter_id):
    day = db.today_str()
    now = db.now_str()
    with db.LOCK, db.get_conn() as conn:
        n = conn.execute(
            "UPDATE queue SET status='missed', time_done=? "
            "WHERE counter=? AND date_record=? AND status='serving'",
            (now, counter_id, day),
        ).rowcount
    if not n:
        raise QueueError("Không có số nào đang phục vụ.")
    return {"ok": True}


def call_specific(counter_id, full_no_str, staff_name=""):
    day = db.today_str()
    now = db.now_str()
    s = full_no_str.strip().upper().replace(" ", "")
    if "-" in s:
        prefix, num = s.split("-", 1)
    else:
        prefix, num = s[:1], s[1:]
    try:
        num = int(num)
    except ValueError:
        raise QueueError("Số không hợp lệ. Ví dụ: A-25")
    with db.LOCK, db.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM queue WHERE date_record=? AND prefix=? AND number=?",
            (day, prefix, num),
        ).fetchone()
        if row is None:
            raise QueueError(f"Không tìm thấy số {prefix}-{num:03d} trong hôm nay.")
        if row["status"] == "done":
            raise QueueError(f"Số {prefix}-{num:03d} đã xử lý xong.")
        conn.execute(
            "UPDATE queue SET status='done', time_done=? "
            "WHERE counter=? AND date_record=? AND status='serving'",
            (now, counter_id, day),
        )
        conn.execute(
            "UPDATE queue SET status='serving', counter=?, staff_name=?, time_start=? WHERE id=?",
            (counter_id, staff_name, now, row["id"]),
        )
        fno = db.full_no(row["prefix"], row["number"])
        _touch_counter(conn, counter_id, staff_name, fno, status="active")
        return _row_to_call(conn, row["id"])


def set_counter_status(counter_id, status, staff_name=None):
    if status not in ("active", "paused", "offline"):
        raise QueueError("Trạng thái không hợp lệ.")
    with db.LOCK, db.get_conn() as conn:
        cur = conn.execute(
            "SELECT staff_name, last_num FROM counters_status WHERE counter_id=?", (counter_id,)
        ).fetchone()
        keep_staff = staff_name if staff_name is not None else (cur["staff_name"] if cur else "")
        _touch_counter(conn, counter_id, keep_staff,
                       cur["last_num"] if cur else "", status=status)
    return {"ok": True, "status": status}


def _touch_counter(conn, counter_id, staff_name, last_num, status="active"):
    conn.execute(
        """INSERT INTO counters_status(counter_id, staff_name, status, last_num, last_update)
           VALUES(?, ?, ?, ?, ?)
           ON CONFLICT(counter_id) DO UPDATE SET
             staff_name=excluded.staff_name, status=excluded.status,
             last_num=excluded.last_num, last_update=excluded.last_update""",
        (counter_id, staff_name or "", status, last_num or "", db.now_str()),
    )


def _row_to_call(conn, row_id, is_recall=False):
    r = conn.execute("SELECT * FROM queue WHERE id=?", (row_id,)).fetchone()
    services = db.get_json_config("services", {}) or {}
    svc = services.get(r["prefix"], {})
    return {
        "id": r["id"],
        "full_no": db.full_no(r["prefix"], r["number"]),
        "prefix": r["prefix"],
        "number": r["number"],
        "counter_id": r["counter"],
        "counter_no": _counter_number(r["counter"]),
        "staff_name": r["staff_name"] or "",
        "service_name": svc.get("name", r["prefix"]),
        "service_short": db.short_label(svc, r["prefix"]),
        "service_color": svc.get("color", "#0b5fa5"),
        "time_start": r["time_start"],
        "is_recall": is_recall,
    }


# --------------------------------------------------------------- ảnh trạng thái
def snapshot():
    day = db.today_str()
    counters_conf = db.get_json_config("counters", {}) or {}
    services = db.get_json_config("services", {}) or {}
    extra = db.get_extra()
    recent_n = int(extra.get("recent_count", 8))

    with db.get_conn() as conn:
        status_rows = {
            row["counter_id"]: row
            for row in conn.execute("SELECT * FROM counters_status")
        }
        serving = {
            row["counter"]: row
            for row in conn.execute(
                "SELECT * FROM queue WHERE date_record=? AND status='serving'", (day,)
            )
        }
        waiting_counts = {
            row["prefix"]: row["c"]
            for row in conn.execute(
                "SELECT prefix, COUNT(*) c FROM queue "
                "WHERE date_record=? AND status='waiting' GROUP BY prefix",
                (day,),
            )
        }
        recent = [
            {
                "full_no": db.full_no(row["prefix"], row["number"]),
                "counter_id": row["counter"],
                "counter_no": _counter_number(row["counter"]),
                "service_color": services.get(row["prefix"], {}).get("color", "#0b5fa5"),
                "time_start": row["time_start"],
            }
            for row in conn.execute(
                "SELECT * FROM queue WHERE date_record=? AND status IN ('serving','done','missed') "
                "AND time_start IS NOT NULL ORDER BY time_start DESC LIMIT ?",
                (day, recent_n),
            )
        ]
        today_total = conn.execute(
            "SELECT COALESCE(count,0) FROM visitor_stats WHERE date_record=?", (day,)
        ).fetchone()
        today_total = today_total[0] if today_total else 0

    counters = []
    for name, conf in sorted(
        counters_conf.items(), key=lambda kv: kv[1].get("display_order", 99)
    ):
        if not conf.get("active", True):
            continue
        st = status_rows.get(name)
        sv = serving.get(name)
        prefixes = [p.strip() for p in str(conf.get("prefix", "")).split(",") if p.strip()]
        svc_short = " / ".join(db.short_label(services.get(p, {}), p) for p in prefixes)
        counters.append({
            "id": name,
            "no": _counter_number(name),
            "prefixes": prefixes,
            "service_short": svc_short,
            "service_color": services.get(prefixes[0], {}).get("color", "#0b5fa5") if prefixes else "#0b5fa5",
            "staff_name": (st["staff_name"] if st else "") or conf.get("staff", ""),
            "status": (st["status"] if st else "offline"),
            "current_no": db.full_no(sv["prefix"], sv["number"]) if sv is not None else None,
            "current_since": sv["time_start"] if sv is not None else None,
        })

    waiting_list = [
        {
            "prefix": p,
            "short": db.short_label(services.get(p, {}), p),
            "color": services.get(p, {}).get("color", "#0b5fa5"),
            "count": waiting_counts.get(p, 0),
        }
        for p, sc in sorted(services.items())
        if sc.get("active", True)
    ]

    return {
        "type": "snapshot",
        "server_time": db.now_str(),
        "date_record": day,
        "session": db.session_now(),
        "counters": counters,
        "waiting": waiting_list,
        "recent": recent,
        "today_total": today_total,
        "time_open": within_time_lock(),
    }


def counter_view(counter_id):
    """Dữ liệu riêng cho một bàn gọi số."""
    day = db.today_str()
    prefixes = counter_prefixes(counter_id)
    services = db.get_json_config("services", {}) or {}
    with db.get_conn() as conn:
        st = conn.execute(
            "SELECT * FROM counters_status WHERE counter_id=?", (counter_id,)
        ).fetchone()
        serving = conn.execute(
            "SELECT * FROM queue WHERE counter=? AND date_record=? AND status='serving' "
            "ORDER BY time_start DESC LIMIT 1",
            (counter_id, day),
        ).fetchone()
        waiting = []
        done_today = 0
        if prefixes:
            ph = ",".join("?" * len(prefixes))
            waiting = [
                {
                    "full_no": db.full_no(r["prefix"], r["number"]),
                    "prefix": r["prefix"],
                    "number": r["number"],
                    "time_issue": r["time_issue"],
                    "fullname": r["fullname"] or "",
                }
                for r in conn.execute(
                    f"SELECT * FROM queue WHERE date_record=? AND status='waiting' "
                    f"AND prefix IN ({ph}) ORDER BY id ASC",
                    [day, *prefixes],
                )
            ]
            done_today = conn.execute(
                f"SELECT COUNT(*) FROM queue WHERE date_record=? AND counter=? "
                f"AND status IN ('done','missed')",
                (day, counter_id),
            ).fetchone()[0]
        history = [
            {
                "full_no": db.full_no(r["prefix"], r["number"]),
                "status": r["status"],
                "time_start": r["time_start"],
            }
            for r in conn.execute(
                "SELECT * FROM queue WHERE date_record=? AND counter=? AND status IN ('done','missed','serving') "
                "ORDER BY time_start DESC LIMIT 12",
                (day, counter_id),
            )
        ]

    current = None
    if serving is not None:
        current = {
            "full_no": db.full_no(serving["prefix"], serving["number"]),
            "prefix": serving["prefix"],
            "service_short": db.short_label(services.get(serving["prefix"], {}), serving["prefix"]),
            "service_color": services.get(serving["prefix"], {}).get("color", "#0b5fa5"),
            "since": serving["time_start"],
            "fullname": serving["fullname"] or "",
        }
    return {
        "counter_id": counter_id,
        "prefixes": prefixes,
        "staff_name": (st["staff_name"] if st else "") or "",
        "status": (st["status"] if st else "offline"),
        "current": current,
        "waiting": waiting,
        "waiting_count": len(waiting),
        "done_today": done_today,
        "history": history,
    }


def _dumps(obj):
    import json
    return json.dumps(obj, ensure_ascii=False)
