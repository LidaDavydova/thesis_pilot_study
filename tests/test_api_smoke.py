"""End-to-end smoke test for the pilot API.

Run from the repository root:

    python pilot/tests/test_api_smoke.py

The test uses a temporary database and never touches ``pilot/data``.
It needs the application dependencies (FastAPI, httpx, uvicorn).
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TMP = Path(tempfile.mkdtemp(prefix="pilot-api-smoke-"))
os.environ["PILOT_DATA_DIR"] = str(TMP)
os.environ["PILOT_DB"] = str(TMP / "smoke.db")
os.environ["PILOT_ADMIN_TOKEN"] = "smoke-token"

from fastapi.testclient import TestClient  # noqa: E402

from pilot.app.main import app  # noqa: E402

ANSWERS = {
    "identify_bug": {"has_bug": False, "line": None},
    "check_spec": {"compliant": True},
    "select_impl": {"candidate": "A"},
}


def main() -> None:
    client = TestClient(app)
    assert client.get("/api/health").status_code == 200

    created = client.post(
        "/api/session",
        json={"participant_code": "SMOKE-1", "mode": "demo"},
    )
    assert created.status_code == 200, created.text
    body = created.json()
    session_id = body["session_id"]
    assert body["total_trials"] == 6

    for index in range(body["total_trials"]):
        trial = client.get(f"/api/session/{session_id}/trial/{index}")
        assert trial.status_code == 200, trial.text
        view = trial.json()
        answer = ANSWERS[view["task"]["type"]]
        time.sleep(0.005)

        initial = client.post(
            f"/api/session/{session_id}/trial/{index}/initial",
            json={"answer": answer},
        )
        assert initial.status_code == 200, initial.text

        confidence = client.post(
            f"/api/session/{session_id}/trial/{index}/confidence",
            json={"confidence": 35},
        )
        assert confidence.status_code == 200, confidence.text
        shown = confidence.json()
        if view["task"]["id"] == "T01":
            assert shown["evidence_available"] is False  # T01 is in `none` in R0
        if shown["evidence_available"]:
            event = client.post(
                f"/api/session/{session_id}/trial/{index}/event",
                json={
                    "event_type": "panel_interaction",
                    "payload": {"action": "scroll"},
                },
            )
            assert event.status_code == 200, event.text

        final = client.post(
            f"/api/session/{session_id}/trial/{index}/final",
            json={
                "answer": answer,
                "evidence_active_ms": 4000,
                "focus_lost_ms": 0,
                "max_blur_ms": 0,
                "interaction_count": 1,
            },
        )
        assert final.status_code == 200, final.text
        expected_next = index + 1 if index < 5 else None
        assert final.json()["next_trial_index"] == expected_next

    complete = client.post(
        f"/api/session/{session_id}/complete",
        json={"questionnaire": {"clarity": 4}},
    )
    assert complete.status_code == 200, complete.text

    headers = {"X-Admin-Token": "smoke-token"}
    exported = client.get(
        "/api/admin/export", params={"format": "json"}, headers=headers
    )
    assert exported.status_code == 200, exported.text
    records = exported.json()["records"]
    assert len(records) == 6
    for record in records:
        assert record["state"] == "final_submitted"
        assert record["decision_time_ms"] is not None
        assert record["decision_time_ms"] >= 0
        assert record["evidence_examined"] in (0, 1)

    assert client.get("/api/admin/summary", headers=headers).status_code == 200
    assert client.get("/api/admin/sessions", headers=headers).status_code == 200
    assert client.get("/api/admin/export").status_code == 401
    print("API smoke test passed")


if __name__ == "__main__":
    try:
        main()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
