from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from ..models import AppStatus, DiagnosticsStatus, HistoryResponse, RaceSnapshot, StartRaceRequest
from ..pm3.device import discover_pm3_ports


router = APIRouter()


@router.get("/api/status", response_model=AppStatus)
async def get_status(request: Request) -> AppStatus:
    race_manager = request.app.state.race_manager
    config = request.app.state.config
    snapshot = await race_manager.get_snapshot()
    return AppStatus(
        app_name=config.app_name,
        race=snapshot,
        serial_ports=discover_pm3_ports(config) or list(config.default_serial_ports),
        using_mock_devices=race_manager.using_mock_devices,
    )


@router.get("/api/race", response_model=RaceSnapshot)
async def get_race(request: Request) -> RaceSnapshot:
    return await request.app.state.race_manager.get_snapshot()


@router.post("/api/start", response_model=RaceSnapshot)
async def start_race(payload: StartRaceRequest, request: Request) -> RaceSnapshot:
    if len(payload.player_names) != 2:
        raise HTTPException(status_code=400, detail="Exactly two player names are required.")
    try:
        return await request.app.state.race_manager.start_race(payload)
    except RuntimeError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/api/reset", response_model=RaceSnapshot)
async def reset_race(request: Request) -> RaceSnapshot:
    return await request.app.state.race_manager.reset_race()


@router.get("/api/history", response_model=HistoryResponse)
async def get_history(
    request: Request,
    distance_m: int | None = Query(default=None, description="Optional race distance filter."),
) -> HistoryResponse:
    return request.app.state.history_store.history(distance_m=distance_m)


@router.get("/api/history/export")
async def export_history_csv(
    request: Request,
    distance_m: int | None = Query(default=None, description="Optional race distance filter."),
    player_name: str | None = Query(default=None, description="Optional player name filter."),
) -> StreamingResponse:
    csv_content = request.app.state.history_store.export_results_csv(
        distance_m=distance_m,
        player_name=player_name,
    )
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    filename = f"race-history-{timestamp}.csv"
    return StreamingResponse(
        iter([csv_content.encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/api/leaderboard/export")
async def export_leaderboard_csv(
    request: Request,
    distance_m: int | None = Query(default=None, description="Optional leaderboard distance filter."),
    limit: int = Query(default=10, ge=1, le=100, description="Maximum leaderboard rows to export."),
) -> StreamingResponse:
    csv_content = request.app.state.history_store.export_leaderboard_csv(distance_m=distance_m, limit=limit)
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    filename = f"leaderboard-{timestamp}.csv"
    return StreamingResponse(
        iter([csv_content.encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/api/diagnostics/status", response_model=DiagnosticsStatus)
async def get_diagnostics_status(request: Request) -> DiagnosticsStatus:
    snapshot = request.app.state.diagnostics_service.snapshot(limit=0)
    return DiagnosticsStatus(
        enabled=snapshot.enabled,
        log_path=snapshot.log_path,
        total_events=snapshot.total_events,
    )


@router.get("/api/diagnostics/events")
async def get_diagnostics_events(request: Request, limit: int = Query(default=50, ge=1, le=500)) -> dict:
    snapshot = request.app.state.diagnostics_service.snapshot(limit=limit)
    return snapshot.model_dump(mode="json")


@router.get("/api/diagnostics/export")
async def export_diagnostics_log(request: Request) -> StreamingResponse:
    log_content = request.app.state.diagnostics_service.export_log_text()
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    filename = f"pm3-diagnostics-{timestamp}.log"
    return StreamingResponse(
        iter([log_content.encode("utf-8")]),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.websocket("/ws/race")
async def race_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    race_manager = websocket.app.state.race_manager
    queue = await race_manager.subscribe()

    try:
        while True:
            snapshot = await queue.get()
            await websocket.send_json(snapshot.model_dump(mode="json"))
    except WebSocketDisconnect:
        race_manager.unsubscribe(queue)