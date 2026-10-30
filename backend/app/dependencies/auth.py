from typing import Any

import jwt
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import Settings, get_settings
from app.database.repositories.users import UserRecord, UserRepository
from app.dependencies.database import get_database

ACCESS_TOKEN_COOKIE = "signlingo_access"
_bearer_scheme = HTTPBearer(auto_error=False)


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication is required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _claims_from_access_token(token: str, settings: Settings) -> dict[str, Any]:
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "iat", "sub", "type"]},
        )
        subject = claims.get("sub")
        version = claims.get("ver", 0)
        if (
            not isinstance(subject, str)
            or claims.get("type") != "access"
            or not isinstance(version, int)
            or version < 0
        ):
            raise unauthorized()
        ObjectId(subject)
        return claims
    except (jwt.InvalidTokenError, InvalidId):
        raise unauthorized() from None


def user_id_from_access_token(token: str, settings: Settings) -> ObjectId:
    return ObjectId(_claims_from_access_token(token, settings)["sub"])


async def get_user_from_access_token(
    token: str | None,
    database: AsyncDatabase[dict[str, Any]],
    settings: Settings,
) -> UserRecord:
    if not token:
        raise unauthorized()
    claims = _claims_from_access_token(token, settings)
    user_id = ObjectId(claims["sub"])
    user = await UserRepository(database).get_by_id(user_id)
    if user is None or not user.is_active or user.session_version != claims.get("ver", 0):
        raise unauthorized()
    return user


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    database: AsyncDatabase[dict[str, Any]] = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> UserRecord:
    token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if token is None and credentials is not None:
        token = credentials.credentials
    return await get_user_from_access_token(token, database, settings)
