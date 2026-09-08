"""Tiện ích dòng lệnh cho hệ thống gọi số.

  python manage.py init                 # tạo/di trú bảng
  python manage.py set-admin-pw <mk>    # đặt lại mật khẩu quản trị
  python manage.py reset-today          # xoá toàn bộ số đã cấp hôm nay
  python manage.py show-config          # in cấu hình hiện tại
"""
import hashlib
import json
import sys

try:  # đảm bảo in được tiếng Việt trên console Windows
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

import db


def main(argv):
    if not argv:
        print(__doc__)
        return
    cmd = argv[0]
    db.init_db()

    if cmd == "init":
        print("Đã khởi tạo / di trú CSDL:", db.DB_PATH)

    elif cmd == "set-admin-pw":
        if len(argv) < 2:
            print("Thiếu mật khẩu. VD: python manage.py set-admin-pw MatKhauMoi")
            return
        h = hashlib.sha256(argv[1].encode("utf-8")).hexdigest()
        db.set_config("admin_password", h)
        print("Đã đặt mật khẩu quản trị mới.")

    elif cmd == "reset-today":
        day = db.today_str()
        with db.LOCK, db.get_conn() as conn:
            n = conn.execute("DELETE FROM queue WHERE date_record=?", (day,)).rowcount
            conn.execute("DELETE FROM visitor_stats WHERE date_record=?", (day,))
            conn.execute("UPDATE counters_status SET last_num='', status='offline'")
            services = db.get_json_config("services", {}) or {}
            for v in services.values():
                v["current_count"] = 0
            conn.execute("UPDATE config SET value=? WHERE key='services'",
                         (json.dumps(services, ensure_ascii=False),))
        print(f"Đã xoá {n} số của ngày {day}.")

    elif cmd == "show-config":
        for key in ("services", "counters", "extra"):
            print(f"\n=== {key} ===")
            print(json.dumps(db.get_json_config(key, {}), ensure_ascii=False, indent=2))

    else:
        print("Lệnh không hợp lệ.\n")
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
