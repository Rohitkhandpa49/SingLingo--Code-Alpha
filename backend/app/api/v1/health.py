import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import PyMongoError

from app.dependencies.database import get_database
from app.schemas.common import APIModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(APIModel):
    status: str
    database: str


@router.get("/live", response_model=HealthResponse)
async def liveness_check() -> HealthResponse:
    return HealthResponse(status="ok", database="not_checked")


@router.get("", response_model=HealthResponse)
@router.get("/ready", response_model=HealthResponse)
async def readiness_check(
    database: AsyncDatabase[dict[str, Any]] = Depends(get_database),
) -> HealthResponse:
    try:
        await database.command("ping")
    except PyMongoError as error:
        logger.warning("MongoDB health check failed: %s", error.__class__.__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from error
    return HealthResponse(status="ok", database="ok")
