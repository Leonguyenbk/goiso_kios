"""Tiện ích dòng lệnh cho hệ thống gọi số ĐA CHI NHÁNH.

  python manage.py init                              # tạo bảng CSDL
  python manage.py set-admin-pw <mk>                 # đặt mật khẩu quản trị TỔNG
  python manage.py add-branch <code> "<tên ngắn>" "<tên đầy đủ>" ["<địa chỉ>"]
  python manage.py seed-branches <branches.csv>      # nạp hàng loạt (code,name,full_name,address)
  python manage.py list-branches                     # xem chi nhánh + khoá
  python manage.py regen-key <code>                  # tạo lại API key kiosk
  python manage.py regen-display-token <code>
  python manage.py reset-today [<code>|all]          # xoá số đã cấp hôm nay
  python manage.py show-config <code>                # in cấu hình 1 chi nhánh
  python manage.py standardize [<code>|all]          # ghi lại DỊCH VỤ + QUẦY mặc định
  python manage.py add-user <user> "<Họ tên>" <mật khẩu> <mã chi nhánh|admin>
  python manage.py list-users
  python manage.py set-user-pw <user> <mật khẩu mới>
  python manage.py import-users <nhansu.csv> [mật_khẩu_mặc_định]
        # CSV cột: branch,full_name[,password]  — branch là MÃ hoặc TÊN chi nhánh
        # username tự sinh: cn<mã>.<tên><chữ đầu các từ còn lại>
"""
import csv
import hashlib
import json
import sys

try:  # đảm bảo in được tiếng Việt trên console Windows
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

import db


def _print_branch(b):
    flag = "ON " if b["active"] else "off"
    print(f"  [{flag}] {b['code']:<12} #{b['display_order']:<3} {b['name']}")
    print(f"        {b['full_name']}")
    print(f"        api_key       = {b['api_key']}")
    print(f"        display_token = {b['display_token']}")


