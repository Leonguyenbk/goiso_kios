"""Gọi GoSo Server. Tái sử dụng kiosk/api_client.py cho phần bốc số/lịch hẹn
(branch-scoped, có X-Branch-Key); bổ sung các call không theo chi nhánh.

KHÔNG nhúng token GitHub / secret. Chỉ nói chuyện với GoSo Server.
"""
import requests

from api_client import ApiClient, ApiError  # module có sẵn trong kiosk/

__all__ = ["ServerClient", "ServerError", "ApiError"]


class ServerError(Exception):
    pass


class ServerClient:
    def __init__(self, server_url, branch_code="", api_key="", timeout=6):
        self.server = (server_url or "").rstrip("/")
        self.branch_code = (branch_code or "").strip().lower()
        self.api_key = api_key or ""
        self.timeout = timeout
        self._api = ApiClient(self.server, self.branch_code, self.api_key, timeout)

    # -------------------------------------------------- không theo chi nhánh
    def ping(self):
        """Xác nhận đây thực sự là GoSo Server. Ném ServerError nếu không phải."""
        try:
            r = requests.get(self.server + "/api/ping", timeout=self.timeout)
        except requests.Timeout:
            raise ServerError("Máy chủ không phản hồi (timeout).")
        except requests.RequestException as e:
            raise ServerError(f"Không kết nối được máy chủ: {e}")
        if not r.ok:
            raise ServerError(f"Máy chủ trả lỗi {r.status_code}. Kiểm tra lại địa chỉ.")
        try:
            data = r.json()
        except ValueError:
            raise ServerError("Địa chỉ không phải GoSo Server (response không hợp lệ).")
        if data.get("service") != "goso-kiosk-server":
            raise ServerError("Địa chỉ này không phải GoSo Server.")
        return data

    def branches(self):
        try:
            r = requests.get(self.server + "/api/branches", timeout=self.timeout)
            r.raise_for_status()
            return r.json().get("branches", [])
        except requests.RequestException as e:
            raise ServerError(f"Không lấy được danh sách chi nhánh: {e}")

    def kiosk_version(self):
        """Bản kiosk mới nhất áp dụng. {} nếu chưa cấu hình / lỗi (không ném)."""
        try:
            params = {"branch_code": self.branch_code} if self.branch_code else {}
            r = requests.get(self.server + "/api/kiosk/version",
                             params=params, timeout=self.timeout)
            if r.ok:
                return r.json() or {}
        except requests.RequestException:
            pass
        return {}

    # -------------------------------------------------- theo chi nhánh
    def config_public(self):
        return self._api.public_config()

    def take_ticket(self, prefix, fullname="", cccd="", phone=""):
        return self._api.take_ticket(prefix, fullname, cccd, phone)

    def checkin(self, code):
        return self._api.checkin(code)

    def heartbeat(self, *, device_id, name="", version="", printer="",
                  paper_mm=80, status="online", update_status=""):
        if not self.branch_code:
            return {}
        try:
            r = requests.post(
                f"{self.server}/api/b/{self.branch_code}/heartbeat",
                json={"device_id": device_id, "name": name, "version": version,
                      "printer": printer, "paper_mm": paper_mm,
                      "status": status, "update_status": update_status},
                headers={"X-Branch-Key": self.api_key}, timeout=self.timeout)
            if r.ok:
                return r.json() or {}
        except requests.RequestException:
            pass
        return {}
