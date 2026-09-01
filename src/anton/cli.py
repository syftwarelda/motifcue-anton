from __future__ import annotations

import argparse
import asyncio
from contextlib import suppress

from anton.config import get_settings
from anton.db import Database
from anton.logging_setup import configure_logging
from anton.worker import Worker


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="anton", description="MotifCue local analysis worker")
    parser.add_argument("command", choices=("run", "once", "status"), nargs="?", default="run")
    parser.add_argument(
        "--prod",
        action="store_true",
        help="Load production configuration from .env.prod instead of .env",
    )
    return parser


def _status(db: Database) -> None:
    jobs = db.recent_jobs()
    if not jobs:
        print("No local jobs yet.")
        return
    print(f"{'ORDER':<38} {'STAGE':<20} {'ATTEMPTS':<8} UPDATED")
    for job in jobs:
        print(
            f"{job.order_id:<38} {job.stage:<20} {job.attempts:<8} "
            f"{job.updated_at.isoformat(timespec='seconds')}"
        )


async def _once(worker: Worker) -> None:
    try:
        await worker.once()
    finally:
        await worker.close()


def main() -> None:
    args = build_parser().parse_args()

    settings = get_settings(".env.prod" if args.prod else ".env")
    configure_logging(settings.log_level)
    db = Database(settings.database_url)
    db.create_schema()

    if args.command == "status":
        _status(db)
        return

    worker = Worker(settings, db)
    if args.command == "once":
        asyncio.run(_once(worker))
    else:
        with suppress(KeyboardInterrupt):
            asyncio.run(worker.run_forever())


if __name__ == "__main__":
    main()
