"""Máy chủ Flask ĐA CHI NHÁNH: API bốc số / gọi số + giao diện web + SSE realtime.

Chạy (dev):   python app.py            (http://0.0.0.0:5000, tự reload nếu GOISO_DEBUG=1)
Chạy (thật):  waitress-serve --listen=127.0.0.1:5000 --threads=32 app:app

Mỗi chi nhánh có mã `code` (vd 'eakar'):
  Trang:  /b/<code>/display   /b/<code>/counter   /b/<code>/display/simple
  API:    /api/b/<code>/...
  Quản trị tổng:  /admin   (+ /api/admin/...)
"""
import functools
import hashlib
import json
import os
import queue as queuelib
import sqlite3
import threading
import time

from flask import (Flask, Response, g, jsonify, redirect, render_template,
                   request, session, stream_with_context, url_for)

import db
import queue_logic as ql
import booking_logic as bk
import tts as tts_engine

app = Flask(__name__)
app.secret_key = os.environ.get("GOISO_SECRET", "goiso-dev-secret-change-me")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=not bool(os.environ.get("GOISO_DEBUG")),
    # Không để trình duyệt/Cloudflare giữ bản JS/CSS cũ — luôn kiểm tra lại (ETag -> 304).
    SEND_FILE_MAX_AGE_DEFAULT=0,
)

DEBUG = bool(os.environ.get("GOISO_DEBUG"))
BASE_URL = os.environ.get("GOISO_BASE_URL", "").rstrip("/")
TURNSTILE_SITE_KEY = os.environ.get("TURNSTILE_SITE_KEY", "")


def _client_ip():
    return (request.headers.get("CF-Connecting-IP")
            or (request.headers.get("X-Forwarded-For", "").split(",")[0].strip())
            or request.remote_addr or "")

db.init_db()

# ----------------------------------------------------------------- SSE hub (theo chi nhánh)
_subscribers = {}  # branch_id -> set[Queue]
_sub_lock = threading.Lock()


def broadcast(branch_id, event: dict):
    data = json.dumps(event, ensure_ascii=False)
    with _sub_lock:
        subs = _subscribers.get(branch_id)
        if not subs:
            return
        dead = []
        for q in subs:
            try:
                q.put_nowait(data)
            except queuelib.Full:
                dead.append(q)
        for q in dead:
            subs.discard(q)


def push_snapshot(branch_id):
    broadcast(branch_id, ql.snapshot(branch_id))


# ----------------------------------------------------------------- decorators
def resolve_branch(view):
    @functools.wraps(view)
    def wrapper(code, *args, **kwargs):
        branch = db.get_branch(code)
        if not branch or not branch["active"]:
            if request.path.startswith("/api/"):
                return jsonify(error="Chi nhánh không tồn tại hoặc đã ngừng hoạt động."), 404
            return "Chi nhánh không tồn tại.", 404
        g.branch = branch
        return view(*args, **kwargs)
    return wrapper


def require_branch_key(view):
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        if not DEBUG:
            sent = request.headers.get("X-Branch-Key", "")
            import secrets as _s
            if not sent or not _s.compare_digest(sent, g.branch["api_key"]):
                return jsonify(error="Sai hoặc thiếu khoá chi nhánh (X-Branch-Key)."), 401
        return view(*args, **kwargs)
    return wrapper


def counter_guard(view):
    """Nếu chi nhánh có cấu hình PIN quầy, yêu cầu đã 'Vào ca' đúng PIN."""
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        pin = (db.get_extra(g.branch["id"]).get("counter_pin") or "").strip()
        if pin and not session.get(f"counter_ok:{g.branch['code']}"):
            return jsonify(error="Cần nhập đúng mã PIN quầy (Vào ca lại)."), 401
        return view(*args, **kwargs)
    return wrapper


def admin_required(view):
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        if session.get("is_admin") is not True:
            return jsonify(error="Chưa đăng nhập quản trị."), 401
        return view(*args, **kwargs)
    return wrapper


def _tpl_ctx(branch):
    """Context cho template: extra của chi nhánh + ten_chi_nhanh lấy từ branch."""
    extra = db.get_extra(branch["id"])
    extra["ten_chi_nhanh"] = branch["full_name"]
    return extra