def main(argv):
    if not argv:
        print(__doc__)
        return
    cmd = argv[0]
    db.init_db()

    if cmd == "init":
        print("Đã khởi tạo CSDL:", db.DB_PATH)
        if not db.list_branches():
            b = db.create_branch("eakar", "Ea Kar",
                                 "CHI NHÁNH KHU VỰC EA KAR", "")
            print("Đã tạo chi nhánh mẫu để chạy thử:")
            _print_branch(b)

    elif cmd == "set-admin-pw":
        if len(argv) < 2:
            print("Thiếu mật khẩu. VD: python manage.py set-admin-pw MatKhauMoi")
            return
        h = hashlib.sha256(argv[1].encode("utf-8")).hexdigest()
        db.set_config("admin_password", h)
        print("Đã đặt mật khẩu quản trị tổng mới.")

    elif cmd == "add-branch":
        if len(argv) < 4:
            print('VD: python manage.py add-branch eakar "Ea Kar" "CHI NHÁNH KHU VỰC EA KAR" "Thị trấn Ea Kar"')
            return
        addr = argv[4] if len(argv) > 4 else ""
        try:
            b = db.create_branch(argv[1], argv[2], argv[3], addr)
        except ValueError as e:
            print("Lỗi:", e)
            return
        print("Đã tạo chi nhánh:")
        _print_branch(b)

    elif cmd == "seed-branches":
        if len(argv) < 2:
            print("Thiếu đường dẫn CSV. Cột: code,name,full_name,address")
            return
        created, skipped = 0, 0
        with open(argv[1], encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                code = (row.get("code") or "").strip()
                if not code:
                    continue
                try:
                    db.create_branch(code, (row.get("name") or code).strip(),
                                     (row.get("full_name") or code).strip(),
                                     (row.get("address") or "").strip())
                    created += 1
                    print("  + ", code)
                except ValueError as e:
                    skipped += 1
                    print("  . ", code, "-", e)
        print(f"Xong: tạo {created}, bỏ qua {skipped}.")

    elif cmd == "list-branches":
        bs = db.list_branches()
        if not bs:
            print("(chưa có chi nhánh nào — dùng add-branch hoặc seed-branches)")
        for b in bs:
            _print_branch(b)
        print(f"\nTổng: {len(bs)} chi nhánh.")

    elif cmd in ("regen-key", "regen-display-token"):
        if len(argv) < 2:
            print("Thiếu mã chi nhánh.")
            return
        field = "api_key" if cmd == "regen-key" else "display_token"
        try:
            val = db.regen_branch_field(argv[1], field)
        except ValueError as e:
            print("Lỗi:", e)
            return
        print(f"{field} mới của {argv[1]}: {val}")

    elif cmd == "reset-today":
        target = argv[1] if len(argv) > 1 else "all"
        day = db.today_str()
        codes = ([b["code"] for b in db.list_branches()] if target == "all" else [target])
        with db.LOCK, db.get_conn() as conn:
            total = 0
            for code in codes:
                b = db.get_branch(code)
                if not b:
                    print("  ? bỏ qua", code)
                    continue
                n = conn.execute("DELETE FROM queue WHERE branch_id=? AND date_record=?",
                                 (b["id"], day)).rowcount
                conn.execute("DELETE FROM visitor_stats WHERE branch_id=? AND date_record=?",
                             (b["id"], day))
                conn.execute("UPDATE counters_status SET last_num='', status='offline' WHERE branch_id=?",
                             (b["id"],))
                total += n
                print(f"  {code}: xoá {n} số")
        print(f"Đã xoá tổng {total} số của ngày {day}.")

    elif cmd == "standardize":
        target = argv[1] if len(argv) > 1 else "all"
        codes = ([b["code"] for b in db.list_branches()] if target == "all" else [target])
        for code in codes:
            b = db.get_branch(code)
            if not b:
                print("  ? bỏ qua", code)
                continue
            db.set_json_config("services", json.loads(json.dumps(db.DEFAULT_SERVICES)), b["id"])
            db.set_json_config("counters", json.loads(json.dumps(db.DEFAULT_COUNTERS)), b["id"])
            print(f"  {code}: đã ghi lại {len(db.DEFAULT_SERVICES)} dịch vụ + "
                  f"{len(db.DEFAULT_COUNTERS)} quầy mặc định")
        print("Xong. (Không đụng tới cấu hình chung / đặt lịch / số đã cấp.)")

    elif cmd == "add-user":
        if len(argv) < 5:
            print('VD: python manage.py add-user hoanv "Nguyễn Văn Hoàn" MatKhau123 eakar')
            print('    python manage.py add-user sep "Phó phòng" MatKhau123 admin')
            return
        role = "admin" if argv[4].lower() == "admin" else "staff"
        bc = None if role == "admin" else argv[4]
        try:
            u = db.create_user(argv[1], argv[2], argv[3], role=role, branch_code=bc)
        except ValueError as e:
            print("Lỗi:", e)
            return
        print(f"Đã tạo: {u['username']} ({u['role']}) - {u['full_name']}"
              + (f" - chi nhánh {u['branch_code']}" if u['branch_code'] else ""))

    elif cmd == "list-users":
        for u in db.list_users():
            flag = "ON " if u["active"] else "off"
            br = u["branch_code"] or "-"
            print(f"  [{flag}] {u['username']:<16} {u['role']:<6} {br:<10} {u['full_name']}")

    elif cmd == "set-user-pw":
        if len(argv) < 3:
            print("VD: python manage.py set-user-pw hoanv MatKhauMoi")
            return
        db.update_user(argv[1], password=argv[2])
        print("Đã đổi mật khẩu cho", argv[1])

    elif cmd == "import-users":
        if len(argv) < 2:
            print("Thiếu CSV. Cột: branch,full_name[,password]")
            return
        default_pw = argv[2] if len(argv) > 2 else "123456"
        # bản đồ tra chi nhánh: mã + tên (bỏ dấu, thường)
        bmap = {}
        for b in db.list_branches():
            bmap[b["code"]] = b["code"]
            bmap[db.strip_accents(b["name"]).lower().strip()] = b["code"]
            bmap[db.strip_accents(b["full_name"]).lower().strip()] = b["code"]
        ok, fail = 0, 0
        rows_out = []
        with open(argv[1], encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                name = (row.get("full_name") or row.get("hoten") or "").strip()
                braw = (row.get("branch") or row.get("chi_nhanh") or "").strip()
                pw = (row.get("password") or "").strip() or default_pw
                if not name or not braw:
                    continue
                code = bmap.get(braw.lower()) or bmap.get(db.strip_accents(braw).lower())
                if not code:
                    print(f"  ! không rõ chi nhánh: {braw!r} ({name})")
                    fail += 1
                    continue
                uname = db.unique_username(db.gen_username(code, name))
                try:
                    db.create_user(uname, name, pw, role="staff", branch_code=code)
                    ok += 1
                    rows_out.append((uname, name, code, pw))
                except ValueError as e:
                    print(f"  ! {name}: {e}")
                    fail += 1
        print(f"\nĐã tạo {ok} tài khoản, lỗi {fail}.\n")
        for u, n, c, p in rows_out:
            print(f"  {u:<24} {p:<12} {c:<10} {n}")

    elif cmd == "show-config":
        if len(argv) < 2:
            print("Thiếu mã chi nhánh.")
            return
        b = db.get_branch(argv[1])
        if not b:
            print("Không có chi nhánh", argv[1])
            return
        for key in ("services", "counters", "extra", "booking"):
            print(f"\n=== {argv[1]} / {key} ===")
            print(json.dumps(db.get_json_config(key, {}, b["id"]), ensure_ascii=False, indent=2))

    else:
        print("Lệnh không hợp lệ.\n")
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
