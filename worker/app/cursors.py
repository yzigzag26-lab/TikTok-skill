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

def encode_cursor(url: str, offset: float) -> str:
    payload = json.dumps({"url": url, "offset": round(offset, 3), "exp": int(time.time()) + 6 * 3600}, separators=(",", ":")).encode()
    token = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    return token + "." + _sign(payload)

def decode_cursor(token: str) -> tuple[str, float]:
    try:
        encoded, signature = token.split(".", 1)
        payload = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        if not hmac.compare_digest(_sign(payload), signature):
            raise InvalidCursor("Continuation cursor signature is invalid.")
        data = json.loads(payload)
        if int(data["exp"]) < int(time.time()):
            raise InvalidCursor("Continuation cursor has expired. Start a new analysis.")
        url = str(data["url"])
        offset = float(data["offset"])
        if offset < 0 or offset > 24 * 3600:
            raise InvalidCursor("Continuation cursor offset is invalid.")
        return url, offset
    except InvalidCursor:
        raise
    except Exception as exc:
        raise InvalidCursor("Continuation cursor is malformed.") from exc
