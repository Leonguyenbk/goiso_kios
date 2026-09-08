"""Giao tiếp với máy chủ Flask (đa chi nhánh).

Mọi lệnh gọi đi qua `{server_url}/api/b/{branch_code}/...`.
POST kèm header `X-Branch-Key: {api_key}` để máy chủ xác thực kiosk của chi nhánh.
"""
import requests


class ApiError(Exception):
    pass


class ApiClient:
    def __init__(self, server_url, branch_code="", api_key="", timeout=6):
        self.server = server_url.rstrip("/")
        self.branch_code = (branch_code or "").strip().lower()
        self.api_key = api_key or ""
        self.timeout = timeout

    @property
    def base(self):
        if not self.branch_code:
            raise ApiError("Chưa cấu hình 'branch_code' trong config.json.")
        return f"{self.server}/api/b/{self.branch_code}"

    def _get(self, path):
        try:
            r = requests.get(self.base + path, timeout=self.timeout)
        except requests.RequestException as e:
            raise ApiError(f"Không kết nối được máy chủ: {e}")
        if not r.ok:
            raise ApiError(self._msg(r))
        return r.json()

    def _post(self, path, body):
        try:
            r = requests.post(self.base + path, json=body, timeout=self.timeout,
                              headers={"X-Branch-Key": self.api_key})
        except requests.RequestException as e:
            raise ApiError(f"Không kết nối được máy chủ: {e}")
        if not r.ok:
            raise ApiError(self._msg(r))
        return r.json()

    @staticmethod
    def _msg(r):
        try:
            return r.json().get("error", f"Lỗi máy chủ ({r.status_code})")
        except ValueError:
            return f"Lỗi máy chủ ({r.status_code})"

    def public_config(self):
        return self._get("/config/public")

    def take_ticket(self, prefix, fullname="", cccd="", phone=""):
        return self._post("/ticket", {
            "prefix": prefix, "fullname": fullname, "cccd": cccd, "phone": phone,
        })

    def checkin(self, code):
        """Đổi mã lịch hẹn online lấy phiếu số (Phase 2)."""
        return self._post("/checkin", {"code": code})
