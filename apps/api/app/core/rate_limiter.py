from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def get_real_ip(request: Request) -> str:
    """
    Extract real client IP, respecting X-Forwarded-For and X-Real-IP headers.
    Falls back to direct connection IP.
    Takes the FIRST IP in X-Forwarded-For (the original client, not the proxy).
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    return get_remote_address(request)


limiter = Limiter(key_func=get_real_ip)
