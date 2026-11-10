# Plan for the full 18-task benchmark

The formal pilot and the main experiment use 18 tasks: six per task type, with
nine correct and nine incorrect recommendations. Within each condition each
participant sees six tasks: two of each type, three correct and three incorrect
recommendations, and one correct and one incorrect recommendation per type.

`T01`–`T18` are adapted from 18 accepted MBPP tasks. They are in `draft` status
until the two-annotator check and the Qwen recommendation freeze are finished.
The previous hand-authored bank and the six dry-run samples have been removed.

## Composition

| Type | Tasks |
|---|---|
| `identify_bug` | T01–T06 |
| `check_spec` | T07–T12 |
| `select_impl` | T13–T18 |

Difficulty is distributed evenly across the bank: six low, six medium, six high.

| Task | MBPP id | Type | Difficulty | Status |
|---|---|---|---|---|
| T01 | 9 | identify_bug | medium | draft |
| T02 | 11 | identify_bug | medium | draft |
| T03 | 69 | identify_bug | high | draft |
| T04 | 125 | identify_bug | high | draft |
| T05 | 3 | identify_bug | low | draft |
| T06 | 68 | identify_bug | low | draft |
| T07 | 1 | check_spec | high | draft |
| T08 | 5 | check_spec | high | draft |
| T09 | 6 | check_spec | medium | draft |
| T10 | 12 | check_spec | medium | draft |
| T11 | 56 | check_spec | medium | draft |
| T12 | 175 | check_spec | high | draft |
| T13 | 37 | select_impl | low | draft |
| T14 | 41 | select_impl | low | draft |
| T15 | 126 | select_impl | low | draft |
| T16 | 127 | select_impl | medium | draft |
| T17 | 145 | select_impl | low | draft |
| T18 | 195 | select_impl | high | draft |

Difficulty counts: low T05, T06, T13, T14, T15, T17; medium T01, T02, T09, T10,
T11, T16; high T03, T04, T07, T08, T12, T18. Six each.

## Recommendation composition

The collection script sampled the frozen Qwen3-8B snapshot fifteen times per
task and selected one answer per task so that the bank contains nine correct and
nine incorrect recommendations, three of each per type. The selection is in
`mbpp/recommendations_selection.json`; `recommendation.correct` is
analysis-only.

| Type | Correct recommendations | Incorrect recommendations |
|---|---|---|
| `identify_bug` | T01, T02, T03 | T04, T05, T06 |
| `check_spec` | T08, T10, T12 | T07, T09, T11 |
| `select_impl` | T14, T15, T17 | T13, T16, T18 |

Four tasks (T05, T13, T16, T18) use a documented minimal perturbation from
`mbpp/perturbations.json`; they carry `source: "perturbed_model"` and
`flags.model_seeded: true`.

## Base condition assignment

`design.json` is regenerated after recommendation selection. For each task type,
the three correct and three incorrect tasks are paired, and one pair per type is
assigned to each condition:

| Condition | `identify_bug` | `check_spec` | `select_impl` |
|---|---|---|---|
| none (0) | one correct + one incorrect | one correct + one incorrect | one correct + one incorrect |
| static (1) | one correct + one incorrect | one correct + one incorrect | one correct + one incorrect |
| adaptive (2) | one correct + one incorrect | one correct + one incorrect | one correct + one incorrect |

This gives every condition six tasks, two per type, and a 3/3 correctness split.
Rotating the base condition by `(base + r) % 3` over three rotations makes every
task appear once in every condition. The previous assignment in `design.json`
is stale until the collection script writes the new one.

## Validation checklist for every new task

- [ ] Prompt states the task type and the required response format.
- [ ] Code is syntactically valid Python and line numbers are stable.
- [ ] Canonical answer and accepted-equivalence set are correct.
- [ ] Evidence is derived from the task, not from the recommendation.
- [ ] Evidence never states whether the recommendation is correct.
- [ ] Incorrect recommendation is objectively wrong but plausible to a novice.
- [ ] Two annotators checked correctness and plausibility.
- [ ] `status` is `ready`; `flags.needs_review` is false only after annotation.
