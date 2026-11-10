# Prototype specification

## 1. Architecture

```
Browser (HTML/CSS/JS)
        |
        | fetch JSON
        v
FastAPI application  --->  SQLite (sessions, trials, events)
        |
        +--> benchmark JSON files
        |
Researcher dashboard (Streamlit, read-only)
        |
        +--> calibration analysis (Python)
```

The participant interface is plain HTML, CSS, and JavaScript. It does not use a
front-end framework because the study needs precise control over focus, visibility,
and evidence-panel dwell events.

## 2. Components

| Component | Path | Responsibility |
| --- | --- | --- |
| API | `pilot/app/main.py` | Session lifecycle, trial state machine, export |
| Database | `pilot/app/db.py` | SQLite schema and helpers |
| Benchmark loader | `pilot/app/benchmark.py` | Load, validate, public views, scoring |
| Condition logic | `pilot/app/conditions.py` | Counterbalancing, tau policy, timing rules |
| Configuration | `pilot/app/config.py` | Paths and provisional thresholds |
| Participant UI | `pilot/app/static/` | Task, confidence, recommendation, evidence, final |
| Dashboard | `pilot/app/dashboard.py` | Sessions, trials, calibration view |
| Seed/validation | `pilot/app/seed.py` | Benchmark check, DB init, demo session |

## 3. Session and trial lifecycle

### 3.1 Session creation

`POST /api/session` accepts an optional participant code and dry-run flag. The
server:

1. assigns the next sequence in round-robin order;
2. computes rotation and condition order;
3. builds the 18-trial plan;
4. creates the session and one row per planned trial;
5. returns the session identifier and first trial.

If a participant code already exists, the API returns the existing session for
resume rather than creating a duplicate.

### 3.2 Trial states

```
pending
  -> task_shown
  -> initial_submitted
  -> recommendation_shown
  -> final_submitted
```

The state transitions are enforced server-side. The initial answer and
confidence must be stored before the recommendation is revealed. Final
correctness is never returned to the participant.

### 3.3 Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Health check |
| `POST` | `/api/session` | Create or resume a session |
| `GET` | `/api/session/{sid}` | Session status and progress |
| `GET` | `/api/session/{sid}/trial/{index}` | Public trial view for resume |
| `POST` | `/api/session/{sid}/trial/{index}/initial` | Initial answer |
| `POST` | `/api/session/{sid}/trial/{index}/confidence` | Confidence rating |
| `POST` | `/api/session/{sid}/trial/{index}/event` | Browser/evidence event |
| `POST` | `/api/session/{sid}/trial/{index}/final` | Final answer and timing metrics |
| `POST` | `/api/session/{sid}/complete` | Questionnaire and completion |
| `GET` | `/api/admin/export?format=csv\|json` | Analysis export |
| `GET` | `/api/admin/sessions` | Session list |
| `GET` | `/api/admin/summary` | Quick summary |

Admin endpoints require `X-Admin-Token` or `?token=...`. The default
`dev-token` is for local development only.

## 4. Conditions and policy

```
none      -> evidence_available = false, policy_decision = not_applicable
static    -> evidence_available = true,  policy_decision = always
adaptive  -> evidence_available = confidence < tau
             policy_decision = offered / withheld
```

The recommendation is shown in all conditions. The disabled-evidence message is
identical for `none` and `adaptive` withheld.

## 5. Measurement definitions

### 5.1 Decision time

`decision_time_ms` is the interval from the server timestamp when the task is
shown (`started_at`) to the final submission. It includes reading, initial
answer, confidence, recommendation, evidence inspection, and final answer.

### 5.2 Evidence active time

`evidence_active_ms` increases only when:

- the evidence panel is open; **and**
- the page is visible; **and**
- the window is focused.

It stops when the panel closes, the page is hidden, or the window loses focus.
The client sends cumulative values at the final submission; the server stores
them. The client also sends focus-loss and blur metrics.

