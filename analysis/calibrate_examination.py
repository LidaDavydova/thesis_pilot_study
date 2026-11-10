"""Calibrate the evidence-examination dwell cutoff.

The cutoff is the number of seconds the verification panel must be active and
focused, or the participant must interact with it, for the trial to count as
evidence examination. The protocol bounds the value to 2-5 seconds.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks

from . import schema

DEFAULT_CUTOFF_S = 3.0
BOUNDS_S = (2.0, 5.0)


def dwell_frame(df: pd.DataFrame) -> pd.DataFrame:
    data = schema.analysis_frame(df)
    data = data[data["evidence_available"] == True].copy()  # noqa: E712
    data = data[data["evidence_active_ms"].notna()]
    data["dwell_s"] = data["evidence_active_ms"] / 1000.0
    return data


def choose_cutoff(
    df: pd.DataFrame,
    *,
    bounds: tuple[float, float] = BOUNDS_S,
    default: float = DEFAULT_CUTOFF_S,
) -> dict[str, Any]:
    data = dwell_frame(df)
    positive = data.loc[data["dwell_s"] > 0, "dwell_s"].to_numpy()
    low, high = bounds

    result: dict[str, Any] = {
        "cutoff_s": default,
        "method": "default",
        "n_available": int(len(data)),
        "n_positive_dwell": int(len(positive)),
        "bounds_s": [low, high],
        "default_s": default,
    }
    if len(positive) < 10:
        result["note"] = "Too few positive dwell observations; kept the default."
        return result

    max_time = float(min(60.0, max(high * 4, np.quantile(positive, 0.99))))
    bin_width = 0.25
    bins = np.arange(0, max_time + bin_width, bin_width)
    counts, edges = np.histogram(positive, bins=bins)
    centers = (edges[:-1] + edges[1:]) / 2
    density = gaussian_filter1d(counts.astype(float), sigma=1.2)

    # A trough between the short-glance and sustained-inspection modes appears
    # as a local minimum of the smoothed density. Pick the most prominent one
    # inside the allowed range.
    minima, properties = find_peaks(-density, prominence=0.2)
    candidates = [
        (centers[index], float(properties["prominences"][position]))
        for position, index in enumerate(minima)
        if low <= centers[index] <= high
    ]
    if candidates:
        cutoff, prominence = max(candidates, key=lambda item: item[1])
        result.update(
            {
                "cutoff_s": round(float(cutoff), 2),
                "method": "histogram_trough",
                "prominence": round(prominence, 3),
            }
        )
    else:
        result["note"] = "No clear trough inside the bounds; kept the default."

    available = schema.analysis_frame(df)
    available = available[available["evidence_available"] == True]  # noqa: E712
    result["observed_rate_at_cutoff"] = float(
        examination_rate(available, result["cutoff_s"]).mean()
    )
    result["sensitivity"] = sensitivity(df, bounds=(low, high))
    return result


def sensitivity(
    df: pd.DataFrame, bounds: tuple[float, float] = BOUNDS_S
) -> list[dict[str, Any]]:
    data = schema.analysis_frame(df)
    available = data[data["evidence_available"] == True]  # noqa: E712
    rows: list[dict[str, Any]] = []
    for cutoff in np.arange(bounds[0], bounds[1] + 0.01, 0.5):
        examined = (available["evidence_active_ms"] >= cutoff * 1000) | (
            available["interaction_count"] > 0
        )
        interaction_only = (available["evidence_active_ms"] < cutoff * 1000) & (
            available["interaction_count"] > 0
        )
        rows.append(
            {
                "cutoff_s": float(round(cutoff, 2)),
                "examined_fraction": float(examined.mean()) if len(available) else None,
                "interaction_only_fraction": (
                    float(interaction_only.mean()) if len(available) else None
                ),
                "n_available": int(len(available)),
            }
        )
    return rows


def examination_rate(df: pd.DataFrame, cutoff_s: float) -> pd.Series:
    available = df["evidence_available"] == True  # noqa: E712
    examined = (df["evidence_active_ms"] >= cutoff_s * 1000) | (
        df["interaction_count"] > 0
    )
    return available & examined


def plot_dwell(df: pd.DataFrame, cutoff_s: float, path: str | Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    data = dwell_frame(df)
    values = data["dwell_s"].clip(upper=30)
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    ax.hist(values, bins=np.arange(0, 30.5, 0.5), color="#0f766e", alpha=0.75)
    ax.axvline(cutoff_s, color="#a61b1b", linestyle="--", label=f"cutoff = {cutoff_s:g} s")
    ax.set_xlabel("Evidence panel active time (s, clipped at 30)")
    ax.set_ylabel("Trials")
    ax.legend()
    fig.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", default="pilot/data/calibration/examination.json")
    parser.add_argument("--plot", default="pilot/data/calibration/examination.png")
    args = parser.parse_args()

    df = schema.load_trials(args.input)
    result = choose_cutoff(df)
    available = schema.analysis_frame(df)
    available = available[available["evidence_available"] == True]  # noqa: E712
    result["observed_rate_at_cutoff"] = float(
        examination_rate(available, result["cutoff_s"]).mean()
    )
    result["warnings"] = schema.validate(df)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    plot_dwell(df, result["cutoff_s"], args.plot)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
