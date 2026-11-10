# Pilot benchmark

This directory holds the fixed task bank used by the experimental prototype.
The bank contains 18 tasks (`T01`–`T18`), six per task type and six per
difficulty level. Each task is adapted from an accepted task in the MBPP review
set, with a documented one-line mutation where the task needs a bug or a
non-compliant implementation. All tasks are in `draft` status until the
two-annotator check and the Qwen recommendation freeze are completed.

The previous hand-authored bank and the six dry-run samples have been removed;
only the current `tasks/` bank is kept.

## Files

```
schema.json                  JSON schema for one task
design.json                  base task-to-condition assignment and rotation settings
tasks/T01.json ... T18       one file per task
benchmark-18-plan.md         composition, balance, and condition assignment
mbpp/build_tasks.py          deterministic MBPP-to-benchmark builder
mbpp/collect_recommendations.py  Qwen collection, scoring, selection, design update
mbpp/annotate.py             blind two-annotator review and annotation merge
mbpp/recommendations_raw.jsonl   archived model samples (created at collection time)
mbpp/recommendations_selection.json  selected recommendation per task (created at collection time)
mbpp/mbpp.jsonl              full MBPP pool
mbpp/review_state.json       accepted/rejected MBPP review decisions
mbpp/selection.json          provenance for the current 18 tasks
```

## Task types and response spaces

| Type | Response | Scoring |
|---|---|---|
| `identify_bug` | `{"has_bug": bool, "line": int\|null}` | `has_bug` must match; when true, `line` must be in `accepted_equivalence` |
| `check_spec` | `{"compliant": bool}` | exact match with `canonical.compliant` |
| `select_impl` | `{"candidate": "A"\|"B"\|"C"\|"D"}` | exact match with `canonical.candidate` |

Line numbers are **1-based and include the `def` line**. The participant
interface must render line numbers next to the code. A bug that spans a region
may accept several line numbers through `accepted_equivalence`.

## Correctness and equivalence

`canonical` is the reference answer. `accepted_equivalence` lists every
structured answer that is scored as correct. The scorer compares the canonical
tuple, never free text. For `identify_bug`, a judgment without a line is scored
as a separate answer from a judgment with a line.

The participant's initial answer, the LLM recommendation, and the final answer
all use the same response widget and the same option labels, so no letter
remapping can occur.

## Evidence

Each task carries a list of verification artifacts. An artifact has:

- `kind`: `test`, `trace`, `spec_case`, or `execution_table`;
- `title`, `body`: rendered in the evidence panel;
- `table`: optional `{columns, rows}` for execution tables;
- `decisiveness`: `partial` or `decisive`, used only in exploratory analysis.

Evidence is derived from the task specification and reference answer, never
from the recommendation. It never states whether the recommendation is correct.
The builder executes every MBPP test (plus task-specific boundary tests) and
writes the observed expected/actual values into the evidence body.

## Recommendations

Recommendations are **not hand-authored**. The bank was collected from the
frozen local `Qwen3-8B-Q8_0.gguf` snapshot through the `llm-manager` gateway
(model id `qwen3-8b-q8_0`). Fifteen samples were collected per task. The raw
outputs, prompts and model hash are archived in
`mbpp/recommendations_raw.jsonl`; the selected answer per task is in
`mbpp/recommendations_selection.json`. `recommendation.correct` is
analysis-only: the API must never expose it to the participant-facing
application or the policy module.

The collection follows proposal-v4 §4:

- thinking disabled with `/no_think`;
- temperature 0.7, top_p 0.8, top_k 20, max 256 tokens, frequency penalty 0;
- fifteen samples per task, parsed into the task's canonical response space;
- one recommendation selected per task so that the bank has nine correct and
  nine incorrect recommendations, three of each per task type;
- raw outputs, prompt text, model name and model SHA-256 archived;
- `design.json` rewritten so each condition has one correct and one incorrect
  recommendation of each type.

The model supplied enough incorrect answers for `identify_bug` (T04, T06) and
`check_spec` (T07, T09, T11), but not for all `select_impl` tasks and not for a
third `identify_bug` task. Four tasks therefore use a documented minimal
perturbation from `mbpp/perturbations.json`: T05, T13, T16 and T18. They carry
`source: "perturbed_model"` and `flags.model_seeded: true`; exclude them from
the sensitivity analysis.

```bash
cd pilot/benchmark/mbpp
python collect_recommendations.py --dry-run           # inspect prompts, no model
python collect_recommendations.py \
    --endpoint http://127.0.0.1:8010/v1/chat/completions \
    --model qwen3-8b-q8_0 \
    --model-path /media/data/models/Qwen3-8B-Q8_0.gguf \
    --samples 15 --write
python collect_recommendations.py --select-only --allow-perturbation --write
```

## Annotating the bank

