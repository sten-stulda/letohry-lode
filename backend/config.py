from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def read_project_version() -> str:
    version_file = PROJECT_ROOT / "VERSION"
    try:
        return version_file.read_text(encoding="utf-8").strip() or "0.0.0"
    except FileNotFoundError:
        return "0.0.0"


@dataclass(slots=True)
class AppConfig:
    app_name: str = "LetoHry Lode"
    version: str = read_project_version()
    host: str = os.getenv("ROWING_HOST", "0.0.0.0")
    port: int = int(os.getenv("ROWING_PORT", "8000"))
    poll_interval_s: float = float(os.getenv("ROWING_POLL_INTERVAL", "0.25"))
    countdown_seconds: int = int(os.getenv("ROWING_COUNTDOWN_SECONDS", "3"))
    mock_speed_multiplier: float = float(os.getenv("ROWING_MOCK_SPEED_MULTIPLIER", "1.0"))
    serial_connect_retries: int = int(os.getenv("ROWING_SERIAL_CONNECT_RETRIES", "3"))
    diagnostics_enabled: bool = os.getenv("ROWING_DIAGNOSTICS_ENABLED", "1") == "1"
    diagnostics_max_events: int = int(os.getenv("ROWING_DIAGNOSTICS_MAX_EVENTS", "500"))
    database_url: str = os.getenv(
        "ROWING_DATABASE_URL",
        f"sqlite:///{PROJECT_ROOT / 'data' / 'race_history.db'}",
    )
    default_serial_ports: tuple[str, str] = (
        os.getenv("ROWING_PORT_1", "/dev/ttyUSB0"),
        os.getenv("ROWING_PORT_2", "/dev/ttyUSB1"),
    )
    frontend_dir: Path = PROJECT_ROOT / "frontend"
    data_dir: Path = PROJECT_ROOT / "data"
    diagnostics_log_path: Path = PROJECT_ROOT / "data" / "pm3-diagnostics.log"
    pm3_discovery_keywords: tuple[str, ...] = tuple(
        keyword.strip().lower()
        for keyword in os.getenv("ROWING_PM3_KEYWORDS", "concept2,pm3,performance monitor").split(",")
        if keyword.strip()
    )


def get_config() -> AppConfig:
    return AppConfig()