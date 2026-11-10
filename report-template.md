# Calibration pilot report template

**Study:** Adaptive verification for AI-assisted introductory Python tasks  
**Pilot dates:** [start] – [end]  
**Report date:** [date]  
**Prepared by:** [name]  
**Ethics reference:** [reference / status]  
**Software version / commit:** [version]

## 1. Summary

- Participants analysed: [N] of [N recruited].
- Completed trials: [N].
- Chosen tau: [tau].
- Evidence-examination cutoff: [seconds].
- Focus-loss exclusion rate: [%].
- `N_main`: [N].
- Main safety target met: [yes/no].
- Recommendation: [proceed / fix and repeat / stop].

## 2. Data and exclusions

| Item | Count |
| --- | --- |
| Recruited | |
| Consented | |
| Completed | |
| Excluded from calibration | |
| Analysed | |

Reasons for exclusion:

- [reason, n]
- [reason, n]

## 3. Benchmark balance

- 18 tasks: [yes/no]
- Six per type: [yes/no]
- Nine correct / nine incorrect recommendations: [yes/no]
- Two per type per condition: [yes/no]
- One correct and one incorrect per type per condition: [yes/no]
- Task-quality problems: [list]

## 4. Tau calibration

| tau | S(tau) | Both branches | p_hat static | p_hat adaptive |
| --- | --- | --- | --- | --- |
| | | | | |

Chosen tau: [tau]  
Rule satisfied: [yes/no]  
Fallback used: [yes/no]  
Confidence drift across blocks: [points]

Decision:

> [Freeze tau = ... / repeat calibration because ...]

## 5. Evidence-examination cutoff

Dwell distribution:

- Available evidence trials: [N].
- Positive dwell trials: [N].
- Median dwell: [s].
- Trough / chosen cutoff: [s].
- Default retained: [yes/no].

Sensitivity:

| Cutoff (s) | Examined fraction | Interaction-only fraction |
| --- | --- | --- |
| 2.0 | | |
| 2.5 | | |
| 3.0 | | |
| 3.5 | | |
| 4.0 | | |
| 4.5 | | |
| 5.0 | | |

Decision:

> [Freeze cutoff = ... s / retain 3.0 s because ...]

## 6. Focus-loss rule

- Cumulative focus-loss exclusion rate: [%].
- Single-interval exclusion rate: [%].
- Target < 5%: [met/not met].
- Distribution notes: [notes].

Decision:

> [Keep / revise the rule before the main experiment.]

## 7. Variance components

### Accuracy

| Component | Estimate |
| --- | --- |
| Participant SD | |
| Task SD | |
| Residual SD | |
| ICC participant | |
| ICC task | |

Adaptive − static contrast: [estimate], 95% CI [low, high].

### Decision time

| Component | Estimate |
| --- | --- |
| Participant SD | |
| Task SD | |
| Residual SD | |
| ICC participant | |
| ICC task | |

Adaptive / static ratio: [ratio], 95% CI [low, high].

## 8. High-confidence safety projection

| Condition | Eligible trials | p_hat | 80% lower | Expected at N=60 | Required N |
| --- | --- | --- | --- | --- | --- |
| static | | | | | |
| adaptive | | | | | |

Target: 40 eligible trials per arm at N=60.  
Met by point estimate: [yes/no].  
Met by lower bound: [yes/no].  
`N_main`: [N].

## 9. Precision simulation

| N | Accuracy half-width | Accuracy power | Timing ratio | Timing power |
| --- | --- | --- | --- | --- |
| 40 | | | | |
| 60 | | | | |
| 80 | | | | |
| 100 | | | | |
| 120 | | | | |

Required N for 80% accuracy power: [N / not reached].  
Required N for 80% timing power: [N / not reached].

## 10. Values to freeze

| Value | Frozen choice |
| --- | --- |
| tau | |
| Examination cutoff | |
| Cumulative focus-loss rule | |
| Single focus-loss rule | |
| Accuracy non-inferiority margin | 10 pp |
| `N_main` | |
| Safety target | 40 per arm |
| Primary outcomes | Accuracy; decision time |
| Analysis models | Logistic/Gamma mixed models; participant bootstrap |

## 11. Deviations

| Date | Participant / session | Deviation | Action |
| --- | --- | --- | --- |
| | | | |

## 12. Interpretation and recommendation

- What the pilot did well:
  - [ ]
- What was ambiguous or unstable:
  - [ ]
- What must change before the main experiment:
  - [ ]

**Decision:** [proceed to main / repeat pilot / revise design]

**Signed:** [researcher]  
**Date:** [date]  
**Supervisor review:** [name / date]
