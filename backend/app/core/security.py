"""JWT, password hashing, and Fernet credential encryption."""
import json
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from cryptography.fernet import Fernet
from jose import JWTError, jwt

from app.core.config import settings

# ----- Passwords -----------------------------------------------------------

# bcrypt's max input length is 72 bytes; longer inputs are truncated explicitly.
def _prepare(password: str) -> bytes:
    return password.encode("utf-8")[:72]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare(plain), hashed.encode("utf-8"))
    except ValueError:
        return False


# ----- JWT -----------------------------------------------------------------

def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


# ----- Fernet encryption for SSH credentials -------------------------------

def _get_fernet() -> Fernet:
    if not settings.FERNET_KEY:
        raise RuntimeError(
            "FERNET_KEY is not configured. Generate one with "
            "Fernet.generate_key() and put it into your .env."
        )
    return Fernet(settings.FERNET_KEY.encode())


def encrypt_credentials(data: dict[str, Any]) -> str:
    return _get_fernet().encrypt(json.dumps(data).encode()).decode()


def decrypt_credentials(encrypted: str) -> dict[str, Any]:
    return json.loads(_get_fernet().decrypt(encrypted.encode()))
