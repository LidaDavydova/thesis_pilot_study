"""Runtime configuration for the pilot prototype.

All values can be overridden with environment variables, which keeps the
threshold and timing rules out of the code and makes the frozen configuration
easy to reproduce.
"""

from __future__ import annotations

import os
from pathlib import Path

PILOT_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = PILOT_DIR.parent

BENCHMARK_DIR = Path(
    os.getenv("PILOT_BENCHMARK_DIR", str(PILOT_DIR / "benchmark"))
)
TASKS_DIR = BENCHMARK_DIR / "tasks"
DESIGN_PATH = BENCHMARK_DIR / "design.json"

DATA_DIR = Path(os.getenv("PILOT_DATA_DIR", str(PILOT_DIR / "data")))
DB_PATH = Path(os.getenv("PILOT_DB", str(DATA_DIR / "pilot.db")))

# Experimental configuration. These are provisional until the formal pilot.
TAU = int(os.getenv("PILOT_TAU", "50"))
EXAMINATION_CUTOFF_MS = int(os.getenv("PILOT_EXAMINATION_CUTOFF_MS", "3000"))
FOCUS_TOTAL_MS = int(os.getenv("PILOT_FOCUS_TOTAL_MS", "10000"))
FOCUS_SINGLE_MS = int(os.getenv("PILOT_FOCUS_SINGLE_MS", "30000"))

ADMIN_TOKEN = os.getenv("PILOT_ADMIN_TOKEN", "dev-token")

CONDITIONS = ("none", "static", "adaptive")
CONDITION_LABELS = {
    "none": "No verification",
    "static": "Static verification",
    "adaptive": "Adaptive verification",
}

# Human-readable condition order codes used by the counterbalancing scheme.
ORDER_CODES = {
    "ABC": ("none", "static", "adaptive"),
    "CBA": ("adaptive", "static", "none"),
}
