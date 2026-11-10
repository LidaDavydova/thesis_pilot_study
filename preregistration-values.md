# Preregistration values

**Status:** draft. Complete after the formal calibration pilot and freeze before
the main experiment.  
**Version:** 0.1, 21 October 2026.

This document separates values that are fixed a priori from values calibrated in
the pilot. Do not re-estimate a calibrated value from main data.

## 1. Fixed a priori

| Item | Value |
| --- | --- |
| Conditions | `none`, `static`, `adaptive` |
| Design | Within-subject; all participants complete all 18 tasks |
| Tasks | 18: six per type, two per type per condition |
| Recommendation balance | 9 correct, 9 incorrect; 3/3 per type; 1/1 per type per condition |
| Practice trials | 2, not analysed |
| Primary outcome 1 | Final-answer accuracy, adaptive vs static, non-inferiority |
| Non-inferiority margin | 10 percentage points |
| Primary outcome 2 | Total decision time, adaptive vs static, superiority |
| One-sided alpha | 0.025 for each primary outcome |
| Accuracy model | Logistic mixed model, participant and task random intercepts |
| Timing model | Gamma/log mixed model, participant and task random intercepts |
| Marginal effect | Parametric bootstrap over participants |
| Reliance | Secondary: influence, harmful adoption, missed correction |
| Safety analysis | High-confidence incorrect-recommendation `A != L` trials, adaptive and static |
| Safety target | At least 40 eligible trials per arm at N=60 |
| Tau rule | `S(tau)` in [0.40, 0.60]; both branches for >= 80%; closest to 0.50; ties lower |
| Examination bounds | 2–5 s |
| Focus-loss target | Exclusion < 5% |
| Main sample floor | N = 60 analysable participants |

`A != L` means the initial answer differs from the recommendation.

## 2. Pilot-calibrated values

Fill these after the formal pilot. The provisional values are for development
only.

| Value | Provisional | Pilot result | Frozen |
| --- | --- | --- | --- |
| `tau` | 50 | [ ] | [ ] |
| `examination_cutoff_s` | 3.0 | [ ] | [ ] |
| Cumulative focus-loss exclusion | > 10 s | [ ] | [ ] |
| Single focus-loss exclusion | > 30 s | [ ] | [ ] |
| Participant SD, accuracy | 0.18 | [ ] | [ ] |
| Task SD, accuracy | 0.10 | [ ] | [ ] |
| Residual SD, accuracy | 0.30 | [ ] | [ ] |
| Participant SD, log time | 0.22 | [ ] | [ ] |
| Task SD, log time | 0.10 | [ ] | [ ] |
| Residual SD, log time | 0.42 | [ ] | [ ] |
| `p_hat` static | [ ] | [ ] | [ ] |
| `p_hat` adaptive | [ ] | [ ] | [ ] |
| `N_main` | 60 | [ ] | [ ] |

## 3. Tau decision rule

Compute `S(tau) = P(confidence < tau)` over completed pilot trials. For each
candidate tau:

1. Keep candidates with `0.40 <= S(tau) <= 0.60`.
2. Keep candidates where at least 80% of participants have both a trial below
   tau and a trial at or above tau.
3. Among the remainder, choose the candidate closest to `S = 0.50`.
4. If two candidates are equally close, choose the lower tau.

Record:

- chosen tau;
- `S(tau)`;
- both-branch fraction;
- whether the rule was satisfied or a fallback was used;
- confidence drift across blocks.

Do **not** choose tau by maximising the confidence–correctness association. The
premise check is descriptive and does not determine tau.

## 4. Examination cutoff rule

Use positive dwell times from trials where evidence was available. Find a
prominent trough in the smoothed distribution inside 2–5 s. If no clear trough
exists, keep 3.0 s.

A trial is examined if:

`evidence_active_ms >= cutoff_ms` **or** `interaction_count > 0`.

Report sensitivity at 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, and 5.0 s. Freeze one
cutoff before the main experiment.

## 5. Focus-loss rule

Provisional:

- exclude a trial from timing if cumulative page-hidden time > 10 s;
- or if a single hidden interval > 30 s.

Report the observed exclusion rate. Target < 5%. If the rate is higher, inspect
the distribution and freeze a revised rule before the main experiment. Do not
revise it on main data.

## 6. Safety projection and N

For each of `static` and `adaptive`:

`p_hat = k / n`

where `k` is the number of pilot trials with:

- `confidence >= tau`;
- `recommendation_correct == false`;
- `A_neq_L == true`.

Compute the 80% Wilson lower bound `p_lower`. The expected count at N=60 is:

`6 * 60 * p_hat`.

The conservative main-sample size is:

`N_main = max(60, ceil(40 / (6 * p_lower)))`.

At N=60, the design needs `p_hat >= 40 / 360 = 0.111` per arm. If the lower bound
is below 0.111, increase N rather than changing the target.

Record `N_main` and the per-arm expected count in the preregistration.

## 7. Precision check

Use the pilot variance components to simulate participant and task random
effects. Report one-sided 95% precision for:

- accuracy risk difference, non-inferiority margin 10 pp;
- decision-time ratio, target 0.75.

The simulation is a planning approximation. It does not replace the main
analysis and does not estimate the main effect.

## 8. Main analysis plan

### 8.1 Accuracy

Fit a logistic mixed model:

`final_correct ~ condition + (1 | participant) + (1 | task)`

with `static` as the reference. Report the adaptive−static marginal risk
difference and its one-sided 95% lower bound. Non-inferiority is concluded if the
lower bound is above −0.10.

### 8.2 Decision time

Fit a Gamma mixed model with a log link:

`decision_time ~ condition + (1 | participant) + (1 | task)`

with `static` as the reference. Report the adaptive/static ratio and its
one-sided 95% upper bound. Superiority is concluded if the upper bound is below
1.0. The target ratio of 0.75 is used for precision planning, not as the
superiority threshold.

### 8.3 Reliance

Secondary descriptive and model-based analyses:

- influence;
- harmful adoption;
- missed correction;
- evidence examination.

These are not primary outcomes and are not used to change the primary
conclusions.

### 8.4 High-confidence blind spot

Pre-specified secondary safety analysis:

- proportion of high-confidence trials with an incorrect recommendation and
  `A != L`;
- condition comparison;
- count per arm against the 40-trial target.

### 8.5 Missing data and exclusions

- Primary analysis uses completed trials with a final answer.
- Timing analysis excludes trials flagged by the frozen focus-loss rule.
- Report the number and reason for exclusions.
- Run a sensitivity analysis without the timing exclusions.
- Do not impute the primary outcome.

### 8.6 Multiplicity

Each primary outcome is tested one-sided at alpha = 0.025. Report both; do not
reinterpret a non-significant result as evidence of equivalence.

## 9. Freeze checklist

- [ ] Tau frozen.
- [ ] Examination cutoff frozen.
- [ ] Focus-loss rule frozen.
- [ ] `p_hat` and `N_main` recorded.
- [ ] Benchmark frozen and reviewed.
- [ ] Analysis plan and model specifications frozen.
- [ ] Ethics approval confirmed.
- [ ] Pilot data separated from main data.
- [ ] Software version recorded.
- [ ] Date and signatures recorded.

## 10. Sign-off

**Researcher:** [name]  
**Date:** [date]  
**Supervisor:** [name]  
**Date:** [date]

**Ethics reference:** [reference]  
**Date approved:** [date]