@app.errorhandler(sqlite3.OperationalError)
def _db_locked(e):
    msg = str(e)
    if "locked" in msg or "busy" in msg:
        text = ("CSDL đang bị một chương trình khác khoá (thường là DB Browser "
                "for SQLite / SQLiteStudio đang mở file hethong_v2.db). "
                "Hãy đóng chương trình đó rồi thử lại.")
        code = 503
    else:
        text = "Lỗi CSDL: " + msg
        code = 500
    if request.path.startswith("/api/"):
        return jsonify(error=text), code
    return text, code


# ----------------------------------------------------------------- SSE stream
@app.route("/api/b/<code>/stream")
@resolve_branch
def stream():
    branch_id = g.branch["id"]

    def gen():
        q = queuelib.Queue(maxsize=64)
        with _sub_lock:
            _subscribers.setdefault(branch_id, set()).add(q)
        try:
            yield "retry: 3000\n\n"
            yield f"data: {json.dumps(ql.snapshot(branch_id), ensure_ascii=False)}\n\n"
            last_beat = time.time()
            while True:
                try:
                    data = q.get(timeout=10)
                    yield f"data: {data}\n\n"
                except queuelib.Empty:
                    pass
                if time.time() - last_beat > 10:
                    yield ": ping\n\n"
                    last_beat = time.time()
        finally:
            with _sub_lock:
                subs = _subscribers.get(branch_id)
                if subs:
                    subs.discard(q)

    resp = Response(stream_with_context(gen()), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    # KHÔNG đặt header "Connection" ở đây: đó là hop-by-hop header, waitress (PEP 3333)
    # sẽ ném AssertionError. Keep-alive do máy chủ/Cloudflare tự quản lý.
    return resp


# ----------------------------------------------------------------- trang web
@app.route("/")
def index():
    return render_template("index.html", branches=db.list_branches(active_only=True))


@app.route("/b/<code>/display")
@resolve_branch
def page_display():
    return render_template("display.html", extra=_tpl_ctx(g.branch), branch=g.branch,
                           layout=request.args.get("layout", "landscape"))


@app.route("/b/<code>/display/simple")
@resolve_branch
def page_display_simple():
    return render_template("display_simple.html", extra=_tpl_ctx(g.branch), branch=g.branch)


@app.route("/b/<code>/counter")
@resolve_branch
def page_counter():
    counters = db.get_json_config("counters", {}, g.branch["id"]) or {}
    active = [
        {"id": k, **v}
        for k, v in sorted(counters.items(), key=lambda kv: kv[1].get("display_order", 99))
        if v.get("active", True)
    ]
    extra = _tpl_ctx(g.branch)
    return render_template("counter.html", extra=extra, branch=g.branch, counters=active,
                           pin_required=bool((extra.get("counter_pin") or "").strip()))


@app.route("/admin")
def page_admin():
    return render_template("admin.html")


@app.route("/dat-lich")
def page_booking():
    return render_template("booking.html", turnstile_site_key=TURNSTILE_SITE_KEY)


@app.route("/lich-hen/<token>")
def page_booking_lookup(token):
    return render_template("booking_lookup.html", token=token)


# ----------------------------------------------------------------- API cấp số (kiosk)
@app.post("/api/b/<code>/ticket")
@resolve_branch
@require_branch_key
def api_ticket():
    body = request.get_json(silent=True) or request.form
    prefix = (body.get("prefix") or "").strip().upper()
    if not prefix:
        return jsonify(error="Thiếu mã dịch vụ."), 400
    try:
        ticket = ql.issue_ticket(
            g.branch["id"], prefix,
            fullname=body.get("fullname", ""),
            cccd=body.get("cccd", ""),
            phone=body.get("phone", ""),
        )
    except ql.QueueError as e:
        return jsonify(error=str(e)), 409
    push_snapshot(g.branch["id"])
    return jsonify(ticket)


@app.get("/api/b/<code>/state")
@resolve_branch
def api_state():
    return jsonify(ql.snapshot(g.branch["id"]))


@app.get("/api/b/<code>/tts")
@resolve_branch
def api_tts():
    """Đọc số bằng giọng tiếng Việt phía máy chủ -> trả file mp3."""
    text = request.args.get("text", "")
    voice = request.args.get("voice", "") or db.get_extra(g.branch["id"]).get("tts_voice", "")
    if not tts_engine.available():
        return jsonify(error="Máy chủ chưa cài edge-tts."), 503
    try:
        path = tts_engine.get_or_make(text, voice)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    except Exception:  # noqa: BLE001
        return jsonify(error="Không tạo được âm thanh."), 502
    from flask import send_file
    resp = send_file(path, mimetype="audio/mpeg", conditional=True)
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


@app.post("/api/b/<code>/checkin")
@resolve_branch
@require_branch_key
def api_checkin():
    body = request.get_json(silent=True) or {}
    try:
        ticket = bk.checkin(g.branch["id"], body.get("code", ""))
    except bk.BookingError as e:
        return jsonify(error=str(e)), 409
    except ql.QueueError as e:
        return jsonify(error=str(e)), 409
    push_snapshot(g.branch["id"])
    return jsonify(ticket)


@app.get("/api/b/<code>/config/public")
@resolve_branch
def api_config_public():
    """Cấu hình công khai cho kiosk / màn hình (không có mật khẩu)."""
    branch_id = g.branch["id"]
    services = db.get_json_config("services", {}, branch_id) or {}
    day = db.today_str()
    with db.get_conn() as conn:
        issued = {
            r["prefix"]: r["c"]
            for r in conn.execute(
                "SELECT prefix, COUNT(*) c FROM queue WHERE branch_id=? AND date_record=? GROUP BY prefix",
                (branch_id, day),
            )
        }
    svc_out = {}
    for k, v in services.items():
        if not v.get("active", True):
            continue
        limit = int(v.get("daily_limit") or 0)
        used = issued.get(k, 0)
        svc_out[k] = {
            "name": v.get("name", k),
            "short": db.short_label(v, k),
            "color": v.get("color", "#0b5fa5"),
            "daily_limit": limit,
            "issued_today": used,
            "sold_out": bool(limit and used >= limit),
        }
    extra = db.get_extra(branch_id)
    return jsonify({
        "branch": {"code": g.branch["code"], "name": g.branch["name"],
                   "full_name": g.branch["full_name"]},
        "services": svc_out,
        "extra": {
            "ten_co_quan": extra.get("ten_co_quan", ""),
            "ten_chi_nhanh": g.branch["full_name"],
            "link_qr": extra.get("link_qr", ""),
            "qr_enabled": extra.get("qr_enabled", False),
            "lock_time_enabled": extra.get("lock_time_enabled", False),
            "lock_message": extra.get("lock_message", ""),
            "time_slots": extra.get("time_slots", []),
            "voice_rate": extra.get("voice_rate", 0.95),
            "voice_repeat": extra.get("voice_repeat", 2),
            "voice_template": extra.get("voice_template", "Xin mời số thứ tự {so}, đến quầy số {quay}"),
            "spotlight_seconds": extra.get("spotlight_seconds", 20),
            "tts_mode": extra.get("tts_mode", "server"),
            "tts_voice": extra.get("tts_voice", "vi-VN-HoaiMyNeural"),
        },
        "time_open": ql.within_time_lock(branch_id),
    })


# ----------------------------------------------------------------- API quầy
@app.get("/api/b/<code>/counter/<path:counter_id>/view")
@resolve_branch
def api_counter_view(counter_id):
    return jsonify(ql.counter_view(g.branch["id"], counter_id))


@app.post("/api/b/<code>/counter/<path:counter_id>/login")
@resolve_branch
def api_counter_login(counter_id):
    body = request.get_json(silent=True) or {}
    staff = (body.get("staff_name") or "").strip()
    pin_cfg = (db.get_extra(g.branch["id"]).get("counter_pin") or "").strip()
    if pin_cfg and (body.get("pin") or "").strip() != pin_cfg:
        return jsonify(error="Sai mã PIN quầy."), 401
    if pin_cfg:
        session[f"counter_ok:{g.branch['code']}"] = True
        session.permanent = True
    ql.set_counter_status(g.branch["id"], counter_id, "active", staff_name=staff)
    push_snapshot(g.branch["id"])
    return jsonify(ql.counter_view(g.branch["id"], counter_id))


@app.post("/api/b/<code>/counter/<path:counter_id>/next")
@resolve_branch
@counter_guard
def api_counter_next(counter_id):
    body = request.get_json(silent=True) or {}
    try:
        called = ql.call_next(g.branch["id"], counter_id,
                              staff_name=(body.get("staff_name") or "").strip())
    except ql.QueueError as e:
        return jsonify(error=str(e)), 409
    broadcast(g.branch["id"], {"type": "call", **called})
    push_snapshot(g.branch["id"])
    return jsonify(called)


@app.post("/api/b/<code>/counter/<path:counter_id>/recall")
@resolve_branch
@counter_guard
def api_counter_recall(counter_id):
    try:
        called = ql.recall(g.branch["id"], counter_id)
    except ql.QueueError as e:
        return jsonify(error=str(e)), 409
    broadcast(g.branch["id"], {"type": "call", **called})
    return jsonify(called)


@app.post("/api/b/<code>/counter/<path:counter_id>/done")
@resolve_branch
@counter_guard
def api_counter_done(counter_id):
    try:
        ql.finish_current(g.branch["id"], counter_id)
    except ql.QueueError as e:
        return jsonify(error=str(e)), 409
    push_snapshot(g.branch["id"])
    return jsonify(ql.counter_view(g.branch["id"], counter_id))


@app.post("/api/b/<code>/counter/<path:counter_id>/missed")
@resolve_branch
@counter_guard
def api_counter_missed(counter_id):
    try:
        ql.mark_missed(g.branch["id"], counter_id)
    except ql.QueueError as e:
        return jsonify(error=str(e)), 409
    push_snapshot(g.branch["id"])
    return jsonify(ql.counter_view(g.branch["id"], counter_id))


@app.post("/api/b/<code>/counter/<path:counter_id>/call")
@resolve_branch
@counter_guard
def api_counter_call_specific(counter_id):
    body = request.get_json(silent=True) or {}
    try:
        called = ql.call_specific(
            g.branch["id"], counter_id, body.get("full_no", ""),
            staff_name=(body.get("staff_name") or "").strip(),
        )
    except ql.QueueError as e:
        return jsonify(error=str(e)), 409
    broadcast(g.branch["id"], {"type": "call", **called})
    push_snapshot(g.branch["id"])
    return jsonify(called)


@app.post("/api/b/<code>/counter/<path:counter_id>/status")
@resolve_branch
@counter_guard
def api_counter_status(counter_id):
    body = request.get_json(silent=True) or {}
    try:
        r = ql.set_counter_status(g.branch["id"], counter_id, (body.get("status") or "").strip())
    except ql.QueueError as e:
        return jsonify(error=str(e)), 409
    push_snapshot(g.branch["id"])
    return jsonify(r)


# ----------------------------------------------------------------- API admin
def _hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


@app.post("/api/admin/login")
def api_admin_login():
    body = request.get_json(silent=True) or {}
    stored = db.get_config("admin_password", "")
    if stored and _hash_pw(body.get("password", "")) == stored:
        session["is_admin"] = True
        session.permanent = True
        return jsonify(ok=True)
    return jsonify(error="Sai mật khẩu."), 401


@app.post("/api/admin/logout")
def api_admin_logout():
    session.pop("is_admin", None)
    return jsonify(ok=True)


@app.get("/api/admin/branches")
@admin_required
def api_admin_branches():
    return jsonify(branches=db.list_branches())


@app.post("/api/admin/branches")
@admin_required
def api_admin_branches_write():
    body = request.get_json(silent=True) or {}
    action = body.get("action", "")
    code = (body.get("code") or "").strip().lower()
    try:
        if action == "create":
            b = db.create_branch(code, body.get("name", ""), body.get("full_name", ""),
                                 body.get("address", ""))
            return jsonify(ok=True, branch=b)
        if action == "update":
            b = db.update_branch(code, **{k: body[k] for k in
                                         ("name", "full_name", "address", "active", "display_order")
                                         if k in body})
            return jsonify(ok=True, branch=b)
        if action == "delete":
            db.delete_branch(code)
            return jsonify(ok=True)
        if action in ("regen_key", "regen_display_token"):
            field = "api_key" if action == "regen_key" else "display_token"
            token = db.regen_branch_field(code, field)
            return jsonify(ok=True, field=field, value=token)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    return jsonify(error="action không hợp lệ."), 400


@app.get("/api/admin/b/<code>/config")
@admin_required
@resolve_branch
def api_admin_get_config():
    bid = g.branch["id"]
    return jsonify({
        "branch": g.branch,
        "services": db.get_json_config("services", {}, bid),
        "counters": db.get_json_config("counters", {}, bid),
        "extra": db.get_extra(bid),
        "booking": db.get_booking_config(bid),
    })


@app.post("/api/admin/b/<code>/config")
@admin_required
@resolve_branch
def api_admin_set_config():
    bid = g.branch["id"]
    body = request.get_json(silent=True) or {}
    if "services" in body:
        db.set_json_config("services", body["services"], bid)
    if "counters" in body:
        db.set_json_config("counters", body["counters"], bid)
    if "extra" in body:
        merged = db.get_json_config("extra", {}, bid) or {}
        merged.update(body["extra"])
        db.set_json_config("extra", merged, bid)
    if "booking" in body:
        merged = db.get_json_config("booking", {}, bid) or {}
        merged.update(body["booking"])
        db.set_json_config("booking", merged, bid)
    if body.get("new_password"):
        db.set_config("admin_password", _hash_pw(body["new_password"]))
    push_snapshot(bid)
    return jsonify(ok=True)


@app.get("/api/admin/stats")
@admin_required
def api_admin_stats():
    which = request.args.get("branch", "all")
    day = db.today_str()
    branches = db.list_branches() if which == "all" else [db.get_branch(which)]
    branches = [b for b in branches if b]
    if not branches:
        return jsonify(error="Không có chi nhánh."), 404

    with db.get_conn() as conn:
        out = []
        for b in branches:
            bid = b["id"]
            by_service = [
                {"prefix": r["prefix"], "issued": r["issued"], "done": r["done"] or 0,
                 "missed": r["missed"] or 0, "waiting": r["waiting"] or 0}
                for r in conn.execute(
                    """SELECT prefix, COUNT(*) issued,
                              SUM(status='done') done, SUM(status='missed') missed,
                              SUM(status='waiting') waiting
                       FROM queue WHERE branch_id=? AND date_record=?
                       GROUP BY prefix ORDER BY prefix""",
                    (bid, day),
                )
            ]
            avg_wait = conn.execute(
                """SELECT AVG((julianday(time_start) - julianday(time_issue)) * 86400.0)
                   FROM queue WHERE branch_id=? AND date_record=?
                     AND time_start IS NOT NULL AND time_issue IS NOT NULL""",
                (bid, day),
            ).fetchone()[0]
            total = conn.execute(
                "SELECT COALESCE(count,0) FROM visitor_stats WHERE branch_id=? AND date_record=?",
                (bid, day),
            ).fetchone()
            out.append({
                "code": b["code"], "name": b["name"],
                "today_total": total[0] if total else 0,
                "avg_wait_seconds": round(avg_wait) if avg_wait else 0,
                "by_service": by_service,
            })
        visitors = []
        if which != "all":
            visitors = [
                {"date": r["date_record"], "count": r["count"]}
                for r in conn.execute(
                    "SELECT * FROM visitor_stats WHERE branch_id=? ORDER BY date_record DESC LIMIT 30",
                    (branches[0]["id"],),
                )
            ]
    return jsonify({"today": day, "scope": which, "branches": out, "visitors": visitors})


@app.get("/api/admin/b/<code>/appointments")
@admin_required
@resolve_branch
def api_admin_appointments():
    d = request.args.get("date", db.today_str())
    with db.get_conn() as conn:
        rows = [
            {"code": r["code"], "token": r["token"], "prefix": r["prefix"],
             "slot_start": r["slot_start"], "slot_end": r["slot_end"],
             "status": r["status"], "citizen_name": r["citizen_name"],
             "cccd": r["cccd"], "phone": r["phone"],
             "created_at": r["created_at"], "checkin_at": r["checkin_at"]}
            for r in conn.execute(
                "SELECT * FROM appointments WHERE branch_id=? AND slot_date=? "
                "ORDER BY slot_start, created_at",
                (g.branch["id"], d),
            )
        ]
    return jsonify({"date": d, "appointments": rows})


@app.post("/api/admin/b/<code>/appointments/cancel")
@admin_required
@resolve_branch
def api_admin_appt_cancel():
    body = request.get_json(silent=True) or {}
    try:
        bk.cancel(body.get("token", ""))
    except bk.BookingError as e:
        return jsonify(error=str(e)), 409
    return jsonify(ok=True)


@app.post("/api/admin/b/<code>/reset-today")
@admin_required
@resolve_branch
def api_admin_reset_today():
    bid = g.branch["id"]
    day = db.today_str()
    with db.LOCK, db.get_conn() as conn:
        conn.execute("DELETE FROM queue WHERE branch_id=? AND date_record=?", (bid, day))
        conn.execute("DELETE FROM visitor_stats WHERE branch_id=? AND date_record=?", (bid, day))
        conn.execute("UPDATE counters_status SET last_num='', status='offline' WHERE branch_id=?", (bid,))
        conn.execute(
            "UPDATE appointments SET status='cancelled' "
            "WHERE branch_id=? AND slot_date=? AND status='booked'",
            (bid, day),
        )
    push_snapshot(bid)
    return jsonify(ok=True)


# ----------------------------------------------------------------- API đặt lịch online (công khai)
@app.get("/api/booking/branches")
def api_booking_branches():
    return jsonify(branches=bk.public_branches())


@app.get("/api/booking/<code>/slots")
@resolve_branch
def api_booking_slots():
    try:
        slots = bk.list_slots(g.branch["id"], request.args.get("date", ""),
                              (request.args.get("prefix", "") or "").upper())
    except bk.BookingError as e:
        return jsonify(error=str(e)), 400
    return jsonify({"slots": slots})


@app.post("/api/booking/<code>/book")
@resolve_branch
def api_booking_book():
    body = request.get_json(silent=True) or {}
    ip = _client_ip()
    if not bk.rate_limit_ok(ip):
        return jsonify(error="Bạn đã đặt quá nhiều lần trong 1 giờ. Vui lòng thử lại sau."), 429
    if not bk.verify_turnstile(g.branch["id"], body.get("turnstile_token", ""), ip):
        return jsonify(error="Xác thực chống spam thất bại. Vui lòng tải lại trang."), 400
    try:
        appt = bk.create_appointment(
            g.branch["id"], (body.get("prefix", "") or "").upper(),
            body.get("slot_date", ""), body.get("slot_start", ""),
            body.get("citizen_name", ""), body.get("cccd", ""), body.get("phone", ""),
            ip=ip,
        )
    except bk.BookingError as e:
        return jsonify(error=str(e)), 409
    return jsonify(appt)


@app.get("/api/booking/appt/<token>")
def api_booking_appt(token):
    try:
        return jsonify(bk.appointment_view(token))
    except bk.BookingError as e:
        return jsonify(error=str(e)), 404


@app.post("/api/booking/appt/<token>/cancel")
def api_booking_appt_cancel(token):
    try:
        return jsonify(bk.cancel(token))
    except bk.BookingError as e:
        return jsonify(error=str(e)), 409


# ----------------------------------------------------------------- sweeper nền
def _sweeper():
    while True:
        time.sleep(300)
        try:
            bk.expire_stale()
        except Exception:  # noqa: BLE001
            pass


threading.Thread(target=_sweeper, daemon=True).start()


if __name__ == "__main__":
    port = int(os.environ.get("GOISO_PORT", "5000"))
    app.run(host="0.0.0.0", port=port, threaded=True, debug=DEBUG)
