#!/usr/bin/env python3
"""Build the 18-task benchmark bank from the accepted MBPP review set.

The script is deterministic: it reads ``review_state.json`` and ``mbpp.jsonl``,
applies the declared mutations, runs every MBPP test, and writes
``../tasks/T01.json`` ... ``../tasks/T18.json``.

Recommendations are intentionally left as placeholders.  Run
``collect_recommendations.py`` after the Qwen3-8B endpoint is available; that
script fills ``recommendation`` and then updates the condition assignment.

Usage:
    python build_tasks.py [--write] [--check]

Without ``--write`` the script only validates the design and prints a summary.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BENCHMARK = HERE.parent
TASKS = BENCHMARK / "tasks"
POOL = HERE / "mbpp.jsonl"
STATE = HERE / "review_state.json"

# ---------------------------------------------------------------------------
# Design
# ---------------------------------------------------------------------------

# Each entry selects one accepted MBPP task and turns it into one benchmark
# task.  ``mutation`` is a single (old, new, occurrence) replacement; the line
# of the first changed line becomes the canonical bug/spec line.
#
# Mutations are documented here rather than hidden in the output JSON, so the
# derivation can be audited against the original MBPP source.
TASKS_DESIGN = [
    {
        "id": "T01", "mbpp_id": 9, "type": "identify_bug", "difficulty": "medium",
        "title": "Minimum rotations to a repeated string",
        "spec": "Given a non-empty string s, return the smallest positive k such that rotating s left by k positions gives s again. For example, 'aaaa' needs 1 rotation and 'abc' needs 3.",
        "mutation": ("            return i", "            return n", 1),
        "why": "Returns the full length instead of the first matching rotation.",
    },
    {
        "id": "T02", "mbpp_id": 11, "type": "identify_bug", "difficulty": "medium",
        "title": "Removing the first and last occurrence",
        "spec": "Given a string s and a character ch, remove the first and the last occurrence of ch. If ch occurs once, remove that occurrence. If ch does not occur, return s unchanged.",
        "mutation": ("            s = s[0 : i] + s[i + 1:]", "            s = s[0 : i] + s[i + 2:]", 1),
        "why": "The first removal skips two characters instead of one.",
    },
    {
        "id": "T03", "mbpp_id": 69, "type": "identify_bug", "difficulty": "high",
        "title": "Contiguous sublist check",
        "spec": "Return True if and only if s appears as a contiguous sublist of l. An empty s is a sublist of every list, and a sublist longer than l cannot match.",
        "mutation": ("                if n == len(s):", "                if n == 1:", 1),
        "why": "Accepts a match after the first element instead of the whole sublist.",
    },
    {
        "id": "T04", "mbpp_id": 125, "type": "identify_bug", "difficulty": "high",
        "title": "Longest substring with more zeros",
        "spec": "Given a binary string and its length n, return the maximum over all substrings of (number of zeros minus number of ones). Return 0 if every substring has a non-positive difference.",
        "mutation": (
            "        current_sum += (1 if string[i] == '0' else -1) ",
            "        current_sum += (1 if string[i] == '1' else -1) ",
            1,
        ),
        "why": "The score is inverted: ones count +1 and zeros count -1.",
    },
    {
        "id": "T05", "mbpp_id": 3, "type": "identify_bug", "difficulty": "low",
        "title": "Detecting non-prime numbers",
        "spec": "For an integer n >= 2, return True if n is composite and False if n is prime.",
        "mutation": (
            "    for i in range(2,int(math.sqrt(n)) + 1):",
            "    for i in range(2,int(math.sqrt(n))):",
            1,
        ),
        "why": "The loop misses the integer square root, so some composites look prime.",
    },
    {
        "id": "T06", "mbpp_id": 68, "type": "identify_bug", "difficulty": "low",
        "title": "Monotonic array check",
        "spec": "Return True if the array is non-decreasing or non-increasing, and False otherwise.",
        "mutation": None,
        "why": "No bug; the original implementation is correct.",
    },
    {
        "id": "T07", "mbpp_id": 1, "type": "check_spec", "difficulty": "high",
        "title": "Minimum cost path in a grid",
        "spec": "Given a 3 x 3 cost matrix and a target position (m, n) with 0 <= m, n < 3, return the minimum total cost of a path from (0, 0) to (m, n), moving only right or down.",
        "mutation": None,
        "why": "Original implementation satisfies the specification.",
    },
    {
        "id": "T08", "mbpp_id": 5, "type": "check_spec", "difficulty": "high",
        "title": "Tiling a 3 by n board",
        "spec": "Return the number of ways to tile a 3 x n board with 2 x 1 dominoes, for n >= 2.",
        "mutation": None,
        "why": "Original implementation satisfies the specification.",
    },
    {
        "id": "T09", "mbpp_id": 6, "type": "check_spec", "difficulty": "medium",
        "title": "Numbers differing in one bit",
        "spec": "Return True if and only if two non-negative integers differ in exactly one bit position.",
        "mutation": None,
        "why": "Original implementation satisfies the specification.",
    },
    {
        "id": "T10", "mbpp_id": 12, "type": "check_spec", "difficulty": "medium",
        "title": "Sorting rows by their sum",
        "spec": "Return the rows of a matrix sorted in ascending order of their sums. Rows with equal sums keep their original relative order.",
        "mutation": ("    result = sorted(M, key=sum)", "    result = sorted(M, key=min)", 1),
        "why": "Sorts by the smallest row element instead of the row sum.",
    },
    {
        "id": "T11", "mbpp_id": 56, "type": "check_spec", "difficulty": "medium",
        "title": "One less than twice the reverse",
        "spec": "For a positive integer n, return True if and only if 2 * reverse(n) == n + 1, where reverse(n) is the decimal representation of n read backwards with no leading zeros.",
        "mutation": None,
        "why": "Original implementation satisfies the specification.",
    },
    {
        "id": "T12", "mbpp_id": 175, "type": "check_spec", "difficulty": "high",
        "title": "Valid bracket sequence",
        "spec": "Return True if and only if the string consists only of the characters (), {}, [] and every opening bracket is closed by the matching type in the correct order.",
        "mutation": ("        return len(stack) == 0", "        return True", 1),
        "why": "Accepts a sequence with unclosed opening brackets.",
        "extra_tests": ['assert is_valid_parenthese("(") == False'],
    },
    {
        "id": "T13", "mbpp_id": 37, "type": "select_impl", "difficulty": "low",
        "title": "Sorting a mixed list",
        "spec": "Return a new list containing all integers from the input in ascending order, followed by all strings in ascending order. The input contains only integers and strings.",
        "correct_position": 2,
        "extra_tests": ["assert sort_mixed_list([2,'b',1,'a']) == [1, 2, 'a', 'b']"],
        "variants": [
            ("    return int_part + str_part", "    return str_part + int_part", 1),
            ("    return int_part + str_part", "    return sorted(mixed_list)", 1),
            ("    return int_part + str_part", "    return int_part", 1),
        ],
    },
    {
        "id": "T14", "mbpp_id": 41, "type": "select_impl", "difficulty": "low",
        "title": "Filtering even numbers",
        "spec": "Return a list of all even integers from the input, preserving their original order.",
        "correct_position": 3,
        "variants": [
            (" even_nums = list(filter(lambda x: x%2 == 0, nums))", " even_nums = list(filter(lambda x: x%2 != 0, nums))", 1),
            (" even_nums = list(filter(lambda x: x%2 == 0, nums))", " even_nums = list(filter(lambda x: x > 0, nums))", 1),
            (" even_nums = list(filter(lambda x: x%2 == 0, nums))", " even_nums = list(filter(lambda x: x%2 == 0 and x > 5, nums))", 1),
        ],
    },
    {
        "id": "T15", "mbpp_id": 126, "type": "select_impl", "difficulty": "low",
        "title": "Sum of common divisors",
        "spec": "For integers a, b >= 2, return the sum of every positive integer that divides both a and b.",
        "correct_position": 1,
        "base_mutation": (
            "    for i in range (1,min(a,b)): ",
            "    for i in range (1,min(a,b) + 1): ",
            1,
        ),
        "extra_tests": ["assert sum(4,8) == 7"],
        "variants": [
            ("        if (a % i == 0 and b % i == 0):", "        if (a % i == 0 or b % i == 0):", 1),
            ("        if (a % i == 0 and b % i == 0):", "        if True:", 1),
            ("        if (a % i == 0 and b % i == 0):", "        if (i % 2 == 0):", 1),
        ],
        "why": "The original range omits min(a,b); the corrected candidate includes it, and the test (4,8) separates them.",
    },
    {
        "id": "T16", "mbpp_id": 127, "type": "select_impl", "difficulty": "medium",
        "title": "Multiplication without the star operator",
        "spec": "Return x * y for integers x and y, using recursion and addition rather than the * operator.",
        "correct_position": 4,
        "variants": [
            ("        return x + multiply_int(x, y - 1)", "        return x + multiply_int(x, y - 2)", 1),
            ("        return x + multiply_int(x, y - 1)", "        return x + 1 + multiply_int(x, y - 1)", 1),
            ("        return x + multiply_int(x, y - 1)", "        return multiply_int(x, y - 1) + 1", 1),
        ],
    },
    {
        "id": "T17", "mbpp_id": 145, "type": "select_impl", "difficulty": "low",
        "title": "Maximum difference in an array",
        "spec": "Given a non-empty array and its length n, return the difference between its largest and smallest elements.",
        "correct_position": 2,
        "variants": [
            ("    return (maxEle - minEle)", "    return (maxEle - arr[0])", 1),
            ("    return (maxEle - minEle)", "    return (maxEle - minEle + 1)", 1),
            ("    return (maxEle - minEle)", "    return (maxEle - minEle - 1)", 1),
        ],
    },
    {
        "id": "T18", "mbpp_id": 195, "type": "select_impl", "difficulty": "high",
        "title": "First occurrence in a sorted array",
        "spec": "Given a sorted array arr of length n and a value x, return the index of the first occurrence of x, or -1 if x is absent.",
        "correct_position": 3,
        "tests": [
            "assert first([1,2,3,4,5,6,6],6,6) == 5",
            "assert first([1,1,1,2,3],1,5) == 0",
            "assert first([1,2,3],1,3) == 0",
            "assert first([1,2,3],4,3) == -1",
        ],
        "variants": [
            ("            high = mid - 1", "            low = mid + 1", 2),
            ("    return res", "    return mid", 1),
            ("        if arr[mid] > x:", "        if arr[mid] >= x:", 1),
        ],
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_pool() -> dict[int, dict]:
    pool = {}
    with POOL.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            pool[row["task_id"]] = row
    return pool


def accepted_ids() -> set[int]:
    state = json.loads(STATE.read_text(encoding="utf-8"))
    return {
        int(key)
        for key, value in state["decisions"].items()
        if value["decision"] == "accept"
    }


def normalize(code: str) -> str:
    return code.replace("\r\n", "\n").replace("\r", "\n").expandtabs(4).rstrip() + "\n"


def apply_mutation(code: str, mutation: tuple[str, str, int] | None) -> str:
    if mutation is None:
        return code
    old, new, occurrence = mutation
    count = code.count(old)
    if count < occurrence:
        raise ValueError(f"mutation target not found ({count} occurrences): {old!r}")
    start = -1
    for _ in range(occurrence):
        start = code.index(old, start + 1)
    return code[:start] + new + code[start + len(old):]


def changed_line(before: str, after: str) -> int:
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, before_lines, after_lines).get_opcodes():
        if tag != "equal":
            return j1 + 1
    raise ValueError("mutation did not change the code")


def run_tests(code: str, tests: list[str], setup: str = "") -> list[dict]:
    namespace: dict = {}
    try:
        exec(setup, namespace)
        exec(code, namespace)
    except Exception as exc:  # pragma: no cover - surfaced in the report
        return [
            {
                "test": test,
                "passed": False,
                "expected": "<code did not load>",
                "actual": f"{type(exc).__name__}: {exc}",
            }
            for test in tests
        ]

    results = []
    for test in tests:
        source = test.strip()
        expression = source[len("assert "):] if source.startswith("assert ") else source
        try:
            node = ast.parse(source, mode="exec").body[0]
            assert isinstance(node, ast.Assert)
            expected = eval(compile(ast.Expression(node.test.comparators[0]), "<test>", "eval"), namespace)
        except Exception as exc:
            expected = f"<unparsed: {type(exc).__name__}: {exc}>"
        try:
            exec(source, namespace)
            passed = True
            actual = expected
        except Exception as exc:
            passed = False
            try:
                actual = eval(compile(ast.Expression(node.test.left), "<test>", "eval"), namespace)
            except Exception:
                actual = f"{type(exc).__name__}: {exc}"
        results.append({"test": source, "passed": passed, "expected": expected, "actual": actual})
    return results


def format_value(value) -> str:
    if isinstance(value, str) and value.startswith("<"):
        return value
    return repr(value)


def tests_block(results: list[dict]) -> str:
    lines = []
    for result in results:
        status = "PASS" if result["passed"] else "FAIL"
        lines.append(f"{status}: {result['test']}")
        if not result["passed"]:
            lines.append(f"  expected: {format_value(result['expected'])}")
            lines.append(f"  actual:   {format_value(result['actual'])}")
    return "\n".join(lines)


def prompt_for(design: dict, kind: str) -> str:
    text = design["spec"]
    if kind == "identify_bug":
        return (
            f"Specification: {text} "
            "The function below is intended to satisfy this specification. "
            "Does it contain a bug? If yes, give the line number of the faulty "
            "statement (1-based, counting the `def` line as line 1). If the bug "
            "spans several lines, give the first line of the faulty statement. "
            "If there is no bug, set the line to null."
        )
    if kind == "check_spec":
        return (
            f"Specification: {text} "
            "The implementation below should satisfy this specification for all "
            "valid inputs. Does it? Answer COMPLIANT or NOT_COMPLIANT."
        )
    return (
        f"Specification: {text} "
        "Four candidate implementations follow. Which candidate satisfies the "
        "specification for all valid inputs? Select one candidate."
    )


def evidence_for(kind: str, results: list[dict], candidate_results: dict[str, list[dict]] | None = None):
    if kind == "select_impl":
        assert candidate_results is not None
        test_labels = [f"Test {index + 1}" for index in range(len(results))]
        rows = []
        for candidate, outcome in candidate_results.items():
            row = [candidate]
            row.extend("pass" if item["passed"] else "fail" for item in outcome)
            rows.append(row)
        body = "Each candidate was executed against the same test suite.\n\n"
        for index, result in enumerate(results, start=1):
            body += f"Test {index}: {result['test']}\n"
        return [
            {
                "kind": "execution_table",
                "title": "Candidate executions against the test suite",
                "body": body.strip(),
                "table": {
                    "columns": ["Candidate", *test_labels],
                    "rows": rows,
                },
                "decisiveness": "decisive",
            }
        ]

    failed = [result for result in results if not result["passed"]]
    if failed:
        first = failed[0]
        body = (
            f"Test: {first['test']}\n"
            f"Expected: {format_value(first['expected'])}\n"
            f"Actual: {format_value(first['actual'])}"
        )
        return [
            {
                "kind": "test",
                "title": "A test that exposes the defect",
                "body": body,
                "table": None,
                "decisiveness": "partial",
            }
        ]
    return [
        {
            "kind": "test",
            "title": "The implementation passes the test suite",
            "body": tests_block(results),
            "table": None,
            "decisiveness": "partial",
        }
    ]


def placeholder_recommendation(kind: str, canonical: dict, candidates: list[dict] | None = None):
    if kind == "identify_bug":
        if canonical.get("has_bug"):
            structured = {"has_bug": False, "line": None}
        else:
            structured = {"has_bug": True, "line": 1}
    elif kind == "check_spec":
        structured = {"compliant": not canonical["compliant"]}
    else:
        ids = [candidate["id"] for candidate in candidates or []]
        structured = {"candidate": next(candidate for candidate in ids if candidate != canonical["candidate"])}
    return {
        "text": "Recommendation pending model collection.",
        "structured": structured,
        "correct": False,
        "source": "pending",
        "model": "Qwen3-8B-Q8_0.gguf",
        "model_revision": None,
        "model_hash": None,
    }


def build_one(design: dict, pool: dict[int, dict]) -> tuple[dict, dict]:
    row = pool[design["mbpp_id"]]
    original = normalize(row["code"])
    if "tests" in design:
        tests = list(design["tests"])
    else:
        tests = list(row.get("test_list", [])) + list(design.get("extra_tests", []))
        tests = list(dict.fromkeys(tests))
    kind = design["type"]

    if kind in {"identify_bug", "check_spec"}:
        candidate = apply_mutation(original, design.get("mutation"))
        line = changed_line(original, candidate) if design.get("mutation") else None
        results = run_tests(candidate, tests, row.get("test_setup_code", ""))
        if kind == "identify_bug":
            has_bug = design.get("mutation") is not None
            canonical = {"has_bug": has_bug, "line": line if has_bug else None}
        else:
            canonical = {"compliant": design.get("mutation") is None}
        code = candidate
        candidates = None
        candidate_results = None
        evidence = evidence_for(kind, results)
    else:
        position = design["correct_position"]
        # The correct implementation is the original MBPP code, optionally with
        # a documented base correction. Each variant replaces one source line
        # with a plausible distractor.
        base = apply_mutation(original, design.get("base_mutation"))
        candidate_sources = [base]
        for source, replacement, occurrence in design["variants"]:
            candidate_sources.append(apply_mutation(base, (source, replacement, occurrence)))
        ordered = candidate_sources[:]
        correct = ordered.pop(0)
        ordered.insert(position - 1, correct)
        labels = ["A", "B", "C", "D"]
        code = ""
        candidates = []
        candidate_results = {}
        for label, source in zip(labels, ordered):
            candidates.append({"id": label, "code": source})
            candidate_results[label] = run_tests(source, tests, row.get("test_setup_code", ""))
        passing = [label for label, outcome in candidate_results.items() if all(item["passed"] for item in outcome)]
        if len(passing) != 1:
            raise ValueError(f"{design['id']}: expected exactly one passing candidate, got {passing}")
        canonical = {"candidate": passing[0]}
        results = candidate_results[passing[0]]
        evidence = evidence_for(kind, results, candidate_results)

    task = {
        "id": design["id"],
        "status": "draft",
        "type": kind,
        "difficulty": design["difficulty"],
        "title": design["title"],
        "prompt": prompt_for(design, kind),
        "code": code,
        "response_schema": response_schema(kind),
        "canonical": canonical,
        "accepted_equivalence": [canonical],
        "evidence": evidence,
        "recommendation": placeholder_recommendation(kind, canonical, candidates),
        "annotations": {
            "plausibility": None,
            "annotator_1": None,
            "annotator_2": None,
            "notes": (
                f"Adapted from MBPP task_id {design['mbpp_id']}. "
                f"{design.get('why', '')} Recommendation pending Qwen3-8B collection."
            ).strip(),
        },
        "flags": {"model_seeded": False, "needs_review": True},
    }
    if candidates is not None:
        task["candidates"] = candidates
    meta = {
        "id": design["id"],
        "mbpp_id": design["mbpp_id"],
        "type": kind,
        "difficulty": design["difficulty"],
        "canonical": canonical,
        "tests": tests,
        "evidence": evidence,
        "passing_candidates": [label for label, outcome in (candidate_results or {}).items() if all(item["passed"] for item in outcome)],
    }
    return task, meta


def response_schema(kind: str) -> dict:
    if kind == "identify_bug":
        return {
            "widget": "bug_form",
            "fields": {
                "has_bug": "boolean",
                "line": "integer|null (1-based, required when has_bug is true)",
            },
        }
    if kind == "check_spec":
        return {"widget": "compliance_form", "fields": {"compliant": "boolean"}}
    return {
        "widget": "candidate_select",
        "fields": {"candidate": "string (one of the candidate ids)"},
    }


def validate_design(designs: list[dict], accepted: set[int]) -> None:
    ids = [design["id"] for design in designs]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate task ids")
    missing = [design["mbpp_id"] for design in designs if design["mbpp_id"] not in accepted]
    if missing:
        raise ValueError(f"selected MBPP tasks not accepted: {missing}")
    for kind in ("identify_bug", "check_spec", "select_impl"):
        if sum(1 for design in designs if design["type"] == kind) != 6:
            raise ValueError(f"expected six tasks of type {kind}")
    for difficulty in ("low", "medium", "high"):
        if sum(1 for design in designs if design["difficulty"] == difficulty) != 6:
            raise ValueError(f"expected six {difficulty} tasks")
    for design in designs:
        if design["type"] == "select_impl":
            if len(design["variants"]) != 3:
                raise ValueError(f"{design['id']}: select_impl needs three variants")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write task files")
    parser.add_argument("--check", action="store_true", help="only validate (default)")
    args = parser.parse_args()

    pool = load_pool()
    accepted = accepted_ids()
    validate_design(TASKS_DESIGN, accepted)

    built = []
    metas = []
    for design in TASKS_DESIGN:
        task, meta = build_one(design, pool)
        built.append(task)
        metas.append(meta)
        print(f"{task['id']}: MBPP {design['mbpp_id']} {task['type']:13s} {task['difficulty']:6s} -> {task['canonical']}")

    # Print a compact evidence summary.
    for meta in metas:
        passed = meta["passing_candidates"]
        print(f"  {meta['id']}: tests={len(meta['tests'])} passing={passed or 'n/a'}")

    if args.write:
        TASKS.mkdir(parents=True, exist_ok=True)
        for task in built:
            path = TASKS / f"{task['id']}.json"
            path.write_text(json.dumps(task, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (HERE / "selection.json").write_text(
            json.dumps({"tasks": metas}, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {len(built)} tasks to {TASKS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
