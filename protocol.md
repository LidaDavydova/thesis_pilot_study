# Calibration pilot protocol

**Version:** 0.1 (draft for ethics and supervisor review)  
**Date:** 21 October 2026  
**Study:** Adaptive verification for AI-assisted introductory Python tasks  
**Pilot type:** Calibration pilot, separate from the main experiment

## 1. Purpose

The pilot has two purposes:

1. **Technical validation.** Confirm that the benchmark, participant interface,
   timing instrumentation, and export work as intended.
2. **Calibration.** Fix the adaptive threshold, the evidence-examination cutoff,
   the focus-loss exclusion rule, variance components, and the main-sample size
   before the main experiment.

The pilot is **not** a test of the main hypotheses. It does not estimate the
effect of adaptive verification on learning or task performance, and pilot data
are excluded from the main analyses.

## 2. Calibration targets

| Target | Rule | Output |
| --- | --- | --- |
| Adaptive threshold `tau` | `S(tau)=P(confidence<tau)` in `[0.40, 0.60]`; both branches for at least 80% of participants; closest to `S=0.50`; ties to lower tau | One integer tau |
| Evidence-examination cutoff | Trough in positive dwell-time distribution inside 2–5 s; default 3.0 s if no trough | Seconds |
| Focus-loss exclusion | Cumulative page-hidden time > 10 s or a single hidden interval > 30 s; target exclusion < 5% | Rule plus observed rate |
| High-confidence safety | At least 40 high-confidence, incorrect-recommendation, `A != L` trials per adaptive/static arm at N=60 | `p_hat`, lower bound, `N_main` |
| Variance components | Participant and task variance for accuracy and decision time | Planning values for precision simulation |
| Precision | One-sided 95% precision for accuracy non-inferiority (margin 10 pp) and timing superiority | Precision table and `N_main` |

`A != L` means the participant's initial answer differs from the recommendation.

## 3. Design

### 3.1 Benchmark

- 18 introductory Python tasks.
- Six tasks per type: `identify_bug`, `check_spec`, `select_impl`.
- Two tasks per type per condition.
- Three correct and three incorrect recommendations per condition.
- One correct and one incorrect recommendation per type per condition.
- Nine correct and nine incorrect recommendations overall.
- Two practice trials, not analysed.

Each participant sees all 18 tasks exactly once. Tasks are rotated across
conditions between participants, so a task is not nested in a condition.

### 3.2 Conditions

| Condition | Recommendation | Verification |
| --- | --- | --- |
| `none` | Shown | Never available |
| `static` | Shown | Always available |
| `adaptive` | Shown | Available only when confidence < tau |

The recommendation is shown in every condition. "No verification" means no
evidence panel, not no recommendation.

The disabled-evidence message is identical in `none` and in the withheld branch
of `adaptive`: “No verification is available for this trial. Continue with your
own judgment.” This prevents the participant from inferring the condition from
the wording.

### 3.3 Counterbalancing

Six sequences are used:

| Sequence | Block order |
| --- | --- |
| R0-ABC | none → static → adaptive |
| R1-ABC | static → adaptive → none |
| R2-ABC | adaptive → none → static |
| R0-CBA | adaptive → static → none |
| R1-CBA | none → adaptive → static |
| R2-CBA | static → none → adaptive |

Sequence assignment is round-robin over the six sequences, stratified by mode
where applicable. The realised condition is `(base_condition + rotation) % 3`.
Within a condition block, task order is shuffled deterministically from the
session identifier.

### 3.4 Trial sequence

For each trial:

1. Task prompt and code are shown.
2. Participant submits an initial answer.
3. Participant rates confidence (0–100).
4. Recommendation is revealed.
5. Evidence panel is available, unavailable, or withheld according to condition.
6. Participant may inspect evidence.
7. Participant submits a final answer.
8. Decision time and focus metrics are recorded.

The initial answer and confidence are stored before the recommendation is
revealed. The final endpoint never returns correctness.

## 4. Participants

### 4.1 Target sample

**12 participants** in the formal calibration pilot.

The pilot is a calibration study, not a hypothesis test, so the sample size is
justified by the precision of the calibration quantities rather than by power
for a treatment effect. Twelve participants provide:

- 216 completed trials;
- 72 trials per condition;
- 24 trials per task type per condition;
- 12 observations of each task across participants (with rotation);
- enough participants to check both adaptive branches and the dwell
  distribution.

The pilot sample is disjoint from the main sample.

### 4.2 Inclusion criteria

