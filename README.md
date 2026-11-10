# Pilot package

This directory contains the calibration pilot for the thesis proposal. It has
two tracks:

1. **Technical dry run** (November 2026): 3–5 colleagues test the interface with
   six tasks. It produces bug reports only. No consent, recording, trial data, or
   research analysis.
2. **Formal calibration pilot** (January 2027): 12 participants complete the
   full 18-task benchmark under all three conditions. It calibrates tau, the
   evidence-examination cutoff, variance components, and the high-confidence
   safety projection. Pilot participants are disjoint from the main sample and
   pilot data are excluded from main analyses.

## Quick start

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r pilot/app/requirements.txt
pip install -r pilot/analysis/requirements.txt

python -m pilot.app.seed --check-only
python -m pilot.app.seed --init-db
uvicorn pilot.app.main:app --port 8000
```

Open <http://localhost:8000>. The researcher dashboard is separate:

```bash
streamlit run pilot/app/dashboard.py
```

Synthetic pipeline smoke test:

```bash
python -m pilot.analysis.synthetic --out pilot/data/synthetic.csv
python -m pilot.analysis.report --input pilot/data/synthetic.csv \
  --out-dir pilot/data/report-synthetic --n-sim 100
```

API smoke test (uses a temporary database, not `pilot/data`):

```bash
python pilot/tests/test_api_smoke.py
```

## Directory map

```
pilot/
  README.md                  this file
  protocol.md                formal pilot protocol
  dry-run-plan.md            technical dry-run plan
  benchmark-spec.md          18-task benchmark specification
  prototype-spec.md          application and measurement specification
  session-script.md          participant-facing session script
  checklist.md               pre-flight and run-day checklist
  report-template.md         human-readable calibration report template
  preregistration-values.md  values and rules to freeze
  benchmark/
    schema.json              task JSON Schema
    design.json              counterbalancing design
    tasks/T01..T18.json      task files (18 tasks, draft status)
    benchmark-18-plan.md     composition and balance plan
    README.md                task-authoring notes
  app/
    main.py                  FastAPI application
    static/                  participant interface
    dashboard.py             Streamlit researcher dashboard
    seed.py                  validation, DB init, demo session
    README.md                run and configuration notes
  analysis/
    schema.py                export loader
    synthetic.py             synthetic data generator
    calibrate_tau.py         tau calibration
    calibrate_examination.py dwell cutoff calibration
    variance_components.py   planning variance components
    safety_projection.py     high-confidence blind-spot projection
    precision_simulation.py  N and precision check
    report.py                full report builder
    README.md                pipeline commands
  tests/
    test_api_smoke.py        end-to-end API smoke test
  data/                      local database, exports, reports (not tracked)
```

## Current status

- The FastAPI prototype, participant interface, database, and admin export are
  implemented and passed an end-to-end smoke test with six sample tasks.
- The full 18-task bank exists (`T01`–`T18`), adapted from MBPP. All tasks are
  still `draft`; the two-annotator review and recommendation freeze must be
  completed before the formal pilot.
- The analysis pipeline runs end to end on synthetic data. It has not yet been
  run on real pilot data.
- Tau, the examination cutoff, and the focus-loss thresholds are provisional
  until the formal pilot.

## What must be decided before data collection

- **Ethics.** Confirm the ethics status for the formal pilot in writing before
  recruiting participants. The proposal states that approval is required before
  any pilot or main data collection. The technical dry run is designed to avoid
  research data, but that does not replace an ethics decision for the formal
  pilot.
- **Benchmark.** Complete the two-annotator review of the 18-task set, resolve
  every `draft` task, and run the task-quality checks.
- **Compensation and recruitment.** Decide how participants are recruited and
  compensated, and record it in the protocol.
- **Data protection.** Decide where the SQLite database and exports live, who
  can access them, and when they are deleted.

## Timeline

| Period | Work |
| --- | --- |
| November 2026 | Author and review the 18-task benchmark; technical dry run |
| December 2026 | Finalise prototype; fix dry-run bugs |
| November 2026 – January 2027 | Ethics decision, formal pilot, calibration, preregistration |
| February 2027 | Main experiment |
| March 2027 | Main analysis |
| By 15 May 2027 | Thesis submission |

## Related documents

- `../proposal-v4.tex` — thesis proposal and design commitments.
- `../references.bib` — bibliography.
- `benchmark/README.md` — task schema and scoring.
- `analysis/README.md` — pipeline and calibration rules.
