from __future__ import annotations

import asyncio
from datetime import datetime
from uuid import uuid4

from ..config import AppConfig
from ..models import PM3Frame, RaceResult, RaceSnapshot, StartRaceRequest, TelemetryFrame
from ..pm3.device import MockRowingMonitor, PM3SerialMonitor, RowingMonitor, resolve_pm3_ports
from ..services.diagnostics import DiagnosticsService
from ..storage import HistoryStore


ACHIEVEMENTS = {
    "first_race": "Prvni zavod",
    "personal_best": "Osobni rekord",
    "ten_races": "10 zavodu",
    "ten_k": "10000 m celkem",
}


class RaceManager:
    def __init__(self, config: AppConfig, history_store: HistoryStore, diagnostics_service: DiagnosticsService) -> None:
        self.config = config
        self.history_store = history_store
        self.diagnostics_service = diagnostics_service
        self.snapshot = RaceSnapshot(race_id="idle")
        self.monitors: list[RowingMonitor] = []
        self._broadcast_queues: set[asyncio.Queue[RaceSnapshot]] = set()
        self._lock = asyncio.Lock()
        self._countdown_task: asyncio.Task[None] | None = None
        self._polling_task: asyncio.Task[None] | None = None
        self._using_mock_devices = True

    @property
    def using_mock_devices(self) -> bool:
        return self._using_mock_devices

    async def start_race(self, request: StartRaceRequest) -> RaceSnapshot:
        async with self._lock:
            await self._stop_active_tasks()
            self._using_mock_devices = request.use_mock_devices
            self.monitors = self._build_monitors(request)
            for monitor in self.monitors:
                await monitor.connect()
                await monitor.reset()

            self.snapshot = RaceSnapshot(
                race_id=uuid4().hex,
                status="countdown",
                mode=request.mode,
                theme=request.theme,
                distance_m=request.distance_m,
                countdown_s=3,
                lanes=[
                    TelemetryFrame(lane_id=index + 1, name=name)
                    for index, name in enumerate(request.player_names)
                ],
                event="countdown",
            )
            self._attach_ghost_lane(request)
            self._countdown_task = asyncio.create_task(self._run_countdown(request), name="race-countdown")
            await self._broadcast()
            return self.snapshot

    async def reset_race(self) -> RaceSnapshot:
        async with self._lock:
            await self._stop_active_tasks()
            for monitor in self.monitors:
                await monitor.reset()
                await monitor.disconnect()
            self.monitors = []
            self.snapshot = RaceSnapshot(race_id="idle")
            await self._broadcast()
            return self.snapshot

    async def get_snapshot(self) -> RaceSnapshot:
        return self.snapshot

    async def subscribe(self) -> asyncio.Queue[RaceSnapshot]:
        queue: asyncio.Queue[RaceSnapshot] = asyncio.Queue(maxsize=4)
        self._broadcast_queues.add(queue)
        await queue.put(self.snapshot)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[RaceSnapshot]) -> None:
        self._broadcast_queues.discard(queue)

    async def shutdown(self) -> None:
        await self.reset_race()

    def _build_monitors(self, request: StartRaceRequest) -> list[RowingMonitor]:
        if request.use_mock_devices:
            return [
                MockRowingMonitor(
                    lane_id=index + 1,
                    name=name,
                    speed_multiplier=self.config.mock_speed_multiplier,
                )
                for index, name in enumerate(request.player_names)
            ]

        resolved_ports = resolve_pm3_ports(self.config, expected_count=len(request.player_names))

        return [
            PM3SerialMonitor(
                lane_id=index + 1,
                name=name,
                port=resolved_ports[index],
                connect_retries=self.config.serial_connect_retries,
                diagnostics_service=self.diagnostics_service,
            )
            for index, name in enumerate(request.player_names)
        ]

    async def _run_countdown(self, request: StartRaceRequest) -> None:
        for second in range(self.config.countdown_seconds, 0, -1):
            self.snapshot.countdown_s = second
            self.snapshot.event = "countdown"
            await self._broadcast()
            await asyncio.sleep(1)

        self.snapshot.countdown_s = 0
        self.snapshot.status = "racing"
        self.snapshot.event = "race_started"
        for lane in self.snapshot.lanes:
            lane.status = "racing"
        await self._broadcast()
        self._polling_task = asyncio.create_task(self._poll_race(request), name="race-polling")

    async def _poll_race(self, request: StartRaceRequest) -> None:
        total_distance = float(request.distance_m)

        while True:
            frames = await asyncio.gather(*(monitor.read_frame() for monitor in self.monitors), return_exceptions=True)
            lane_distances: list[float] = []
            all_finished = True

            for lane, frame in zip(self.snapshot.lanes, frames, strict=True):
                if isinstance(frame, Exception):
                    lane.connected = False
                    lane.status = "idle"
                    all_finished = False
                    lane_distances.append(lane.distance_m)
                    continue

                self._update_lane(lane, frame, request, total_distance)
                lane_distances.append(lane.distance_m)
                if lane.distance_m < total_distance:
                    all_finished = False

            if self.snapshot.ghost_lane:
                self._advance_ghost_lane(request, total_distance)

            self._refresh_ranks_and_lead(lane_distances)
            self.snapshot.elapsed_s = max((lane.elapsed_s for lane in self.snapshot.lanes), default=0.0)
            self.snapshot.event = "telemetry"
            await self._broadcast()

            if all_finished:
                await self._finish_race(request)
                return
            await asyncio.sleep(self.config.poll_interval_s)

    def _update_lane(self, lane: TelemetryFrame, frame: PM3Frame, request: StartRaceRequest, total_distance: float) -> None:
        previous_distance = lane.distance_m
        previous_elapsed = lane.elapsed_s

        if lane.status == "finished":
            lane.connected = True
            return

        next_distance = min(frame.distance_m, total_distance)
        crossed_finish = previous_distance < total_distance <= frame.distance_m

        lane.connected = True
        lane.distance_m = next_distance
        lane.pace_per_500_s = frame.pace_per_500_s
        lane.stroke_rate = frame.stroke_rate
        lane.watts = frame.watts
        lane.progress = min(lane.distance_m / total_distance, 1.0)

        if crossed_finish and frame.distance_m > previous_distance and frame.elapsed_s >= previous_elapsed:
            finish_fraction = (total_distance - previous_distance) / (frame.distance_m - previous_distance)
            lane.elapsed_s = previous_elapsed + ((frame.elapsed_s - previous_elapsed) * finish_fraction)
            lane.distance_m = total_distance
            lane.progress = 1.0
            lane.status = "finished"
        else:
            lane.elapsed_s = frame.elapsed_s
            lane.status = "finished" if lane.progress >= 1.0 else "racing"

        lane.bonus_points = self._calculate_bonus_points(lane, request.distance_m)
        lane.achievements = []
        if request.mode == "interval":
            lane.interval_phase = self._resolve_interval_phase(request, frame.elapsed_s)

    def _advance_ghost_lane(self, request: StartRaceRequest, total_distance: float) -> None:
        ghost = self.snapshot.ghost_lane
        if not ghost:
            return

        ghost_speed = total_distance / max(ghost.elapsed_s or 1.0, 1.0)
        ghost.distance_m = min(ghost.distance_m + (ghost_speed * self.config.poll_interval_s), total_distance)
        ghost.progress = min(ghost.distance_m / total_distance, 1.0)
        ghost.status = "finished" if ghost.progress >= 1.0 else "racing"

    def _refresh_ranks_and_lead(self, lane_distances: list[float]) -> None:
        ranking = sorted(enumerate(lane_distances), key=lambda item: item[1], reverse=True)
        leader_distance = ranking[0][1] if ranking else 0.0
        second_distance = ranking[1][1] if len(ranking) > 1 else leader_distance
        leader_gap = leader_distance - second_distance
        for rank, (index, distance) in enumerate(ranking, start=1):
            lane = self.snapshot.lanes[index]
            lane.rank = rank
            lane.lead_m = leader_gap if rank == 1 else distance - leader_distance
        self.snapshot.lead_m = leader_gap

    async def _finish_race(self, request: StartRaceRequest) -> None:
        self.snapshot.status = "finished"
        self.snapshot.event = "race_finished"
        ordered_lanes = sorted(self.snapshot.lanes, key=lambda lane: lane.elapsed_s)
        self.snapshot.winner_lane = ordered_lanes[0].lane_id if ordered_lanes else None
        for rank, lane in enumerate(ordered_lanes, start=1):
            lane.rank = rank
            lane.lead_m = 0.0

        for lane in ordered_lanes:
            achievements = self._resolve_achievements(lane, request.distance_m)
            lane.achievements = achievements
            result = RaceResult(
                player_name=lane.name,
                lane_id=lane.lane_id,
                race_id=self.snapshot.race_id,
                mode=request.mode,
                distance_m=request.distance_m,
                finish_time_s=lane.elapsed_s,
                created_at=datetime.utcnow(),
                bonus_points=lane.bonus_points,
                achievements=achievements,
            )
            self.history_store.save_result(result)

        await self._broadcast()

    def _resolve_achievements(self, lane: TelemetryFrame, distance_m: int) -> list[str]:
        achievements: list[str] = []
        recent_results = [result for result in self.history_store.get_recent_results(limit=200) if result.player_name == lane.name]
        cumulative_distance = sum(result.distance_m for result in recent_results) + distance_m
        best = self.history_store.get_personal_best(lane.name, distance_m)
        if not recent_results:
            achievements.append(ACHIEVEMENTS["first_race"])
        if len(recent_results) + 1 >= 10:
            achievements.append(ACHIEVEMENTS["ten_races"])
        if cumulative_distance >= 10000:
            achievements.append(ACHIEVEMENTS["ten_k"])
        if not best or lane.elapsed_s < best.finish_time_s:
            achievements.append(ACHIEVEMENTS["personal_best"])
        return achievements

    def _calculate_bonus_points(self, lane: TelemetryFrame, distance_m: int) -> int:
        points = 0
        if lane.pace_per_500_s and lane.distance_m >= distance_m - 100:
            points += 50
        if lane.stroke_rate and 24 <= lane.stroke_rate <= 30:
            points += 10
        if lane.pace_per_500_s and lane.pace_per_500_s <= 120:
            points += 25
        return points

    def _resolve_interval_phase(self, request: StartRaceRequest, elapsed_s: float) -> str | None:
        if not request.interval:
            return None
        cycle = request.interval.sprint_s + request.interval.rest_s
        phase_position = elapsed_s % cycle
        return "sprint" if phase_position < request.interval.sprint_s else "rest"

    def _attach_ghost_lane(self, request: StartRaceRequest) -> None:
        if request.mode != "ghost" or request.ghost_source == "none":
            self.snapshot.ghost_lane = None
            return

        source = None
        if request.ghost_source == "previous":
            source = self.history_store.get_last_result(request.player_names[0], request.distance_m)
        elif request.ghost_source == "personal_best":
            source = self.history_store.get_personal_best(request.player_names[0], request.distance_m)

        if not source:
            self.snapshot.ghost_lane = TelemetryFrame(
                lane_id=99,
                name="Ghost",
                is_ghost=True,
                pace_per_500_s=120,
                elapsed_s=max(request.distance_m / 4.4, 1.0),
            )
            return

        self.snapshot.ghost_lane = TelemetryFrame(
            lane_id=99,
            name=f"Ghost {source.player_name}",
            is_ghost=True,
            elapsed_s=source.finish_time_s,
            pace_per_500_s=(source.finish_time_s / request.distance_m) * 500,
        )

    async def _stop_active_tasks(self) -> None:
        for task in (self._countdown_task, self._polling_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._countdown_task = None
        self._polling_task = None

    async def _broadcast(self) -> None:
        stale_queues: list[asyncio.Queue[RaceSnapshot]] = []
        for queue in self._broadcast_queues:
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    stale_queues.append(queue)
                    continue
            await queue.put(self.snapshot.model_copy(deep=True))

        for queue in stale_queues:
            self._broadcast_queues.discard(queue)