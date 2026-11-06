import ipaddress
import socket
from urllib.parse import urlparse

ALLOWED_HOSTS = {"tiktok.com", "www.tiktok.com", "m.tiktok.com", "vm.tiktok.com", "vt.tiktok.com"}

class UnsafeSource(ValueError):
    pass

def validate_tiktok_url(value: str) -> str:
    if not isinstance(value, str) or len(value) > 2048:
        raise UnsafeSource("TikTok URL is missing or too long.")
    parsed = urlparse(value.strip())
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or host not in ALLOWED_HOSTS or parsed.username or parsed.password:
        raise UnsafeSource("Only public HTTPS TikTok links are supported.")
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeSource("TikTok hostname could not be resolved.") from exc
    for item in addresses:
        ip = ipaddress.ip_address(item[4][0])
        if not ip.is_global:
            raise UnsafeSource("TikTok hostname resolved to a non-public network address.")
    return parsed.geturl()

def require_worker_key(provided: str | None, expected: str) -> None:
    import hmac
    if not expected:
        raise RuntimeError("WORKER_API_KEY must be configured before exposing the worker.")
    if not provided or not hmac.compare_digest(provided, expected):
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Invalid worker API key.")
