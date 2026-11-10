# Pilot checklist

## A. Before the technical dry run

- [+] 18-task benchmark drafted.
- [ ] `python -m pilot.app.seed --check-only` passes.
- [ ] `node --check pilot/app/static/experiment.js` passes.
- [ ] FastAPI smoke test passes.
- [ ] `PILOT_DB=pilot/data/dry-run.db` set for the dry-run server.
- [ ] Browser and screen ready for think-aloud.
- [ ] Bug-log table prepared.
- [ ] No consent, recording, or trial data will be retained.

## B. After the technical dry run

- [ ] Bugs triaged by severity.
- [ ] Blockers and majors fixed and retested.
- [ ] Wording issues updated.
- [ ] Dry-run database deleted.
- [ ] Go/no-go note written.
- [ ] Any change that would collect research data referred for ethics review.

## C. Before the formal pilot

### C.11 Benchmark

- [ ] 18 tasks exist; `status: ready` for all.
- [ ] Six per type; three correct and three incorrect recommendations per type.
- [ ] Two tasks per type per condition; one correct and one incorrect each.
- [ ] Canonical answers independently checked.
- [ ] Incorrect recommendations are plausible.
- [ ] Evidence is consistent with the canonical answer.
- [ ] Line numbers are 1-based and include `def`.
- [ ] No task mentions the condition or adaptive rule.
- [ ] Second reviewer sign-off recorded.
- [ ] `python -m pilot.app.seed --check-only` passes.

### C.2 Software

- [ ] Fresh virtual environment; dependencies installed.
- [ ] `python -m pilot.app.seed --init-db` run on the pilot database.
- [ ] Application starts without errors.
- [ ] All three task types render.
- [ ] Confidence slider works with keyboard and mouse.
- [ ] Recommendation appears only after confidence.
- [ ] Evidence panel opens, closes, and tracks dwell.
- [ ] Disabled-evidence wording is identical in `none` and adaptive withheld.
- [ ] Break screen appears between blocks.
- [ ] Resume works after reload.
- [ ] Completion questionnaire submits.
- [ ] Admin export works.
- [ ] Dashboard reads the database.
- [ ] Analysis pipeline runs on synthetic data.
- [ ] `PILOT_TAU`, `PILOT_EXAMINATION_CUTOFF_MS`, focus thresholds, and admin token set.
- [ ] Code and configuration frozen; version recorded.

### C.3 Materials

- [ ] Information sheet and consent form printed or available electronically.
- [ ] Session script available.
- [ ] Debrief text available.
- [ ] Compensation ready.
- [ ] Paper/notes for deviations.
- [ ] Contact details for questions.

## D. Run day

### D.1 Setup

- [ ] Server running on the intended database.
- [ ] Fresh browser profile or local storage cleared.
- [ ] Notifications silenced.
- [ ] Screen sharing or observation setup ready, if consented.
- [ ] Backup of the previous database made.

### D.2 Start

- [ ] Consent signed.
- [ ] Participant code assigned.
- [ ] Sequence checked.
- [ ] Practice trials completed.
- [ ] Participant knows they can stop at any time.

### D.3 During

- [ ] Do not answer tasks or explain recommendations.
- [ ] Record start time and any deviations.
- [ ] Watch for interface errors, not for answer correctness.
- [ ] Confirm breaks occur between blocks.
- [ ] Confirm final submission and questionnaire.

### D.4 End

- [ ] Debrief completed.
- [ ] Compensation recorded.
- [ ] Session marked completed.
- [ ] Database backed up.
- [ ] Quick check that the session appears in the export.
- [ ] Notes filed.

## E. After each session

- [ ] Export the session or confirm the row count.
- [ ] Check for missing trials or duplicate submissions.
- [ ] Check decision times and evidence dwell values are plausible.
- [ ] Record any protocol deviation.
- [ ] Do not inspect condition effects until the pilot is complete.

## F. Close-out

- [ ] All 12 participants completed or exclusions documented.
- [ ] Export final CSV.
- [ ] Run `python -m pilot.analysis.report`.
- [ ] Review tau, cutoff, focus exclusion rate, safety projection, precision.
- [ ] Freeze values in `preregistration-values.md`.
- [ ] Archive the database, export, report, and code version.
- [ ] Delete dry-run and temporary files.
- [ ] Confirm pilot data are excluded from main analyses.
- [ ] Record any changes to the main experiment.

## G. Stop rules

Stop and record if:

- the participant withdraws or is distressed;
- the interface prevents valid task presentation;
- data are lost or duplicated;
- the participant cannot see the recommendation or evidence as intended;
- a task has no valid canonical answer;
- the session exceeds the agreed time by a large margin and the participant
  wants to stop.

Do not continue a session with a known data-integrity failure.