`mbpp/annotate.py` is the two-annotator review tool. It is blind: it never
renders `recommendation.correct`, the canonical answer, `accepted_equivalence`,
or `flags.model_seeded`. Each annotator records, per task, whether the
recommendation is correct/incorrect/unsure, whether the canonical answer is
defensible, and an optional note. Plausibility (1-5) is rated for incorrect
recommendations only: it asks how plausible the wrong advice is to a novice, not
whether the advice is correct. That correctness judgment is the separate
`correct`/`incorrect`/`unsure` verdict.

The tool opens with a page explaining the three judgments (what the
recommendation verdict means, what plausibility measures and how the 1-5 scale
is anchored, and when to accept or dispute the canonical answer). It is shown
once per annotator state; press `h` to reopen it. The three recorded values are
always displayed in a status line above the key hints, on every page. Tasks are
presented in a random order drawn once per annotator and saved in the state
file, so resuming keeps both the order and the position (`--sorted` falls back
to id order, `--seed N` reshuffles). Every key that changes a rating saves
immediately; `q` or Ctrl+C saves and quits, and rerunning the same command
continues from the same task. Ctrl+C at a `g` or `e` prompt only cancels that
prompt.

```bash
cd pilot/benchmark/mbpp
python annotate.py --annotator AA            # start or resume
python annotate.py --annotator BB --pending  # only unfinished tasks
python annotate.py --annotator AA --sorted   # alphabetical order instead
python annotate.py --stats                   # progress for all state files
python annotate.py --apply --dry-run         # preview merge + Cohen's kappa
python annotate.py --apply --write           # merge and promote to ready
```

Progress is stored in one file per annotator (`annotation_<name>.json`), so the
two reviews never overwrite each other. `--apply` merges both files into
`tasks/*.json`. It writes `status: ready` and `needs_review: false` only when
both annotators completed every task, agreed with the file's correctness label,
accepted the canonical answer, and rated plausibility for every incorrect
recommendation. Following proposal-v4, an incorrect recommendation is retained
only if its mean plausibility is at least 3 and neither rating is below 2;
violations are blocking. Disagreements are listed; `--force` overrides the check
and should only be used with a documented note.

Run `build_tasks.py --write` **before** annotating: it recreates the task files
from scratch, resets annotations to `null`, and returns every task to `draft`.

## Design and balance

`design.json` gives each task a base condition index:

- `0` = no verification
- `1` = static verification
- `2` = adaptive verification

The realised condition for rotation `r` is `(base + r) % 3`. With three
rotations, every task appears once in every condition. The collection script
pairs one correct and one incorrect task of each type per condition, so each
condition contains six tasks (two per type) with a 3/3 correctness split.

## Choosing the code-task set (`mbpp/`)

The current bank uses 18 of the 23 accepted MBPP tasks. The mapping is stored in
`mbpp/selection.json` and in the `annotations.notes` field of each task.
`mbpp/build_tasks.py` is deterministic and can rebuild the bank:

```bash
cd pilot/benchmark/mbpp
python build_tasks.py          # validate mutations and tests
python build_tasks.py --write  # rewrite tasks/ and selection.json
```

Every mutation is declared in `build_tasks.py` with a reason. The builder
executes the original MBPP tests against every generated implementation,
computes the canonical answer, and refuses to write a task set unless every
`select_impl` has exactly one passing candidate and every bug/non-compliance is
reproducible.

`mbpp/review.py` remains the terminal reviewer for the pool:

```bash
cd pilot/benchmark/mbpp
python review.py                 # resume the interactive review
python review.py --filter pending
python review.py --search heapq  # only tasks whose text/code contains a term
python review.py --list          # one-line overview of the whole pool
python review.py --stats         # accepted / rejected / pending counters
python review.py --export selected.jsonl
python review.py --export-md selected.md
```

Each screen shows the prompt, the code with 1-based line numbers, and every
test. Keys: `a` accept, `r` reject, `u` undo, `j`/`k` next/previous task,
`space` next page, `g` go to id, `/` search, `f` cycle filter
(all/pending/accepted/rejected), `e` edit a note, `q` quit. Decisions are
written to `review_state.json` (resumable; the cursor is saved too), notes
travel with the export, and `--export` writes the accepted tasks as a JSONL
subset in the original MBPP format.

## Adding or changing tasks

1. Add or edit the corresponding entry in `mbpp/build_tasks.py`.
2. Run `python build_tasks.py`; fix any mutation that does not fail the tests.
3. Run `python build_tasks.py --write` to regenerate the task files and
   `selection.json`.
4. Run the collection script to refresh recommendations and `design.json`.
5. Set `status` to `ready` only after the two-annotator check; leave
   `flags.needs_review` true until then.

Validate all task files with:

```bash
python -m pilot.app.seed --check-only
```
