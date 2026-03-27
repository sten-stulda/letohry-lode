from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api.routes import router
from .config import get_config
from .core.race_manager import RaceManager
from .services.diagnostics import DiagnosticsService
from .storage import HistoryStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = app.state.config
    history_store = HistoryStore(config.database_url)
    diagnostics_service = DiagnosticsService(
        enabled=config.diagnostics_enabled,
        log_path=config.diagnostics_log_path,
        max_events=config.diagnostics_max_events,
    )
    race_manager = RaceManager(
        config=config,
        history_store=history_store,
        diagnostics_service=diagnostics_service,
    )
    app.state.history_store = history_store
    app.state.diagnostics_service = diagnostics_service
    app.state.race_manager = race_manager
    yield
    await race_manager.shutdown()


def create_app(config=None) -> FastAPI:
    resolved_config = config or get_config()
    app = FastAPI(title="LetoHry Lode", lifespan=lifespan)
    app.state.config = resolved_config
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    app.mount("/", StaticFiles(directory=resolved_config.frontend_dir, html=True), name="frontend")
    return app


app = create_app()