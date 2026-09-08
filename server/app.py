"""Máy chủ Flask: API bốc số / gọi số + phục vụ giao diện web + luồng SSE realtime.

Chạy:  python app.py            (mặc định http://0.0.0.0:5000)
       GOISO_PORT=8080 python app.py
"""
import hashlib
import json
import os
import queue as queuelib
import threading
import time

from flask import (Flask, Response, jsonify, redirect, render_template, request,
                   session, stream_with_context, url_for)

import db
import queue_logic as ql

app = Flask(__name__)
app.secret_key = os.environ.get("GOISO_SECRET", "goiso-eakar-secret-key-change-me")

db.init_db()

# ----------------------------------------------------------------- SSE hub
_subscribers = set()
_sub_lock = threading.Lock()


def broadcast(event: dict):
    data = json.dumps(event, ensure_ascii=False)
    with _sub_lock:
        dead = []
        for q in _subscribers:
            try:
                q.put_nowait(data)
            except queuelib.Full:
                dead.append(q)
        for q in dead:
            _subscribers.discard(q)


def push_snapshot():
    broadcast(ql.snapshot())


@app.route("/api/stream")
def stream():
    def gen():
        q = queuelib.Queue(maxsize=64)
        with _sub_lock:
            _subscribers.add(q)
        try:
            yield "retry: 3000\n\n"
            yield f"data: {json.dumps(ql.snapshot(), ensure_ascii=False)}\n\n"
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
                _subscribers.discard(q)

    resp = Response(stream_with_context(gen()), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    resp.headers["Connection"] = "keep-alive"
    return resp


# ----------------------------------------------------------------- trang web
@app.route("/")
def index():
    return redirect(url_for("page_display"))


@app.route("/display")
def page_display():
    return render_template("display.html", extra=db.get_extra(),
                           layout=request.args.get("layout", "landscape"))


@app.route("/display/simple")
def page_display_simple():
    return render_template("display_simple.html", extra=db.get_extra())


@app.route("/counter")
def page_counter():
    counters = db.get_json_config("counters", {}) or {}
    active = [
        {"id": k, **v}
        for k, v in sorted(counters.items(), key=lambda kv: kv[1].get("display_order", 99))
        if v.get("active", True)
    ]
    return render_template("counter.html", extra=db.get_extra(), counters=active)


@app.route("/admin")
def page_admin():
    return render_template("admin.html", extra=db.get_extra())


# ----------------------------------------------------------------- API cấp số
@app.post("/api/ticket")
def api_ticket():
    body = request.get_json(silent=True) or request.form
    prefix = (body.get("prefix") or "").strip().upper()
    if not prefix:
        return jsonify(error="Thiếu mã dịch vụ."), 400
    try:
        ticket = ql.issue_ticket(
            prefix,
            fullname=body.get("fullname", ""),
            cccd=body.get("cccd", ""),
            phone=body.get("phone", ""),
        )
    except ql.QueueError as e:
        return jsonify(error=str(e)), 409
    push_snapshot()
    return jsonify(ticket)


@app.get("/api/state")
def api_state():
    return jsonify(ql.snapshot())


@app.get("/api/config/public")
def api_config_public():
    """Cấu hình công khai cho kiosk / màn hình (không có mật khẩu)."""
    services = db.get_json_config("services", {}) or {}
    day = db.today_str()
    with db.get_conn() as conn:
        issued = {
            r["prefix"]: r["c"]
            for r in conn.execute(
                "SELECT prefix, COUNT(*) c FROM queue WHERE date_record=? GROUP BY prefix",
                (day,),
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
    extra = db.get_extra()
    return jsonify({
        "services": svc_out,
        "extra": {
            "ten_co_quan": extra.get("ten_co_quan", ""),
            "ten_chi_nhanh": extra.get("ten_chi_nhanh", ""),
            "link_qr": extra.get("link_qr", ""),
            "qr_enabled": extra.get("qr_enabled", False),
            "lock_time_enabled": extra.get("lock_time_enabled", False),
            "lock_message": extra.get("lock_message", ""),
            "time_slots": extra.get("time_slots", []),
            "voice_rate": extra.get("voice_rate", 0.95),
            "voice_repeat": extra.get("voice_repeat", 2),
            "voice_template": extra.get("voice_template", "Mời số {so}, đến quầy số {quay}"),
            "spotlight_seconds": extra.get("spotlight_seconds", 20),
        },
        "time_open": ql.within_time_lock(),
    })


# ----------------------------------------------------------------- API quầy
@app.get("/api/counter/<path:counter_id>/view")
def api_counter_view(counter_id):
    return jsonify(ql.counter_view(counter_id))


@app.post("/api/counter/<path:counter_id>/login")
def api_counter_login(counter_id):
    body = request.get_json(silent=True) or {}
    staff = (body.get("staff_name") or "").strip()
    ql.set_counter_status(counter_id, "active", staff_name=staff)
    push_snapshot()
    return jsonify(ql.counter_view(counter_id))


@app.post("/api/counter/<path:counter_id>/next")
def api_counter_next(counter_id):
    body = request.get_json(silent=True) or {}
    try:
        called = ql.call_next(counter_id, staff_name=(body.get("staff_name") or "").strip())
    except ql.QueueError as e:
        return jsonify(error=str(e)), 409
    broadcast({"type": "call", **called})
    push_snapshot()
    return jsonify(called)


@app.post("/api/counter/<path:counter_id>/recall")
def api_counter_recall(counter_id):
    try:
        called = ql.recall(counter_id)
    except ql.QueueError as e:
        return jsonify(error=str(e)), 409
    broadcast({"type": "call", **called})
    return jsonify(called)


@app.post("/api/counter/<path:counter_id>/done")
def api_counter_done(counter_id):
    try:
        ql.finish_current(counter_id)
    except ql.QueueError as e:
        return jsonify(error=str(e)), 409
    push_snapshot()
    return jsonify(ql.counter_view(counter_id))


@app.post("/api/counter/<path:counter_id>/missed")
def api_counter_missed(counter_id):
    try:
        ql.mark_missed(counter_id)
    except ql.QueueError as e:
        return jsonify(error=str(e)), 409
    push_snapshot()
    return jsonify(ql.counter_view(counter_id))


@app.post("/api/counter/<path:counter_id>/call")
def api_counter_call_specific(counter_id):
    body = request.get_json(silent=True) or {}
    try:
        called = ql.call_specific(
            counter_id, body.get("full_no", ""),
            staff_name=(body.get("staff_name") or "").strip(),
        )
    except ql.QueueError as e:
        return jsonify(error=str(e)), 409
    broadcast({"type": "call", **called})
    push_snapshot()
    return jsonify(called)


@app.post("/api/counter/<path:counter_id>/status")
def api_counter_status(counter_id):
    body = request.get_json(silent=True) or {}
    try:
        r = ql.set_counter_status(counter_id, (body.get("status") or "").strip())
    except ql.QueueError as e:
        return jsonify(error=str(e)), 409
    push_snapshot()
    return jsonify(r)


# ----------------------------------------------------------------- API admin
def _hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


def _admin_ok():
    return session.get("is_admin") is True


@app.post("/api/admin/login")
def api_admin_login():
    body = request.get_json(silent=True) or {}
    pw = body.get("password", "")
    stored = db.get_config("admin_password", "")
    if stored and _hash_pw(pw) == stored:
        session["is_admin"] = True
        return jsonify(ok=True)
    return jsonify(error="Sai mật khẩu."), 401


@app.post("/api/admin/logout")
def api_admin_logout():
    session.pop("is_admin", None)
    return jsonify(ok=True)


@app.get("/api/admin/config")
def api_admin_get_config():
    if not _admin_ok():
        return jsonify(error="Chưa đăng nhập."), 401
    return jsonify({
        "services": db.get_json_config("services", {}),
        "counters": db.get_json_config("counters", {}),
        "extra": db.get_extra(),
    })


@app.post("/api/admin/config")
def api_admin_set_config():
    if not _admin_ok():
        return jsonify(error="Chưa đăng nhập."), 401
    body = request.get_json(silent=True) or {}
    if "services" in body:
        db.set_json_config("services", body["services"])
    if "counters" in body:
        db.set_json_config("counters", body["counters"])
    if "extra" in body:
        merged = db.get_extra()
        merged.update(body["extra"])
        db.set_json_config("extra", merged)
    if body.get("new_password"):
        db.set_config("admin_password", _hash_pw(body["new_password"]))
    push_snapshot()
    return jsonify(ok=True)


@app.get("/api/admin/stats")
def api_admin_stats():
    if not _admin_ok():
        return jsonify(error="Chưa đăng nhập."), 401
    day = db.today_str()
    with db.get_conn() as conn:
        visitors = [
            {"date": r["date_record"], "count": r["count"]}
            for r in conn.execute(
                "SELECT * FROM visitor_stats ORDER BY date_record DESC LIMIT 30"
            )
        ]
        by_service = [
            {"prefix": r["prefix"], "issued": r["issued"], "done": r["done"],
             "missed": r["missed"], "waiting": r["waiting"]}
            for r in conn.execute(
                """SELECT prefix,
                          COUNT(*) issued,
                          SUM(status='done') done,
                          SUM(status='missed') missed,
                          SUM(status='waiting') waiting
                   FROM queue WHERE date_record=? GROUP BY prefix ORDER BY prefix""",
                (day,),
            )
        ]
        avg_wait = conn.execute(
            """SELECT AVG((julianday(time_start) - julianday(time_issue)) * 86400.0)
               FROM queue WHERE date_record=? AND time_start IS NOT NULL AND time_issue IS NOT NULL""",
            (day,),
        ).fetchone()[0]
    return jsonify({
        "today": day,
        "visitors": visitors,
        "by_service": by_service,
        "avg_wait_seconds": round(avg_wait) if avg_wait else 0,
    })


@app.post("/api/admin/reset-today")
def api_admin_reset_today():
    if not _admin_ok():
        return jsonify(error="Chưa đăng nhập."), 401
    day = db.today_str()
    with db.LOCK, db.get_conn() as conn:
        conn.execute("DELETE FROM queue WHERE date_record=?", (day,))
        conn.execute("DELETE FROM visitor_stats WHERE date_record=?", (day,))
        conn.execute("UPDATE counters_status SET last_num='', status='offline'")
        services = db.get_json_config("services", {}) or {}
        for v in services.values():
            v["current_count"] = 0
        conn.execute("UPDATE config SET value=? WHERE key='services'",
                     (json.dumps(services, ensure_ascii=False),))
    push_snapshot()
    return jsonify(ok=True)


if __name__ == "__main__":
    port = int(os.environ.get("GOISO_PORT", "5000"))
    app.run(host="0.0.0.0", port=port, threaded=True, debug=bool(os.environ.get("GOISO_DEBUG")))
