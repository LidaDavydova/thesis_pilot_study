# Benchmark audit: 18-task bank

> **Historical note:** this audit applies to the previous hand-authored bank,
> which has since been removed. The current `tasks/` bank is adapted from the
> accepted MBPP review set; see `README.md` and `benchmark-18-plan.md`.

**Date:** 7 November 2026  
**Scope:** `pilot/benchmark/tasks/T01.json`–`T18.json`, `design.json`,
`benchmark-spec.md`, `benchmark-18-plan.md`, and the Qwen3-8B collection report.  
**Verdict:** the task content is mostly sound, but the bank is **not ready for the
formal pilot**. Four issues are blocking; the largest is a design confound, not a
typo.

## 1. What was checked

- Structural validity and balance (18 tasks, 6 per type, 9 correct / 9 incorrect,
  6 low / 6 medium / 6 high).
- Every canonical answer, and every recommendation correctness label against
  `accepted_equivalence`.
- Every evidence claim that can be executed, by running the task code and all
  `select_impl` candidates on the stated inputs.
- Task-to-condition assignment in `design.json`, including the three rotations.
- Consistency between the task files and the two benchmark documents.

Automated checks confirmed:

- all 18 recommendation labels agree with `accepted_equivalence`;
- composition is 6/6/6 by type, 3/3 correct/incorrect per type, 9/9 overall;
- difficulty is 6 low / 6 medium / 6 high;
- all executed evidence matches the file **except T13's second row**.

## 2. Blocking issues

### B1. No task is runnable (`status: draft`)

All 18 tasks have `"status": "draft"`, `flags.needs_review: true`, and empty
`annotations`. `python -m pilot.app.seed --check-only` therefore fails with:

```text
BenchmarkError: No ready tasks found in the benchmark
```

The prototype cannot run the pilot until the annotation and sign-off step is
done. This is a process blocker, not a content bug.

### B2. T13 contains a mathematically false evidence row

T13 (`check_spec`, condition `(xs[i] + xs[j]) % 9 == (j - i) % 9`) claims:

| input | expected | actual |
|---|---|---|
| `[9, 9, 9]` | 2 | 2 |

The code returns **0**. For every pair the sum is 18, so `18 % 9 == 0`, while
the distance is 1 or 2, so the remainder is 1 or 2. No pair matches. The first
row (`[9, 1]` → 1) is correct. A false "expected" value in verification evidence
is a fatal benchmark defect: it can teach participants the wrong rule.

### B3. T09 has an ambiguous canonical line

T09's root cause is line 4 (`for j in range(len(xs))`), but line 5
(`if i != j ...`) is a defensible contributing line: it is the guard that fails
to prevent double counting. The file accepts only line 4, and the frozen
recommendation says line 5, which is therefore scored as **incorrect**. The
LLM report acknowledges this choice, but a novice or a second annotator can
reasonably disagree. Either accept `{4, 5}` (and replace the incorrect
recommendation slot) or rewrite the task so the bug is localised to one line.

### B4. Task families are confounded with condition (the main design problem)

The 18 tasks are not 18 independent problems. They are **seven underlying
problem families**, each repeated across task types:

| Family | Core problem | Tasks |
|---|---|---|
| F1 | `count_pairs(xs, m, b)`: sum divisible by `m`, at least one `> b` | T01, T05, T16 |
| F2 | `best_pair(xs, k)`: maximum sum at distance `>= k` | T03, T04, T11 |
| F3 | `count_pairs(xs)`: product divisible by 26 | T02, T09, T15 |
| F4 | `count_pairs(xs)`: product ends with exactly two zeros | T06, T14 |
| F5 | `solve(pairs)`: choose one per pair, sum not divisible by 3 | T07, T12, T17 |
| F6 | `count_subarrays(xs, k)`: contiguous sum divisible by `k` | T08 |
| F7 | `solve(triples, k)`: choose one per triple, sum not divisible by `k` | T10, T18 |

Consequences:

1. **Each participant sees the same problem up to three times.** Task random
   intercepts do not remove this: the repeats have different task IDs, so the
   model treats them as independent even though they share content and answer.