### 5.3 Evidence examined

A trial is examined if:

`evidence_active_ms >= cutoff_ms` **or** `interaction_count > 0`.

The cutoff is provisional 3000 ms and is calibrated in the pilot.

### 5.4 Focus loss

- `focus_lost_ms`: cumulative time the page is hidden or the window is blurred.
- `max_blur_ms`: longest single hidden/blurred interval.
- `excluded_from_timing`: true if cumulative > 10 s or single > 30 s.

The exclusion rule is provisional and frozen after the pilot.

### 5.5 Answer keys

Answers are normalised to canonical JSON and compared by sorted key:

- `initial_key`;
- `final_key`;
- `recommendation_key`.

`A_neq_L` is true when `initial_key != recommendation_key`.

## 6. Database

### 6.1 `sessions`

- `session_id`, `participant_code`, `mode`;
- `sequence_id`, `rotation`, `condition_order`;
- `plan_json`;
- timestamps and status;
- `questionnaire_json`.

### 6.2 `trials`

- session and trial identity;
- task, condition, state;
- initial answer, confidence, policy decision;
- evidence availability and examination;
- recommendation text/structured answer/correctness;
- final answer and answer-change flag;
- decision time, evidence active time, focus metrics;
- exclusion flag and reason.

### 6.3 `events`

- session, trial, event type;
- client time and server time;
- JSON payload.

Events are append-only. They support audit and timing diagnostics; the primary
analysis uses the trial table.

## 7. Export

The CSV export joins sessions and trials and adds derived fields:

- task type and difficulty;
- initial, final, and recommendation keys;
- correctness flags;
- `A_neq_L`, `final_equals_recommendation`;
- `influence`, `harmful_adoption`, `missed_correction`;
- decision time in seconds;
- evidence active time in seconds.

The export includes planned but unstarted trials. Analysis filters
`state == "final_submitted"`.

## 8. Resume and failure handling

- The browser stores the session identifier in `localStorage`.
- On reload, the UI calls the session status endpoint and resumes at the first
  incomplete trial.
- Re-submitting an initial or final answer is rejected if the state has already
  advanced.
- Duplicate final submissions do not create duplicates because trials are
  unique by `(session_id, trial_index)`.
- If the server is unavailable, the UI shows an error and does not silently
  discard the current answer.
- The researcher can export at any time; incomplete sessions remain visible.

## 9. Security and privacy

- Participant codes are study codes, not names.
- No audio or video recording.
- Admin endpoints are token-protected; change the default token outside local
  development.
- The database and exports stay on the researcher's encrypted device.
- CORS is open for local development; restrict it for any networked deployment.
- Do not expose the FastAPI server to the public internet without HTTPS and
  authentication.

## 10. Browser requirements

- Current Chrome, Firefox, Edge, or Safari.
- JavaScript enabled.
- Local storage enabled for resume.
- A screen large enough to show code and response widgets without horizontal
  scrolling; the layout is responsive but the study is designed for desktop.
- Do not use private browsing if resume is needed.

## 11. Testing

### 11.1 Automated smoke test

- `python -m pilot.app.seed --check-only` validates the benchmark.
- FastAPI TestClient exercises session creation, all trial endpoints, export,
  and completion.
- `node --check pilot/app/static/experiment.js` checks JavaScript syntax.
- `python -m pilot.analysis.synthetic` then `report` checks the analysis
  pipeline.

### 11.2 Dry-run checks

See `dry-run-plan.md` for the manual checklist: task rendering, line numbers,
confidence, recommendation, evidence panel, focus tracking, resume, export, and
dashboard.

## 12. Deployment for the pilot

- Run locally on the researcher's machine or a trusted local network.
- Use a dedicated database file.
- Back up the database after each session.
- Record the software version and configuration values in the session log.
- Freeze code changes during data collection; record any hotfix as a deviation.
