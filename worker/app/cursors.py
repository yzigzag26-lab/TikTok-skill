import base64
import hashlib
import hmac
import json
import time
from .config import CURSOR_SECRET

class InvalidCursor(ValueError):
    pass

def _sign(payload: bytes) -> str:
    if not CURSOR_SECRET:
        raise RuntimeError("CURSOR_SECRET must be configured.")
    return hmac.new(CURSOR_SECRET.encode(), payload, hashlib.sha256).hexdigest()

def _encode(data: dict) -> str:
    payload = json.dumps(data, separators=(",", ":")).encode()
    token = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    return token + "." + _sign(payload)

def _decode(token: str) -> dict:
    try:
        encoded, signature = token.split(".", 1)
        payload = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        if not hmac.compare_digest(_sign(payload), signature):
            raise InvalidCursor("Continuation cursor signature is invalid.")
        data = json.loads(payload)
        if int(data["exp"]) < int(time.time()):
            raise InvalidCursor("Continuation cursor has expired. Start a new analysis.")
        return data
    except InvalidCursor:
        raise
    except Exception as exc:
        raise InvalidCursor("Continuation cursor is malformed.") from exc

def encode_cursor(url: str, offset: float) -> str:
    return _encode({"kind": "url", "url": url, "offset": round(offset, 3), "exp": int(time.time()) + 6 * 3600})

def decode_cursor(token: str) -> tuple[str, float]:
    data = _decode(token)
    if data.get("kind", "url") != "url":
        raise InvalidCursor("This is not a TikTok URL continuation cursor.")
    offset = float(data["offset"])
    if offset < 0 or offset > 24 * 3600:
        raise InvalidCursor("Continuation cursor offset is invalid.")
    return str(data["url"]), offset

def encode_upload_cursor(session_id: str, offset: float) -> str:
    return _encode({"kind": "upload", "session": session_id, "offset": round(offset, 3), "exp": int(time.time()) + 6 * 3600})

def decode_upload_cursor(token: str) -> tuple[str, float]:
    data = _decode(token)
    if data.get("kind") != "upload":
        raise InvalidCursor("This is not an upload continuation cursor.")
    session_id = str(data["session"])
    if not session_id.isalnum() or len(session_id) != 32:
        raise InvalidCursor("Upload continuation session is invalid.")
    offset = float(data["offset"])
    if offset < 0 or offset > 24 * 3600:
        raise InvalidCursor("Upload continuation offset is invalid.")
    return session_id, offset
