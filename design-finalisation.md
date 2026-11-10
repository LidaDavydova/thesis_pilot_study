# Finalisation of the experimental design

**Status:** working document for the 1–15 November 2026 milestone  
**Companion documents:** `../proposal-v4.tex` §4–§6, `protocol.md`,
`preregistration-values.md`, `benchmark/task-audit.md`  
**Rule:** everything marked **fixed** is frozen before main data collection;
everything marked **pilot-calibrated** is estimated once, from pilot data only.

> Note on terminology: the request mentions "theta". In this design the
> confidence threshold is denoted **τ (tau)**. There is no separate θ parameter;
> τ is the only calibrated policy parameter.

---

## 1. Operational definitions

These definitions are the codebook. The analysis code must implement exactly
these, and the application must log the fields needed to compute them.

| Term | Definition |
|---|---|
| **Trial** | One task shown once to one participant, ending in a final submission or a recorded dropout. |
| **Initial answer `A`** | The structured answer submitted **before** the recommendation is displayed. |
| **Confidence `c`** | Self-report on a 0–100 slider, elicited after `A` and **before** the recommendation: "How confident are you that your initial answer is correct?" 0 = pure guess, 50 = unsure, 100 = certain. |
| **Recommendation `L`** | The frozen structured LLM answer, rendered in the same response widget and with the same option labels as `A`. |
| **Final answer `F`** | The structured answer submitted after the recommendation and, when available, the evidence panel. |
| **Final-answer correctness** | `1` if `F` is in the task's `accepted_equivalence` set, else `0`. Never scored on free text. |
| **Recommendation correctness** | `1` if `L` is in `accepted_equivalence`, else `0`. Analysis-only; never exposed to the participant, the app, or the policy. |
| **Evidence available** | `1` if the verification panel is enabled for the trial: always in `static`, `c < τ` in `adaptive`, never in `none`. |
| **Evidence examined** | `1` if the panel was active and focused for at least the frozen cutoff **or** the participant performed a recorded interaction (open/scroll/copy). |
| **Total decision time** | Seconds from the first display of the recommendation to submission of `F`. Excludes task reading and `A`/`c` entry. |
| **Focus loss** | Cumulative `document.hidden` time > 10 s, or any single hidden interval > 30 s. Such trials are excluded from timing analyses only. |
| **`A ≠ L`** | Initial answer differs from the recommendation in the canonical response space. This is the denominator for reliance measures. |
| **Influence (true reliance)** | `A ≠ L` and `F = L`: the participant moved to the recommendation from a different prior answer. |
| **Stable prior agreement** | `A = L` and `F = L`: agreement that is not attributable to the LLM. |
| **Switch away** | `A = L` and `F ≠ L`: the participant moved away from a recommendation they initially matched. |
| **Over-reliance** | Among `A ≠ L`, the share of **incorrect** recommendations adopted (`F = L`). |
| **Under-reliance** | Among `A ≠ L`, the share of **correct** recommendations not adopted (`F ≠ L`). |
| **Appropriate reliance** | Accept a correct recommendation or reject an incorrect one. Also report the stricter appropriate-updating rate restricted to `A ≠ L`. |
| **Harmful adoption** | `A ≠ L`, recommendation incorrect, and `F = L`. |
| **Missed correction** | `A ≠ L`, recommendation correct, and `F ≠ L`. |
| **High-confidence stratum** | Trials with `c ≥ τ`. In `adaptive` this is exactly the branch where evidence is withheld. |
| **Verification availability rate (VAR)** | Share of trials on which evidence is offered: 0 in `none`, 1 in `static`, realised `P(c < τ)` in `adaptive`. Manipulation check, not an effort outcome. |
| **Task family** | The underlying problem shared by an `identify_bug`, a `check_spec`, and a `select_impl` variant (e.g. `best_pair`). Six families, three tasks each. |
| **Block** | The six consecutive trials of one condition. Three blocks per participant. |
| **Analysable participant** | Consented, eligible, completed at least 80% of trials, and not excluded for a documented technical or integrity failure. |
| **Pilot participant** | Enrolled in the calibration pilot; disjoint from the main sample; never pooled with main data. |