- Age 18 or older.
- Comfortable reading and writing basic Python.
- Able to give informed consent.
- No prior participation in this study.
- Able to complete a 60–75 minute session in one sitting.

### 4.3 Exclusion criteria

- Incomplete session with fewer than 80% of trials completed.
- Technical failure that prevents the participant from seeing the task,
  recommendation, or evidence as intended.
- Evidence of deliberate random responding (e.g., all confidence ratings
  identical and all answers submitted in under 2 seconds), documented before
  analysis.
- Withdrawal of consent.

Exclusions are recorded with a reason; the analysis reports the flow of
participants.

### 4.4 Recruitment and compensation

Recruitment method and compensation are decided before recruitment and recorded
in the ethics application. Participants may withdraw at any time without
penalty.

## 5. Procedure

### 5.1 Before the session

- Confirm ethics approval and consent materials.
- Assign the next sequence in the round-robin order.
- Check the database, browser, network, and screen sharing setup.
- Open a fresh browser profile or clear local storage to avoid resuming another
  session.

### 5.2 Session outline

| Stage | Time | Content |
| --- | --- | --- |
| Welcome and consent | 5 min | Study information, voluntary participation, data handling |
| Interface introduction | 3 min | Task types, confidence slider, recommendation, evidence panel |
| Practice | 5 min | Two practice trials with feedback on the interface only |
| Main trials | 45–55 min | 18 trials in three condition blocks, breaks between blocks |
| Questionnaire | 5 min | Clarity, perceived usefulness, strategy, technical issues |
| Debrief | 5 min | Explanation of conditions, incorrect recommendations, questions |

Total: approximately 60–75 minutes.

### 5.3 Instructions

Participants are told:

- Some recommendations are correct and some are incorrect.
- They should use their own judgment; the recommendation is decision support,
  not an answer key.
- When verification is available, they may inspect it or not.
- They may take as long as they need, but should not leave the session.
- They should keep the browser tab focused; focus loss is recorded for timing
  quality.

The full participant-facing text is in `session-script.md`.

## 6. Measures

### 6.1 Trial-level measures

- Initial answer and correctness.
- Confidence (0–100).
- Recommendation shown, recommendation correctness, and answer key.
- Evidence availability and policy decision (`not_applicable`, `always`,
  `offered`, `withheld`).
- Evidence active time, focus loss, maximum blur, interaction count.
- Evidence examined (cutoff rule).
- Final answer and correctness.
- Decision time from task display to final submission.
- Answer change, `A != L`, influence, harmful adoption, missed correction.
- Timing exclusion flag and reason.

### 6.2 Session-level measures

- Participant code, sequence, rotation, condition order.
- Start and completion times.
- Completion questionnaire: clarity, usefulness, strategy, technical issues,
  comments.
- Device/browser metadata where available.

### 6.3 Derived measures

- `influence = A_neq_L and final == recommendation`.
- `harmful_adoption = influence and recommendation incorrect`.
- `missed_correction = A_neq_L and recommendation correct and final != recommendation`.
- `decision_time_s`.
- `evidence_active_s`.

## 7. Calibration analysis

### 7.1 Tau

For each candidate tau in the pre-specified grid (20–80), compute:

- escalation share `S(tau)`;
- fraction of participants with at least one trial below and one trial at or
  above tau;
- high-confidence, incorrect-recommendation, `A != L` counts separately for
  adaptive and static.

Choose tau by the rule in Section 2. Do **not** choose tau by maximising the
confidence–correctness association. If no candidate satisfies the rule, use the
closest candidate, record `fallback=true`, and describe the deviation.

### 7.2 Evidence-examination cutoff

Use positive dwell times from trials where evidence was available. Find a
prominent trough in the smoothed dwell distribution inside 2–5 s. If no clear
trough exists, keep 3.0 s. Report the examined fraction at 2.0, 2.5, 3.0, 3.5,
4.0, 4.5, and 5.0 s.

A trial counts as examined if:

`evidence_active_ms >= cutoff_ms` **or** `interaction_count > 0`.

### 7.3 Focus-loss rule

Apply the provisional rule:

- cumulative page-hidden time > 10 s, or
- a single page-hidden interval > 30 s.

Report the exclusion rate. The target is below 5%. If the rate is higher,
inspect the distribution and freeze a revised rule before the main experiment;
do not tune it on main data.

### 7.4 Variance components

Fit planning models with participant and task random intercepts:

- linear probability model for final-answer accuracy;
- log-linear model for decision time.

