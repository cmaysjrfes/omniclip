from cryptography.fernet import Fernet
from fastapi import Header, HTTPException, Query

from .config import get_settings


async def require_api_key(x_api_key: str = Header(default=""), key: str = Query(default="")) -> None:
    """Internal tool: a shared team key. Swap for SSO/OIDC before exposing beyond the VPN.
    `?key=` exists only because browser EventSource (SSE) cannot send custom headers."""
    if get_settings().api_key not in (x_api_key, key):
        raise HTTPException(status_code=401, detail="invalid API key")


def _fernet() -> Fernet:
    key = get_settings().token_encryption_key
    if not key:
        raise RuntimeError("TOKEN_ENCRYPTION_KEY is not set")
    return Fernet(key.encode())


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    return _fernet().decrypt(value.encode()).decode()
