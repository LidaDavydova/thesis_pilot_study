"""Researcher dashboard for the pilot database.

Run from the repository root:
    streamlit run pilot/app/dashboard.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pilot.app import config  # noqa: E402

st.set_page_config(page_title="Pilot dashboard", layout="wide")
st.title("Pilot dashboard")

sidebar = st.sidebar
db_path = Path(sidebar.text_input("Database", value=str(config.DB_PATH)))
n_sim = sidebar.number_input("Precision simulations", min_value=20, max_value=1000, value=100, step=20)
sidebar.caption(
    "Read-only view. Use the FastAPI admin export for the analysis file."
)

if not db_path.exists():
    st.warning(
        f"Database not found: `{db_path}`. Initialise it with "
        "`python -m pilot.app.seed --init-db` and collect a session first."
    )
    st.stop()


@st.cache_data(ttl=10)
def read_tables(path: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    connection = sqlite3.connect(path)
    try:
        sessions = pd.read_sql_query("SELECT * FROM sessions ORDER BY created_at", connection)
        trials = pd.read_sql_query(
            "SELECT * FROM trials ORDER BY session_id, trial_index", connection
        )
        events = pd.read_sql_query("SELECT * FROM events ORDER BY event_id", connection)
    finally:
        connection.close()
    return sessions, trials, events


try:
    sessions, trials, events = read_tables(str(db_path))
except Exception as exc:  # noqa: BLE001
    st.error(f"Could not read the database: {exc}")
    st.stop()

for frame, columns in (
    (trials, ["evidence_available", "evidence_examined", "recommendation_correct", "answer_changed", "excluded_from_timing"]),
    (sessions, []),
):
    for column in columns:
        if column in frame.columns:
            frame[column] = frame[column].map(lambda value: bool(value) if pd.notna(value) else None)

overview, session_tab, trial_tab, calibration_tab = st.tabs(
    ["Overview", "Sessions", "Trials", "Calibration"]
)

with overview:
    completed_sessions = int((sessions["status"] == "completed").sum()) if len(sessions) else 0
    completed_trials = int((trials["state"] == "final_submitted").sum()) if len(trials) else 0
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Sessions", len(sessions))
    col2.metric("Completed sessions", completed_sessions)
    col3.metric("Completed trials", completed_trials)
    col4.metric("Event rows", len(events))

    if len(trials):
        shown = trials[trials["state"] == "final_submitted"]
        if len(shown):
            col1, col2, col3 = st.columns(3)
            col1.metric("Mean confidence", f"{shown['confidence'].mean():.1f}")
            col2.metric(
                "Recommendation accuracy",
                f"{shown['recommendation_correct'].mean():.1%}",
            )
            col3.metric(
                "Evidence examined",
                f"{shown['evidence_examined'].fillna(False).mean():.1%}",
            )
        st.subheader("Trials per condition")
        st.dataframe(
            trials.groupby("condition", dropna=False)
            .size()
            .rename("trials")
            .reset_index(),
            use_container_width=True,
            hide_index=True,
        )

with session_tab:
    st.subheader("Sessions")
    if len(sessions):
        display = sessions.copy()
        for column in ("plan_json", "questionnaire_json"):
            if column in display.columns:
                display = display.drop(columns=[column])
        st.dataframe(display, use_container_width=True, hide_index=True)
    else:
        st.info("No sessions yet.")

with trial_tab:
    st.subheader("Trials")
    if not len(trials):
        st.info("No trials yet.")
    else:
        condition = st.selectbox(
            "Condition", ["all", *sorted(trials["condition"].dropna().unique())]
        )
        state = st.selectbox("State", ["all", *sorted(trials["state"].dropna().unique())])
        view = trials.copy()
        if condition != "all":
            view = view[view["condition"] == condition]
        if state != "all":
            view = view[view["state"] == state]
        columns = [
            "session_id",
            "trial_index",
            "task_id",
            "condition",
            "state",
            "confidence",
            "evidence_available",
            "evidence_examined",
            "recommendation_correct",
            "decision_time_ms",
            "evidence_active_ms",
            "interaction_count",
        ]
        columns = [column for column in columns if column in view.columns]
        st.dataframe(view[columns], use_container_width=True, hide_index=True)

        selected = st.selectbox("Session", sorted(trials["session_id"].unique()))
        session_trials = trials[trials["session_id"] == selected]
        st.caption(f"Session {selected}: {len(session_trials)} trials")
        st.dataframe(session_trials, use_container_width=True, hide_index=True)

with calibration_tab:
    st.subheader("Calibration")
    st.caption(
        "Build the report from the current database, or load the latest artifacts."
    )
    if st.button("Build calibration report", type="primary"):
        try:
            from pilot.analysis import report, schema
            from pilot.app.main import _export_records

            records = _export_records()
            if not records:
                st.warning("No exportable trials yet.")
            else:
                export_path = config.DATA_DIR / "dashboard_export.csv"
                export_path.parent.mkdir(parents=True, exist_ok=True)
                pd.DataFrame(records).to_csv(export_path, index=False)
                frame = schema.load_trials(export_path)
                text, artifacts = report.build_report(
                    frame, n_sim=int(n_sim)
                )
                out_dir = config.DATA_DIR / "report"
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / "pilot-report.md").write_text(text, encoding="utf-8")
                (out_dir / "artifacts.json").write_text(
                    json.dumps(artifacts, indent=2, default=str), encoding="utf-8"
                )
                st.success(f"Wrote {out_dir / 'pilot-report.md'}")
                st.markdown(text)
        except Exception as exc:  # noqa: BLE001
            st.exception(exc)

    artifacts_path = config.DATA_DIR / "report" / "artifacts.json"
    if artifacts_path.exists():
        artifacts = json.loads(artifacts_path.read_text(encoding="utf-8"))
        col1, col2, col3 = st.columns(3)
        col1.metric("tau", artifacts.get("chosen_tau", "—"))
        col2.metric(
            "Examination cutoff (s)",
            f"{artifacts.get('examination', {}).get('cutoff_s', float('nan')):.2f}",
        )
        col3.metric(
            "N_main",
            artifacts.get("preregistration", {}).get("n_main", "—"),
        )
        st.subheader("Safety projection")
        safety = artifacts.get("safety", {}).get("conditions", {})
        st.dataframe(pd.DataFrame(safety).T, use_container_width=True)
        st.subheader("Precision simulation")
        st.dataframe(
            pd.DataFrame(artifacts.get("precision", {}).get("grid", [])),
            use_container_width=True,
            hide_index=True,
        )
        with st.expander("Full artifacts"):
            st.json(artifacts)
    else:
        st.info("No calibration artifacts yet.")
