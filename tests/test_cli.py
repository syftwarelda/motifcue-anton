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
