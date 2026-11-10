"""Generate synthetic pilot data for pipeline development.

The generator is deliberately explicit: it creates the same columns as the
researcher export, including the analysis-only keys, so every downstream script
can be tested before real data exist. It is not a substitute for the pilot.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import schema

TASK_TYPES = ["identify_bug", "check_spec", "select_impl"]
DIFFICULTIES = ["low", "medium", "high"]


def _key(answer: dict[str, Any]) -> str:
    return json.dumps(answer, sort_keys=True, separators=(",", ":"))


def _canonical(task_type: str) -> dict[str, Any]:
    if task_type == "identify_bug":
        return {"has_bug": True, "line": 3}
    if task_type == "check_spec":
        return {"compliant": False}
    return {"candidate": "B"}


def _wrong(task_type: str, variant: int = 0) -> dict[str, Any]:
    if task_type == "identify_bug":
        if variant % 2 == 0:
            return {"has_bug": True, "line": 4}
        return {"has_bug": False, "line": None}
    if task_type == "check_spec":
        return {"compliant": True}
    return {"candidate": "A" if variant % 2 == 0 else "C"}


def build_tasks() -> list[dict[str, Any]]:
    """18 tasks: six per type, three correct and three incorrect per type.

    Each condition receives one correct and one incorrect task per type.
    """
    tasks: list[dict[str, Any]] = []
    task_number = 1
    for task_type in TASK_TYPES:
        for pair in range(3):
            for correct in (True, False):
                tasks.append(
                    {
                        "task_id": f"T{task_number:02d}",
                        "task_type": task_type,
                        "difficulty": DIFFICULTIES[pair],
                        "pair": pair,
                        "recommendation_correct": correct,
                        "canonical": _canonical(task_type),
                        "wrong": _wrong(task_type, pair),
                    }
                )
                task_number += 1
    return tasks


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + np.exp(-value))


def _confidence(rng: np.random.Generator, ability: float) -> int:
    if rng.random() < 0.5:
        value = rng.normal(36 + 7 * ability, 11)
    else:
        value = rng.normal(70 + 6 * ability, 11)
    return int(np.clip(round(value), 0, 100))


def _iso(base: datetime, seconds: float) -> str:
    return (base + timedelta(seconds=seconds)).isoformat(timespec="milliseconds")


def generate(
    *,
    n_participants: int = 60,
    tau: int = 50,
    seed: int = 20261021,
    cutoff_ms: int = 3000,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    tasks = build_tasks()
    rows: list[dict[str, Any]] = []
    start = datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc)

    for participant_index in range(n_participants):
        participant_code = f"SYN-{participant_index + 1:03d}"
        session_id = f"ses_syn_{participant_index + 1:04d}"
        ability = rng.normal(0, 0.9)
        speed = rng.normal(0, 0.22)
        session_start = start + timedelta(hours=participant_index * 1.5)

        # Rotate tasks across conditions so that tasks are crossed with
        # condition, as in the real counterbalanced design.
        rotation = participant_index % 3
        trial_index = 0
        for block_index, condition in enumerate(schema.CONDITIONS):
            block_tasks = [
                task
                for task in tasks
                if schema.CONDITIONS[(task["pair"] + rotation) % 3] == condition
            ]
            rng.shuffle(block_tasks)
            for task in block_tasks:
                task_type = task["task_type"]
                canonical = task["canonical"]
                wrong = task["wrong"]
                recommendation_correct = bool(task["recommendation_correct"])
                recommendation = canonical if recommendation_correct else wrong
                confidence = _confidence(rng, ability)

                difficulty_adjust = {"low": 0.35, "medium": 0.0, "high": -0.35}[
                    task["difficulty"]
                ]
                p_initial = _sigmoid(
                    0.55 * ability + (confidence - 50) / 28 + difficulty_adjust
                )
                initial_correct = bool(rng.random() < p_initial)
                initial = canonical if initial_correct else _wrong(
                    task_type, int(rng.integers(0, 2))
                )
                if condition == "none":
                    evidence_available = False
                    policy_decision = "not_applicable"
                elif condition == "static":
                    evidence_available = True
                    policy_decision = "always"
                else:
                    evidence_available = confidence < tau
                    policy_decision = "offered" if evidence_available else "withheld"

                if evidence_available:
                    examine_prob = 0.72 if condition == "adaptive" else 0.62
                    examined = bool(rng.random() < examine_prob)
                    if examined:
                        active_ms = int(
                            np.clip(rng.lognormal(np.log(6500), 0.55), cutoff_ms, 60000)
                        )
                        interactions = int(rng.integers(1, 5))
                    else:
                        active_ms = int(rng.uniform(0, cutoff_ms * 0.8))
                        interactions = 0
                else:
                    examined = False
                    active_ms = 0
                    interactions = 0

                # Adoption of the recommendation.
                if not evidence_available:
                    base_adopt = 0.20 if recommendation_correct else 0.12
                elif examined:
                    base_adopt = (0.60 if recommendation_correct else 0.38)
                    if condition == "static":
                        base_adopt -= 0.04
                else:
                    base_adopt = 0.22 if recommendation_correct else 0.14
                if condition == "adaptive" and not evidence_available:
                    base_adopt *= 0.6
                if confidence >= 70:
                    base_adopt *= 0.75
                elif confidence < 40:
                    base_adopt *= 1.2
                adopt = bool(rng.random() < float(np.clip(base_adopt, 0, 0.9)))

                if adopt:
                    final = recommendation
                elif rng.random() < 0.88:
                    final = initial
                else:
                    final = canonical if not initial_correct else _wrong(
                        task_type, int(rng.integers(0, 2))
                    )

                base_seconds = {"none": 21.0, "static": 30.0, "adaptive": 27.0}[
                    condition
                ]
                if examined:
                    base_seconds += 12.0
                if confidence >= 70:
                    base_seconds -= 3.0
                decision_seconds = float(
                    np.clip(
                        rng.lognormal(
                            np.log(max(6.0, base_seconds)) + speed, 0.42
                        ),
                        2.0,
                        240.0,
                    )
                )

                focus_lost_ms = 0
                max_blur_ms = 0
                if rng.random() < 0.08:
                    focus_lost_ms = int(rng.lognormal(np.log(3500), 0.9))
                    max_blur_ms = int(focus_lost_ms * rng.uniform(1.0, 1.8))
                excluded = focus_lost_ms > 10000 or max_blur_ms > 30000

                initial_key = _key(initial)
                final_key = _key(final)
                recommendation_key = _key(recommendation)
                a_neq_l = initial_key != recommendation_key
                final_equals_recommendation = final_key == recommendation_key
                influence = a_neq_l and final_equals_recommendation
                harmful_adoption = influence and not recommendation_correct
                missed_correction = (
                    a_neq_l and recommendation_correct and not final_equals_recommendation
                )

                shown_at = _iso(session_start, trial_index * 90 + 35)
                final_at = _iso(
                    session_start, trial_index * 90 + 35 + decision_seconds
                )
                rows.append(
                    {
                        "session_id": session_id,
                        "participant_code": participant_code,
                        "mode": "synthetic",
                        "sequence_id": f"SYN-R{rotation}-ABC",
                        "rotation": rotation,
                        "condition_order": "ABC",
                        "session_status": "completed",
                        "session_created_at": session_start.isoformat(),
                        "session_completed_at": _iso(session_start, 18 * 90 + 120),
                        "trial_index": trial_index,
                        "block_index": block_index,
                        "task_id": task["task_id"],
                        "task_type": task_type,
                        "difficulty": task["difficulty"],
                        "condition": condition,
                        "state": "final_submitted",
                        "initial_answer": json.dumps(initial, sort_keys=True),
                        "initial_key": initial_key,
                        "initial_correct": initial_correct,
                        "confidence": confidence,
                        "policy_decision": policy_decision,
                        "evidence_available": evidence_available,
                        "evidence_examined": examined,
                        "recommendation_answer": json.dumps(
                            recommendation, sort_keys=True
                        ),
                        "recommendation_key": recommendation_key,
                        "recommendation_correct": recommendation_correct,
                        "final_answer": json.dumps(final, sort_keys=True),
                        "final_key": final_key,
                        "final_correct": _key(final) == _key(canonical),
                        "answer_changed": initial_key != final_key,
                        "A_neq_L": a_neq_l,
                        "final_equals_recommendation": final_equals_recommendation,
                        "influence": influence,
                        "harmful_adoption": harmful_adoption,
                        "missed_correction": missed_correction,
                        "decision_time_ms": int(round(decision_seconds * 1000)),
                        "decision_time_s": round(decision_seconds, 3),
                        "evidence_active_ms": active_ms,
                        "evidence_active_s": round(active_ms / 1000.0, 3),
                        "focus_lost_ms": focus_lost_ms,
                        "max_blur_ms": max_blur_ms,
                        "interaction_count": interactions,
                        "excluded_from_timing": excluded,
                        "exclusion_reason": (
                            "cumulative_focus_loss"
                            if focus_lost_ms > 10000
                            else ("single_focus_loss" if max_blur_ms > 30000 else None)
                        ),
                        "started_at": _iso(session_start, trial_index * 90),
                        "recommendation_shown_at": shown_at,
                        "final_submitted_at": final_at,
                    }
                )
                trial_index += 1

    frame = pd.DataFrame(rows)
    frame["completed"] = frame["state"].eq("final_submitted")
    return frame


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="pilot/data/synthetic.csv")
    parser.add_argument("--participants", type=int, default=60)
    parser.add_argument("--tau", type=int, default=50)
    parser.add_argument("--seed", type=int, default=20261021)
    parser.add_argument("--cutoff-ms", type=int, default=3000)
    args = parser.parse_args()

    df = generate(
        n_participants=args.participants,
        tau=args.tau,
        seed=args.seed,
        cutoff_ms=args.cutoff_ms,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(json.dumps(schema.summary(df), indent=2))
    print(f"Wrote {len(df)} rows to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
