# Technical dry-run plan

**Purpose:** find interface and benchmark defects before the formal calibration
pilot.  
**When:** November 2026.  
**Who:** 3–5 colleagues with basic Python knowledge.  
**Duration:** 30–40 minutes per person.  
**Data:** bug reports only. No consent, recording, trial data, or research
analysis.

## 1. What the dry run is and is not

It **is**:

- a usability and technical test of the participant interface;
- a check that all three task types render and can be answered;
- a check that the evidence panel, timers, focus tracking, resume, and export
  work;
- a source of concrete bug reports and wording fixes.

It is **not**:

- a pilot study;
- a test of the research hypotheses;
- a source of calibration estimates;
- a substitute for ethics approval for the formal pilot.

Use a separate database file so no dry-run record can be mistaken for pilot
data:

```bash
PILOT_DB=pilot/data/dry-run.db uvicorn pilot.app.main:app --port 8001
```

Delete `pilot/data/dry-run.db` after the debrief and bug triage.

## 2. Participants

Recruit 3–5 colleagues who:

- can read basic Python;
- have not seen the benchmark tasks;
- are comfortable thinking aloud;
- are not members of the main study sample.

Do not collect demographic or research data. A name for scheduling is enough;
do not put it in the application.

## 3. Session outline

| Stage | Time | Activity |
| --- | --- | --- |
| Welcome | 3 min | Explain that this is a interface test, not a study; ask for think-aloud |
| Demo | 3 min | Show one practice task and the evidence panel |
| Tasks | 20–25 min | Six tasks, one at a time, think-aloud |
| Debrief | 5–10 min | Confusing wording, missing feedback, browser issues |

### 3.1 Welcome text

> Thanks for helping test the interface. This is a technical dry run, not a
> study. I am testing the software, not you. Please think aloud: say what you
> are looking for, what you expect to happen, and where you get stuck. There are
> no right or wrong answers for this session, and I will not keep your answers
> as research data. You can stop at any time.

### 3.2 Tasks

Use the six sample tasks `T01`–`T06` in the `static` condition. The aim is
coverage, not balance:

- `T01` identify_bug, low, correct recommendation;
- `T02` check_spec, medium, incorrect recommendation;
- `T03` select_impl, medium, correct recommendation;
- `T04` identify_bug, medium, incorrect recommendation;
- `T05` check_spec, low, incorrect recommendation;
- `T06` select_impl, high, correct recommendation.

If the interface supports it, run at least one task in `none` and one in
`adaptive` to check the disabled-evidence wording. Do not tell the participant
which condition is which.

### 3.3 Observation prompts

Use neutral prompts:

- “What are you looking at now?”
- “What do you expect that button to do?”
- “What would you do next?”
- “Was that message clear?”
- “Did anything feel slow or broken?”

Do not defend the design or explain the intended answer during the task. Note
the issue and move on.

## 4. Bug log

Record every issue in the table below. Take a screenshot where useful. Do not
record the participant's answers as research data; the bug report should contain
only the interface problem.

| ID | Severity | Area | Steps to reproduce | Expected | Actual | Browser/device | Screenshot |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DR-01 | blocker / major / minor / wording | welcome / task / confidence / recommendation / evidence / final / break / completion / export | | | | | |

Severity:

- **Blocker:** cannot complete the session or data are lost.
- **Major:** task or evidence cannot be completed as intended; timing or focus
  data are wrong.
- **Minor:** layout, wording, or navigation problem with a workaround.
- **Wording:** confusing instruction or label; no functional failure.

## 5. Specific checks

### 5.1 Interface

- [ ] Welcome screen loads; blank participant code creates a session.
- [ ] Practice trials explain the interface without revealing the hypothesis.
- [ ] All three task types render code with correct line numbers.
- [ ] Bug line selector only appears for `identify_bug`.
- [ ] Candidate cards only appear for `select_impl`.
- [ ] Confidence slider starts at a neutral value and can be changed with the
      keyboard.
- [ ] Recommendation appears only after confidence is submitted.
- [ ] Evidence panel opens and closes; disabled wording is identical in `none`
      and `adaptive` withheld.
- [ ] Final screen re-shows the task and recommendation.
- [ ] Break screen appears between conditions.
- [ ] Completion questionnaire submits.
- [ ] Resume works after a page reload.

### 5.2 Timing and focus

- [ ] Decision time starts when the task is shown.
- [ ] Evidence active time increases only while the panel is open and the page
      is focused.
- [ ] Switching tabs or minimising the window increases focus-loss time.
- [ ] Blur intervals are recorded.
- [ ] Interaction count increases on scroll or click in the panel.
- [ ] Timestamps are plausible and monotonic.

### 5.3 Data

- [ ] The session appears in `/api/admin/sessions`.
- [ ] The CSV export contains the trial with the expected state.
- [ ] `initial_answer`, `confidence`, `recommendation_correct`, `final_answer`,
      and `decision_time_ms` are present.
- [ ] Re-submitting a final answer does not duplicate the trial.
- [ ] The dashboard reads the database.
- [ ] `python -m pilot.analysis.synthetic` and `report` still run.

## 6. Success criteria

The dry run passes if:

- all 3–5 participants complete six tasks without a blocker;
- every task type renders and scores;
- the evidence panel and focus tracking work;
- the export contains the expected rows and columns;
- no data loss after a reload;
- the remaining issues are minor or wording-level.

If a blocker remains, fix it and run one additional dry-run session before the
formal pilot.

## 7. After the session

1. Triage bugs by severity.
2. Fix blockers and majors; retest.
3. Update wording that more than one participant misunderstood.
4. Record decisions that change the prototype or benchmark.
5. Delete the dry-run database.
6. Write a one-page go/no-go note for the formal pilot.

## 8. Ethics note

This plan is designed so that the dry run produces no research data. Do not add
consent, recording, questionnaires, or retained trial data without confirming
that the formal pilot ethics approval covers the change. If in doubt, treat the
session as a pilot and obtain approval first.
