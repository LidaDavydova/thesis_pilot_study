"""Precision simulation for the main experiment sample size.

This is a planning approximation. It simulates participant and task random
effects, analyses participant-level condition contrasts, and reports the
one-sided 95% precision and power for non-inferiority (accuracy) and superiority
(decision time). The main analysis will use the pre-specified mixed models.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import t as t_dist

from . import variance_components

DEFAULT_GRID = [40, 60, 80, 100, 120]


def _t_crit(n: int, alpha: float = 0.05) -> float:
    return float(t_dist.ppf(1 - alpha, max(n - 1, 1)))


def load_settings(components: dict[str, Any] | None) -> dict[str, Any]:
    defaults = variance_components.defaults()
    if not components:
        return defaults
    accuracy = components.get("accuracy", {})
    timing = components.get("timing", {})
    acc_vc = accuracy.get("variance_components") or defaults["accuracy"]["variance_components"]
    time_vc = timing.get("variance_components") or defaults["timing"]["variance_components"]
    return {
        "accuracy": {
            "variance_components": acc_vc,
            "baseline_accuracy": accuracy.get("baseline_accuracy", 0.70),
        },
        "timing": {
            "variance_components": time_vc,
            "median_seconds_static": timing.get("median_seconds_static", 30.0),
        },
    }


def simulate_once(
    rng: np.random.Generator,
    *,
    n_participants: int,
    settings: dict[str, Any],
    accuracy_effect: float,
    timing_log_effect: float,
) -> dict[str, float]:
    acc_vc = settings["accuracy"]["variance_components"]
    time_vc = settings["timing"]["variance_components"]
    base = float(settings["accuracy"]["baseline_accuracy"])
    median = float(settings["timing"]["median_seconds_static"])

    n_tasks = 18
    task_accuracy = rng.normal(0, acc_vc["task_sd"], n_tasks)
    task_timing = rng.normal(0, time_vc["task_sd"], n_tasks)
    condition_index = np.array([0] * 6 + [1] * 6 + [2] * 6)  # none, static, adaptive
    is_adaptive = condition_index == 2
    is_static = condition_index == 1

    acc_diffs: list[float] = []
    time_diffs: list[float] = []
    for _ in range(n_participants):
        participant_accuracy = rng.normal(0, acc_vc["participant_sd"])
        participant_timing = rng.normal(0, time_vc["participant_sd"])

        p = np.clip(
            base
            + participant_accuracy
            + task_accuracy
            + accuracy_effect * is_adaptive,
            0.02,
            0.98,
        )
        correct = rng.random(n_tasks) < p

        log_time = (
            np.log(median)
            + participant_timing
            + task_timing
            + timing_log_effect * is_adaptive
            + rng.normal(0, time_vc["residual_sd"], n_tasks)
        )
        # The analysis uses participant-level means of log time.
        acc_diffs.append(
            float(correct[is_adaptive].mean() - correct[is_static].mean())
        )
        time_diffs.append(
            float(log_time[is_adaptive].mean() - log_time[is_static].mean())
        )

    acc = np.asarray(acc_diffs)
    tim = np.asarray(time_diffs)
    return {
        "accuracy_diff": float(acc.mean()),
        "accuracy_se": float(acc.std(ddof=1) / math.sqrt(len(acc))),
        "timing_log_ratio": float(tim.mean()),
        "timing_se": float(tim.std(ddof=1) / math.sqrt(len(tim))),
    }


def run(
    *,
    components: dict[str, Any] | None = None,
    grid: list[int] | None = None,
    n_sim: int = 500,
    delta: float = 0.10,
    timing_target: float = 0.75,
    power_target: float = 0.80,
    seed: int = 20261021,
) -> dict[str, Any]:
    grid = grid or DEFAULT_GRID
    settings = load_settings(components)
    rng = np.random.default_rng(seed)
    rows: list[dict[str, Any]] = []

    for n in grid:
        accuracy_lower: list[float] = []
        accuracy_half: list[float] = []
        timing_upper: list[float] = []
        timing_ratio: list[float] = []
        for _ in range(n_sim):
            result = simulate_once(
                rng,
                n_participants=n,
                settings=settings,
                accuracy_effect=0.0,
                timing_log_effect=math.log(timing_target),
            )
            critical = _t_crit(n)
            accuracy_lower.append(
                result["accuracy_diff"] - critical * result["accuracy_se"]
            )
            accuracy_half.append(critical * result["accuracy_se"])
            timing_upper.append(
                result["timing_log_ratio"] + critical * result["timing_se"]
            )
            timing_ratio.append(math.exp(result["timing_log_ratio"]))

        rows.append(
            {
                "n": n,
                "accuracy_mean_diff": float(np.mean(accuracy_lower) + np.mean(accuracy_half)),
                "accuracy_mean_half_width": float(np.mean(accuracy_half)),
                "accuracy_power": float(np.mean(np.asarray(accuracy_lower) > -delta)),
                "timing_mean_ratio": float(np.mean(timing_ratio)),
                "timing_power": float(
                    np.mean(np.asarray(timing_upper) < math.log(timing_target))
                ),
                "timing_mean_upper_log_ratio": float(np.mean(timing_upper)),
            }
        )

    def required(key: str) -> int | None:
        eligible = [row["n"] for row in rows if row[key] >= power_target]
        return min(eligible) if eligible else None

    return {
        "settings": settings,
        "n_sim": n_sim,
        "delta_accuracy": delta,
        "timing_target_ratio": timing_target,
        "power_target": power_target,
        "grid": rows,
        "required_n_accuracy": required("accuracy_power"),
        "required_n_timing": required("timing_power"),
        "note": (
            "Participant-level contrast simulation. Accuracy is a risk difference; "
            "timing is the adaptive/static ratio of geometric means. Task variance "
            "is included in the data-generating process."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--components", default=None)
    parser.add_argument("--out", default="pilot/data/calibration/precision.json")
    parser.add_argument("--n-sim", type=int, default=500)
    parser.add_argument("--delta", type=float, default=0.10)
    parser.add_argument("--timing-target", type=float, default=0.75)
    parser.add_argument("--power", type=float, default=0.80)
    args = parser.parse_args()

    components = None
    if args.components:
        components = json.loads(Path(args.components).read_text(encoding="utf-8"))

    result = run(
        components=components,
        n_sim=args.n_sim,
        delta=args.delta,
        timing_target=args.timing_target,
        power_target=args.power,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
