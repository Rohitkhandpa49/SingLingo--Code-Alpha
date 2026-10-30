from typing import Any

from fastapi import HTTPException, Request, status
from pymongo.asynchronous.database import AsyncDatabase


async def get_database(request: Request) -> AsyncDatabase[dict[str, Any]]:
    database = getattr(request.app.state, "database", None)
    if database is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        )
    return database
