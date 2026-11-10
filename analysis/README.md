# Pilot analysis

Python pipeline for the calibration pilot. It reads the FastAPI CSV export and
produces the values that are frozen before the main experiment: tau, the
evidence-examination cutoff, variance components, the high-confidence safety
projection, and a precision check on N.

## Install

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r pilot/analysis/requirements.txt
```

## Full pipeline

From the repository root, with a real export at `pilot/data/export.csv`:

```bash
python -m pilot.analysis.calibrate_tau \
  --input pilot/data/export.csv \
  --out pilot/data/calibration/tau.json \
  --plot pilot/data/calibration/tau.png

python -m pilot.analysis.calibrate_examination \
  --input pilot/data/export.csv \
  --out pilot/data/calibration/examination.json \
  --plot pilot/data/calibration/examination.png

python -m pilot.analysis.variance_components \
  --input pilot/data/export.csv \
  --out pilot/data/calibration/variance_components.json

# Use the tau printed by calibrate_tau.
python -m pilot.analysis.safety_projection \
  --input pilot/data/export.csv \
  --tau 52 \
  --out pilot/data/calibration/safety.json

python -m pilot.analysis.precision_simulation \
  --components pilot/data/calibration/variance_components.json \
  --out pilot/data/calibration/precision.json

python -m pilot.analysis.report \
  --input pilot/data/export.csv \
  --out-dir pilot/data/report \
  --n-sim 500
```

`report.py` runs all of the above and writes:

- `pilot/data/report/pilot-report.md`
- `pilot/data/report/artifacts.json`
- `pilot/data/report/tau.png`
- `pilot/data/report/examination.png`

## Synthetic smoke test

```bash
python -m pilot.analysis.synthetic \
  --out pilot/data/synthetic.csv \
  --participants 60

python -m pilot.analysis.report \
  --input pilot/data/synthetic.csv \
  --out-dir pilot/data/report-synthetic \
  --n-sim 100
```

Synthetic values are for pipeline testing only. They are not empirical and must
not be used to justify design choices.

## Calibration rules

### Tau

`calibrate_tau.py` computes, for each candidate tau, the escalation share
`S(tau) = P(confidence < tau)`, the fraction of participants who used both
branches, and the safety-relevant high-confidence error counts.

The chosen tau satisfies:

- `S(tau)` in `[0.40, 0.60]`;
- both branches for at least 80% of participants;
- closest to `S = 0.50`;
- ties go to the lower tau.

The confidence–correctness association is **not** used to choose tau. If no
candidate satisfies the rule, the script falls back to the closest tau and marks
`fallback: true`; that decision must be documented as a protocol deviation.

### Examination cutoff

`calibrate_examination.py` looks for a trough in the positive dwell-time
distribution inside the pre-specified 2–5 s window. If no clear trough exists,
it keeps the provisional 3.0 s. `sensitivity` reports the examined fraction at
0.5 s steps. A trial counts as examined if the panel is active and focused for at
least the cutoff **or** the participant interacts with it.

The cutoff is a measurement rule, not an outcome. Freeze it before the main
experiment.

### Safety projection

For each of `static` and `adaptive`, the script estimates

`p_hat = P(confidence >= tau, recommendation incorrect, A != L)`

and projects the expected number of eligible trials at `N = 60`:

`6 * N * p_hat`.

It reports the 80% Wilson lower bound and the conservative

`N_main = max(60, ceil(40 / (6 * p_lower_80)))`.

The target is at least 40 eligible trials per arm. The preregistration should
use the lower bound, not only the point estimate.

### Variance components

`variance_components.py` fits planning models:

- accuracy: linear probability model for `final_correct`;
- timing: log-linear model for `decision_time_s`;
- both with participant and task random intercepts, condition reference
  `static`.

These are not the main analysis models. The main analysis uses the
pre-specified logistic and Gamma models with a participant bootstrap.

### Precision simulation

`precision_simulation.py` simulates participant and task random effects and
analyses participant-level adaptive−static contrasts. It reports one-sided 95%
precision and power for:

- accuracy non-inferiority with margin `delta = 0.10`;
- timing superiority with target ratio `0.75`.

It is a planning approximation. It does not replace the main mixed-model
analysis and it does not estimate the main treatment effect.

## Data conventions

- One row per planned trial; analysis keeps `state == "final_submitted"`.
- Conditions: `none`, `static`, `adaptive`.
- Task types: `identify_bug`, `check_spec`, `select_impl`.
- Answers are canonical sorted-JSON keys: `initial_key`, `final_key`,
  `recommendation_key`.
- `A_neq_L` means the initial answer differs from the recommendation.
- `influence = A_neq_L and final == recommendation`.
- `harmful_adoption = influence and recommendation incorrect`.
- `missed_correction = A_neq_L and recommendation correct and final != recommendation`.
- Timing exclusions use `excluded_from_timing`; the default rule is cumulative
  page-hidden time > 10 s or a single hidden interval > 30 s.
