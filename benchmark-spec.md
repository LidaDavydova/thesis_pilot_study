# Benchmark specification

The benchmark is the fixed set of 18 introductory Python tasks used in the
calibration pilot and the main experiment. It is designed so that task type,
recommendation correctness, difficulty, and condition are balanced.

## 1. Task types

### 1.1 `identify_bug`

The participant sees a short function and decides whether it contains a bug. If
yes, they select the line containing the bug.

Response schema:

```json
{"has_bug": true, "line": 3}
```

Canonical answer: `has_bug` plus the accepted line or lines. Line numbers are
1-based and include the `def` line. A response is correct only if `has_bug`
matches and, when a bug is present, the selected line is in the accepted set.

### 1.2 `check_spec`

The participant sees a function and a short specification, and decides whether
the implementation satisfies the specification.

Response schema:

```json
{"compliant": false}
```

Canonical answer: exact boolean. No partial credit.

### 1.3 `select_impl`

The participant sees a specification and four candidate implementations, and
selects the one that satisfies it.

Response schema:

```json
{"candidate": "B"}
```

Canonical answer: the candidate identifier. No partial credit.

## 2. Composition

### 2.1 Balance

- 18 tasks: six per type.
- Nine correct and nine incorrect recommendations.
- Three correct and three incorrect recommendations per type.
- Two tasks per type per condition.
- One correct and one incorrect recommendation per type per condition.

### 2.2 Task table

| Task | Type | Difficulty | Recommendation | Base condition |
| --- | --- | --- | --- | --- |
| T01 | identify_bug | low | correct | none |
| T02 | check_spec | medium | incorrect | none |
| T03 | select_impl | medium | correct | none |
| T04 | identify_bug | medium | incorrect | none |
| T05 | check_spec | low | incorrect | static |
| T06 | select_impl | high | correct | static |
| T07 | identify_bug | medium | correct | static |
| T08 | identify_bug | high | incorrect | static |
| T09 | identify_bug | low | incorrect | adaptive |
| T10 | identify_bug | high | correct | adaptive |
| T11 | check_spec | low | correct | none |
| T12 | check_spec | high | correct | static |
| T13 | check_spec | medium | incorrect | adaptive |
| T14 | check_spec | high | correct | adaptive |
| T15 | select_impl | low | incorrect | none |
| T16 | select_impl | medium | correct | adaptive |
| T17 | select_impl | high | incorrect | static |
| T18 | select_impl | low | incorrect | adaptive |

Base-condition pairs:

- `none`: T01+T04, T02+T11, T03+T15
- `static`: T07+T08, T05+T12, T06+T17
- `adaptive`: T10+T09, T13+T14, T16+T18

The realised condition is `(base + rotation) % 3`, with three rotations. The
within-condition task order is shuffled per session.

## 3. Difficulty

Difficulty is defined by the number of concepts and the ease of checking the
answer, not by how long the code is.

| Level | Anchor |
| --- | --- |
| Low | One concept; the bug or specification violation is visible after one reading; short code |
| Medium | Two interacting concepts; the participant must trace one or two values or compare two conditions |
| High | Multiple concepts or edge cases; the code or specification requires careful tracing; plausible distractors |

Every task type has two low, two medium, and two high tasks across the 18. Do not
change difficulty after the pilot without recording it as a deviation.

## 4. Code and prompts

- Python 3.10-compatible code only.
- No imports beyond the standard library unless the prompt explains them.
- Functions are short: generally 5–15 lines.
- The prompt states the intended behaviour and the response required.
- Code is shown with line numbers; the first line is line 1.
- Avoid decorative comments that give away the answer.
- Avoid constructs that require knowledge outside introductory Python.
- Do not use ambiguous names such as `l`, `O`, or `I`.

## 5. Recommendations

Every task has a recommendation with:

- `text`: participant-facing recommendation;
- `structured`: canonical recommendation answer;
- `correct`: whether the recommendation is correct;
- `source`: `manual_sample`, `manual`, or `model`;
- `model`: model identifier if applicable.

Rules:

- Recommendations are plausible, concise, and written in the same register as a
  helpful assistant.
- Incorrect recommendations are wrong for a substantive reason, not a trivial
  typo.
- An incorrect recommendation must not be so obviously wrong that no participant
  would consider it.
- The recommendation is shown in all three conditions.
- The recommendation text must not mention the experimental condition or the
  adaptive rule.
- Model-generated recommendations are reviewed by a human before use.

## 6. Evidence

Evidence is shown in a panel when verification is available. Supported kinds:

| Kind | Content |
| --- | --- |
| `test` | A small test case, expected output, and observed output |
| `trace` | A step-by-step trace of selected variables |
| `spec_case` | A concrete input that violates or satisfies the specification |
| `execution_table` | A table of inputs, outputs, and pass/fail for candidates |

Each evidence item has:

- `kind`;
- `title`;
- `body` or structured rows;
- `decisiveness`: `partial` or `decisive`.

`decisiveness` is stripped from the participant view. It is used for analysis
and task review only.

Evidence must be sufficient for a careful participant to verify the
recommendation, but it need not be a complete proof. Evidence should not reveal
the condition. Do not include phrases such as “because you were uncertain” or
“the adaptive system”.

## 7. Scoring

| Type | Correctness |
| --- | --- |
| `identify_bug` | `has_bug` matches and the selected line is in `accepted_equivalence.lines` when `has_bug` is true |
| `check_spec` | `compliant` matches the canonical boolean |
| `select_impl` | `candidate` matches the canonical candidate |

Primary outcome is binary final-answer correctness. Do not use partial credit in
the primary analysis. If a task has multiple defensible answers, encode them in
`accepted_equivalence` and have a second reviewer confirm them.

## 8. Authoring and review

1. **Draft.** Write the task, canonical answer, evidence, and recommendation.
2. **Execute.** Run the code and the evidence; confirm the canonical answer.
3. **Ambiguity review.** A second reviewer checks the prompt, code, and
   canonical answer.
4. **Recommendation review.** Confirm correctness, plausibility, and that the
   incorrect recommendation is not a straw man.
5. **Line-number check.** Confirm 1-based line numbers including `def`.
6. **Balance check.** Update `design.json` and run
   `python -m pilot.app.seed --check-only`.
7. **Freeze.** Mark `status: ready` and remove `needs_review` only after both
   reviewers sign off.

Every task file has:

```json
{
  "id": "T01",
  "status": "ready",
  "type": "identify_bug",
  "difficulty": "low",
  "title": "...",
  "prompt": "...",
  "code": "...",
  "response_schema": {},
  "canonical": {},
  "accepted_equivalence": {},
  "evidence": [],
  "recommendation": {},
  "annotations": {},
  "flags": {"needs_review": true}
}
```

The JSON Schema is `benchmark/schema.json`.

## 9. Quality checks before the pilot

- [ ] 18 tasks exist and validate.
- [ ] 6 per type, 3 correct and 3 incorrect per type.
- [ ] 2 per type per condition, 1 correct and 1 incorrect each.
- [ ] All canonical answers verified by execution or a formal check.
- [ ] All incorrect recommendations are plausible.
- [ ] All evidence is consistent with the canonical answer.
- [ ] No task mentions the condition or the adaptive rule.
- [ ] Line numbers are correct and stable.
- [ ] Two reviewers have signed off.
- [ ] `python -m pilot.app.seed --check-only` passes.

## 10. Changes after the pilot

The benchmark is frozen before the main experiment. If a task is discovered to
be broken during the pilot:

- Record the problem and the decision.
- If the task cannot be scored validly, replace it before the main experiment
  and document the replacement in the preregistration.
- Do not change task content after main data collection begins.
- Do not re-balance the benchmark using main results.