---

## 2. Conditions and the confidence policy

### 2.1 Conditions

| Condition | Recommendation | Verification |
|---|---|---|
| `none` | Shown | Never available |
| `static` | Shown | Always available |
| `adaptive` | Shown | Available iff `c < τ` |

The recommender, evidence provider, decider, task set, interface layout, and
logging are identical in all three conditions. Only the availability rule
changes. Decision authority is never reassigned: the participant decides in
every condition.

### 2.2 Policy

The policy receives exactly one input, `c ∈ [0, 100]`, and returns
`available = 1[c < τ]`. It does **not** receive task type, difficulty,
recommendation correctness, accuracy, time, or any model signal. τ is a single
integer fixed from the pilot and recorded in the preregistration.

### 2.3 Interface and blinding

- The evidence affordance is present in every trial.
- In `none` and in the withheld branch of `adaptive`, the control is disabled
  with the identical text: "No verification is available for this trial.
  Continue with your own judgment."
- The correctness label is stripped from every API response, including the
  final-submit endpoint. It exists only in the analysis export.
- τ is not disclosed to participants; the debrief explains that evidence was
  sometimes unavailable, without stating the rule.
- The session script is fixed; the researcher answers technical questions only.

### 2.4 Confidence drift

Because participants experience all three conditions, they may learn that low
confidence triggers evidence and adjust their reports. Pre-specified checks:

- mean and median `c` by block and by condition;
- share of participants whose block-to-block mean changes by more than 10
  points;
- debrief question: "Did you notice a pattern in when verification was
  available? Did it change how you used the slider?"

Any evidence of strategic reporting is reported as a limitation. The primary
analysis is not changed post hoc; a sensitivity analysis restricted to block 1
is reported if drift is detected.

---

## 3. Hypotheses and estimands

### 3.1 Primary hypothesis 1 — accuracy non-inferiority

Let `Δ = π_adaptive − π_static`, the marginal difference in the probability of a
correct final answer, standardised over the target participant and task
population.

```
H0: Δ ≤ −δ_Q          H1: Δ > −δ_Q
```

- `δ_Q = 0.10` (10 percentage points), fixed a priori as a substantive margin.
- One-sided `α = 0.025`.
- Non-inferiority is concluded iff the lower one-sided 95 % bound on `Δ`
  exceeds `−0.10`.
- A non-significant difference is **not** evidence of equivalence; only the
  bound is interpreted.

### 3.2 Primary hypothesis 2 — effort superiority

Let `ρ = μ_adaptive / μ_static`, the ratio of expected total decision times.

```
H0: ρ ≥ 1             H1: ρ < 1
```

- One-sided `α = 0.025`.
- Superiority is concluded iff the upper one-sided 95 % bound on `ρ` is below
  `1.0`.
- The smallest effect of interest (SEI) is a 25 % reduction in mean decision
  time or 60 s per trial, whichever is larger. Statistical superiority and
  practical relevance are reported separately; a ratio of 0.95 is statistically
  detectable but not practically meaningful under the SEI.

### 3.3 Secondary safety hypothesis (descriptive, pre-specified)

Within the high-confidence stratum `c ≥ τ`, among trials with an incorrect
recommendation and `A ≠ L`, let `RD = p_adaptive − p_static` for harmful
adoption. Report `RD` with a 95 % CI. Blind-spot harm is considered bounded if
the **upper** bound is below `+0.10` and accuracy in the same stratum is not
materially lower. This is interpreted against a margin, not tested as a third
confirmatory hypothesis, and it does not spend the primary alpha.

### 3.4 Secondary and exploratory questions

- Reliance: influence, over-, under-, appropriate reliance, by condition and
  recommendation correctness. Descriptive.
- Effort: evidence-examination rate and examination time, conditional on
  availability; answer-change rate. Descriptive.
