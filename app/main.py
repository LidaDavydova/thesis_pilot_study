"""FastAPI backend for the pilot experiment."""

from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import benchmark, conditions, config, db
from .schemas import (
    ConfidenceRating,
    FinalAnswer,
    InitialAnswer,
    SessionComplete,
    SessionCreate,
    TrialEvent,
)

app = FastAPI(title="Verification support pilot", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = config.PILOT_DIR / "app" / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_session(session_id: str) -> dict[str, Any]:
    session = db.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def _plan(session: dict[str, Any]) -> list[dict[str, Any]]:
    return json.loads(session["plan_json"])


def _task_map(include_drafts: bool = False) -> dict[str, dict[str, Any]]:
    return {
        task["id"]: task
        for task in benchmark.load_tasks(include_drafts=include_drafts)
    }


def _task_for_trial(
    session: dict[str, Any], trial_index: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    plan = _plan(session)
    if not 0 <= trial_index < len(plan):
        raise HTTPException(status_code=404, detail="Trial index out of range")
    entry = plan[trial_index]
    task = _task_map().get(entry["task_id"])
    if task is None:
        raise HTTPException(status_code=500, detail="Task missing from benchmark")
    return entry, task


def _next_trial_info(session: dict[str, Any], trial_index: int) -> dict[str, Any]:
    plan = _plan(session)
    next_index = trial_index + 1
    if next_index >= len(plan):
        return {
            "next_trial_index": None,
            "block_complete": True,
            "session_complete": True,
        }
    block_complete = plan[next_index]["block_index"] != plan[trial_index]["block_index"]
    return {
        "next_trial_index": next_index,
        "block_complete": block_complete,
        "session_complete": False,
    }


def _ms_since(timestamp: str | None) -> int:
    if not timestamp:
        return 0
    then = datetime.fromisoformat(timestamp)
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    return max(0, int((datetime.now(timezone.utc) - then).total_seconds() * 1000))


def _trial_view(
    session: dict[str, Any], trial: dict[str, Any], task: dict[str, Any]
) -> dict[str, Any]:
    state = trial["state"]
    view: dict[str, Any] = {
        "trial_index": trial["trial_index"],
        "total_trials": len(_plan(session)),
        "block_index": trial["block_index"],
        "state": state,
        "task": benchmark.public_task(task),
    }
    if state in {"initial_submitted", "recommendation_shown", "final_submitted"}:
        view["initial_answer"] = json.loads(trial["initial_answer_json"])
    if state in {"recommendation_shown", "final_submitted"}:
        view["confidence"] = trial["confidence"]
        view["recommendation"] = {
            "text": trial["recommendation_text"],
            "structured": json.loads(trial["recommendation_structured_json"]),
        }
        view["evidence_available"] = bool(trial["evidence_available"])
        view["evidence"] = (
            benchmark.public_evidence(task) if trial["evidence_available"] else []
        )
    if state == "final_submitted":
        view.update(_next_trial_info(session, trial["trial_index"]))
    return view


def _admin_guard(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    token: str | None = Query(default=None),
) -> None:
    if (x_admin_token or token) != config.ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid admin token")


# ---------------------------------------------------------------------------
# Participant API
# ---------------------------------------------------------------------------


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "experiment.html")


@app.get("/api/health")
def health() -> dict[str, Any]:
    tasks = benchmark.load_tasks()
    return {
        "status": "ok",
        "n_tasks": len(tasks),
        "tau": config.TAU,
        "examination_cutoff_ms": config.EXAMINATION_CUTOFF_MS,
    }


@app.post("/api/session")
def create_session(payload: SessionCreate) -> dict[str, Any]:
    db.init_db()
    tasks = benchmark.load_tasks()
    design = benchmark.load_design()

    if len(tasks) % 3 != 0:
        raise HTTPException(
            status_code=500,
            detail="The number of ready tasks must be divisible by three",
        )

    mode = payload.mode
    participant_code = (payload.participant_code or "").strip()
    if not participant_code:
        prefix = {"pilot": "P", "dry_run": "DRY", "demo": "DEMO"}.get(mode, "S")
        participant_code = f"{prefix}-{uuid.uuid4().hex[:8].upper()}"

    if db.get_session_by_code(participant_code) is not None:
        raise HTTPException(
            status_code=409, detail="Participant code already has a session"
        )

    sequence = conditions.assign_sequence(db.count_sessions(mode))
    session_id = f"ses_{uuid.uuid4().hex[:12]}"
    try:
        plan = conditions.build_plan(
            tasks,
            design,
            rotation=sequence["rotation"],
            order_code=sequence["condition_order"],
            session_id=session_id,
        )
    except conditions.DesignError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    db.create_session(
        session_id=session_id,
        participant_code=participant_code,
        mode=mode,
        sequence_id=sequence["sequence_id"],
        rotation=sequence["rotation"],
        condition_order=sequence["condition_order"],
        plan=plan,
    )

    return {
        "session_id": session_id,
        "participant_code": participant_code,
        "mode": mode,
        "sequence_id": sequence["sequence_id"],
        "total_trials": len(plan),
        "status": "created",
    }


@app.get("/api/session/{session_id}")
def session_status(session_id: str) -> dict[str, Any]:
    session = _require_session(session_id)
    trials = db.list_trials(session_id)
    completed = sum(1 for trial in trials if trial["state"] == "final_submitted")
    next_index = next(
        (trial["trial_index"] for trial in trials if trial["state"] != "final_submitted"),
        None,
    )
    return {
        "session_id": session_id,
        "participant_code": session["participant_code"],
        "mode": session["mode"],
        "status": session["status"],
        "total_trials": len(trials),
        "completed_trials": completed,
        "next_trial_index": next_index,
    }


@app.get("/api/session/{session_id}/trial/{trial_index}")
def get_trial(session_id: str, trial_index: int) -> dict[str, Any]:
    session = _require_session(session_id)
    trial = db.get_trial(session_id, trial_index)
    if trial is None:
        raise HTTPException(status_code=404, detail="Trial not found")
    entry, task = _task_for_trial(session, trial_index)
    if trial["state"] == "pending":
        db.update_trial(
            session_id,
            trial_index,
            state="task_shown",
            started_at=trial["started_at"] or db.now_iso(),
        )
        db.update_session(session_id, status="in_progress", started_at=db.now_iso())
        trial = db.get_trial(session_id, trial_index)
    return _trial_view(session, trial, task)


@app.post("/api/session/{session_id}/trial/{trial_index}/initial")
def submit_initial(
    session_id: str, trial_index: int, payload: InitialAnswer
) -> dict[str, Any]:
    session = _require_session(session_id)
    trial = db.get_trial(session_id, trial_index)
    if trial is None:
        raise HTTPException(status_code=404, detail="Trial not found")
    if trial["state"] not in {"pending", "task_shown"}:
        raise HTTPException(
            status_code=409,
            detail=f"Initial answer is not accepted in state {trial['state']}",
        )
    entry, task = _task_for_trial(session, trial_index)
    try:
        normalized = benchmark.normalize_answer(task, payload.answer)
    except benchmark.BenchmarkError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    db.update_trial(
        session_id,
        trial_index,
        state="initial_submitted",
        initial_answer_json=json.dumps(normalized),
        started_at=trial["started_at"] or db.now_iso(),
    )
    db.insert_event(
        session_id=session_id,
        trial_index=trial_index,
        event_type="initial_submitted",
        client_time_ms=None,
        payload={"answer": normalized},
    )
    return {"ok": True, "state": "initial_submitted"}


@app.post("/api/session/{session_id}/trial/{trial_index}/confidence")
def submit_confidence(
    session_id: str, trial_index: int, payload: ConfidenceRating
) -> dict[str, Any]:
    session = _require_session(session_id)
    trial = db.get_trial(session_id, trial_index)
    if trial is None:
        raise HTTPException(status_code=404, detail="Trial not found")
    if trial["state"] != "initial_submitted":
        raise HTTPException(
            status_code=409,
            detail=f"Confidence is not accepted in state {trial['state']}",
        )
    entry, task = _task_for_trial(session, trial_index)
    available, policy_decision = conditions.decide_evidence(
        entry["condition"], payload.confidence
    )
    recommendation = benchmark.public_recommendation(task)
    db.update_trial(
        session_id,
        trial_index,
        state="recommendation_shown",
        confidence=payload.confidence,
        policy_decision=policy_decision,
        evidence_available=int(available),
        recommendation_text=recommendation["text"],
        recommendation_structured_json=json.dumps(recommendation["structured"]),
        recommendation_correct=int(task["recommendation"]["correct"]),
        recommendation_shown_at=db.now_iso(),
    )
    db.insert_event(
        session_id=session_id,
        trial_index=trial_index,
        event_type="confidence_submitted",
        client_time_ms=None,
        payload={
            "confidence": payload.confidence,
            "policy_decision": policy_decision,
            "evidence_available": available,
        },
    )
    return {
        "ok": True,
        "state": "recommendation_shown",
        "recommendation": recommendation,
        "evidence_available": available,
        "evidence": benchmark.public_evidence(task) if available else [],
    }


@app.post("/api/session/{session_id}/trial/{trial_index}/event")
def log_event(
    session_id: str, trial_index: int, payload: TrialEvent
) -> dict[str, Any]:
    _require_session(session_id)
    if db.get_trial(session_id, trial_index) is None:
        raise HTTPException(status_code=404, detail="Trial not found")
    db.insert_event(
        session_id=session_id,
        trial_index=trial_index,
        event_type=payload.event_type,
        client_time_ms=payload.client_time_ms,
        payload=payload.payload,
    )
    if payload.event_type == "panel_interaction":
        trial = db.get_trial(session_id, trial_index)
        db.update_trial(
            session_id,
            trial_index,
            interaction_count=(trial.get("interaction_count") or 0) + 1,
        )
    return {"ok": True}


@app.post("/api/session/{session_id}/trial/{trial_index}/final")
def submit_final(
    session_id: str, trial_index: int, payload: FinalAnswer
) -> dict[str, Any]:
    session = _require_session(session_id)
    trial = db.get_trial(session_id, trial_index)
    if trial is None:
        raise HTTPException(status_code=404, detail="Trial not found")
    if trial["state"] == "final_submitted":
        result = _next_trial_info(session, trial_index)
        return {"ok": True, "state": "final_submitted", **result}
    if trial["state"] != "recommendation_shown":
        raise HTTPException(
            status_code=409,
            detail=f"Final answer is not accepted in state {trial['state']}",
        )

    entry, task = _task_for_trial(session, trial_index)
    try:
        normalized = benchmark.normalize_answer(task, payload.answer)
    except benchmark.BenchmarkError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    initial = json.loads(trial["initial_answer_json"])
    changed = benchmark.answer_key(normalized) != benchmark.answer_key(initial)

    server_interactions = db.count_events(session_id, trial_index, "panel_interaction")
    interaction_count = max(payload.interaction_count, server_interactions)
    examined = conditions.evidence_examined(
        evidence_available=bool(trial["evidence_available"]),
        evidence_active_ms=payload.evidence_active_ms,
        interaction_count=interaction_count,
    )
    excluded, reason = conditions.timing_exclusion(
        focus_lost_ms=payload.focus_lost_ms,
        max_blur_ms=payload.max_blur_ms,
    )
    decision_time_ms = _ms_since(
        trial["started_at"] or trial["recommendation_shown_at"]
    )

    db.update_trial(
        session_id,
        trial_index,
        state="final_submitted",
        final_answer_json=json.dumps(normalized),
        answer_changed=int(changed),
        decision_time_ms=decision_time_ms,
        evidence_active_ms=payload.evidence_active_ms,
        focus_lost_ms=payload.focus_lost_ms,
        max_blur_ms=payload.max_blur_ms,
        interaction_count=interaction_count,
        evidence_examined=int(examined),
        excluded_from_timing=int(excluded),
        exclusion_reason=reason,
        final_submitted_at=db.now_iso(),
    )
    db.insert_event(
        session_id=session_id,
        trial_index=trial_index,
        event_type="final_submitted",
        client_time_ms=None,
        payload={
            "answer": normalized,
            "answer_changed": changed,
            "decision_time_ms": decision_time_ms,
            "evidence_active_ms": payload.evidence_active_ms,
            "focus_lost_ms": payload.focus_lost_ms,
            "max_blur_ms": payload.max_blur_ms,
            "interaction_count": interaction_count,
            "evidence_examined": examined,
            "excluded_from_timing": excluded,
        },
    )
    result = _next_trial_info(session, trial_index)
    if result["session_complete"]:
        db.update_session(session_id, status="awaiting_completion")
    return {"ok": True, "state": "final_submitted", **result}


@app.post("/api/session/{session_id}/complete")
def complete_session(session_id: str, payload: SessionComplete) -> dict[str, Any]:
    session = _require_session(session_id)
    trials = db.list_trials(session_id)
    if any(trial["state"] != "final_submitted" for trial in trials):
        raise HTTPException(
            status_code=409, detail="Cannot complete: not all trials are submitted"
        )
    db.update_session(
        session_id,
        status="completed",
        completed_at=db.now_iso(),
        questionnaire_json=json.dumps(payload.questionnaire),
    )
    db.insert_event(
        session_id=session_id,
        trial_index=None,
        event_type="session_completed",
        client_time_ms=None,
        payload=payload.questionnaire,
    )
    return {"ok": True, "status": "completed", "session_id": session["session_id"]}


# ---------------------------------------------------------------------------
# Researcher API
# ---------------------------------------------------------------------------


def _export_records() -> list[dict[str, Any]]:
    tasks = _task_map(include_drafts=True)
    records: list[dict[str, Any]] = []
    for row in db.export_rows():
        task = tasks.get(row["task_id"], {})
        initial = json.loads(row["initial_answer_json"]) if row["initial_answer_json"] else None
        final = json.loads(row["final_answer_json"]) if row["final_answer_json"] else None
        recommendation = (
            json.loads(row["recommendation_structured_json"])
            if row["recommendation_structured_json"]
            else None
        )
        initial_key = benchmark.answer_key(initial) if initial is not None else None
        final_key = benchmark.answer_key(final) if final is not None else None
        recommendation_key = (
            benchmark.answer_key(recommendation) if recommendation is not None else None
        )
        initial_correct = (
            benchmark.is_correct(task, initial)
            if initial is not None and task
            else None
        )
        final_correct = (
            benchmark.is_correct(task, final) if final is not None and task else None
        )
        a_neq_l = (
            initial_key != recommendation_key
            if initial_key is not None and recommendation_key is not None
            else None
        )
        final_equals_recommendation = (
            final_key == recommendation_key
            if final_key is not None and recommendation_key is not None
            else None
        )
        influence = (
            bool(a_neq_l and final_equals_recommendation)
            if a_neq_l is not None and final_equals_recommendation is not None
            else None
        )
        harmful_adoption = (
            bool(
                influence
                and row["recommendation_correct"] == 0
            )
            if influence is not None and row["recommendation_correct"] is not None
            else None
        )
        missed_correction = (
            bool(
                a_neq_l
                and row["recommendation_correct"] == 1
                and final_key != recommendation_key
            )
            if a_neq_l is not None
            and row["recommendation_correct"] is not None
            and final_key is not None
            and recommendation_key is not None
            else None
        )
        record = {
            **row,
            "task_type": task.get("type"),
            "difficulty": task.get("difficulty"),
            "initial_answer": json.dumps(initial, sort_keys=True) if initial else None,
            "final_answer": json.dumps(final, sort_keys=True) if final else None,
            "recommendation_answer": (
                json.dumps(recommendation, sort_keys=True) if recommendation else None
            ),
            "initial_key": initial_key,
            "final_key": final_key,
            "recommendation_key": recommendation_key,
            "initial_correct": initial_correct,
            "final_correct": final_correct,
            "A_neq_L": a_neq_l,
            "final_equals_recommendation": final_equals_recommendation,
            "influence": influence,
            "harmful_adoption": harmful_adoption,
            "missed_correction": missed_correction,
            "decision_time_s": (
                row["decision_time_ms"] / 1000.0
                if row["decision_time_ms"] is not None
                else None
            ),
            "evidence_active_s": (
                row["evidence_active_ms"] / 1000.0
                if row["evidence_active_ms"] is not None
                else None
            ),
        }
        records.append(record)
    return records


CSV_COLUMNS = [
    "session_id",
    "participant_code",
    "mode",
    "sequence_id",
    "rotation",
    "condition_order",
    "session_status",
    "session_created_at",
    "session_completed_at",
    "trial_index",
    "block_index",
    "task_id",
    "task_type",
    "difficulty",
    "condition",
    "state",
    "initial_answer",
    "initial_key",
    "initial_correct",
    "confidence",
    "policy_decision",
    "evidence_available",
    "evidence_examined",
    "recommendation_answer",
    "recommendation_key",
    "recommendation_correct",
    "final_answer",
    "final_key",
    "final_correct",
    "answer_changed",
    "A_neq_L",
    "final_equals_recommendation",
    "influence",
    "harmful_adoption",
    "missed_correction",
    "decision_time_ms",
    "decision_time_s",
    "evidence_active_ms",
    "evidence_active_s",
    "focus_lost_ms",
    "max_blur_ms",
    "interaction_count",
    "excluded_from_timing",
    "exclusion_reason",
    "started_at",
    "recommendation_shown_at",
    "final_submitted_at",
]


@app.get("/api/admin/export", dependencies=[Depends(_admin_guard)])
def export_data(format: str = Query(default="csv", pattern="^(csv|json)$")):
    records = _export_records()
    if format == "json":
        return {"records": records}
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for record in records:
        writer.writerow(
            {
                key: ("" if record.get(key) is None else record.get(key))
                for key in CSV_COLUMNS
            }
        )
    buffer.seek(0)
    filename = f"pilot_export_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/admin/sessions", dependencies=[Depends(_admin_guard)])
def admin_sessions() -> dict[str, Any]:
    sessions = []
    for session in db.list_sessions():
        trials = db.list_trials(session["session_id"])
        sessions.append(
            {
                "session_id": session["session_id"],
                "participant_code": session["participant_code"],
                "mode": session["mode"],
                "sequence_id": session["sequence_id"],
                "status": session["status"],
                "created_at": session["created_at"],
                "completed_at": session["completed_at"],
                "n_trials": len(trials),
                "n_completed": sum(
                    1 for trial in trials if trial["state"] == "final_submitted"
                ),
            }
        )
    return {"sessions": sessions}


@app.get("/api/admin/summary", dependencies=[Depends(_admin_guard)])
def admin_summary() -> dict[str, Any]:
    records = _export_records()
    return {
        "n_sessions": len({row["session_id"] for row in records}),
        "n_trials": len(records),
        "n_completed_trials": sum(
            1 for row in records if row["state"] == "final_submitted"
        ),
        "n_completed_sessions": len(
            {
                row["session_id"]
                for row in records
                if row["session_status"] == "completed"
            }
        ),
    }
