"""Đọc số bằng giọng tiếng Việt ở PHÍA MÁY CHỦ (dùng edge-tts).

Màn hình chỉ việc phát file mp3 do máy chủ tạo — không cần cài giọng đọc trên
từng máy nối TV. Có bộ nhớ đệm trên đĩa vì các câu đọc lặp lại rất nhiều.
"""
import asyncio
import hashlib
import os
import re
import threading

CACHE_DIR = os.environ.get(
    "GOISO_TTS_CACHE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "tts_cache"),
)
os.makedirs(CACHE_DIR, exist_ok=True)

DEFAULT_VOICE = "vi-VN-HoaiMyNeural"
ALLOWED_VOICES = {"vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural"}
MAX_TEXT = 300

_meta_lock = threading.Lock()
_key_locks = {}


def available():
    try:
        import edge_tts  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def normalize_voice(v):
    return v if v in ALLOWED_VOICES else DEFAULT_VOICE


def _key(text, voice):
    return hashlib.sha1(f"{voice}|{text}".encode("utf-8")).hexdigest()


def _synthesize(text, voice, path):
    import edge_tts
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(edge_tts.Communicate(text, voice).save(path))
    finally:
        loop.close()


def get_or_make(text, voice=DEFAULT_VOICE):
    """Trả về đường dẫn file mp3 (tạo mới nếu chưa có trong đệm)."""
    text = re.sub(r"\s+", " ", (text or "").strip())[:MAX_TEXT]
    if not text:
        raise ValueError("Thiếu nội dung đọc.")
    voice = normalize_voice(voice)
    key = _key(text, voice)
    path = os.path.join(CACHE_DIR, key + ".mp3")
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path

    with _meta_lock:
        lock = _key_locks.setdefault(key, threading.Lock())
    with lock:
        if not (os.path.exists(path) and os.path.getsize(path) > 0):
            tmp = path + ".part"
            _synthesize(text, voice, tmp)
            os.replace(tmp, path)
    return path