2. **Within a participant, some families sit entirely in one condition.** In the
   base assignment:
   - F5 (T07, T12, T17) is **entirely static**;
   - F7 (T10, T18) is **entirely adaptive**;
   - F2 (T03, T04) and F3 (T02, T15) each have **two tasks in `none`**.
   Rotations move whole families together, so this is not repaired by rotation
   within a participant. Across participants it averages out, but with about ten
   participants per rotation the condition contrast is partly a family contrast.
3. **Learning transfers between trials.** Once a participant has solved
   `best_pair` once, the identify/check/select variants are no longer independent
   observations. This inflates accuracy and shortens decision time in whichever
   condition is seen later.

A clean fix exists without writing 18 unrelated tasks: make the family a
**crossed factor** (6 families × 3 task types), and assign the three typed
variants of each family to the three different conditions. Then every
participant sees every family in every condition, so family content cannot be
confounded with condition, and condition contrasts are estimated within family.

## 3. Major issues

### M1. Four of nine incorrect recommendations are artificial

`T13`, `T15`, `T17`, `T18` are `source: "perturbed_model"`; all `select_impl`
incorrect recommendations are perturbations. The proposal permits this, but the
sensitivity analysis that excludes them leaves **14 tasks and only 5 incorrect
recommendations**. In practice the `select_impl` incorrect arm would test
reactions to hand-made advice, not to model advice. Collect additional samples
for the three `select_impl` slots (and one `check_spec`) as recommended in
`llm_recommendations_report.md` §10, or accept the limitation explicitly.

### M2. No archived model hash or revision

Every task has `model_hash: null` and `model_revision: null`. The proposal
promises an archived artifact hash. Fill both for all model-sourced and
perturbed items, and record the exact prompt and generation parameters.

### M3. Documentation disagrees with the task files

`benchmark-spec.md` §2.2 lists different difficulties and base conditions:

| Task | `benchmark-spec.md` | Task file / `design.json` |
|---|---|---|
| T06 | high | medium |
| T16 | medium | low |
| T18 | low | high |

It also lists T09 as adaptive and T11 as `none`, while `design.json` puts T09
in adaptive and T11 in `none` (this part agrees), but the whole table must be
regenerated from the files, not maintained by hand. `benchmark-spec.md` §7 also
refers to `accepted_equivalence.lines`, while the actual schema is a list of
full answer objects. Fix the documents or generate the tables from JSON.

### M4. Evidence decisiveness is skewed and inconsistently defined

Roughly 11 of 18 evidence blocks are marked `decisive`; all `select_impl`
evidence is a fully decisive execution table. If most verification artifacts
determine the answer outright, the adaptive-versus-static contrast measures
compliance with an answer key rather than the effort of verification. Also, a
single failing test is decisive for "there is a bug" but **not** for "the bug is
on line 5". Define decisiveness explicitly:

- `decisive`: the artifact alone determines the full canonical response,
  including the line for `identify_bug`;
- `partial`: the artifact supports the answer but does not determine it.

Then re-score all 18 evidence blocks and report the distribution. Aim for a
deliberate mix, not an accident.

### M5. Recommendation text is authored, not raw model output

The `structured` answers are frozen model outputs, but the participant-facing
`text` is written by the researcher. That is acceptable, but it must be
documented: the study tests reactions to a rendered recommendation, not to the
model's exact wording. Add a `render_rule` or a note in `annotations`, and keep
the raw output alongside it.

## 4. Minor issues

- **T14 title** says "At least two trailing zeros"; the specification says
  "exactly two". The title is metadata, but it should match the spec.
- **T03 evidence** row 2 (`[5, 1, 4], k=2`) is passed by both A and B, so it does
  not discriminate; row 1 does. Add one more discriminating row if space allows.
- **T18 evidence** row 2 (`[(10, 6, 5)], k=5`) is passed by both A and B; row 1
  discriminates. Same note.
- **T13 recommendation text** says the specification "allows an element to be
  paired with itself", while the prompt says `i < j` (distinct elements). This is
  not a plausible novice misconception; replace it even if T13 is rewritten.
