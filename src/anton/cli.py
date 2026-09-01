from __future__ import annotations

import argparse
import asyncio
import time
from collections import deque
from contextlib import suppress
from pathlib import Path

from anton.config import get_settings
from anton.db import Database
from anton.local_data import export_order_data
from anton.logging_setup import configure_logging
from anton.worker import Worker


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="anton", description="MotifCue local analysis worker")
    parser.add_argument(
        "command",
        choices=("run", "once", "status", "logs", "regenerate", "export"),
        nargs="?",
        default="run",
    )
    parser.add_argument("order_id", nargs="?", help="Order ID for regenerate or export")
    parser.add_argument(
        "--prod",
        action="store_true",
        help="Load production configuration from .env.prod instead of .env",
    )
    parser.add_argument("--lines", type=int, default=100, help="Lines shown by 'anton logs'")
    parser.add_argument(
        "--no-follow", action="store_true", help="Print existing logs without following them"
    )
    parser.add_argument("--output", type=Path, help="Custom output path")
    parser.add_argument(
        "--language",
        choices=("en", "es"),
        help="Report language override for 'anton regenerate'",
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


async def _once(worker: Worker) -> bool | None:
    try:
        return await worker.once()
    except Exception:
        return None
    finally:
        await worker.close()


async def _regenerate(
    worker: Worker, order_id: str, output: Path | None, language: str | None
) -> Path:
    try:
        return await worker.pipeline.regenerate_local(order_id, output, language)
    finally:
        await worker.close()


def _show_logs(path: Path, lines: int, follow: bool) -> None:
    if not path.exists():
        print(f"No log file yet: {path}")
        return

    with path.open(encoding="utf-8") as source:
        for line in deque(source, maxlen=max(1, lines)):
            print(line, end="")
        if not follow:
            return
        try:
            while True:
                line = source.readline()
                if line:
                    print(line, end="", flush=True)
                else:
                    time.sleep(0.25)
        except KeyboardInterrupt:
            return


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command in {"regenerate", "export"} and not args.order_id:
        parser.error(f"anton {args.command} requires an order ID")

    settings = get_settings(".env.prod" if args.prod else ".env")
    if args.command == "logs":
        _show_logs(settings.log_directory / "anton.log", args.lines, not args.no_follow)
        return

    configure_logging(settings.log_level, settings.log_directory, settings.log_to_file)
    db = Database(settings.database_url)
    db.create_schema()

    if args.command == "status":
        _status(db)
        return

    if args.command == "export":
        exported = export_order_data(settings, db, args.order_id, args.output)
        print(exported.resolve())
        return

    worker = Worker(settings, db)
    if args.command == "regenerate":
        regenerated = asyncio.run(_regenerate(worker, args.order_id, args.output, args.language))
        print(regenerated.resolve())
    elif args.command == "once":
        if asyncio.run(_once(worker)) is None:
            raise SystemExit(1)
    else:
        with suppress(KeyboardInterrupt):
            asyncio.run(worker.run_forever())


if __name__ == "__main__":
    main()
