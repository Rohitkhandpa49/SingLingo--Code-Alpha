from datetime import datetime, timedelta, timezone

import jwt
from bson import ObjectId
from pwdlib import PasswordHash

from app.core.config import Settings

_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password, password_hash)


def create_access_token(
    subject: ObjectId,
    settings: Settings,
    session_version: int = 0,
) -> str:
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": str(subject),
        "iat": issued_at,
        "exp": expires_at,
        "type": "access",
        "ver": session_version,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str, settings: Settings) -> dict[str, object]:
    return jwt.decode(
        token,
        settings.jwt_secret.get_secret_value(),
        algorithms=[settings.jwt_algorithm],
        options={"require": ["exp", "iat", "sub", "type"]},
    )
