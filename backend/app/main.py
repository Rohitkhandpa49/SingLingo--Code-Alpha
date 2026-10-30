import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import PyMongoError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.health import router as health_router
from app.api.v1.router import router as v1_router
from app.core.config import Settings, get_settings
from app.core.rate_limit import limiter
from app.database.connection import create_mongo_client, get_database_from_client
from app.database.documents import StoredDocumentError
from app.database.indexes import create_indexes
from app.database.validation import ensure_collections
from app.services.gesture_classifier import GestureClassifier
from app.services.speech import SpeechRecognitionService
from app.websockets.manager import ConnectionManager
from app.websockets.rate_limiter import UserMessageRateLimiter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    test_database: AsyncDatabase[dict[str, Any]] | None = None,
) -> FastAPI:
    app_settings = settings or get_settings()
    websocket_manager = ConnectionManager(
        app_settings.websocket_max_connections_per_user
    )
    websocket_rate_limiter = UserMessageRateLimiter(
        app_settings.websocket_rate_limit_per_minute
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if app_settings.app_env == "test":
            app.state.database = test_database
            try:
                yield
            finally:
                await websocket_manager.close_all()
            return

        client: AsyncMongoClient[dict[str, Any]] = create_mongo_client(app_settings)
        try:
            database = get_database_from_client(client, app_settings)
            await database.command("ping")
            await ensure_collections(database)
            await create_indexes(database)
            app.state.database = database
            app.state.mongo_client = client
            logger.info("Connected to MongoDB database")
            yield
        finally:
            await websocket_manager.close_all()
            await client.close()
            logger.info("MongoDB client closed")

    app = FastAPI(
        title="SignLingo API",
        description="SignLingo account and translation-history API.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.limiter = limiter
    app.state.settings = app_settings
    app.state.gesture_classifier = GestureClassifier(app_settings)
    app.state.speech_service = SpeechRecognitionService(app_settings)
    app.state.websocket_manager = websocket_manager
    app.state.websocket_rate_limiter = websocket_rate_limiter
    app.dependency_overrides[get_settings] = lambda: app_settings
    if app_settings.app_env == "test":
        limiter.enabled = False
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    async def handle_database_error(request: Request, error: PyMongoError) -> JSONResponse:
        logger.error(
            "MongoDB operation failed: %s %s",
            request.method,
            request.url.path,
            extra={"error_type": error.__class__.__name__},
        )
        return JSONResponse(
            status_code=503,
            content={"detail": "Database service is temporarily unavailable"},
        )

    async def handle_invalid_stored_document(
        request: Request,
        error: StoredDocumentError,
    ) -> JSONResponse:
        logger.error(
            "Stored document validation failed for collection %s on %s %s",
            error.collection_name,
            request.method,
            request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Stored data failed validation"},
        )

    app.add_exception_handler(PyMongoError, handle_database_error)
    app.add_exception_handler(StoredDocumentError, handle_invalid_stored_document)

    @app.middleware("http")
    async def enforce_browser_origin(request: Request, call_next: Any) -> Any:
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            has_session_cookie = "signlingo_access" in request.cookies
            expected_origin = str(app_settings.frontend_origin).rstrip("/")
            invalid_origin = origin is not None and (
                origin == "null"
                or origin.rstrip("/") != expected_origin
                or bool(urlsplit(origin).path)
            )
            missing_cookie_origin = (
                origin is None
                and has_session_cookie
                and app_settings.app_env != "test"
            )
            if invalid_origin or missing_cookie_origin:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Request origin is not allowed"},
                )
        return await call_next(request)

    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(app_settings.frontend_origin).rstrip("/")],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.include_router(health_router)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(v1_router, prefix="/api/v1")
    return app


app = create_app()
