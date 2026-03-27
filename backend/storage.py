from __future__ import annotations

from datetime import datetime
from pathlib import Path
from io import StringIO
import json
import sqlite3
import csv

from .models import HistoryResponse, LeaderboardEntry, RaceResult


class HistoryStore:
    def __init__(self, database_url: str) -> None:
        self.database_path = self._extract_sqlite_path(database_url)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @staticmethod
    def _extract_sqlite_path(database_url: str) -> Path:
        if database_url.startswith("sqlite:///"):
            return Path(database_url.removeprefix("sqlite:///"))
        raise ValueError("Only sqlite:/// paths are supported by the default store.")

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS race_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_name TEXT NOT NULL,
                    lane_id INTEGER NOT NULL,
                    race_id TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    distance_m INTEGER NOT NULL,
                    finish_time_s REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    bonus_points INTEGER NOT NULL DEFAULT 0,
                    achievements TEXT NOT NULL DEFAULT '[]'
                )
                """
            )

    def save_result(self, result: RaceResult) -> RaceResult:
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO race_results (
                    player_name, lane_id, race_id, mode, distance_m,
                    finish_time_s, created_at, bonus_points, achievements
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.player_name,
                    result.lane_id,
                    result.race_id,
                    result.mode,
                    result.distance_m,
                    result.finish_time_s,
                    result.created_at.isoformat(),
                    result.bonus_points,
                    json.dumps(result.achievements),
                ),
            )
        return result.model_copy(update={"id": cursor.lastrowid})

    def get_recent_results(self, limit: int = 20) -> list[RaceResult]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT id, player_name, lane_id, race_id, mode, distance_m,
                       finish_time_s, created_at, bonus_points, achievements
                FROM race_results
                ORDER BY datetime(created_at) DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_result(row) for row in rows]

    def get_top_results(self, distance_m: int | None = None, limit: int = 10) -> list[LeaderboardEntry]:
        query = """
            SELECT player_name, MIN(finish_time_s) AS best_time_s, distance_m,
                   MIN(created_at) AS achieved_at
            FROM race_results
        """
        parameters: tuple[object, ...]
        if distance_m is None:
            query += " GROUP BY player_name, distance_m ORDER BY best_time_s ASC LIMIT ?"
            parameters = (limit,)
        else:
            query += " WHERE distance_m = ? GROUP BY player_name, distance_m ORDER BY best_time_s ASC LIMIT ?"
            parameters = (distance_m, limit)

        with self._connection() as connection:
            rows = connection.execute(query, parameters).fetchall()

        return [
            LeaderboardEntry(
                player_name=row["player_name"],
                best_time_s=row["best_time_s"],
                distance_m=row["distance_m"],
                achieved_at=datetime.fromisoformat(row["achieved_at"]),
            )
            for row in rows
        ]

    def get_last_result(self, player_name: str, distance_m: int) -> RaceResult | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT id, player_name, lane_id, race_id, mode, distance_m,
                       finish_time_s, created_at, bonus_points, achievements
                FROM race_results
                WHERE player_name = ? AND distance_m = ?
                ORDER BY datetime(created_at) DESC
                LIMIT 1
                """,
                (player_name, distance_m),
            ).fetchone()
        return self._row_to_result(row) if row else None

    def get_personal_best(self, player_name: str, distance_m: int) -> RaceResult | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT id, player_name, lane_id, race_id, mode, distance_m,
                       finish_time_s, created_at, bonus_points, achievements
                FROM race_results
                WHERE player_name = ? AND distance_m = ?
                ORDER BY finish_time_s ASC
                LIMIT 1
                """,
                (player_name, distance_m),
            ).fetchone()
        return self._row_to_result(row) if row else None

    def history(self, distance_m: int | None = None) -> HistoryResponse:
        return HistoryResponse(
            top_results=self.get_top_results(distance_m=distance_m),
            recent_results=self.get_recent_results(),
        )

    def clear_history(self) -> None:
        with self._connection() as connection:
            connection.execute("DELETE FROM race_results")

    def export_results_csv(self, distance_m: int | None = None, player_name: str | None = None) -> str:
        query = """
            SELECT id, player_name, lane_id, race_id, mode, distance_m,
                   finish_time_s, created_at, bonus_points, achievements
            FROM race_results
        """
        conditions: list[str] = []
        parameters: list[object] = []

        if distance_m is not None:
            conditions.append("distance_m = ?")
            parameters.append(distance_m)
        if player_name:
            conditions.append("player_name = ?")
            parameters.append(player_name)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY datetime(created_at) DESC, id DESC"

        with self._connection() as connection:
            rows = connection.execute(query, tuple(parameters)).fetchall()

        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "id",
                "player_name",
                "lane_id",
                "race_id",
                "mode",
                "distance_m",
                "finish_time_s",
                "created_at",
                "bonus_points",
                "achievements",
            ]
        )

        for row in rows:
            writer.writerow(
                [
                    row["id"],
                    row["player_name"],
                    row["lane_id"],
                    row["race_id"],
                    row["mode"],
                    row["distance_m"],
                    row["finish_time_s"],
                    row["created_at"],
                    row["bonus_points"],
                    ";".join(json.loads(row["achievements"])),
                ]
            )

        return buffer.getvalue()

    def export_leaderboard_csv(self, distance_m: int | None = None, limit: int = 10) -> str:
        rows = self.get_top_results(distance_m=distance_m, limit=limit)

        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["rank", "player_name", "best_time_s", "distance_m", "achieved_at"])
        for index, row in enumerate(rows, start=1):
            writer.writerow(
                [
                    index,
                    row.player_name,
                    row.best_time_s,
                    row.distance_m,
                    row.achieved_at.isoformat(),
                ]
            )
        return buffer.getvalue()

    @staticmethod
    def _row_to_result(row: sqlite3.Row) -> RaceResult:
        return RaceResult(
            id=row["id"],
            player_name=row["player_name"],
            lane_id=row["lane_id"],
            race_id=row["race_id"],
            mode=row["mode"],
            distance_m=row["distance_m"],
            finish_time_s=row["finish_time_s"],
            created_at=datetime.fromisoformat(row["created_at"]),
            bonus_points=row["bonus_points"],
            achievements=json.loads(row["achievements"]),
        )