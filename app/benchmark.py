"""Benchmark loading, validation, public views, and scoring."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import config


class BenchmarkError(ValueError):
    """Raised when the benchmark is malformed or incomplete."""


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_design(path: Path | None = None) -> dict[str, Any]:
    path = path or config.DESIGN_PATH
    if not path.exists():
        raise BenchmarkError(f"Design file not found: {path}")
    design = _read_json(path)
    if "base_assignment" not in design:
        raise BenchmarkError("design.json is missing 'base_assignment'")
    return design


def load_tasks(include_drafts: bool = False) -> list[dict[str, Any]]:
    if not config.TASKS_DIR.exists():
        raise BenchmarkError(f"Tasks directory not found: {config.TASKS_DIR}")
    tasks: list[dict[str, Any]] = []
    for path in sorted(config.TASKS_DIR.glob("*.json")):
        task = _read_json(path)
        if not include_drafts and task.get("status") not in {"ready", "frozen"}:
            continue
        validate_task(task)
        tasks.append(task)
    if not tasks:
        raise BenchmarkError("No ready tasks found in the benchmark")
    return tasks


def line_count(code: str) -> int:
    return len(code.splitlines())


def validate_task(task: dict[str, Any]) -> None:
    required = [
        "id",
        "status",
        "type",
        "difficulty",
        "title",
        "prompt",
        "code",
        "response_schema",
        "canonical",
        "accepted_equivalence",
        "evidence",
        "recommendation",
        "annotations",
        "flags",
    ]
    missing = [key for key in required if key not in task]
    if missing:
        raise BenchmarkError(f"{task.get('id', '<unknown>')}: missing {missing}")

    task_type = task["type"]
    if task_type not in {"identify_bug", "check_spec", "select_impl"}:
        raise BenchmarkError(f"{task['id']}: unknown type {task_type!r}")

    canonical = task["canonical"]
    if not task["accepted_equivalence"]:
        raise BenchmarkError(f"{task['id']}: accepted_equivalence is empty")

    if task_type == "identify_bug":
        if not isinstance(canonical.get("has_bug"), bool):
            raise BenchmarkError(f"{task['id']}: canonical.has_bug must be boolean")
        if canonical["has_bug"]:
            line = canonical.get("line")
            if not isinstance(line, int) or not 1 <= line <= line_count(task["code"]):
                raise BenchmarkError(f"{task['id']}: canonical.line is invalid")
    elif task_type == "check_spec":
        if not isinstance(canonical.get("compliant"), bool):
            raise BenchmarkError(f"{task['id']}: canonical.compliant must be boolean")
    else:
        candidates = task.get("candidates") or []
        ids = [candidate.get("id") for candidate in candidates]
        if len(ids) < 2:
            raise BenchmarkError(f"{task['id']}: select_impl needs at least two candidates")
        if canonical.get("candidate") not in ids:
            raise BenchmarkError(f"{task['id']}: canonical candidate is not in candidates")

    recommendation = task["recommendation"]
    if not isinstance(recommendation.get("correct"), bool):
        raise BenchmarkError(f"{task['id']}: recommendation.correct must be boolean")
    # The structured recommendation must be a valid answer in the task space.
    normalize_answer(task, recommendation["structured"])


def public_task(task: dict[str, Any]) -> dict[str, Any]:
    """The participant-facing part of a task.

    Correctness labels, accepted answers, and annotation metadata are removed.
    """
    view: dict[str, Any] = {
        "id": task["id"],
        "type": task["type"],
        "difficulty": task["difficulty"],
        "title": task["title"],
        "prompt": task["prompt"],
        "code": task["code"],
        "line_count": line_count(task["code"]),
        "response_schema": task["response_schema"],
    }
    if task["type"] == "select_impl":
        view["candidates"] = [
            {"id": candidate["id"], "code": candidate["code"]}
            for candidate in task.get("candidates", [])
        ]
    return view


def public_recommendation(task: dict[str, Any]) -> dict[str, Any]:
    recommendation = task["recommendation"]
    return {
        "text": recommendation["text"],
        "structured": recommendation["structured"],
    }


def public_evidence(task: dict[str, Any]) -> list[dict[str, Any]]:
    """Evidence as shown to the participant.

    ``decisiveness`` is benchmark metadata and is intentionally omitted: the
    proposal records it for exploratory analysis but does not display it.
    """
    return [
        {
            "kind": item["kind"],
            "title": item["title"],
            "body": item["body"],
            "table": item.get("table"),
        }
        for item in task["evidence"]
    ]


def normalize_answer(task: dict[str, Any], answer: dict[str, Any]) -> dict[str, Any]:
    """Validate and canonicalise a structured answer."""
    if not isinstance(answer, dict):
        raise BenchmarkError("Answer must be an object")

    task_type = task["type"]
    if task_type == "identify_bug":
        has_bug = answer.get("has_bug")
        if not isinstance(has_bug, bool):
            raise BenchmarkError("has_bug must be a boolean")
        line = answer.get("line")
        if has_bug:
            if line is None or line == "":
                raise BenchmarkError("A line number is required when has_bug is true")
            try:
                line = int(line)
            except (TypeError, ValueError) as exc:
                raise BenchmarkError("line must be an integer") from exc
            if not 1 <= line <= line_count(task["code"]):
                raise BenchmarkError(
                    f"line must be between 1 and {line_count(task['code'])}"
                )
        else:
            line = None
        return {"has_bug": has_bug, "line": line}

    if task_type == "check_spec":
        compliant = answer.get("compliant")
        if not isinstance(compliant, bool):
            raise BenchmarkError("compliant must be a boolean")
        return {"compliant": compliant}

    candidate = answer.get("candidate")
    valid = {item["id"] for item in task.get("candidates", [])}
    if candidate not in valid:
        raise BenchmarkError("candidate must be one of the available options")
    return {"candidate": candidate}


def is_correct(task: dict[str, Any], normalized: dict[str, Any]) -> bool:
    for accepted in task["accepted_equivalence"]:
        if task["type"] == "identify_bug":
            if accepted.get("has_bug") != normalized.get("has_bug"):
                continue
            if not normalized.get("has_bug"):
                return True
            if accepted.get("line") == normalized.get("line"):
                return True
        elif task["type"] == "check_spec":
            if accepted.get("compliant") == normalized.get("compliant"):
                return True
        else:
            if accepted.get("candidate") == normalized.get("candidate"):
                return True
    return False


def answer_key(normalized: dict[str, Any]) -> str:
    """Stable comparison key for A/L/F equality."""
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def recommendation_key(task: dict[str, Any]) -> str:
    return answer_key(normalize_answer(task, task["recommendation"]["structured"]))


def benchmark_summary(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    by_type: dict[str, int] = {}
    by_difficulty: dict[str, int] = {}
    correct = 0
    for task in tasks:
        by_type[task["type"]] = by_type.get(task["type"], 0) + 1
        by_difficulty[task["difficulty"]] = by_difficulty.get(task["difficulty"], 0) + 1
        correct += int(task["recommendation"]["correct"])
    return {
        "n_tasks": len(tasks),
        "by_type": by_type,
        "by_difficulty": by_difficulty,
        "correct_recommendations": correct,
        "incorrect_recommendations": len(tasks) - correct,
    }