- **T07/T10 evidence** demonstrates wrong output but does not localise the line;
  under the stricter definition in M4 these are `partial`, not `decisive`.
- **No task-level accuracy pilot data exists yet**, so difficulty labels are
  author judgements, not empirical. Keep them descriptive and do not use them in
  the confirmatory model (the proposal already says this).

## 5. Proposed 6-family × 3-type design

Rewrite two tasks so that six families each have exactly one `identify_bug`,
one `check_spec`, and one `select_impl` variant:

- **T08** becomes the `identify_bug` variant of the "exactly two trailing
  zeros" family (replacing the subarray task).
- **T13** becomes the `check_spec` variant of the "choose from triples"
  family (replacing the mod-9 task; its current evidence is already broken).

The six families are then F1, F2, F3, F4, F5, F7. Assign the three typed
variants of each family to the three conditions with the following Latin
square (`none / static / adaptive`):

| Family | `none` | `static` | `adaptive` |
|---|---|---|---|
| F1 `count_pairs(m,b)` | T01 I (correct) | T05 C (incorrect) | T16 S (correct) |
| F2 `best_pair` | T04 I (incorrect) | T03 S (correct) | T11 C (correct) |
| F3 product ÷ 26 | T02 C (incorrect) | T09 I (incorrect) | T15 S (incorrect) |
| F4 two trailing zeros | T06 S (correct) | T14 C (correct) | T08 I (incorrect) |
| F5 pairs not ÷ 3 | T12 C (correct) | T17 S (incorrect) | T07 I (correct) |
| F6 triples not ÷ k | T18 S (incorrect) | T10 I (correct) | T13 C (incorrect) |

Check of the resulting design:

- each condition: 6 tasks, 2 per task type, 3 correct / 3 incorrect, and one
  correct + one incorrect per type;
- each family: exactly one task in each condition;
- overall: 9 correct / 9 incorrect, 6 per type, 6/6/6 difficulty (re-check
  T08/T13 after rewriting).

Under this assignment, **family is crossed with condition**: every participant
sees every family in every condition. Add `family` as a fixed effect in a
sensitivity model (six levels; not a random effect with so few levels) and keep
`task` as the random intercept. Repetition still exists — each family is seen
three times, once per type — but it can no longer bias the condition contrast,
and the practice effect is spread evenly across conditions.

If you prefer no repetition at all, the alternative is 18 genuinely distinct
problems. That is cleaner for independence but requires authoring and validating
12 new tasks; the 6-family design reuses the existing content and is the
pragmatic choice for this thesis.

## 6. Fix list before the formal pilot

| Priority | Action | Owner | Done |
|---|---|---|---|
| Blocking | Rewrite T13 evidence; replace its false `[9,9,9]` row | | [ ] |
| Blocking | Resolve T09 line 4 vs 5; update `accepted_equivalence` or task | | [ ] |
| Blocking | Rewrite T08 as F4 `identify_bug`; T13 as F6 `check_spec` | | [ ] |
| Blocking | Replace `design.json` with the 6-family Latin square above | | [ ] |
| Blocking | Two annotators: correctness + plausibility (5-point), Cohen's κ | | [ ] |
| Blocking | Set `status: ready`, `flags.needs_review: false`; seed check passes | | [ ] |
| Major | Collect natural incorrect recs for `select_impl`; or document limitation | | [ ] |
| Major | Fill `model_hash` / `model_revision` / raw output for all items | | [ ] |
| Major | Regenerate `benchmark-spec.md` tables from JSON | | [ ] |
| Major | Define and re-score `decisiveness`; report distribution | | [ ] |
| Minor | Fix T14 title; strengthen T03/T18 evidence rows | | [ ] |
| Minor | Document that recommendation `text` is a researcher rendering | | [ ] |

After these changes, rerun:

```bash
python -m pilot.app.seed --check-only
python -m pilot.analysis.synthetic --out pilot/data/synthetic.csv
python -m pilot.analysis.report --input pilot/data/synthetic.csv \
  --out-dir pilot/data/report-synthetic --n-sim 100
```

The benchmark is frozen only when the seed check passes, the annotation record
is complete, and the design file reproduces the balance table.
