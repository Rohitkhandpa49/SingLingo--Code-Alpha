import argparse
import asyncio

from app.core.config import get_settings
from app.database.connection import create_mongo_client, get_database_from_client
from app.database.repositories.history import HistoryRepository


async def purge_history(*, execute: bool) -> int:
    settings = get_settings()
    if settings.history_retention_days is None:
        raise RuntimeError("Set HISTORY_RETENTION_DAYS before running history retention")

    client = create_mongo_client(settings)
    try:
        database = get_database_from_client(client, settings)
        await database.command("ping")
        repository = HistoryRepository(
            database,
            retention_days=settings.history_retention_days,
        )
        return await repository.purge_expired(dry_run=not execute)
    finally:
        await client.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Preview or explicitly remove expired translation history."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Delete expired history instead of only counting it.",
    )
    arguments = parser.parse_args()
    count = asyncio.run(purge_history(execute=arguments.execute))
    if arguments.execute:
        print(f"Deleted {count} expired translation history records.")
    else:
        print(f"{count} expired translation history records would be deleted.")


if __name__ == "__main__":
    main()
