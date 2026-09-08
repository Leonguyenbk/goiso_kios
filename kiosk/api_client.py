"""Giao tiếp với máy chủ Flask."""
import requests


class ApiError(Exception):
    pass


class ApiClient:
    def __init__(self, base_url, timeout=6):
        self.base = base_url.rstrip("/")
        self.timeout = timeout

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
            r = requests.post(self.base + path, json=body, timeout=self.timeout)
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
        return self._get("/api/config/public")

    def take_ticket(self, prefix, fullname="", cccd="", phone=""):
        return self._post("/api/ticket", {
            "prefix": prefix, "fullname": fullname, "cccd": cccd, "phone": phone,
        })
