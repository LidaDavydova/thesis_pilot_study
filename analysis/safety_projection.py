"""Project the high-confidence blind-spot safety target.

The target is at least 40 high-confidence trials with an incorrect
recommendation and A != L in each of the adaptive and static conditions. The
pilot estimate p_hat is the corresponding per-trial probability; at N=60 each
condition contributes 6*N trials.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from . import schema

TARGET = 40
TRIALS_PER_CONDITION = 6
DEFAULT_N = 60


def wilson_interval(k: int, n: int, z: float = 1.2816) -> tuple[float, float]:
    """Wilson interval; z=1.2816 gives an 80% two-sided interval."""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    half = (
        z
        * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
        / denominator
    )
    return max(0.0, center - half), min(1.0, center + half)


def _condition_projection(
    data: pd.DataFrame,
    condition: str,
    *,
    tau: int,
    target: int,
    trials_per_condition: int,
    n_target: int,
) -> dict[str, Any]:
    subset = data[data["condition"] == condition]
    high = subset["confidence"] >= tau
    incorrect = subset["recommendation_correct"] == False  # noqa: E712
    a_neq_l = subset["A_neq_L"] == True  # noqa: E712
    eligible = high & incorrect & a_neq_l

    n = int(len(subset))
    k = int(eligible.sum())
    p_hat = k / n if n else float("nan")
    lower, upper = wilson_interval(k, n)
    expected = trials_per_condition * n_target * p_hat if n else float("nan")
    required_n = (
        math.ceil(target / (trials_per_condition * lower))
        if lower > 0
        else None
    )
    return {
        "condition": condition,
        "n_trials": n,
        "n_participants": int(subset["participant_code"].nunique()),
        "n_high_confidence": int(high.sum()),
        "n_high_confidence_incorrect": int((high & incorrect).sum()),
        "n_eligible": k,
        "p_hat": p_hat,
        "wilson_lower_80": lower,
        "wilson_upper_80": upper,
        "expected_at_n": expected,
        "n_target": n_target,
        "required_n_lower_bound": required_n,
        "target_met_by_point_estimate": bool(expected >= target),
        "target_met_by_lower_bound": bool(
            required_n is not None and required_n <= n_target
        ),
        "p_switch_given_high_incorrect": (
            float((a_neq_l & high & incorrect).sum() / (high & incorrect).sum())
            if (high & incorrect).sum()
            else None
        ),
    }


def project(
    df: pd.DataFrame,
    *,
    tau: int,
    target: int = TARGET,
    trials_per_condition: int = TRIALS_PER_CONDITION,
    n_target: int = DEFAULT_N,
) -> dict[str, Any]:
    data = schema.analysis_frame(df)
    conditions = {
        condition: _condition_projection(
            data,
            condition,
            tau=tau,
            target=target,
            trials_per_condition=trials_per_condition,
            n_target=n_target,
        )
        for condition in ("static", "adaptive")
    }

    high = data["confidence"] >= tau
    incorrect = data["recommendation_correct"] == False  # noqa: E712
    return {
        "tau": tau,
        "target": target,
        "trials_per_condition": trials_per_condition,
        "n_target": n_target,
        "conditions": conditions,
        "overall": {
            "n_trials": int(len(data)),
            "n_high_confidence": int(high.sum()),
            "p_high_confidence": float(high.mean()) if len(data) else None,
            "p_incorrect_given_high": (
                float((high & incorrect).sum() / high.sum()) if high.sum() else None
            ),
            "note": (
                "The design target is evaluated separately for adaptive and "
                "static. The point estimate and the 80% Wilson lower bound are "
                "both reported; the preregistration should use the lower bound "
                "for the required-N rule."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--tau", type=int, required=True)
    parser.add_argument("--out", default="pilot/data/calibration/safety.json")
    parser.add_argument("--target", type=int, default=TARGET)
    parser.add_argument("--n-target", type=int, default=DEFAULT_N)
    args = parser.parse_args()

    df = schema.load_trials(args.input)
    result = project(
        df,
        tau=args.tau,
        target=args.target,
        n_target=args.n_target,
    )
    result["warnings"] = schema.validate(df)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
