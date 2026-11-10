"""Counterbalancing, condition order, and the adaptive policy."""

from __future__ import annotations

import random
from typing import Any

from . import config


class DesignError(ValueError):
    """Raised when the benchmark design cannot be balanced."""


def assign_sequence(session_count: int) -> dict[str, Any]:
    """Return the next rotation group and condition order.

    The six sequences are the three rotations crossed with the two orderings
    ABC and CBA. They are assigned round-robin and repeat every six sessions.
    """
    rotation = session_count % 3
    order_code = "ABC" if (session_count // 3) % 2 == 0 else "CBA"
    return {
        "rotation": rotation,
        "condition_order": order_code,
        "sequence_id": f"R{rotation}-{order_code}",
    }


def build_plan(
    tasks: list[dict[str, Any]],
    design: dict[str, Any],
    *,
    rotation: int,
    order_code: str,
    session_id: str,
) -> list[dict[str, Any]]:
    """Assign tasks to conditions and order the three condition blocks.

    A task's base condition is rotated by ``(base + rotation) % 3`` so that,
    across the three rotations, every task appears once in every condition.
    Task order within a condition is shuffled with a session-specific seed.
    """
    if order_code not in config.ORDER_CODES:
        raise DesignError(f"Unknown condition order: {order_code}")

    base_assignment = design.get("base_assignment", {})
    grouped: dict[str, list[str]] = {condition: [] for condition in config.CONDITIONS}

    for task in tasks:
        task_id = task["id"]
        if task_id not in base_assignment:
            raise DesignError(
                f"{task_id} has no entry in design.json base_assignment"
            )
        base = int(base_assignment[task_id])
        condition = config.CONDITIONS[(base + rotation) % 3]
        grouped[condition].append(task_id)

    expected = len(tasks) // 3
    for condition, task_ids in grouped.items():
        if len(task_ids) != expected:
            raise DesignError(
                f"Condition {condition!r} has {len(task_ids)} tasks, "
                f"expected {expected} (n_tasks={len(tasks)})"
            )

    plan: list[dict[str, Any]] = []
    trial_index = 0
    for block_index, condition in enumerate(config.ORDER_CODES[order_code]):
        task_ids = grouped[condition]
        random.Random(f"{session_id}:{condition}").shuffle(task_ids)
        for task_id in task_ids:
            plan.append(
                {
                    "trial_index": trial_index,
                    "block_index": block_index,
                    "task_id": task_id,
                    "condition": condition,
                }
            )
            trial_index += 1

    return plan


def decide_evidence(
    condition: str, confidence: int, tau: int | None = None
) -> tuple[bool, str]:
    """Return (evidence_available, policy_decision)."""
    tau = config.TAU if tau is None else tau
    if condition == "none":
        return False, "not_applicable"
    if condition == "static":
        return True, "always"
    if condition == "adaptive":
        if confidence < tau:
            return True, "offered"
        return False, "withheld"
    raise DesignError(f"Unknown condition: {condition}")


def evidence_examined(
    *,
    evidence_available: bool,
    evidence_active_ms: int | None,
    interaction_count: int | None,
    cutoff_ms: int | None = None,
) -> bool:
    cutoff = config.EXAMINATION_CUTOFF_MS if cutoff_ms is None else cutoff_ms
    if not evidence_available:
        return False
    return bool((evidence_active_ms or 0) >= cutoff or (interaction_count or 0) > 0)


def timing_exclusion(
    *,
    focus_lost_ms: int | None,
    max_blur_ms: int | None,
    total_limit_ms: int | None = None,
    single_limit_ms: int | None = None,
) -> tuple[bool, str | None]:
    total_limit = config.FOCUS_TOTAL_MS if total_limit_ms is None else total_limit_ms
    single_limit = config.FOCUS_SINGLE_MS if single_limit_ms is None else single_limit_ms
    if (max_blur_ms or 0) > single_limit:
        return True, "single_focus_loss"
    if (focus_lost_ms or 0) > total_limit:
        return True, "cumulative_focus_loss"
    return False, None


def validate_design_balance(
    tasks: list[dict[str, Any]], design: dict[str, Any]
) -> list[str]:
    """Check the rotation balance and return human-readable warnings."""
    warnings: list[str] = []
    n_tasks = len(tasks)
    if n_tasks % 3 != 0:
        warnings.append(f"Task count {n_tasks} is not divisible by 3")

    task_by_id = {task["id"]: task for task in tasks}
    per_condition = n_tasks // 3

    for rotation in range(3):
        counts: dict[str, dict[str, int]] = {
            condition: {"tasks": 0, "correct": 0, "incorrect": 0}
            for condition in config.CONDITIONS
        }
        type_counts: dict[str, dict[str, int]] = {
            condition: {} for condition in config.CONDITIONS
        }
        for task in tasks:
            base = design.get("base_assignment", {}).get(task["id"])
            if base is None:
                warnings.append(f"{task['id']} is missing from design.json")
                continue
            condition = config.CONDITIONS[(int(base) + rotation) % 3]
            counts[condition]["tasks"] += 1
            if task["recommendation"]["correct"]:
                counts[condition]["correct"] += 1
            else:
                counts[condition]["incorrect"] += 1
            type_counts[condition][task["type"]] = (
                type_counts[condition].get(task["type"], 0) + 1
            )

        for condition, values in counts.items():
            if values["tasks"] != per_condition:
                warnings.append(
                    f"Rotation {rotation}, {condition}: {values['tasks']} tasks, "
                    f"expected {per_condition}"
                )
            if n_tasks % 6 == 0 and values["correct"] != per_condition // 2:
                warnings.append(
                    f"Rotation {rotation}, {condition}: {values['correct']} correct "
                    f"recommendations, expected {per_condition // 2}"
                )
            if n_tasks % 9 == 0:
                for task_type in ("identify_bug", "check_spec", "select_impl"):
                    expected_type = n_tasks // 9
                    if type_counts[condition].get(task_type, 0) != expected_type:
                        warnings.append(
                            f"Rotation {rotation}, {condition}: "
                            f"{type_counts[condition].get(task_type, 0)} {task_type} "
                            f"tasks, expected {expected_type}"
                        )

    # Every task must appear once in each condition across the three rotations.
    for task in tasks:
        base = design.get("base_assignment", {}).get(task["id"])
        if base is None:
            continue
        appearances = {config.CONDITIONS[(int(base) + r) % 3] for r in range(3)}
        if appearances != set(config.CONDITIONS):
            warnings.append(f"{task['id']} does not cover all three conditions")

    # Report the realised composition in the first rotation for the operator.
    for condition in config.CONDITIONS:
        ids = [
            task["id"]
            for task in tasks
            if config.CONDITIONS[
                (int(design["base_assignment"][task["id"]]) + 0) % 3
            ]
            == condition
        ]
        correct = sum(
            task_by_id[task_id]["recommendation"]["correct"] for task_id in ids
        )
        warnings.append(
            f"Rotation 0, {condition}: {len(ids)} tasks, "
            f"{correct} correct / {len(ids) - correct} incorrect ({', '.join(ids)})"
        )
    return warnings
