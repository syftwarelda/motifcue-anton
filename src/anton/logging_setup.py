import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler


def configure_logging(level: str, log_directory: Path, log_to_file: bool = True) -> None:
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(numeric_level)

    console_handler = RichHandler(
        console=Console(stderr=True),
        rich_tracebacks=True,
        tracebacks_show_locals=False,
        show_path=False,
        markup=False,
        omit_repeated_times=False,
    )
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(console_handler)

    if log_to_file:
        log_directory.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_directory / "anton.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        root.addHandler(file_handler)

    for noisy in ("httpx", "httpcore", "urllib3", "botocore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
