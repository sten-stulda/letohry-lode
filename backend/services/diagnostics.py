from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from pathlib import Path
import json

from pydantic import BaseModel, Field


class DiagnosticEvent(BaseModel):
    timestamp: datetime
    lane_id: int
    port: str
    direction: str
    payload_hex: str
    note: str | None = None


class DiagnosticsSnapshot(BaseModel):
    enabled: bool
    log_path: str
    total_events: int
    recent_events: list[DiagnosticEvent] = Field(default_factory=list)


class DiagnosticsService:
    def __init__(self, enabled: bool, log_path: Path, max_events: int = 500) -> None:
        self.enabled = enabled
        self.log_path = log_path
        self.max_events = max(max_events, 10)
        self._events: deque[DiagnosticEvent] = deque(maxlen=self.max_events)
        self._total_events = 0
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_event(
        self,
        *,
        lane_id: int,
        port: str,
        direction: str,
        payload: bytes,
        note: str | None = None,
    ) -> None:
        if not self.enabled:
            return

        event = DiagnosticEvent(
            timestamp=datetime.now(timezone.utc),
            lane_id=lane_id,
            port=port,
            direction=direction,
            payload_hex=payload.hex(" "),
            note=note,
        )
        self._events.append(event)
        self._total_events += 1
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.model_dump(mode="json"), ensure_ascii=True) + "\n")

    def recent_events(self, limit: int = 50) -> list[DiagnosticEvent]:
        return list(self._events)[-max(limit, 0) :]

    def snapshot(self, limit: int = 20) -> DiagnosticsSnapshot:
        return DiagnosticsSnapshot(
            enabled=self.enabled,
            log_path=str(self.log_path),
            total_events=self._total_events,
            recent_events=self.recent_events(limit=limit),
        )

    def export_log_text(self) -> str:
        if not self.log_path.exists():
            return ""
        return self.log_path.read_text(encoding="utf-8")