from datetime import datetime

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings

_hasher = PasswordHasher()
_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(session_id: str, expires_at: datetime) -> str:
    """The token only carries the session id; validity is checked against the sessions table."""
    return jwt.encode(
        {"sid": session_id, "exp": expires_at}, get_settings().secret_key, algorithm=_ALGORITHM
    )


def decode_access_token(token: str) -> str | None:
    """Return the session id, or None for any invalid/expired token."""
    try:
        payload = jwt.decode(
            token,
            get_settings().secret_key,
            algorithms=[_ALGORITHM],
            options={"require": ["exp", "sid"]},
        )
    except jwt.PyJWTError:
        return None
    sid = payload.get("sid")
    return sid if isinstance(sid, str) else None
