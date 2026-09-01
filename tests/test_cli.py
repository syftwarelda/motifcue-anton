from anton.cli import build_parser


def test_run_prod_flag() -> None:
    args = build_parser().parse_args(["run", "--prod"])
    assert args.command == "run"
    assert args.prod is True


def test_default_uses_development_mode() -> None:
    args = build_parser().parse_args(["run"])
    assert args.command == "run"
    assert args.prod is False


def test_logs_options() -> None:
    args = build_parser().parse_args(["logs", "--lines", "250", "--no-follow", "--prod"])
    assert args.command == "logs"
    assert args.lines == 250
    assert args.no_follow is True
    assert args.prod is True


def test_regenerate_and_export_arguments() -> None:
    regenerate = build_parser().parse_args(
        ["regenerate", "order-123", "--language", "es", "--output", "preview.pdf"]
    )
    assert regenerate.command == "regenerate"
    assert regenerate.order_id == "order-123"
    assert regenerate.language == "es"
    assert regenerate.output.name == "preview.pdf"

    export = build_parser().parse_args(["export", "order-123", "--prod"])
    assert export.command == "export"
    assert export.order_id == "order-123"
    assert export.prod is True


def test_reanalyze_can_refresh_images() -> None:
    args = build_parser().parse_args(
        ["reanalyze", "order-123", "--refresh-images", "--language", "es"]
    )
    assert args.command == "reanalyze"
    assert args.order_id == "order-123"
    assert args.refresh_images is True
    assert args.language == "es"


def test_knowledge_commands() -> None:
    sync = build_parser().parse_args(["knowledge", "sync", "--prod"])
    assert sync.command == "knowledge"
    assert sync.order_id == "sync"
    assert sync.prod is True

    search = build_parser().parse_args(
        ["knowledge", "search", "reels", "retention", "--limit", "4"]
    )
    assert search.order_id == "search"
    assert search.knowledge_args == ["reels", "retention"]
    assert search.limit == 4
