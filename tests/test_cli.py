from anton.cli import build_parser


def test_run_prod_flag() -> None:
    args = build_parser().parse_args(["run", "--prod"])
    assert args.command == "run"
    assert args.prod is True


def test_default_uses_development_mode() -> None:
    args = build_parser().parse_args(["run"])
    assert args.command == "run"
    assert args.prod is False
