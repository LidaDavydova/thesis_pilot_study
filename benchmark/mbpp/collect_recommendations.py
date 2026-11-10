#!/usr/bin/env python3
"""Collect frozen Qwen3-8B recommendations for the adapted benchmark.

The script follows proposal-v4 §4:

* one offline model snapshot, thinking disabled via ``/no_think``;
* several samples per task, parsed into the task's canonical response space;
* one recommendation selected per task so that the bank has nine correct and
  nine incorrect recommendations, three of each per task type;
* raw outputs and the model hash are archived;
* recommendation correctness is stored for analysis only.

It does not run verification or expose correctness to participants.

Typical use on a machine with a llama.cpp OpenAI-compatible server:

    python collect_recommendations.py \
        --endpoint http://127.0.0.1:8080/v1/chat/completions \
        --samples 5 \
        --model-path /media/data/models/Qwen3-8B-Q8_0.gguf \
        --write

To prepare prompts without a server:

    python collect_recommendations.py --dry-run

To re-select recommendations from an existing raw file:

    python collect_recommendations.py --select-only --write
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
BENCHMARK = HERE.parent
TASKS = BENCHMARK / "tasks"
RAW = HERE / "recommendations_raw.jsonl"
SELECTION = HERE / "recommendations_selection.json"
DESIGN = BENCHMARK / "design.json"

SYSTEM_PROMPT = """You are a careful reviewer of introductory Python solutions.

You will receive exactly one task. Read the task description, the specification,
and the code. Do not assume that the code is correct. Check every requirement,
including boundary conditions and cases that are easy to overlook.

Return exactly one JSON object matching the requested schema.
Do not use Markdown, code fences, comments, or explanations.
Do not write anything before or after the JSON.
Do not mention uncertainty."""


def numbered_code(code: str) -> str:
    return "\n".join(f"{index:>3} | {line}" for index, line in enumerate(code.splitlines(), start=1))


def build_prompt(task: dict) -> str:
    kind = task["type"]
    if kind == "identify_bug":
        body = f"""Task type: identify_bug

Task description:
{task['prompt']}

Code:
The numbers at the start of each line are line numbers. Use them in your answer.

{numbered_code(task['code'])}

Question:
Does this code contain a bug with respect to the task description?
If it does, give the line number of the faulty statement. If the bug spans
several lines, give the first line of the faulty statement.
If it does not, set "line" to null.

Return exactly one JSON object:
{{"bug_present": <true|false>, "line": <integer|null>}}"""
    elif kind == "check_spec":
        body = f"""Task type: check_spec

Specification:
{task['prompt']}

Code:
{task['code']}

Question:
Does the code satisfy every requirement in the specification for all valid
inputs? Answer COMPLIANT if it does; otherwise answer NOT_COMPLIANT.

Return exactly one JSON object:
{{"verdict": "COMPLIANT"}}
or
{{"verdict": "NOT_COMPLIANT"}}"""
    else:
        blocks = []
        for candidate in task["candidates"]:
            blocks.append(f"{candidate['id']}:\n{candidate['code']}")
        body = f"""Task type: select_implementation

Specification:
{task['prompt']}

Candidate implementations:

{chr(10).join(blocks)}

Question:
Which candidate satisfies every requirement in the specification for all valid
inputs? Return only the candidate letter.