- RQ3 (exploratory): moderation by prior confidence, task type, difficulty, and
  task family. Unadjusted estimates, hypothesis-generating only.
- Premise check: mixed logistic model of initial-answer correctness on `c`,
  calibration curve, AUC. Descriptive; does not set τ.

---

## 4. Metrics

| Role | Metric | Level | Definition | Analysis |
|---|---|---|---|---|
| **Primary** | Final-answer accuracy | Trial | `1[F ∈ accepted_equivalence]` | Logistic GLMM; marginal RD; non-inferiority |
| **Primary** | Total decision time | Trial | Recommendation → final submission, seconds | Gamma GLMM log link; marginal ratio; superiority |
| Secondary effort | VAR | System | Share of trials with evidence offered | Manipulation check; descriptive |
| Secondary effort | Evidence-examination rate | Participant | Share of available trials examined | Logistic, available trials; descriptive |
| Secondary effort | Evidence-examination time | Participant | Seconds panel active and focused | Gamma, examined trials; descriptive |
| Secondary effort | Answer-change rate | Trial | `1[F ≠ A]` | Descriptive; correctness transition and direction to/from `L` |
| Secondary reliance | Influence | Trial | `1[A ≠ L ∧ F = L]` | By condition × recommendation correctness |
| Secondary reliance | Over-/under-/appropriate reliance | Trial | Defined in §1 | Descriptive with 95 % CI |
| Safety | Harmful adoption | Trial | `1[A ≠ L ∧ L wrong ∧ F = L]`, high-confidence stratum | Risk difference adaptive − static; 95 % CI |
| Safety | Missed correction | Trial | `1[A ≠ L ∧ L correct ∧ F ≠ L]`, high-confidence stratum | Risk difference; 95 % CI |
| Exploratory | Initial-answer correctness | Trial | `1[A correct]` | Logistic on `c`; calibration; AUC |
| Exploratory | Confidence drift | Block | Mean/median `c` by block | Descriptive |
| Exploratory | Task type / difficulty / family | Trial | Metadata | Descriptive; interaction only exploratory |

No aggregate "effort score" is formed. The measures are reported separately.

---

## 5. Design and randomisation

### 5.1 Benchmark

- 18 tasks: six per type (`identify_bug`, `check_spec`, `select_impl`).
- Nine correct and nine incorrect recommendations; three of each per type.
- Six task families × three types; each family appears once in each condition
  (see `benchmark/task-audit.md` §5).
- Difficulty: six low, six medium, six high; descriptive only, never a policy
  input.
- Two practice trials, not analysed.

### 5.2 Assignment

Each participant completes all 18 tasks, six per condition. The family ×
condition assignment is the Latin square in `benchmark/task-audit.md` §5. Across
three rotations, every task appears exactly once in every condition. Condition
order is counterbalanced with six sequences (three rotations × two orderings);
task order within a block is randomised per participant from the session ID.

This makes task and family crossed with condition, not nested in it. Task and
family can therefore enter sensitivity models without being confounded with the
manipulation.

### 5.3 Sample

- Target `N = 60` analysable participants (provisional; see §7.5).
- 18 trials each → up to 1,080 trial records; 360 per condition; about 180 per
  condition × recommendation correctness.
- Over-recruit by ~50 % to offset screening failures, no-shows, and withdrawals.
- No optional stopping and no outcome-dependent extension.

### 5.4 Procedure

Consent → interface introduction → two practice trials → three condition blocks
(breaks only between blocks) → questionnaire → debrief. Remote,
self-administered, 60–75 minutes. The trial sequence is: task → `A` → `c` →
`L` → evidence (never / always / iff `c < τ`) → `F`.

---

## 6. Statistical analysis plan

### 6.1 Analysis populations

| Population | Definition | Use |
|---|---|---|
| **mITT** | All consented, eligible participants with at least one completed trial | Primary |
| **Per-protocol** | mITT with ≥ 80 % of trials completed and no documented protocol deviation | Sensitivity |
| **Timing** | mITT trials not excluded by the focus-loss rule | Primary for RQ2 |
| **Safety stratum** | High-confidence trials with the relevant recommendation correctness and `A ≠ L` | Safety |

