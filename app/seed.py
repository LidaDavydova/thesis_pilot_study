"""Benchmark validation, database initialisation, and development helpers."""

from __future__ import annotations

import argparse
import json
import sys

from . import benchmark, conditions, config, db


def check() -> int:
    tasks = benchmark.load_tasks()
    design = benchmark.load_design()
    summary = benchmark.benchmark_summary(tasks)
    print("Benchmark summary")
    print(json.dumps(summary, indent=2))
    print()
    print("Design checks")
    warnings = conditions.validate_design_balance(tasks, design)
    for warning in warnings:
        print(f"  - {warning}")

    errors: list[str] = []
    if len(tasks) % 3 != 0:
        errors.append("The number of ready tasks must be divisible by three.")
    missing = [task["id"] for task in tasks if task["id"] not in design["base_assignment"]]
    if missing:
        errors.append(f"Tasks missing from design.json: {', '.join(missing)}")
    extra = [
        task_id
        for task_id in design["base_assignment"]
        if task_id not in {task["id"] for task in tasks}
    ]
    if extra:
        print(f"  - design.json contains tasks that are not ready: {', '.join(extra)}")

    if tasks and len(tasks) % 6 == 0:
        for rotation in range(3):
            for condition in config.CONDITIONS:
                plan = conditions.build_plan(
                    tasks,
                    design,
                    rotation=rotation,
                    order_code="ABC",
                    session_id="check",
                )
                block = [item for item in plan if item["condition"] == condition]
                if len(block) != len(tasks) // 3:
                    errors.append(
                        f"Rotation {rotation}, {condition}: unexpected block size"
                    )

    if errors:
        print()
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print()
    print("Benchmark is structurally valid.")
    if any(task.get("flags", {}).get("needs_review") for task in tasks):
        print("Note: at least one task still has flags.needs_review = true.")
    return 0


def init_db() -> int:
    db.init_db()
    print(f"Initialised database at {config.DB_PATH}")
    return 0


def demo_session() -> int:
    db.init_db()
    tasks = benchmark.load_tasks()
    design = benchmark.load_design()
    sequence = conditions.assign_sequence(db.count_sessions("demo"))
    session_id = "ses_demo_" + __import__("uuid").uuid4().hex[:8]
    plan = conditions.build_plan(
        tasks,
        design,
        rotation=sequence["rotation"],
        order_code=sequence["condition_order"],
        session_id=session_id,
    )
    db.create_session(
        session_id=session_id,
        participant_code=f"DEMO-{session_id[-6:].upper()}",
        mode="demo",
        sequence_id=sequence["sequence_id"],
        rotation=sequence["rotation"],
        condition_order=sequence["condition_order"],
        plan=plan,
    )
    print(f"Created demo session {session_id} ({sequence['sequence_id']})")
    print("Open http://127.0.0.1:8000/ and resume the session from the welcome screen.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true", help="validate the benchmark")
    parser.add_argument("--init-db", action="store_true", help="create the SQLite database")
    parser.add_argument("--demo-session", action="store_true", help="create a demo session")
    args = parser.parse_args()

    if args.check_only:
        return check()
    if args.init_db:
        return init_db()
    if args.demo_session:
        return demo_session()
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
