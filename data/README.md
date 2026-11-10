# Data directory

This directory is for local pilot data and generated artefacts. It is intentionally
not a place for source files.

- `dry-run.db`, `pilot.db` and other SQLite files are created when the prototype is
  run. They contain participant-level data and must stay local and be handled
  according to the ethics and data-management rules in `../protocol.md`.
- `synthetic.csv` and `calibration/` / `report/` are generated from synthetic data by
  the analysis pipeline. They are examples for testing the code, **not empirical
  pilot results**.
- Do not commit real participant data, exports, recordings or consent material.
- The formal pilot protocol requires a separate database and a separate data
  directory from any dry run.
