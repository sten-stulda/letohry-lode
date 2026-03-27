from __future__ import annotations

from backend.config import AppConfig
from backend.pm3.csafe import CSAFECommand, build_frame, parse_frame
from backend.pm3.device import discover_pm3_ports


def test_csafe_roundtrip() -> None:
    frame = build_frame(CSAFECommand(command_id=0xA0, payload=b"\x01\xF1\x02"))
    parsed = parse_frame(frame)
    assert parsed == bytes([0xA0, 0x03, 0x01, 0xF1, 0x02])


def test_port_discovery_prefers_existing_explicit_paths() -> None:
    config = AppConfig(default_serial_ports=("/dev/null", "/definitely-missing"))
    ports = discover_pm3_ports(config)
    assert "/dev/null" in ports