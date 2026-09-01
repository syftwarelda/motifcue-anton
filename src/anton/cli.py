from __future__ import annotations

import argparse
import asyncio
import difflib
import time
from collections import deque
from contextlib import suppress
from pathlib import Path

from anton.config import get_settings
from anton.db import Database
from anton.knowledge import KnowledgeService
from anton.llm import LlamaClient
from anton.local_data import export_order_data
from anton.logging_setup import configure_logging
from anton.worker import Worker


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="anton", description="MotifCue local analysis worker")
    parser.add_argument(
        "command",
        choices=(
            "run",
            "once",
            "status",
            "logs",
            "regenerate",
            "reanalyze",
            "export",
            "knowledge",
        ),
        nargs="?",
        default="run",
    )
    parser.add_argument("order_id", nargs="?", help="Order ID for local order commands")
    parser.add_argument(
        "knowledge_args",
        nargs="*",
        help="Action and value for 'anton knowledge' commands",
    )
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
        help="Report language override for regenerate or reanalyze",
    )
    parser.add_argument(
        "--refresh-images",
        action="store_true",
        help="Re-download saved media URLs and rerun local visual analysis",
    )
    parser.add_argument("--limit", type=int, default=6, help="Maximum knowledge search results")
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


async def _reanalyze(
    worker: Worker,
    order_id: str,
    output: Path | None,
    language: str | None,
    refresh_images: bool,
) -> Path:
    try:
        return await worker.pipeline.reanalyze_local(
            order_id,
            output,
            language,
            refresh_images=refresh_images,
        )
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


def _print_knowledge_results(results) -> None:
    if not results:
        print("No approved knowledge matched the query.")
        return
    for index, result in enumerate(results, start=1):
        excerpt = result.content.replace("\n", " ")[:300]
        print(f"{index}. {result.title} [{result.context}] · score={result.score:g}")
        print(f"   {result.url}")
        print(f"   {excerpt}")


def _knowledge(service: KnowledgeService, action: str, values: list[str]) -> None:
    service.register_catalog()
    if action == "status":
        rows = service.status_rows()
        print(f"{'SOURCE':<42} {'ACTIVE':<8} {'PENDING':<9} STATUS")
        for row in rows:
            status = row["error"] or ("OK" if row["active"] else "NOT_SYNCED")
            print(f"{row['id']:<42} {str(row['active']):<8} {str(row['pending']):<9} {status}")
        return
    if action == "approve":
        service.approve(values[0])
        print(f"Approved latest pending revision: {values[0]}")
        return
    if action == "diff":
        active, pending = service.db.knowledge_review_pair(values[0])
        if pending is None:
            print(f"No pending revision: {values[0]}")
            return
        before = active.content.splitlines() if active else []
        after = pending.content.splitlines()
        difference = difflib.unified_diff(
            before,
            after,
            fromfile=f"{values[0]}:active",
            tofile=f"{values[0]}:pending",
            lineterm="",
        )
        print("\n".join(difference))
        return
    raise ValueError(f"Unsupported knowledge action: {action}")


def _llm(settings) -> LlamaClient:
    return LlamaClient(
        str(settings.llm_base_url),
        settings.llm_api_key.get_secret_value(),
        settings.llm_text_model,
        settings.llm_vision_model,
        settings.llm_embedding_model,
        settings.llm_timeout_seconds,
        settings.llm_max_retries,
    )


async def _sync_knowledge(service: KnowledgeService, llm: LlamaClient) -> dict[str, int]:
    try:
        return await service.sync()
    finally:
        await llm.close()


async def _search_knowledge(service: KnowledgeService, llm: LlamaClient, query: str, limit: int):
    try:
        return await service.semantic_search(query, limit)
    finally:
        await llm.close()


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command in {"regenerate", "reanalyze", "export"} and not args.order_id:
        parser.error(f"anton {args.command} requires an order ID")
    if args.refresh_images and args.command != "reanalyze":
        parser.error("--refresh-images can only be used with 'anton reanalyze'")
    if args.command != "knowledge" and args.knowledge_args:
        parser.error("unexpected additional arguments")
    if args.command == "knowledge":
        action = args.order_id
        if action not in {"sync", "status", "search", "diff", "approve"}:
            parser.error("anton knowledge requires: sync, status, search, diff, or approve")
        if action in {"search", "diff", "approve"} and not args.knowledge_args:
            parser.error(f"anton knowledge {action} requires a value")
        if action in {"sync", "status"} and args.knowledge_args:
            parser.error(f"anton knowledge {action} accepts no additional value")
        if action in {"diff", "approve"} and len(args.knowledge_args) != 1:
            parser.error(f"anton knowledge {action} requires exactly one source ID")
    if args.limit < 1 or args.limit > 20:
        parser.error("--limit must be between 1 and 20")

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

    if args.command == "knowledge":
        if args.order_id in {"sync", "search"}:
            llm = _llm(settings)
            service = KnowledgeService(db, settings.request_timeout_seconds, embedder=llm)
        else:
            llm = None
            service = KnowledgeService(db, settings.request_timeout_seconds)
        if args.order_id == "sync":
            summary = asyncio.run(_sync_knowledge(service, llm))
            print(
                "Knowledge sync completed · "
                + " · ".join(f"{key}={value}" for key, value in summary.items())
            )
        elif args.order_id == "search":
            results = asyncio.run(
                _search_knowledge(
                    service,
                    llm,
                    " ".join(args.knowledge_args),
                    args.limit,
                )
            )
            _print_knowledge_results(results)
        else:
            _knowledge(service, args.order_id, args.knowledge_args)
        return

    if args.command == "export":
        exported = export_order_data(settings, db, args.order_id, args.output)
        print(exported.resolve())
        return

    worker = Worker(settings, db)
    if args.command == "regenerate":
        regenerated = asyncio.run(_regenerate(worker, args.order_id, args.output, args.language))
        print(regenerated.resolve())
    elif args.command == "reanalyze":
        reanalyzed = asyncio.run(
            _reanalyze(
                worker,
                args.order_id,
                args.output,
                args.language,
                args.refresh_images,
            )
        )
        print(reanalyzed.resolve())
    elif args.command == "once":
        if asyncio.run(_once(worker)) is None:
            raise SystemExit(1)
    else:
        with suppress(KeyboardInterrupt):
            asyncio.run(worker.run_forever())


if __name__ == "__main__":
    main()