Condition reference is `static`. Report participant, task, and residual
variances, and the adaptive−static contrast. These models are for planning and
precision simulation, not the main analysis.

### 7.5 Safety projection

For each arm (`static`, `adaptive`), estimate:

`p_hat = P(confidence >= tau, recommendation incorrect, A != L)`.

Compute the expected count at N=60 as `6 * 60 * p_hat`, and the 80% Wilson lower
bound. Set:

`N_main = max(60, ceil(40 / (6 * p_lower_80)))`.

If the lower bound implies more than 60 participants, record the larger N. If it
implies fewer, keep N=60.

### 7.6 Precision check

Simulate participant and task random effects using the pilot variance
components. Report one-sided 95% precision and power for:

- accuracy non-inferiority, margin 10 percentage points;
- decision-time superiority, target ratio 0.75.

The simulation is a planning approximation. The main analysis remains the
pre-specified mixed-effects model with a participant bootstrap.

### 7.7 What the pilot does not do

- No hypothesis test of adaptive vs static.
- No estimate of the main treatment effect used as a confirmatory result.
- No re-estimation of tau or the cutoff from main data.
- No pooling of pilot and main data.

## 8. Ethics and data management

### 8.1 Ethics status

**Formal pilot:** written ethics approval must be confirmed before recruitment.
The proposal states that approval is required before any pilot or main data
collection. Record the approval reference, date, and any amendments in the study
file.

**Technical dry run:** the dry run is designed to produce bug reports only, with
no consent, recording, trial data, or research analysis. It does not replace the
ethics decision for the formal pilot. If the dry run is changed in a way that
collects research data, it becomes a pilot and requires approval.

### 8.2 Consent

Participants receive a plain-language information sheet and consent form. Consent
covers:

- purpose and procedure;
- voluntary participation and withdrawal;
- data collected and how they are stored;
- anonymised participant codes;
- use of data in the thesis and publications;
- contact details for questions and complaints.

### 8.3 Confidentiality

- Participants are identified by a study code, not by name, in the database.
- The linking key, if any, is stored separately from the trial data.
- No audio or video is recorded.
- Free-text questionnaire comments are reviewed for identifying information
  before quotation.
- Exports are stored on the researcher's encrypted device.

### 8.4 Data storage and retention

- SQLite database: local encrypted disk.
- Exports and reports: local encrypted disk; no cloud sync unless approved.
- Retention: until thesis examination and any required publication period, then
  deleted according to institutional policy.
- Access: researcher and supervisor only, unless ethics approval says otherwise.

### 8.5 Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Frustration or fatigue | Breaks between blocks; option to stop |
| Concern about incorrect recommendations | Debrief explains the design; recommendations are decision support |
| Privacy | Study codes; no recording; minimal demographic data |
| Power imbalance | Participation is voluntary; no effect on course grades |

## 9. Deviations and stopping rules

- Stop the session if the participant withdraws or is distressed.
- Stop if the interface fails in a way that prevents valid task presentation.
- Record every deviation (sequence error, missing trial, timer failure) in the
  session log.
- Do not change the benchmark, tau, cutoff, or exclusion rules mid-pilot without
  recording the change and its reason.

## 10. Analysis software and reproducibility

- Python analysis pipeline in `pilot/analysis/`.
- SQLite database and CSV export in `pilot/data/`.
- Random seed for any simulation recorded in the report.
- The report builder writes `pilot-report.md` and `artifacts.json`.
- Code and configuration are versioned locally; the project directory is not a
  git repository at the time of writing.

## 11. Timeline

| Period | Milestone |
| --- | --- |
| November 2026 | Complete 18-task benchmark; technical dry run |
| December 2026 | Fix prototype; freeze software version |
| January 2027 | Ethics decision; formal pilot; calibration report |
| January 2027 | Freeze tau, cutoff, exclusion rule, N, and analysis plan |
| February 2027 | Main experiment |
| March 2027 | Main analysis |
| 15 May 2027 | Thesis submission |

## Appendix A. Task composition

The full composition and balance table is in
`benchmark/benchmark-18-plan.md`. In summary:

- 9 correct and 9 incorrect recommendations;
- 3 correct and 3 incorrect per task type;
- 2 tasks per type per condition;
- 1 correct and 1 incorrect recommendation per type per condition.

## Appendix B. Sequence assignment

Sequences are assigned round-robin in the order listed in Section 3.3. The
session record stores `sequence_id`, `rotation`, and `condition_order` so the
realised design can be checked after data collection.