Pilot participants are excluded from every main analysis. The number of
participants and trials at each stage is reported in a flow table.

### 6.2 Primary models

Let `Y_ij` be the outcome for participant `i` on task `j`, `X_ij` the condition
indicators (`static`, `adaptive`; reference `none`), and `u_i`, `v_j` random
intercepts for participant and task.

**Accuracy (RQ1):**

```
logit P(Y_ij = 1) = β0 + β1·static_ij + β2·adaptive_ij + u_i + v_j
```

**Decision time (RQ2):**

```
E[Y_ij] = exp(β0 + β1·static_ij + β2·adaptive_ij + u_i + v_j),  Y_ij ~ Gamma
```

The adaptive − static contrast is `β2 − β1` on the model scale. Because the
link is nonlinear, the reported estimand is the **marginal** risk difference or
time ratio obtained by g-computation: predict every observed trial under
`adaptive` and under `static`, average, and take the difference or ratio.

### 6.3 Uncertainty

- Parametric bootstrap over participants: resample participants with
  replacement, refit, recompute the marginal contrast; 2,000 replicates.
- Report percentile one-sided 95 % bounds for each primary contrast.
- Report raw condition proportions/means and their model-free 95 % CIs
  alongside.
- The bootstrap seed and software versions are recorded.

### 6.4 Decision rules

| Question | Estimate | Conclude |
|---|---|---|
| RQ1 non-inferiority | `Δ`, lower one-sided 95 % bound | Non-inferior if bound > −0.10 |
| RQ2 superiority | `ρ`, upper one-sided 95 % bound | Superior if bound < 1.00 |
| RQ2 practical relevance | `ρ` vs SEI | Report whether the point estimate and bound clear 0.75 / 60 s |
| Safety | `RD`, upper 95 % bound | Bounded if < +0.10 and accuracy not materially lower; otherwise report the gate as unsafe for the subgroup |

If a bound crosses the decision threshold, the result is **inconclusive**, not
negative evidence. Do not reinterpret a non-significant difference as
equivalence.

### 6.5 Multiplicity

The two primary tests are each one-sided at `α = 0.025`. No alpha is spent on
secondary, safety, or exploratory analyses; those are reported with unadjusted
95 % CIs and interpreted descriptively. The safety analysis has its own
pre-specified margin, not a confirmatory alpha.

### 6.6 Model diagnostics and fallbacks

- Check convergence, singular fits, separation, and overdispersion.
- If the task random-intercept variance is effectively zero or the model does
  not converge, drop the task random intercept and report the simpler model;
  report both if they differ materially.
- If the logistic GLMM fails due to separation, use a penalised likelihood
  (Firth) or a Bayesian mixed model with weakly informative priors; freeze the
  fallback in the preregistration.
- If the Gamma model is unstable, report a log-linear model on `log(1 + t)` as a
  sensitivity analysis, not as the primary result.
- Do not simplify the fixed effects; condition is always retained.

### 6.7 Missing data and exclusions

- Primary accuracy: available-case mixed model under MAR; report the amount and
  pattern of missing final answers.
- Timing: exclude trials flagged by the frozen focus-loss rule; report the
  exclusion rate and run a sensitivity analysis without exclusions.
- Do not impute the primary outcome.
- Excluded/withdrawn participants are reported, not silently dropped.

### 6.8 Sensitivity analyses (pre-specified)

1. Exclude `model_seeded` / perturbed recommendations (if any remain).
2. Per-protocol population (≥ 80 % completion).
3. Timing analysis without focus-loss exclusions.
4. Add task family as a fixed effect (six levels) to the primary models.
5. Add block index and condition order as covariates.
6. Restrict to block 1 if confidence drift is detected.
7. Accuracy without practice trials (already excluded by design).
8. Worst-case sensitivity for missing final answers (all missing scored wrong).

