"""Load and validate the trial-level export used by the analysis scripts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

CONDITIONS = ["none", "static", "adaptive"]
TASK_TYPES = ["identify_bug", "check_spec", "select_impl"]

REQUIRED_COLUMNS = [
    "session_id",
    "participant_code",
    "condition",
    "trial_index",
    "task_id",
    "task_type",
    "confidence",
    "recommendation_correct",
    "initial_key",
    "final_key",
    "recommendation_key",
    "decision_time_ms",
    "state",
]

BOOL_COLUMNS = [
    "evidence_available",
    "evidence_examined",
    "recommendation_correct",
    "initial_correct",
    "final_correct",
    "answer_changed",
    "A_neq_L",
    "final_equals_recommendation",
    "influence",
    "harmful_adoption",
    "missed_correction",
    "excluded_from_timing",
]

NUMERIC_COLUMNS = [
    "trial_index",
    "block_index",
    "confidence",
    "decision_time_ms",
    "decision_time_s",
    "evidence_active_ms",
    "evidence_active_s",
    "focus_lost_ms",
    "max_blur_ms",
    "interaction_count",
    "rotation",
]


def _to_bool(value: Any) -> bool | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "1.0", "yes", "y"}:
        return True
    if text in {"false", "0", "0.0", "no", "n"}:
        return False
    return None


def _parse_json(value: Any) -> Any:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (dict, list)):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def load_trials(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Export not found: {path}")
    df = pd.read_csv(path)

    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Export is missing required columns: {missing}")

    for column in BOOL_COLUMNS:
        if column in df.columns:
            df[column] = df[column].map(_to_bool)
    for column in NUMERIC_COLUMNS:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    for column in ("initial_answer", "final_answer", "recommendation_answer"):
        if column in df.columns:
            df[column] = df[column].map(_parse_json)

    df["condition"] = pd.Categorical(df["condition"], categories=CONDITIONS, ordered=True)
    df["task_type"] = pd.Categorical(df["task_type"], categories=TASK_TYPES, ordered=True)
    df["participant_code"] = df["participant_code"].astype(str)
    df["session_id"] = df["session_id"].astype(str)
    df["task_id"] = df["task_id"].astype(str)
    df["completed"] = df["state"].eq("final_submitted")
    df["high_confidence"] = False  # replaced after tau is chosen
    return df


def analysis_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Completed trials with a final answer and a decision time."""
    out = df[df["completed"]].copy()
    out = out[out["final_key"].notna()]
    return out.reset_index(drop=True)


def add_tau(df: pd.DataFrame, tau: int) -> pd.DataFrame:
    out = df.copy()
    out["high_confidence"] = out["confidence"] >= tau
    return out


def validate(df: pd.DataFrame) -> list[str]:
    warnings: list[str] = []
    if df.empty:
        warnings.append("The export contains no trials.")
        return warnings

    conditions = set(df["condition"].dropna().astype(str))
    unknown = conditions - set(CONDITIONS)
    if unknown:
        warnings.append(f"Unknown conditions: {sorted(unknown)}")

    per_session = df.groupby("session_id")["condition"].nunique()
    if (per_session < 3).any():
        warnings.append(
            f"{int((per_session < 3).sum())} sessions do not contain all three conditions."
        )

    completed = df[df["completed"]]
    if not completed.empty:
        per_condition = completed.groupby(["session_id", "condition"], observed=True).size()
        if not per_condition.empty and per_condition.nunique() > 1:
            warnings.append("Condition block sizes are not constant across sessions.")

    duplicates = df.duplicated(subset=["session_id", "trial_index"]).sum()
    if duplicates:
        warnings.append(f"{int(duplicates)} duplicated session/trial rows.")

    missing_times = completed["decision_time_ms"].isna().sum()
    if missing_times:
        warnings.append(f"{int(missing_times)} completed trials have no decision time.")

    return warnings


def summary(df: pd.DataFrame) -> dict[str, Any]:
    completed = df[df["completed"]]
    return {
        "n_rows": int(len(df)),
        "n_completed_trials": int(len(completed)),
        "n_sessions": int(df["session_id"].nunique()),
        "n_participants": int(df["participant_code"].nunique()),
        "conditions": {
            condition: int((completed["condition"] == condition).sum())
            for condition in CONDITIONS
        },
        "task_types": {
            task_type: int((completed["task_type"] == task_type).sum())
            for task_type in TASK_TYPES
        },
        "recommendation_accuracy": float(completed["recommendation_correct"].mean())
        if len(completed)
        else None,
        "initial_accuracy": float(completed["initial_correct"].mean())
        if "initial_correct" in completed and len(completed)
        else None,
        "final_accuracy": float(completed["final_correct"].mean())
        if "final_correct" in completed and len(completed)
        else None,
    }
