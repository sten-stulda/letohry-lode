from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


RaceMode = Literal["realtime", "ghost", "interval"]
ThemeName = Literal["river", "lake", "night"]
GhostSource = Literal["none", "previous", "personal_best"]
LaneStatus = Literal["idle", "racing", "finished", "resting"]


class IntervalConfig(BaseModel):
    sprint_s: int = Field(default=30, ge=5, le=600)
    rest_s: int = Field(default=30, ge=5, le=600)
    repeats: int = Field(default=8, ge=1, le=30)


class StartRaceRequest(BaseModel):
    player_names: list[str] = Field(default_factory=lambda: ["Veslar 1", "Veslar 2"], min_length=2, max_length=2)
    distance_m: Literal[500, 1000, 2000] = 1000
    mode: RaceMode = "realtime"
    theme: ThemeName = "river"
    ghost_source: GhostSource = "none"
    interval: IntervalConfig | None = None
    use_mock_devices: bool = True


class TelemetryFrame(BaseModel):
    lane_id: int
    name: str
    connected: bool = True
    distance_m: float = 0.0
    elapsed_s: float = 0.0
    pace_per_500_s: float = 0.0
    stroke_rate: int = 0
    watts: float | None = None
    progress: float = 0.0
    rank: int = 0
    lead_m: float = 0.0
    status: LaneStatus = "idle"
    is_ghost: bool = False
    bonus_points: int = 0
    achievements: list[str] = Field(default_factory=list)
    interval_phase: Literal["sprint", "rest"] | None = None


class RaceSnapshot(BaseModel):
    race_id: str
    status: Literal["idle", "countdown", "racing", "finished"] = "idle"
    mode: RaceMode = "realtime"
    theme: ThemeName = "river"
    distance_m: int = 1000
    elapsed_s: float = 0.0
    lead_m: float = 0.0
    countdown_s: int = 0
    winner_lane: int | None = None
    lanes: list[TelemetryFrame] = Field(default_factory=list)
    ghost_lane: TelemetryFrame | None = None
    event: str = "idle"


class RaceResult(BaseModel):
    id: int | None = None
    player_name: str
    lane_id: int
    race_id: str
    mode: RaceMode
    distance_m: int
    finish_time_s: float
    created_at: datetime
    bonus_points: int = 0
    achievements: list[str] = Field(default_factory=list)


class LeaderboardEntry(BaseModel):
    player_name: str
    best_time_s: float
    distance_m: int
    achieved_at: datetime


class HistoryResponse(BaseModel):
    top_results: list[LeaderboardEntry]
    recent_results: list[RaceResult]


class AppStatus(BaseModel):
    app_name: str
    version: str
    race: RaceSnapshot
    serial_ports: list[str]
    using_mock_devices: bool


class DiagnosticsStatus(BaseModel):
    enabled: bool
    log_path: str
    total_events: int


class PM3Frame(BaseModel):
    elapsed_s: float = 0.0
    distance_m: float = 0.0
    pace_per_500_s: float = 0.0
    stroke_rate: int = 0
    watts: float | None = None