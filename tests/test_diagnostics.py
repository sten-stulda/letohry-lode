from __future__ import annotations

from pathlib import Path

from backend.services.diagnostics import DiagnosticsService


def test_diagnostics_service_writes_and_reports_events(tmp_path: Path) -> None:
    log_path = tmp_path / "pm3.log"
    service = DiagnosticsService(enabled=True, log_path=log_path, max_events=20)

    service.log_event(
        lane_id=1,
        port="/dev/ttyUSB0",
        direction="tx",
        payload=b"\xf1\xa0\x00\xf2",
        note="test frame",
    )

    snapshot = service.snapshot(limit=10)
    assert snapshot.enabled is True
    assert snapshot.total_events == 1
    assert snapshot.recent_events[0].direction == "tx"
    assert "f1 a0 00 f2" == snapshot.recent_events[0].payload_hex
    assert "test frame" in service.export_log_text()