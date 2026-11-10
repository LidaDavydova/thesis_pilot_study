"""Estimate variance components for the precision simulation.

The pilot models are linear probability models for final-answer accuracy and
log-linear models for decision time, each with participant and task random
intercepts. These are planning models; the main analysis will use the
pre-specified logistic and Gamma specifications with a participant bootstrap.
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from . import schema

REFERENCE = "static"


def _formula(outcome: str) -> str:
    return (
        f"{outcome} ~ C(condition, Treatment(reference='{REFERENCE}'))"
    )


def _fit_model(
    data: pd.DataFrame, outcome: str
) -> tuple[Any, str | None]:
    formula = _formula(outcome)
    try:
        model = smf.mixedlm(
            formula,
            data,
            groups=data["participant_code"],
            re_formula="1",
            vc_formula={"task_id": "0 + C(task_id)"},
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = model.fit(reml=True, method="lbfgs", maxiter=300)
        return result, None
    except Exception as exc:  # statsmodels raises several convergence errors
        try:
            model = smf.mixedlm(
                formula,
                data,
                groups=data["participant_code"],
                re_formula="1",
            )
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                result = model.fit(reml=True, method="lbfgs", maxiter=300)
            return result, f"Task random intercept dropped: {exc}"
        except Exception as exc2:
            return None, f"Model failed: {exc2}"


def _variance_components(result: Any) -> dict[str, float]:
    participant = float(result.cov_re.iloc[0, 0]) if result.cov_re.size else 0.0
    task = 0.0
    if getattr(result, "vcomp", None) is not None and len(result.vcomp):
        task = float(np.asarray(result.vcomp).ravel()[0])
    residual = float(result.scale)
    total = participant + task + residual
    return {
        "participant_variance": participant,
        "task_variance": task,
        "residual_variance": residual,
        "participant_sd": float(np.sqrt(max(participant, 0.0))),
        "task_sd": float(np.sqrt(max(task, 0.0))),
        "residual_sd": float(np.sqrt(max(residual, 0.0))),
        "icc_participant": participant / total if total else None,
        "icc_task": task / total if total else None,
    }


def _contrasts(result: Any, *, log_scale: bool = False) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for name, coefficient in result.fe_params.items():
        if "condition" not in name:
            continue
        condition = "none" if "[T.none]" in name else "adaptive" if "[T.adaptive]" in name else name
        se = float(result.bse[name])
        entry = {
            "coefficient": float(coefficient),
            "se": se,
            "z": float(coefficient / se) if se else None,
            "p_value": float(result.pvalues[name]),
            "ci95_low": float(coefficient - 1.96 * se),
            "ci95_high": float(coefficient + 1.96 * se),
        }
        if log_scale:
            entry.update(
                {
                    "ratio": float(np.exp(coefficient)),
                    "ratio_ci95_low": float(np.exp(coefficient - 1.96 * se)),
                    "ratio_ci95_high": float(np.exp(coefficient + 1.96 * se)),
                }
            )
        output[condition] = entry
    return output


def fit_accuracy(df: pd.DataFrame) -> dict[str, Any]:
    data = schema.analysis_frame(df)
    data = data[data["final_correct"].notna()].copy()
    data["final_correct"] = data["final_correct"].astype(int)
    result, note = _fit_model(data, "final_correct")
    if result is None:
        return {"status": "failed", "note": note}
    return {
        "status": "ok",
        "note": note,
        "n_trials": int(len(data)),
        "n_participants": int(data["participant_code"].nunique()),
        "n_tasks": int(data["task_id"].nunique()),
        "reference": REFERENCE,
        "contrasts": _contrasts(result),
        "variance_components": _variance_components(result),
    }


def fit_timing(df: pd.DataFrame) -> dict[str, Any]:
    data = schema.analysis_frame(df)
    data = data[
        (data["decision_time_s"] > 0)
        & (data["excluded_from_timing"] != True)  # noqa: E712
    ].copy()
    data["log_time"] = np.log(data["decision_time_s"])
    result, note = _fit_model(data, "log_time")
    if result is None:
        return {"status": "failed", "note": note}
    return {
        "status": "ok",
        "note": note,
        "n_trials": int(len(data)),
        "n_participants": int(data["participant_code"].nunique()),
        "n_tasks": int(data["task_id"].nunique()),
        "reference": REFERENCE,
        "contrasts": _contrasts(result, log_scale=True),
        "variance_components": _variance_components(result),
    }


def bootstrap_marginal_rd(
    df: pd.DataFrame, *, n_boot: int = 500, seed: int = 20261021
) -> dict[str, Any]:
    data = schema.analysis_frame(df)
    data = data[data["final_correct"].notna()].copy()
    rng = np.random.default_rng(seed)
    participants = data["participant_code"].unique()
    diffs: list[float] = []
    for _ in range(n_boot):
        sample = rng.choice(participants, size=len(participants), replace=True)
        pieces = [data[data["participant_code"] == code] for code in sample]
        boot = pd.concat(pieces, ignore_index=True)
        means = boot.groupby("condition", observed=True)["final_correct"].mean()
        if "adaptive" in means and "static" in means:
            diffs.append(float(means["adaptive"] - means["static"]))
    if not diffs:
        return {"status": "failed"}
    return {
        "status": "ok",
        "n_boot": len(diffs),
        "estimate": float(np.mean(diffs)),
        "ci95_low": float(np.quantile(diffs, 0.025)),
        "ci95_high": float(np.quantile(diffs, 0.975)),
        "note": "Participant-cluster bootstrap; exploratory planning quantity.",
    }


def defaults() -> dict[str, Any]:
    return {
        "accuracy": {
            "variance_components": {
                "participant_sd": 0.18,
                "task_sd": 0.10,
                "residual_sd": 0.30,
            },
            "baseline_accuracy": 0.70,
        },
        "timing": {
            "variance_components": {
                "participant_sd": 0.22,
                "task_sd": 0.10,
                "residual_sd": 0.42,
            },
            "median_seconds_static": 30.0,
        },
    }


def fit_all(df: pd.DataFrame, *, n_boot: int = 0) -> dict[str, Any]:
    result = {
        "accuracy": fit_accuracy(df),
        "timing": fit_timing(df),
        "defaults": defaults(),
    }
    if n_boot:
        result["bootstrap_marginal_rd"] = bootstrap_marginal_rd(df, n_boot=n_boot)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", default="pilot/data/calibration/variance_components.json")
    parser.add_argument("--boot", type=int, default=0)
    args = parser.parse_args()

    df = schema.load_trials(args.input)
    result = fit_all(df, n_boot=args.boot)
    result["warnings"] = schema.validate(df)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
