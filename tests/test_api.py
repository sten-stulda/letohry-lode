from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.config import AppConfig, PROJECT_ROOT
from backend.main import create_app


def create_test_client(tmp_path: Path) -> TestClient:
    config = AppConfig(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        frontend_dir=PROJECT_ROOT / "frontend",
        data_dir=tmp_path,
        poll_interval_s=0.01,
        countdown_seconds=1,
        mock_speed_multiplier=40.0,
    )
    return TestClient(create_app(config))


def wait_for_race_finish(client: TestClient, timeout_s: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        payload = client.get("/api/race").json()
        if payload["status"] == "finished":
            return payload
        time.sleep(0.05)
    raise AssertionError("Race did not finish within timeout.")


def wait_for_race_progress(client: TestClient, timeout_s: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        payload = client.get("/api/race").json()
        if payload["status"] == "racing":
            ranked_lanes = [lane for lane in payload["lanes"] if lane["rank"] in {1, 2}]
            # Ghost mode with 1 player has only 1 lane + ghost_lane
            if payload.get("ghost_lane"):
                if len(payload["lanes"]) >= 1:
                    return payload
            elif len(ranked_lanes) == 2 and any(lane["lead_m"] > 0 for lane in ranked_lanes):
                return payload
        time.sleep(0.05)
    raise AssertionError("Race did not produce measurable lead within timeout.")


def test_status_start_finish_and_history(tmp_path: Path) -> None:
    with create_test_client(tmp_path) as client:
        status_payload = client.get("/api/status")
        assert status_payload.status_code == 200
        assert status_payload.json()["race"]["status"] == "idle"
        assert status_payload.json()["version"] == "0.1.0"

        start_response = client.post(
            "/api/start",
            json={
                "player_names": ["Alice", "Bob"],
                "distance_m": 500,
                "mode": "realtime",
                "theme": "lake",
                "ghost_source": "none",
                "use_mock_devices": True,
            },
        )
        assert start_response.status_code == 200
        assert start_response.json()["status"] == "countdown"

        racing_payload = wait_for_race_progress(client)
        leader_lane = next(lane for lane in racing_payload["lanes"] if lane["rank"] == 1)
        trailing_lane = next(lane for lane in racing_payload["lanes"] if lane["rank"] == 2)
        assert leader_lane["lead_m"] > 0
        assert trailing_lane["lead_m"] < 0

        finished_payload = wait_for_race_finish(client)
        assert finished_payload["winner_lane"] == 2
        winner_lane = next(lane for lane in finished_payload["lanes"] if lane["lane_id"] == finished_payload["winner_lane"])
        assert winner_lane["rank"] == 1
        assert all(lane["status"] == "finished" for lane in finished_payload["lanes"])

        history_payload = client.get("/api/history")
        assert history_payload.status_code == 200
        history_json = history_payload.json()
        assert len(history_json["recent_results"]) == 2
        assert len(history_json["top_results"]) >= 2


def test_control_panel_page_is_served(tmp_path: Path) -> None:
    with create_test_client(tmp_path) as client:
        response = client.get("/control")

        assert response.status_code == 200
        assert "Ovládací panel" in response.text
        assert 'id="startButton"' in response.text
        assert 'id="serialPort1"' in response.text
        assert 'id="clearHistoryButton"' in response.text


def test_history_can_be_cleared(tmp_path: Path) -> None:
    with create_test_client(tmp_path) as client:
        client.post(
            "/api/start",
            json={
                "player_names": ["Alice", "Bob"],
                "distance_m": 500,
                "mode": "realtime",
                "theme": "lake",
                "ghost_source": "none",
                "use_mock_devices": True,
            },
        )
        wait_for_race_finish(client)

        response = client.post("/api/history/clear")

        assert response.status_code == 200
        payload = response.json()
        assert payload["recent_results"] == []
        assert payload["top_results"] == []


def test_websocket_stream_delivers_race_updates(tmp_path: Path) -> None:
    with create_test_client(tmp_path) as client:
        with client.websocket_connect("/ws/race") as websocket:
            initial_snapshot = websocket.receive_json()
            assert initial_snapshot["status"] == "idle"

            client.post(
                "/api/start",
                json={
                    "player_names": ["Alpha", "Beta"],
                    "distance_m": 500,
                    "mode": "interval",
                    "theme": "night",
                    "ghost_source": "none",
                    "use_mock_devices": True,
                    "interval": {"sprint_s": 30, "rest_s": 30, "repeats": 8},
                },
            )

            statuses = []
            deadline = time.monotonic() + 4.0
            while time.monotonic() < deadline:
                snapshot = websocket.receive_json()
                statuses.append(snapshot["status"])
                if snapshot["status"] == "finished":
                    break

            assert "countdown" in statuses
            assert "racing" in statuses
            assert "finished" in statuses


def test_start_without_mock_and_without_devices_returns_400(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.pm3.device.discover_pm3_ports", lambda _config: [])
    monkeypatch.setattr("backend.pm3.device.discover_pm3_hid_devices", lambda: [])
    monkeypatch.setattr("backend.pm3.device.discover_pm3_usb_devices", lambda: [])

    with create_test_client(tmp_path) as client:
        response = client.post(
            "/api/start",
            json={
                "player_names": ["Alice", "Bob"],
                "distance_m": 500,
                "mode": "realtime",
                "theme": "river",
                "ghost_source": "none",
                "use_mock_devices": False,
            },
        )

        assert response.status_code == 400
        assert "Not enough PM3 devices detected" in response.json()["detail"]


def test_history_can_be_exported_as_csv(tmp_path: Path) -> None:
    with create_test_client(tmp_path) as client:
        client.post(
            "/api/start",
            json={
                "player_names": ["Alice", "Bob"],
                "distance_m": 500,
                "mode": "realtime",
                "theme": "lake",
                "ghost_source": "none",
                "use_mock_devices": True,
            },
        )
        wait_for_race_finish(client)

        response = client.get("/api/history/export", params={"distance_m": 500, "player_name": "Alice"})

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "attachment; filename=\"race-history-" in response.headers["content-disposition"]
        body = response.text
        assert "player_name,lane_id,race_id,mode,distance_m" in body
        assert "Alice" in body


def test_leaderboard_and_diagnostics_exports(tmp_path: Path) -> None:
    with create_test_client(tmp_path) as client:
        client.post(
            "/api/start",
            json={
                "player_names": ["Alice", "Bob"],
                "distance_m": 500,
                "mode": "realtime",
                "theme": "lake",
                "ghost_source": "none",
                "use_mock_devices": True,
            },
        )
        wait_for_race_finish(client)

        leaderboard_response = client.get("/api/leaderboard/export", params={"distance_m": 500, "limit": 10})
        assert leaderboard_response.status_code == 200
        assert leaderboard_response.headers["content-type"].startswith("text/csv")
        assert "rank,player_name,best_time_s,distance_m,achieved_at" in leaderboard_response.text

        diagnostics_status = client.get("/api/diagnostics/status")
        assert diagnostics_status.status_code == 200
        assert diagnostics_status.json()["enabled"] is True

        diagnostics_export = client.get("/api/diagnostics/export")
        assert diagnostics_export.status_code == 200
        assert diagnostics_export.headers["content-type"].startswith("text/plain")


def test_ghost_mode_with_single_player(tmp_path: Path) -> None:
    with create_test_client(tmp_path) as client:
        start_response = client.post(
            "/api/start",
            json={
                "player_names": ["Alice"],
                "distance_m": 500,
                "mode": "ghost",
                "theme": "river",
                "ghost_source": "previous",
                "use_mock_devices": True,
            },
        )
        assert start_response.status_code == 200
        assert start_response.json()["status"] == "countdown"

        racing_payload = wait_for_race_progress(client)
        assert len(racing_payload["lanes"]) == 1
        assert racing_payload["ghost_lane"] is not None

        finished_payload = wait_for_race_finish(client)
        assert finished_payload["status"] == "finished"
        assert len(finished_payload["lanes"]) == 1

        history_payload = client.get("/api/history")
        assert len(history_payload.json()["recent_results"]) == 1


def test_realtime_mode_requires_two_players(tmp_path: Path) -> None:
    with create_test_client(tmp_path) as client:
        response = client.post(
            "/api/start",
            json={
                "player_names": ["Alice"],
                "distance_m": 500,
                "mode": "realtime",
                "theme": "river",
                "ghost_source": "none",
                "use_mock_devices": True,
            },
        )
        assert response.status_code == 400
        assert "two players" in response.json()["detail"].lower()


def test_status_endpoint_stays_responsive_when_discovery_blocks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _slow_discovery(*_args, **_kwargs):
        time.sleep(5)
        return []

    monkeypatch.setattr("backend.api.routes.discover_pm3_ports", _slow_discovery)
    monkeypatch.setattr("backend.api.routes.discover_pm3_hid_devices", _slow_discovery)
    monkeypatch.setattr("backend.api.routes.discover_pm3_usb_devices", _slow_discovery)

    with create_test_client(tmp_path) as client:
        started = time.monotonic()
        response = client.get("/api/status")
        elapsed = time.monotonic() - started

    assert response.status_code == 200
    assert elapsed < 3.0