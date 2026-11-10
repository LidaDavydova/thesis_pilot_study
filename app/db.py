"""SQLite persistence for sessions, trials, and event logs."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from . import config


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class ClosingConnection(sqlite3.Connection):
    """Commit on successful exit, roll back on error, then close."""

    def __exit__(self, exc_type, exc, traceback):  # type: ignore[override]
        try:
            return super().__exit__(exc_type, exc, traceback)
        finally:
            self.close()


def connect() -> sqlite3.Connection:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(
        config.DB_PATH, timeout=30, factory=ClosingConnection
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    participant_code TEXT NOT NULL UNIQUE,
    mode TEXT NOT NULL DEFAULT 'pilot',
    sequence_id TEXT NOT NULL,
    rotation INTEGER NOT NULL,
    condition_order TEXT NOT NULL,
    plan_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    status TEXT NOT NULL DEFAULT 'created',
    questionnaire_json TEXT
);

CREATE TABLE IF NOT EXISTS trials (
    trial_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    trial_index INTEGER NOT NULL,
    block_index INTEGER NOT NULL,
    task_id TEXT NOT NULL,
    condition TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending',
    initial_answer_json TEXT,
    confidence INTEGER,
    policy_decision TEXT,
    evidence_available INTEGER,
    evidence_examined INTEGER,
    recommendation_text TEXT,
    recommendation_structured_json TEXT,
    recommendation_correct INTEGER,
    final_answer_json TEXT,
    answer_changed INTEGER,
    decision_time_ms INTEGER,
    evidence_active_ms INTEGER,
    focus_lost_ms INTEGER,
    max_blur_ms INTEGER,
    interaction_count INTEGER,
    started_at TEXT,
    recommendation_shown_at TEXT,
    final_submitted_at TEXT,
    excluded_from_timing INTEGER,
    exclusion_reason TEXT,
    UNIQUE(session_id, trial_index),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    trial_index INTEGER,
    event_type TEXT NOT NULL,
    client_time_ms REAL,
    server_time TEXT NOT NULL,
    payload_json TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_trials_session ON trials(session_id, trial_index);
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id, trial_index);
"""


TRIAL_FIELDS = {
    "state",
    "initial_answer_json",
    "confidence",
    "policy_decision",
    "evidence_available",
    "evidence_examined",
    "recommendation_text",
    "recommendation_structured_json",
    "recommendation_correct",
    "final_answer_json",
    "answer_changed",
    "decision_time_ms",
    "evidence_active_ms",
    "focus_lost_ms",
    "max_blur_ms",
    "interaction_count",
    "started_at",
    "recommendation_shown_at",
    "final_submitted_at",
    "excluded_from_timing",
    "exclusion_reason",
}


def init_db() -> None:
    with connect() as connection:
        connection.executescript(SCHEMA)


def count_sessions(mode: str | None = None) -> int:
    with connect() as connection:
        if mode is None:
            row = connection.execute("SELECT COUNT(*) AS n FROM sessions").fetchone()
        else:
            row = connection.execute(
                "SELECT COUNT(*) AS n FROM sessions WHERE mode = ?", (mode,)
            ).fetchone()
    return int(row["n"])


def create_session(
    *,
    session_id: str,
    participant_code: str,
    mode: str,
    sequence_id: str,
    rotation: int,
    condition_order: str,
    plan: list[dict[str, Any]],
) -> dict[str, Any]:
    created_at = now_iso()
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO sessions (
                session_id, participant_code, mode, sequence_id, rotation,
                condition_order, plan_json, created_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'created')
            """,
            (
                session_id,
                participant_code,
                mode,
                sequence_id,
                rotation,
                condition_order,
                json.dumps(plan),
                created_at,
            ),
        )
        for entry in plan:
            connection.execute(
                """
                INSERT INTO trials (
                    session_id, trial_index, block_index, task_id, condition, state
                ) VALUES (?, ?, ?, ?, ?, 'pending')
                """,
                (
                    session_id,
                    entry["trial_index"],
                    entry["block_index"],
                    entry["task_id"],
                    entry["condition"],
                ),
            )
    return get_session(session_id)


def get_session(session_id: str) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
    return dict(row) if row else None


def get_session_by_code(participant_code: str) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM sessions WHERE participant_code = ?", (participant_code,)
        ).fetchone()
    return dict(row) if row else None


def list_sessions() -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT * FROM sessions ORDER BY created_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def update_session(session_id: str, **fields: Any) -> None:
    allowed = {"status", "started_at", "completed_at", "questionnaire_json"}
    updates = {key: value for key, value in fields.items() if key in allowed}
    if not updates:
        return
    assignments = ", ".join(f"{key} = ?" for key in updates)
    values = list(updates.values()) + [session_id]
    with connect() as connection:
        connection.execute(
            f"UPDATE sessions SET {assignments} WHERE session_id = ?", values
        )


def get_trial(session_id: str, trial_index: int) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM trials WHERE session_id = ? AND trial_index = ?",
            (session_id, trial_index),
        ).fetchone()
    return dict(row) if row else None


def list_trials(session_id: str) -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT * FROM trials WHERE session_id = ? ORDER BY trial_index",
            (session_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def update_trial(session_id: str, trial_index: int, **fields: Any) -> None:
    updates = {key: value for key, value in fields.items() if key in TRIAL_FIELDS}
    if not updates:
        return
    assignments = ", ".join(f"{key} = ?" for key in updates)
    values = list(updates.values()) + [session_id, trial_index]
    with connect() as connection:
        connection.execute(
            f"UPDATE trials SET {assignments} WHERE session_id = ? AND trial_index = ?",
            values,
        )


def insert_event(
    *,
    session_id: str,
    trial_index: int | None,
    event_type: str,
    client_time_ms: float | None,
    payload: dict[str, Any] | None = None,
) -> None:
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO events (
                session_id, trial_index, event_type, client_time_ms,
                server_time, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                trial_index,
                event_type,
                client_time_ms,
                now_iso(),
                json.dumps(payload or {}),
            ),
        )


def count_events(session_id: str, trial_index: int, event_type: str) -> int:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS n FROM events
            WHERE session_id = ? AND trial_index = ? AND event_type = ?
            """,
            (session_id, trial_index, event_type),
        ).fetchone()
    return int(row["n"])


def export_rows() -> list[dict[str, Any]]:
    query = """
    SELECT
        s.session_id,
        s.participant_code,
        s.mode,
        s.sequence_id,
        s.rotation,
        s.condition_order,
        s.status AS session_status,
        s.created_at AS session_created_at,
        s.completed_at AS session_completed_at,
        t.trial_index,
        t.block_index,
        t.task_id,
        t.condition,
        t.state,
        t.initial_answer_json,
        t.confidence,
        t.policy_decision,
        t.evidence_available,
        t.evidence_examined,
        t.recommendation_text,
        t.recommendation_structured_json,
        t.recommendation_correct,
        t.final_answer_json,
        t.answer_changed,
        t.decision_time_ms,
        t.evidence_active_ms,
        t.focus_lost_ms,
        t.max_blur_ms,
        t.interaction_count,
        t.started_at,
        t.recommendation_shown_at,
        t.final_submitted_at,
        t.excluded_from_timing,
        t.exclusion_reason
    FROM trials t
    JOIN sessions s ON s.session_id = t.session_id
    ORDER BY s.created_at, t.trial_index
    """
    with connect() as connection:
        rows = connection.execute(query).fetchall()
    return [dict(row) for row in rows]
