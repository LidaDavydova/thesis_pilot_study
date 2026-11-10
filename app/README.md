# Pilot prototype

FastAPI backend, vanilla HTML/JS participant interface, and a Streamlit
researcher dashboard. The participant interface is deliberately plain: it needs
precise focus and dwell events, which are easier to control without a
front-end framework.

## Install and run

From the repository root:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r pilot/app/requirements.txt
python -m pilot.app.seed --check-only
python -m pilot.app.seed --init-db
uvicorn pilot.app.main:app --reload --port 8000
```

Open <http://localhost:8000>. The welcome screen accepts an optional participant
code. Leave it blank to receive an anonymous code. Sessions are local to the
SQLite database and can be resumed from the same browser.

For a dry run that must not touch the research database:

```bash
PILOT_DB=pilot/data/dry-run.db uvicorn pilot.app.main:app --port 8001
```

The dry-run checkbox in the welcome screen only changes the wording and the
completion message; it does not delete records. Use a separate database file for
any technical dry run.

## Researcher dashboard

```bash
streamlit run pilot/app/dashboard.py
```

The dashboard reads the SQLite database directly. It is read-only except for the
optional "Build calibration report" button, which writes a CSV export and report
artifacts under `pilot/data/`.

## Export

The analysis pipeline expects the CSV export, not the raw SQLite tables:

```bash
curl -H "X-Admin-Token: dev-token" \
  "http://localhost:8000/api/admin/export?format=csv" \
  -o pilot/data/export.csv
```

The export contains one row per planned trial, including trials that were never
started. Filter on `state == "final_submitted"` before analysis; the analysis
loader does this automatically.

`GET /api/admin/sessions` and `GET /api/admin/summary` provide quick JSON views.
Set `PILOT_ADMIN_TOKEN` to a real secret outside local development.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `PILOT_BENCHMARK_DIR` | `pilot/benchmark` | Task and design files |
| `PILOT_DATA_DIR` | `pilot/data` | Database and exports |
| `PILOT_DB` | `pilot/data/pilot.db` | SQLite file |
| `PILOT_TAU` | `50` | Adaptive escalation threshold |
| `PILOT_EXAMINATION_CUTOFF_MS` | `3000` | Examined-panel dwell cutoff |
| `PILOT_FOCUS_TOTAL_MS` | `10000` | Cumulative focus-loss exclusion |
| `PILOT_FOCUS_SINGLE_MS` | `30000` | Single focus-loss exclusion |
| `PILOT_ADMIN_TOKEN` | `dev-token` | Admin endpoint token |

The values are provisional. Freeze the calibrated values before the main
experiment and record them in the preregistration.

## Trial states

`pending` → `task_shown` → `initial_submitted` → `recommendation_shown` →
`final_submitted`.

The initial answer and confidence are stored before the recommendation is
revealed. The final endpoint never returns correctness. The next trial index and
block/session completion flags are returned instead.

## Conditions

- `none`: a recommendation is shown, but no verification is available.
- `static`: verification is always available.
- `adaptive`: verification is available only when confidence is below tau.

The disabled-evidence wording is identical in `none` and in the withheld branch
of `adaptive`, so the participant cannot infer the condition from the message.

## Data files

- `pilot/data/pilot.db` — sessions, trials, events.
- `pilot/data/export.csv` — analysis export.
- `pilot/data/report/` — calibration report and artifacts.

Back up the SQLite file after each data-collection day. Do not edit it by hand.
