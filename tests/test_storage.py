from anton.config import Settings
from anton.storage import ReportStorage


def test_local_only_keeps_report_without_public_url(tmp_path) -> None:
    report = tmp_path / "order-1.pdf"
    report.write_bytes(b"%PDF-1.4")
    settings = Settings(
        motifcue_api_base_url="https://motifcue.example.com",
        anton_internal_api_key="test-secret",
        report_storage_driver="local_only",
        data_directory=tmp_path / "data",
        report_directory=tmp_path,
    )

    assert ReportStorage(settings).publish("order-1", report) is None