Sensitivity analyses are reported separately and do not replace the primary
result.

### 6.9 Software and reproducibility

- Python 3.10; `pandas`, `numpy`, `scipy`, `statsmodels` (or the frozen R
  equivalent if GLMM convergence requires it).
- One script per primary outcome, one report builder, fixed seeds.
- The analysis code is frozen before main data are opened; the commit hash and
  package versions are archived with the dataset.
- The analysis dataset is derived from the raw export by a script, never edited
  by hand.

---

## 7. Calibration pilot and τ

### 7.1 Purpose

The pilot is a **calibration study**, not a hypothesis test. It fixes:

1. τ, the confidence threshold;
2. the evidence-examination cutoff;
3. the focus-loss exclusion rule (confirm or revise);
4. variance components for precision planning;
5. the high-confidence error prevalence for the safety projection;
6. the main-sample size `N`;
7. task clarity, interface usability, and logging quality.

It does **not** estimate the treatment effect and does not test RQ1/RQ2.

### 7.2 Sample and data volume

- **12 participants** (minimum), disjoint from the main sample.
- 18 trials each → **216 trials**; 72 per condition; 36 per condition ×
  recommendation correctness.
- Each task seen by 12 participants across rotations.
- If the confidence distribution is compressed or the safety stratum is empty,
  extend to 15–18 participants **before** looking at condition effects; record
  the extension as a protocol deviation.

### 7.3 Procedure

- Same application, benchmark, instructions, and logging as the main study.
- Provisional values during the pilot: `τ = 50`, examination cutoff `3.0 s`,
  focus-loss rule `> 10 s` cumulative / `> 30 s` single.
- All three conditions are run, so the pilot also exercises both adaptive
  branches and the disabled-control wording.
- Confidence is elicited on every trial before the recommendation.
- No hypothesis tests are run during the pilot; condition effects are not
  inspected until the pilot closes.

### 7.4 τ calibration

For each candidate `τ ∈ {20, …, 80}` compute:

- `S(τ) = P(c < τ)` over completed pilot trials;
- the fraction of participants with at least one trial below and one at or above
  τ;
- the high-confidence, incorrect-recommendation, `A ≠ L` count per arm.

Decision rule (fixed):

1. keep candidates with `0.40 ≤ S(τ) ≤ 0.60`;
2. keep candidates where at least 80 % of participants use both branches;
3. among the remainder, choose the candidate closest to `S = 0.50`;
4. ties go to the lower τ.

Do **not** choose τ by maximising the confidence–correctness association.

**Precision.** With 216 trials and clustering within participants, the standard
error of `S(τ)` is roughly 3–7 percentage points depending on the intraclass
correlation. The `[0.40, 0.60]` window is therefore a band, not a point
estimate; report `S(τ)` with a cluster bootstrap CI.

**Fallbacks.**

- If no candidate satisfies the rule, choose the candidate closest to
  `S = 0.50`, set `fallback = true`, and describe the deviation.
- If confidence is compressed at the top (e.g. median > 80), the grid may contain
  no candidate. Then set τ to the rounded median confidence if it lies in
  `[20, 80]`; otherwise report that the policy premise is weak in this sample
  and freeze the closest feasible τ. Do not silently move to a different signal.
- If the pilot reveals strategic reporting, keep the rule but report the drift
  and the block-1 sensitivity analysis.

### 7.5 Safety projection and N

For each arm (`static`, `adaptive`), estimate

```
p_hat = P(c ≥ τ, recommendation incorrect, A ≠ L)
```

from the 72 pilot trials per arm, with an 80 % Wilson lower bound `p_lower`.
The main design needs 40 eligible trials per arm at `N`:

```
N_main = max(60, ceil(40 / (6 · p_lower)))
```

At `N = 60`, 360 trials per arm, the target requires `p ≥ 0.111`. With only 72
pilot trials per arm, a true rate of 0.111 gives about 8 events; the 80 % lower
bound is then near 0.07, implying `N ≈ 93`. To keep `N = 60`, the pilot must
observe roughly `p_hat ≥ 0.17` (about 12 events per arm). Plan for this
explicitly:

