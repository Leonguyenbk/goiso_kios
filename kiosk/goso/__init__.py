"""Thư viện dùng chung cho bộ Kiosk Windows: GoSoKiosk / GoSoConfig / GoSoUpdater.

Không đụng tới nghiệp vụ bốc số/gọi số của server. Chỉ lo:
- đường dẫn (Program Files vs ProgramData, dev vs frozen)  -> goso.paths
- phiên bản 1 nguồn                                         -> goso.version
- log xoay vòng                                             -> goso.logs
- đọc/ghi + migrate cấu hình máy                            -> goso.appconfig
- danh tính thiết bị ổn định                                -> goso.device
- gọi server (ping / branches / version / heartbeat)        -> goso.serverclient
- tự khởi động cùng Windows                                 -> goso.autostart
- tải & thay bản mới an toàn (sha256, rollback)             -> goso.updater
"""