Return exactly one JSON object:
{{"choice": "A"}}
Allowed values: "A", "B", "C", "D"."""
    return body + "\n\n/no_think"


def parse_json_object(text: str) -> dict:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"no JSON object in output: {text!r}")
    return json.loads(cleaned[start : end + 1])


def normalize(kind: str, raw: dict) -> dict:
    if kind == "identify_bug":
        if "bug_present" in raw:
            has_bug = raw["bug_present"]
        elif "has_bug" in raw:
            has_bug = raw["has_bug"]
        else:
            raise ValueError(f"identify_bug output lacks bug_present: {raw!r}")
        line = raw.get("line")
        if has_bug and not isinstance(line, int):
            raise ValueError(f"bug is present but line is not an integer: {raw!r}")
        if not has_bug:
            line = None
        return {"has_bug": bool(has_bug), "line": line}
    if kind == "check_spec":
        if "verdict" in raw:
            verdict = str(raw["verdict"]).strip().upper()
            if verdict not in {"COMPLIANT", "NOT_COMPLIANT"}:
                raise ValueError(f"unknown verdict: {raw!r}")
            return {"compliant": verdict == "COMPLIANT"}
        if "compliant" in raw and isinstance(raw["compliant"], bool):
            return {"compliant": raw["compliant"]}
        raise ValueError(f"check_spec output lacks verdict: {raw!r}")
    if "candidate" in raw:
        choice = str(raw["candidate"]).strip().upper()
    elif "choice" in raw:
        choice = str(raw["choice"]).strip().upper()
    else:
        raise ValueError(f"select_impl output lacks choice: {raw!r}")
    if choice not in {"A", "B", "C", "D"}:
        raise ValueError(f"unknown candidate: {raw!r}")
    return {"candidate": choice}


def is_correct(task: dict, answer: dict) -> bool:
    return answer in task["accepted_equivalence"]


def call_endpoint(endpoint: str, model: str, prompt: str, args) -> dict:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": args.temperature,
        "top_p": args.top_p,
        "top_k": args.top_k,
        "max_tokens": args.max_tokens,
        "frequency_penalty": 0,
        "stream": False,
    }
    headers = {"Content-Type": "application/json"}
    if args.api_key:
        headers["Authorization"] = f"Bearer {args.api_key}"
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise SystemExit(f"endpoint error: {exc}") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_tasks() -> list[dict]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(TASKS.glob("T*.json"))]


def collect(args, tasks: list[dict] | None = None) -> None:
    tasks = tasks or load_tasks()
    if args.limit:
        tasks = tasks[: args.limit]
    RAW.parent.mkdir(parents=True, exist_ok=True)
    model_hash = sha256_file(Path(args.model_path)) if args.model_path else None
    total = 0
    with RAW.open("a", encoding="utf-8") as handle:
        for task in tasks:
            prompt = build_prompt(task)
            for sample in range(1, args.samples + 1):
                print(f"{task['id']} sample {sample}/{args.samples} ...", flush=True)
                response = call_endpoint(args.endpoint, args.model, prompt, args)
                choice = response["choices"][0]["message"].get("content", "")
                record = {
                    "task_id": task["id"],
                    "type": task["type"],
                    "sample": sample,
                    "model": args.model,
                    "model_hash": model_hash,
                    "prompt": prompt,
                    "response": choice,
                    "raw": response,
                    "structured": None,
                    "correct": None,
                }
                try:
                    answer = normalize(task["type"], parse_json_object(choice))
                    record["structured"] = answer
                    record["correct"] = is_correct(task, answer)
                except Exception as exc:
                    record["parse_error"] = f"{type(exc).__name__}: {exc}"
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                handle.flush()
                total += 1
    print(f"wrote {total} samples to {RAW}")


def load_raw() -> list[dict]:
    if not RAW.exists():
        raise SystemExit(f"raw recommendation file not found: {RAW}")
    records = []
    for line in RAW.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def load_perturbations() -> dict[str, dict]:
    path = HERE / "perturbations.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {key: value["structured"] for key, value in data.items() if "structured" in value}


def choose_answers(tasks: list[dict], records: list[dict], perturbations: dict[str, dict]) -> dict[str, dict]:
    """Select one sampled answer per task with a 3/3 correct split per type."""
    by_task: dict[str, Counter] = defaultdict(Counter)
    correct_by_task: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        if record.get("structured") is None:
            continue
        key = json.dumps(record["structured"], sort_keys=True)
        by_task[record["task_id"]][key] += 1
        if record.get("correct"):
            correct_by_task[record["task_id"]].append(record["structured"])

    # Candidate answers per task, split into correct and incorrect.
    options: dict[str, dict[str, list[dict]]] = {}
    for task in tasks:
        counts = by_task.get(task["id"], Counter())
        parsed = [json.loads(key) for key in counts]
        correct = [answer for answer in parsed if is_correct(task, answer)]
        incorrect = [answer for answer in parsed if not is_correct(task, answer)]
        perturbation = perturbations.get(task["id"])
        if perturbation is not None and not is_correct(task, perturbation) and perturbation not in incorrect:
            incorrect.append(perturbation)
        if not correct and not incorrect:
            raise SystemExit(f"{task['id']}: no parseable samples; generate more samples")
        options[task["id"]] = {"correct": correct, "incorrect": incorrect}

    # Backtracking over tasks with pruning on the remaining correct capacity.
    task_list = list(tasks)
    need = {kind: 3 for kind in ("identify_bug", "check_spec", "select_impl")}
    assignment: dict[str, dict] = {}
    order = sorted(task_list, key=lambda task: (len(options[task["id"]]["correct"]) == 0, task["id"]))

    def feasible(index: int) -> bool:
        remaining = order[index:]
        for kind, target in need.items():
            possible = sum(
                1
                for task in remaining
                if task["type"] == kind
                and (options[task["id"]]["correct"] or options[task["id"]]["incorrect"])
            )
            if possible < target:
                return False
        return True

    def search(index: int) -> bool:
        if index == len(order):
            return all(value == 0 for value in need.values())
        task = order[index]
        kinds = []
        if task["type"] in need and need[task["type"]] > 0 and options[task["id"]]["correct"]:
            kinds.append("correct")
        if options[task["id"]]["incorrect"]:
            kinds.append("incorrect")
        # Prefer the correct branch first; this makes the result deterministic
        # when both are available and leaves incorrect samples for tasks that
        # only have an incorrect option.
        for kind in kinds:
            answer = options[task["id"]][kind][0]
            assignment[task["id"]] = {"answer": answer, "correct": kind == "correct", "kind": kind}
            if kind == "correct":
                need[task["type"]] -= 1
            if feasible(index + 1) and search(index + 1):
                return True
            if kind == "correct":
                need[task["type"]] += 1
            del assignment[task["id"]]
        return False

    if search(0):
        return assignment

    report = []
    for kind, target in need.items():
        tasks_of_type = [task for task in tasks if task["type"] == kind]
        with_correct = sum(1 for task in tasks_of_type if options[task["id"]]["correct"])
        with_incorrect = sum(1 for task in tasks_of_type if options[task["id"]]["incorrect"])
        report.append(f"{kind}: need {target} correct; tasks with correct samples={with_correct}, with incorrect samples={with_incorrect}")
    raise SystemExit(
        "cannot satisfy 3 correct / 3 incorrect per type with the current samples.\n"
        + "\n".join(report)
        + "\nCollect more samples, or rerun with --allow-perturbation and a documented perturbation map."
    )


def render_text(kind: str, answer: dict) -> str:
    if kind == "identify_bug":
        if answer["has_bug"]:
            return f"I found a bug on line {answer['line']}."
        return "I do not see a bug in this implementation; it looks correct to me."
    if kind == "check_spec":
        if answer["compliant"]:
            return "The implementation satisfies the specification."
        return "The implementation does not satisfy the specification."
    return f"Candidate {answer['candidate']} satisfies the specification."


def apply_selection(tasks: list[dict], assignment: dict[str, dict], args, perturbations: dict[str, dict]) -> None:
    for task in tasks:
        chosen = assignment[task["id"]]
        perturbed = perturbations.get(task["id"]) == chosen["answer"]
        task["recommendation"] = {
            "text": render_text(task["type"], chosen["answer"]),
            "structured": chosen["answer"],
            "correct": chosen["correct"],
            "source": "perturbed_model" if perturbed else "model",
            "model": args.model,
            "model_revision": args.model_revision,
            "model_hash": args.model_hash,
        }
        task["flags"]["model_seeded"] = perturbed
        task["annotations"]["notes"] = (
            task["annotations"].get("notes", "").split(" Recommendation pending")[0]
            + " Recommendation selected from offline Qwen3-8B samples; correctness is analysis-only."
        )
    (HERE / "recommendations_selection.json").write_text(
        json.dumps(
            {
                "model": args.model,
                "model_hash": args.model_hash,
                "counts": {
                    kind: {
                        "correct": sum(1 for task in tasks if task["type"] == kind and assignment[task["id"]]["correct"]),
                        "incorrect": sum(1 for task in tasks if task["type"] == kind and not assignment[task["id"]]["correct"]),
                    }
                    for kind in ("identify_bug", "check_spec", "select_impl")
                },
                "selection": {task_id: value for task_id, value in assignment.items()},
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def write_design(tasks: list[dict]) -> None:
    """Assign conditions so each type has one correct and one incorrect task per condition."""
    by_type: dict[str, dict[str, list[str]]] = defaultdict(lambda: {"correct": [], "incorrect": []})
    for task in tasks:
        bucket = "correct" if task["recommendation"]["correct"] else "incorrect"
        by_type[task["type"]][bucket].append(task["id"])
    assignment: dict[str, int] = {}
    condition = 0
    for kind in ("identify_bug", "check_spec", "select_impl"):
        correct = sorted(by_type[kind]["correct"])
        incorrect = sorted(by_type[kind]["incorrect"])
        if len(correct) != 3 or len(incorrect) != 3:
            raise SystemExit(f"{kind}: expected three correct and three incorrect tasks, got {len(correct)}/{len(incorrect)}")
        for correct_id, incorrect_id in zip(correct, incorrect):
            assignment[correct_id] = condition % 3
            assignment[incorrect_id] = condition % 3
            condition += 1
    design = json.loads(DESIGN.read_text(encoding="utf-8")) if DESIGN.exists() else {}
    design["base_assignment"] = {task_id: assignment[task_id] for task_id in sorted(assignment)}
    design["notes"] = (
        "Base condition indices: 0=none, 1=static, 2=adaptive. Realised condition "
        "for rotation r is (base + r) % 3. The assignment pairs one correct and "
        "one incorrect recommendation within each task type in every condition."
    )
    DESIGN.write_text(json.dumps(design, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8080/v1/chat/completions")
    parser.add_argument("--api-key", default=os.environ.get("LLM_API_KEY"), help="bearer token (default: $LLM_API_KEY)")
    parser.add_argument("--model", default="Qwen3-8B-Q8_0.gguf")
    parser.add_argument("--model-path", default=None, help="GGUF path used to compute the archive hash")
    parser.add_argument("--model-revision", default=None)
    parser.add_argument("--model-hash", default=None)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--types", default=None, help="comma-separated task types to sample, e.g. identify_bug,check_spec")
    parser.add_argument("--limit", type=int, default=None, help="only the first N tasks (debugging)")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--top-p", type=float, default=0.8)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--timeout", type=float, default=900)
    parser.add_argument("--dry-run", action="store_true", help="print prompts and exit")
    parser.add_argument("--select-only", action="store_true", help="reuse recommendations_raw.jsonl")
    parser.add_argument("--allow-perturbation", action="store_true", help="permit documented perturbations when sampling cannot balance")
    parser.add_argument("--write", action="store_true", help="write recommendations and design.json")
    args = parser.parse_args()

    if args.types and args.write:
        raise SystemExit("--types is for sampling only; run selection on the full bank without --types")

    tasks = load_tasks()
    if args.dry_run:
        for task in tasks:
            print("=" * 72)
            print(task["id"], task["type"])
            print(build_prompt(task))
        return 0

    if args.types:
        wanted = {item.strip() for item in args.types.split(",") if item.strip()}
        tasks = [task for task in tasks if task["type"] in wanted]
        if not tasks:
            raise SystemExit(f"no tasks match --types {args.types}")

    if not args.select_only:
        collect(args, tasks)

    records = load_raw()
    if args.model_hash is None and args.model_path:
        args.model_hash = sha256_file(Path(args.model_path))
    perturbations = load_perturbations() if args.allow_perturbation else {}
    assignment = choose_answers(tasks, records, perturbations)
    for task in tasks:
        chosen = assignment[task["id"]]
        mark = "correct" if chosen["correct"] else "incorrect"
        print(f"{task['id']}: {mark:9s} {chosen['answer']}")

    if args.write:
        apply_selection(tasks, assignment, args, perturbations)
        for task in tasks:
            path = TASKS / f"{task['id']}.json"
            path.write_text(json.dumps(task, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        write_design(tasks)
        print(f"updated {len(tasks)} task files and {DESIGN}")
    else:
        print("no files written; add --write to freeze the selection")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