- if `p_lower > 0`, set `N_main` by the formula, up to a pre-agreed ceiling
  (e.g. 120);
- if `p_lower = 0` (zero events), do **not** divide by zero and do not claim the
  target is met: freeze `N = 120`, report the stratum as sparse, and state that
  the safety analysis is descriptive only;
- if `N_main` exceeds the recruitment ceiling, reduce the safety target (e.g. 20
  eligible trials) with a written rationale, or accept that the safety analysis
  is underpowered and say so.

This is the main place where the pilot can change the main design. Decide the
ceiling before recruitment.

### 7.6 Examination cutoff

Use positive dwell times from trials where evidence was available. Look for a
trough in the smoothed dwell distribution inside 2–5 s. If there is no clear
trough, keep 3.0 s. Report the examined fraction at 2.0, 2.5, 3.0, 3.5, 4.0,
4.5, and 5.0 s. Freeze one cutoff. A trial is examined if
`active_ms ≥ cutoff_ms` **or** `interaction_count > 0`.

### 7.7 Variance components and precision

Fit planning models with participant and task random intercepts:

- linear probability model for final-answer accuracy;
- log-linear model for decision time;
- condition reference `static`.

Report participant, task, and residual variances. Use them in
`precision_simulation.py` to report one-sided 95 % precision and power for:

- accuracy non-inferiority, margin 10 pp;
- decision-time superiority, target ratio 0.75.

The simulation is a planning approximation, not the main analysis.

### 7.8 Pilot deliverables

- `tau.json` and `tau.png` (chosen τ, `S(τ)`, both-branch fraction, fallback
  flag, drift check);
- `examination.json` and `examination.png` (cutoff, sensitivity table);
- `variance_components.json`;
- `safety.json` (per-arm `p_hat`, Wilson bounds, `N_main`);
- `precision.json`;
- `pilot-report.md` and `artifacts.json`;
- a signed freeze record in `preregistration-values.md`.

### 7.9 What the pilot must not do

- No test of adaptive vs static.
- No use of the pilot treatment effect as a confirmatory result.
- No re-estimation of τ or the cutoff from main data.
- No pooling of pilot and main data.
- No changing the benchmark after the pilot without documenting the replacement.

---

## 8. Freeze checklist

- [ ] Benchmark: 18 tasks `ready`, two annotators, κ reported, hash recorded.
- [ ] Design: 6 families × 3 types; Latin square; `seed --check-only` passes.
- [ ] τ frozen with the rule and fallback documented.
- [ ] Examination cutoff frozen.
- [ ] Focus-loss rule frozen; observed exclusion rate reported.
- [ ] Variance components and precision table recorded.
- [ ] `p_hat`, `p_lower`, and `N_main` recorded; ceiling respected.
- [ ] Primary and secondary estimands, models, and decision rules frozen.
- [ ] Sensitivity analyses and missing-data rules frozen.
- [ ] Ethics approval reference and date recorded.
- [ ] Pilot data separated from main data; access rules recorded.
- [ ] Software version and commit hash recorded.
- [ ] Date and signatures (researcher, supervisor) recorded.

---

## 9. Open decisions

1. **T09 ambiguity:** accept line 5 as correct (and replace the incorrect
   recommendation) or rewrite the task. See `benchmark/task-audit.md` §2.
2. **Natural incorrect recommendations:** collect more Qwen3-8B samples for the
   `select_impl` slots, or accept four perturbations with a sensitivity
   analysis. The first is stronger; the second is feasible.
3. **N ceiling:** set the maximum `N_main` (suggest 120) before the pilot, so the
   safety projection cannot silently expand the study.
4. **Model implementation:** freeze Python `statsmodels` or R `lme4`/`glmmTMB`
   before analysis; do not choose after seeing convergence.
5. **Preregistration venue:** OSF or the institutional repository; record the
   registration DOI/URL in the thesis.
