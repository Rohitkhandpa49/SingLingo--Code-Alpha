from pathlib import Path

import uvicorn

from app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        app_dir=str(Path(__file__).resolve().parent),
        host=settings.backend_host,
        port=settings.backend_port,
        reload=settings.app_env == "development",
        ws_max_size=settings.websocket_max_message_bytes,
        ws_max_queue=1,
        ws_ping_interval=settings.websocket_heartbeat_interval_seconds,
        ws_ping_timeout=settings.websocket_heartbeat_timeout_seconds,
        timeout_graceful_shutdown=settings.websocket_shutdown_timeout_seconds,
    )


if __name__ == "__main__":
    main()
