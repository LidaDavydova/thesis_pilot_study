"""Calibrate the adaptive threshold tau from pilot confidence ratings.

The rule is fixed in advance: keep the escalation share S(tau) inside
[0.40, 0.60], require both branches for at least 80% of participants, and pick
the candidate closest to S = 0.50, with ties going to the lower tau.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import schema

DEFAULT_GRID = list(range(20, 81))


def escalation_table(
    df: pd.DataFrame, taus: list[int] | None = None, n_target: int = 60
) -> pd.DataFrame:
    taus = taus or DEFAULT_GRID
    data = schema.analysis_frame(df)
    rows: list[dict[str, Any]] = []
    participants = data["participant_code"].nunique()

    for tau in taus:
        low = data["confidence"] < tau
        per_participant = (
            data.assign(low=low)
            .groupby("participant_code", observed=True)["low"]
            .mean()
        )
        both = ((per_participant > 0) & (per_participant < 1)).mean()
        high = data["confidence"] >= tau

        row: dict[str, Any] = {
            "tau": tau,
            "escalation_share": float(low.mean()),
            "both_branch_fraction": float(both),
            "n_participants": int(participants),
            "n_trials": int(len(data)),
            "n_high_confidence": int(high.sum()),
        }
        for condition in ("static", "adaptive"):
            subset = data[data["condition"] == condition]
            eligible = (
                (subset["confidence"] >= tau)
                & (subset["recommendation_correct"] == False)  # noqa: E712
                & (subset["A_neq_L"] == True)  # noqa: E712
            )
            p_hat = float(eligible.mean()) if len(subset) else float("nan")
            row[f"n_high_conf_incorrect_AneqL_{condition}"] = int(eligible.sum())
            row[f"p_hat_{condition}"] = p_hat
            row[f"projected_{condition}_at_{n_target}"] = (
                6 * n_target * p_hat if not np.isnan(p_hat) else float("nan")
            )
        rows.append(row)
    return pd.DataFrame(rows)


def confidence_drift(df: pd.DataFrame) -> dict[str, Any]:
    data = schema.analysis_frame(df)
    by_block = data.groupby("block_index", observed=True)["confidence"].mean()
    values = {str(int(index)): round(float(value), 2) for index, value in by_block.items()}
    spread = float(by_block.max() - by_block.min()) if len(by_block) > 1 else 0.0
    return {
        "mean_by_block": values,
        "max_spread": round(spread, 2),
        "warning": spread > 10,
        "note": (
            "A spread above 10 points suggests confidence drifted across blocks; "
            "the protocol should pre-specify whether to use block 1 only."
            if spread > 10
            else "No large block drift detected."
        ),
    }


def choose_tau(
    df: pd.DataFrame,
    *,
    low: float = 0.40,
    high: float = 0.60,
    target: float = 0.50,
    min_both: float = 0.80,
    grid: list[int] | None = None,
) -> dict[str, Any]:
    table = escalation_table(df, grid)
    candidates = table[
        (table["escalation_share"] >= low)
        & (table["escalation_share"] <= high)
        & (table["both_branch_fraction"] >= min_both)
    ].copy()
    fallback = False
    if candidates.empty:
        fallback = True
        candidates = table.copy()
    candidates["distance"] = (candidates["escalation_share"] - target).abs()
    candidates = candidates.sort_values(["distance", "tau"], ascending=[True, True])
    chosen = candidates.iloc[0]
    return {
        "tau": int(chosen["tau"]),
        "escalation_share": float(chosen["escalation_share"]),
        "both_branch_fraction": float(chosen["both_branch_fraction"]),
        "rule_satisfied": not fallback,
        "fallback": fallback,
        "rule": {
            "escalation_range": [low, high],
            "target": target,
            "min_both_branch_fraction": min_both,
            "tie_break": "lower tau",
        },
        "table": table.to_dict(orient="records"),
    }


def plot_curve(table: pd.DataFrame, path: str | Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax1 = plt.subplots(figsize=(7.5, 4.5))
    ax1.plot(table["tau"], table["escalation_share"], color="#0f766e", label="S(tau)")
    ax1.axhspan(0.40, 0.60, color="#0f766e", alpha=0.10)
    ax1.axhline(0.50, color="#0f766e", linestyle=":", linewidth=1)
    ax1.set_xlabel("tau")
    ax1.set_ylabel("Share escalating (confidence < tau)")
    ax1.set_ylim(0, 1)

    ax2 = ax1.twinx()
    ax2.plot(
        table["tau"],
        table["both_branch_fraction"],
        color="#9a5b00",
        linestyle="--",
        label="Share with both branches",
    )
    ax2.set_ylabel("Both-branch fraction")
    ax2.set_ylim(0, 1.05)

    lines = ax1.get_lines()[:1] + ax2.get_lines()[:1]
    labels = [line.get_label() for line in lines]
    ax1.legend(lines, labels, loc="lower right", fontsize=8)
    fig.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", default="pilot/data/calibration/tau.json")
    parser.add_argument("--plot", default="pilot/data/calibration/tau.png")
    parser.add_argument("--target-n", type=int, default=60)
    args = parser.parse_args()

    df = schema.load_trials(args.input)
    warnings = schema.validate(df)
    result = choose_tau(df)
    result["confidence_drift"] = confidence_drift(df)
    result["n_target"] = args.target_n
    result["warnings"] = warnings

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    plot_curve(pd.DataFrame(result["table"]), args.plot)

    print(
        json.dumps(
            {key: result[key] for key in ("tau", "escalation_share", "both_branch_fraction", "rule_satisfied", "fallback")},
            indent=2,
        )
    )
    print(f"Wrote {out} and {args.plot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
