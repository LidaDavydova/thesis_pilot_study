"""Build the calibration report from a pilot export.

Usage:
    python -m pilot.analysis.report --input pilot/data/export.csv
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from . import (
    calibrate_examination,
    calibrate_tau,
    precision_simulation,
    safety_projection,
    schema,
    variance_components,
)


def _table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    if not rows:
        return "_No rows._\n"
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"
    body = []
    for row in rows:
        values = []
        for column in columns:
            value = row.get(column)
            if isinstance(value, float):
                values.append(f"{value:.3f}")
            elif value is None:
                values.append("—")
            else:
                values.append(str(value))
        body.append("| " + " | ".join(values) + " |")
    return "\n".join([header, separator, *body]) + "\n"


def _safe_get(mapping: dict[str, Any], *keys: str, default: Any = None) -> Any:
    current: Any = mapping
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def build_report(
    df: pd.DataFrame,
    *,
    tau: int | None = None,
    n_sim: int = 500,
    n_target: int = 60,
) -> tuple[str, dict[str, Any]]:
    warnings = schema.validate(df)
    summary = schema.summary(df)
    data = schema.analysis_frame(df)

    tau_result = calibrate_tau.choose_tau(df)
    chosen_tau = int(tau if tau is not None else tau_result["tau"])
    drift = calibrate_tau.confidence_drift(df)

    examination = calibrate_examination.choose_cutoff(df)
    cutoff = float(examination["cutoff_s"])

    components = variance_components.fit_all(df, n_boot=0)
    safety = safety_projection.project(df, tau=chosen_tau, n_target=n_target)
    precision = precision_simulation.run(
        components=components,
        n_sim=n_sim,
    )

    required_ns = [
        condition["required_n_lower_bound"]
        for condition in safety["conditions"].values()
        if condition["required_n_lower_bound"] is not None
    ]
    n_main = max([n_target, *required_ns]) if required_ns else n_target

    preregistration = {
        "tau": chosen_tau,
        "examination_cutoff_s": cutoff,
        "focus_loss_cumulative_ms": 10000,
        "focus_loss_single_ms": 30000,
        "delta_accuracy_pp": 10,
        "n_main": n_main,
        "n_pilot_analysed": summary["n_participants"],
        "safety_target_per_arm": 40,
        "trials_per_condition": 6,
        "primary_outcomes": [
            "final answer accuracy, adaptive vs static, non-inferiority margin 10 pp",
            "total decision time, adaptive vs static, superiority",
        ],
    }

    lines: list[str] = []
    lines.append("# Pilot calibration report\n")
    lines.append(
        "This report is generated from the trial-level export. It is a "
        "calibration document, not a test of the main hypotheses.\n"
    )

    lines.append("## 1. Data\n")
    lines.append(
        f"- Analysed participants: **{summary['n_participants']}**\n"
        f"- Completed trials: **{summary['n_completed_trials']}**\n"
        f"- Sessions: **{summary['n_sessions']}**\n"
        f"- Recommendation accuracy in the benchmark: "
        f"**{summary['recommendation_accuracy']:.1%}**\n"
        f"- Initial accuracy: **{summary['initial_accuracy']:.1%}**\n"
        f"- Final accuracy: **{summary['final_accuracy']:.1%}**\n"
    )
    if warnings:
        lines.append("**Warnings**\n")
        for warning in warnings:
            lines.append(f"- {warning}")
        lines.append("")

    lines.append("## 2. Adaptive threshold tau\n")
    lines.append(
        f"- Chosen tau: **{chosen_tau}**\n"
        f"- Escalation share S(tau): **{tau_result['escalation_share']:.3f}**\n"
        f"- Participants with both branches: "
        f"**{tau_result['both_branch_fraction']:.1%}**\n"
        f"- Rule satisfied: **{tau_result['rule_satisfied']}**"
        + (" (fallback used)" if tau_result["fallback"] else "")
        + "\n"
    )
    lines.append(
        "Rule: S(tau) in [0.40, 0.60], both branches for at least 80% of "
        "participants, closest to S = 0.50, ties to the lower tau. The "
        "confidence–correctness association is not used to choose tau.\n"
    )
    tau_rows = [
        row
        for row in tau_result["table"]
        if 40 <= int(row["tau"]) <= 60 and int(row["tau"]) % 2 == 0
    ]
    lines.append(
        _table(
            tau_rows,
            [
                "tau",
                "escalation_share",
                "both_branch_fraction",
                "p_hat_static",
                "p_hat_adaptive",
            ],
        )
    )
    lines.append(
        f"Confidence drift across blocks: max spread "
        f"**{drift['max_spread']:.2f}** points. {drift['note']}\n"
    )

    lines.append("## 3. Evidence-examination cutoff\n")
    lines.append(
        f"- Chosen cutoff: **{cutoff:g} s**\n"
        f"- Method: **{examination['method']}**\n"
        f"- Available evidence trials: **{examination['n_available']}**\n"
        f"- Observed examination rate at cutoff: "
        f"**{examination.get('observed_rate_at_cutoff', float('nan')):.1%}**\n"
    )
    lines.append(
        "The cutoff is bounded to 2–5 s. A trial counts as examined if the "
        "panel is active and focused for at least the cutoff or the participant "
        "interacts with it.\n"
    )
    lines.append(
        _table(
            examination["sensitivity"],
            ["cutoff_s", "examined_fraction", "interaction_only_fraction"],
        )
    )

    lines.append("## 4. Variance components\n")
    for label, key in (("Final accuracy", "accuracy"), ("Decision time", "timing")):
        block = components[key]
        lines.append(f"### {label}\n")
        if block.get("status") != "ok":
            lines.append(f"Model did not converge: {block.get('note')}\n")
            continue
        vc = block["variance_components"]
        lines.append(
            f"- Participant SD: **{vc['participant_sd']:.3f}**\n"
            f"- Task SD: **{vc['task_sd']:.3f}**\n"
            f"- Residual SD: **{vc['residual_sd']:.3f}**\n"
            f"- ICC participant: **{vc['icc_participant']:.3f}**\n"
            f"- ICC task: **{vc['icc_task']:.3f}**\n"
        )
        contrast_rows = []
        for condition, contrast in block["contrasts"].items():
            row = {"condition": condition, **contrast}
            contrast_rows.append(row)
        columns = ["condition", "coefficient", "se", "p_value", "ci95_low", "ci95_high"]
        if key == "timing":
            columns.extend(["ratio", "ratio_ci95_low", "ratio_ci95_high"])
        lines.append(_table(contrast_rows, columns))
    lines.append(
        "These are planning models: a linear probability model for accuracy and "
        "a log-linear model for decision time, with participant and task random "
        "intercepts. The main analysis uses the pre-specified logistic and Gamma "
        "models with a participant bootstrap.\n"
    )

    lines.append("## 5. High-confidence blind-spot projection\n")
    safety_rows = list(safety["conditions"].values())
    lines.append(
        _table(
            safety_rows,
            [
                "condition",
                "n_trials",
                "n_high_confidence",
                "n_eligible",
                "p_hat",
                "wilson_lower_80",
                "expected_at_n",
                "required_n_lower_bound",
                "target_met_by_lower_bound",
            ],
        )
    )
    lines.append(
        f"Target: at least **{safety['target']}** high-confidence trials with an "
        "incorrect recommendation and A != L in each of the adaptive and static "
        "conditions at N = "
        f"**{safety['n_target']}**. Using the lower 80% Wilson bound, the "
        f"conservative main-sample size is **N_main = {n_main} participants**; "
        "each condition contributes 6 trials per participant.\n"
    )

    lines.append("## 6. Precision simulation\n")
    lines.append(
        f"Planning simulation with **{precision['n_sim']}** replications per row; "
        f"non-inferiority margin **{precision['delta_accuracy']:.0%}**; timing "
        f"target ratio **{precision['timing_target_ratio']:.2f}**.\n"
    )
    lines.append(
        _table(
            precision["grid"],
            [
                "n",
                "accuracy_mean_half_width",
                "accuracy_power",
                "timing_mean_ratio",
                "timing_power",
            ],
        )
    )
    lines.append(
        f"- Required N for accuracy power >= {precision['power_target']:.0%}: "
        f"**{precision['required_n_accuracy']}**\n"
        f"- Required N for timing power >= {precision['power_target']:.0%}: "
        f"**{precision['required_n_timing']}**\n"
        "- This is a participant-level planning approximation, not the main "
        "mixed-model analysis."
        "\n"
    )

    lines.append("## 7. Values to freeze in the preregistration\n")
    for key, value in preregistration.items():
        lines.append(f"- `{key}`: **{value}**")
    lines.append("")
    lines.append(
        "Freeze these values before the main experiment. Do not re-estimate tau, "
        "the examination cutoff, the focus-loss rule, the non-inferiority margin, "
        "or N from the main data.\n"
    )

    lines.append("## 8. Caveats\n")
    lines.append(
        "- The pilot is small; variance components and safety projections are "
        "uncertain.\n"
        "- The sample benchmark tasks in this repository are placeholders and "
        "must be replaced or reviewed before data collection.\n"
        "- The precision simulation is a planning approximation. The main "
        "analysis remains the pre-specified mixed-effects model.\n"
        "- If this report was generated from synthetic data, none of the values "
        "are empirical.\n"
    )

    report = "\n".join(lines)
    artifacts = {
        "summary": summary,
        "warnings": warnings,
        "tau": tau_result,
        "chosen_tau": chosen_tau,
        "examination": examination,
        "variance_components": components,
        "safety": safety,
        "precision": precision,
        "preregistration": preregistration,
    }
    return report, artifacts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--out-dir", default="pilot/data/report")
    parser.add_argument("--tau", type=int, default=None)
    parser.add_argument("--n-sim", type=int, default=500)
    parser.add_argument("--n-target", type=int, default=60)
    args = parser.parse_args()

    df = schema.load_trials(args.input)
    report, artifacts = build_report(
        df,
        tau=args.tau,
        n_sim=args.n_sim,
        n_target=args.n_target,
    )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "pilot-report.md").write_text(report, encoding="utf-8")
    (out_dir / "artifacts.json").write_text(
        json.dumps(artifacts, indent=2, default=str), encoding="utf-8"
    )

    calibrate_tau.plot_curve(
        pd.DataFrame(artifacts["tau"]["table"]), out_dir / "tau.png"
    )
    calibrate_examination.plot_dwell(
        df, artifacts["examination"]["cutoff_s"], out_dir / "examination.png"
    )

    print(f"Wrote {out_dir / 'pilot-report.md'}")
    print(f"Chosen tau: {artifacts['chosen_tau']}")
    print(f"N_main: {artifacts['preregistration']['n_main']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
