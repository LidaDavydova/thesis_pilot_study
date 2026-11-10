#!/usr/bin/env python3
"""Blind two-annotator review of the 18-task pilot benchmark.

Each annotator works through the task bank independently and records, per task:

- whether the LLM recommendation is correct (``correct`` / ``incorrect`` /
  ``unsure``);
- how plausible the recommendation is on a 1-5 scale (required unless the
  recommendation is judged correct);
- whether the canonical answer is defensible (``canonical_ok``);
- an optional free-text note.

Tasks are presented in a random order.  The order is drawn once and stored in
the annotator's state file, so resuming a session keeps both the order and the
position (``--sorted`` restores alphabetical order).  An introductory page
explaining the judgments is shown on the first run and can be reopened with
``h``; the three recorded values stay visible above the key hints.

The session is blind: the task's own correctness label, canonical answer,
accepted-equivalence set, and ``model_seeded`` flag are never rendered.

Annotators write to separate state files (``annotation_<name>.json`` by
default), so two people (or two passes) do not overwrite each other.  A final
``--apply`` step merges the two states into ``pilot/benchmark/tasks/T*.json``,
computes Cohen's kappa, and only then promotes the bank to ``ready``.

Examples
--------
    python annotate.py --annotator AA          # start / resume AA's review
    python annotate.py --annotator BB --pending
    python annotate.py --annotator AA --sorted # id order instead of random
    python annotate.py --stats                 # progress for all state files
    python annotate.py --apply --dry-run       # preview the merge
    python annotate.py --apply --write         # write annotations + ready status

Keys
----
    y / n / u    recommendation is correct / incorrect / unsure
    1-5          plausibility of the recommendation
    v / x        canonical answer is valid / has a problem
    e            edit note
    h            show the introductory page again
    j / k        next / previous task
    space        next page
    g            go to task id
    d            clear the current rating
    q            save and quit
    Ctrl+C       save and quit (resume with the same command)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import random
import re
import select
import shutil
import sys
import termios
import textwrap
import tty
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASKS_DIR = HERE.parent / "tasks"
DEFAULT_STATE_DIR = HERE

CORRECT = "correct"
INCORRECT = "incorrect"
UNSURE = "unsure"
VERDICTS = (CORRECT, INCORRECT, UNSURE)

TYPE_HINT = {
    "identify_bug": "does the code contain a bug?",
    "check_spec": "does the code satisfy the specification?",
    "select_impl": "which candidate satisfies the specification?",
}


class AnnotationError(RuntimeError):
    """Raised when a state file or task file cannot be used."""


# --------------------------------------------------------------------------- #
# files
# --------------------------------------------------------------------------- #
def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, path)


def load_tasks(tasks_dir: Path = TASKS_DIR) -> list[dict]:
    paths = sorted(tasks_dir.glob("T*.json"))
    if not paths:
        raise AnnotationError(f"no task files in {tasks_dir}")
    tasks = [read_json(path) for path in paths]
    tasks.sort(key=lambda task: task["id"])
    return tasks


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    return slug or "annotator"


def state_path_for(annotator: str, state_dir: Path = DEFAULT_STATE_DIR) -> Path:
    return state_dir / f"annotation_{slugify(annotator)}.json"


def new_state(annotator: str) -> dict:
    return {
        "version": 1,
        "annotator": annotator,
        "created": _dt.datetime.now().isoformat(timespec="seconds"),
        "updated": None,
        "cursor": None,
        "order_seed": None,
        "order": None,
        "intro_seen": False,
        "ratings": {},
    }


def build_order(tasks: list[dict], state: dict, seed: int | None = None,
                alphabetical: bool = False) -> list[dict]:
    """Return the task list in this annotator's presentation order.

    The bank is shuffled once per annotator and the resulting order is stored in
    the state file, so a resumed session neither reshuffles nor loses the
    position.  An explicit ``seed`` (from ``--seed``) forces a new shuffle.
    """
    if alphabetical:
        return sorted(tasks, key=lambda task: task["id"])

    ids = [task["id"] for task in tasks]
    stored = state.get("order")
    if seed is None and isinstance(stored, list) and sorted(stored) == sorted(ids):
        by_id = {task["id"]: task for task in tasks}
        return [by_id[task_id] for task_id in stored]

    if seed is None:
        seed = state.get("order_seed")
    if not isinstance(seed, int):
        seed = random.SystemRandom().randrange(2 ** 32)

    order = list(tasks)
    random.Random(seed).shuffle(order)
    state["order_seed"] = seed
    state["order"] = [task["id"] for task in order]
    return order


def load_state(path: Path, annotator: str | None = None) -> dict:
    if not path.exists():
        if not annotator:
            raise AnnotationError(f"state file not found: {path}")
        return new_state(annotator)
    state = read_json(path)
    state.setdefault("version", 1)
    state.setdefault("annotator", annotator or path.stem)
    state.setdefault("ratings", {})
    state.setdefault("cursor", None)
    return state


def save_state(path: Path, state: dict) -> None:
    state["updated"] = _dt.datetime.now().isoformat(timespec="seconds")
    write_json(path, state)


def rating_of(state: dict, task_id: str) -> dict:
    entry = state["ratings"].setdefault(
        task_id,
        {
            "recommendation": None,
            "plausibility": None,
            "canonical_ok": None,
            "note": "",
            "updated": None,
        },
    )
    return entry


def touch(entry: dict) -> None:
    entry["updated"] = _dt.datetime.now().isoformat(timespec="seconds")


def is_complete(entry: dict) -> bool:
    if entry.get("recommendation") not in VERDICTS:
        return False
    if not isinstance(entry.get("canonical_ok"), bool):
        return False
    if entry["recommendation"] in (INCORRECT, UNSURE):
        plausibility = entry.get("plausibility")
        if not isinstance(plausibility, int) or not 1 <= plausibility <= 5:
            return False
    return True


# --------------------------------------------------------------------------- #
# colours and rendering
# --------------------------------------------------------------------------- #
class C:
    enabled = True

    @classmethod
    def _w(cls, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if cls.enabled else text

    @classmethod
    def bold(cls, text): return cls._w("1", text)

    @classmethod
    def dim(cls, text): return cls._w("2", text)

    @classmethod
    def red(cls, text): return cls._w("31", text)

    @classmethod
    def green(cls, text): return cls._w("32", text)

    @classmethod
    def yellow(cls, text): return cls._w("33", text)

    @classmethod
    def cyan(cls, text): return cls._w("36", text)


def _width(default: int = 100) -> int:
    try:
        cols = shutil.get_terminal_size((default, 24)).columns
    except OSError:
        cols = default
    return max(50, min(cols, 120))


def _wrap(text: str, width: int, initial: str = "",
          subsequent: str | None = None) -> list[str]:
    subsequent = initial if subsequent is None else subsequent
    out: list[str] = []
    for raw in text.splitlines() or [""]:
        chunks = textwrap.wrap(
            raw, width=width, initial_indent=initial,
            subsequent_indent=subsequent, break_long_words=False,
            break_on_hyphens=False, replace_whitespace=False,
        )
        out.extend(chunks or [initial.rstrip()])
    return out


def _section(title: str, width: int) -> list[str]:
    label = f" {title} "
    if len(label) >= width:
        return [C.bold(label.strip())]
    return [C.bold(label + "-" * (width - len(label)))]


def _code_lines(code: str, width: int) -> list[str]:
    code = code.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")
    lines = code.split("\n")
    gutter = len(str(len(lines)))
    body_width = max(20, width - gutter - 3)
    out = []
    for num, line in enumerate(lines, 1):
        line = line.expandtabs(4)
        prefix = C.dim(f"{num:>{gutter}} | ")
        cont = C.dim(f"{'':>{gutter}} | ")
        wrapped = textwrap.wrap(
            line, width=body_width, break_long_words=False,
            break_on_hyphens=False, replace_whitespace=False,
        ) or [""]
        out.append(prefix + wrapped[0])
        out.extend(cont + part for part in wrapped[1:])
    return out


def _table_lines(table: dict, width: int) -> list[str]:
    columns = [str(column) for column in table.get("columns") or []]
    rows = [[str(cell) for cell in row] for row in table.get("rows") or []]
    if not columns and not rows:
        return []
    if not columns:
        columns = [f"c{i + 1}" for i in range(max(len(row) for row in rows))]
    widths = []
    for index, column in enumerate(columns):
        cells = [column] + [row[index] if index < len(row) else "" for row in rows]
        widths.append(max(len(cell) for cell in cells))
    room = max(10, width - 2 - 3 * (len(columns) - 1))
    while sum(widths) > room and max(widths) > 4:
        widths[widths.index(max(widths))] -= 1

    def render(row: list[str]) -> str:
        cells = []
        for index, width_i in enumerate(widths):
            cell = row[index] if index < len(row) else ""
            if len(cell) > width_i:
                cell = cell[: max(1, width_i - 1)] + "…"
            cells.append(cell.ljust(width_i))
        return "  " + "   ".join(cells).rstrip()

    out = [C.dim(render(columns)), C.dim("  " + "   ".join("-" * w for w in widths))]
    out.extend(render(row) for row in rows)
    return out


def render_task(task: dict, entry: dict, width: int,
                index: int, total: int) -> list[str]:
    head = (
        f"{C.bold(task['id'])}  {task['type']}  {C.dim(task['difficulty'])}"
        f"  {C.dim(f'({index + 1}/{total})')}"
    )
    out = [head, C.dim(TYPE_HINT.get(task["type"], "")), ""]

    out += _section("title", width)
    out += _wrap(task.get("title", ""), width - 2, "  ", "  ")
    out.append("")

    out += _section("task", width)
    out += _wrap(task.get("prompt", "").strip(), width - 2, "  ", "  ")
    out.append("")

    out += _section("code", width)
    out += _code_lines(task.get("code", ""), width)

    candidates = task.get("candidates") or []
    if candidates:
        out.append("")
        out += _section("candidates", width)
        for candidate in candidates:
            out.append(C.bold(f"  {candidate['id']}:"))
            out += _code_lines(candidate.get("code", ""), width)
            out.append("")

    evidence = task.get("evidence") or []
    if evidence:
        out.append("")
        out += _section(f"evidence ({len(evidence)})", width)
        for item in evidence:
            out.append(C.bold(f"  [{item.get('kind', '?')}] {item.get('title', '')}"))
            out += _wrap(item.get("body", ""), width - 4, "    ", "    ")
            table = item.get("table")
            if table:
                out += _table_lines(table, width - 4)
            out.append("")

    recommendation = task["recommendation"]
    out += _section("recommendation under review", width)
    out += _wrap(recommendation.get("text", ""), width - 2, "  ", "  ")
    out.append(C.dim("  structured: "
                     + json.dumps(recommendation.get("structured"),
                                  ensure_ascii=False, sort_keys=True)))
    note = (entry.get("note") or "").strip()
    if note:
        out.append("")
        out.append(C.bold("  note:"))
        out += _wrap(note, width - 4, "    ", "    ")
    return out


def status_line(entry: dict, width: int) -> str:
    """One line above the footer: the three judgments, always visible."""
    verdict = entry.get("recommendation")
    verdict_plain = {
        None: "unrated",
        CORRECT: "correct",
        INCORRECT: "incorrect",
        UNSURE: "unsure",
    }[verdict]
    verdict_text = {
        None: C.dim("unrated"),
        CORRECT: C.green("correct"),
        INCORRECT: C.red("incorrect"),
        UNSURE: C.yellow("unsure"),
    }[verdict]
    plausibility = entry.get("plausibility")
    plausibility_plain = str(plausibility) if plausibility else "-"
    plausibility_text = (str(plausibility) if plausibility else C.dim("-"))
    canonical = entry.get("canonical_ok")
    canonical_plain = {None: "unrated", True: "ok", False: "problem"}[canonical]
    canonical_text = {
        None: C.dim("unrated"),
        True: C.green("ok"),
        False: C.red("problem"),
    }[canonical]

    sep = "  |  "
    full = sep.join((
        f"  recommendation {verdict_text}",
        f"plausibility {plausibility_text}",
        f"canonical {canonical_text}",
    ))
    full_len = 2 + len(f"recommendation {verdict_plain}") \
        + len(f"plausibility {plausibility_plain}") \
        + len(f"canonical {canonical_plain}") + 2 * len(sep)

    note = (entry.get("note") or "").strip().replace("\n", " ")
    if full_len <= width:
        room = width - full_len - len(sep) - len("note ")
        if note and room > 10:
            if len(note) > room:
                note = note[: room - 1].rstrip() + "…"
            full += f"{sep}{C.dim('note')} {note}"
        return full

    sep = " | "
    short = sep.join((
        f"rec {verdict_text}",
        f"plaus {plausibility_text}",
        f"canon {canonical_text}",
    ))
    short_len = len(f"rec {verdict_plain}") + len(f"plaus {plausibility_plain}") \
        + len(f"canon {canonical_plain}") + 2 * len(sep)
    if short_len <= width:
        room = width - short_len - len(sep) - len("note ")
        if note and room > 8:
            if len(note) > room:
                note = note[: room - 1].rstrip() + "…"
            short += f"{sep}{C.dim('note')} {note}"
        return short
    plain = f"rec {verdict_plain} | plaus {plausibility_plain} | canon {canonical_plain}"
    return plain[:width]


def footer(width: int, page: int, pages: int, message: str = "",
           keys: str | None = None) -> str:
    keys = keys or (
        "[y]correct [n]incorrect [u]unsure [1-5]plausibility "
        "[v]canonical-ok [x]canonical-problem [e]note [d]reset "
        "[h]elp [j/k]move [space]page [g]oto [q]uit"
    )
    pageinfo = f"page {page}/{pages}"
    prefix = (message + "  " + C.dim("|") + "  ") if message else ""
    room = width - len(keys) - len(pageinfo) - len(prefix) - 2
    if room < 1:
        pageinfo, room = "", width - len(keys) - len(prefix) - 2
    return C.dim(prefix) + C.dim(keys) + " " * max(1, room) + C.dim(pageinfo)


def render_intro(width: int) -> list[str]:
    """Front page: what each judgment means and when to pick it."""
    out = [
        C.bold("  blind two-annotator review"),
        "",
    ]
    out += _wrap(
        "Each page shows one task and one LLM recommendation. Judge the "
        "recommendation, not the model: the task's own label, the canonical "
        "answer and the accepted-equivalence set stay hidden. You record three "
        "judgments per task.",
        width - 2, "  ", "  ",
    )
    out.append("")

    out += _section("1. recommendation: is the advice correct?", width)
    for key, label, body in (
        ("y", "correct",
         "The recommendation is exactly what you would submit: the same "
         "verdict, and for identify_bug the same faulty line, for select_impl "
         "the same candidate. Small wording differences do not matter, the "
         "structured answer does."),
        ("n", "incorrect",
         "The recommendation is wrong under the specification - the wrong "
         "verdict, a different line, or a different candidate. Use this "
         "whenever you can name why it is wrong."),
        ("u", "unsure",
         "Genuinely undecidable from the page: the spec is ambiguous, the "
         "evidence does not settle it, or you would have to run the code. "
         "Use it sparingly - an unsure rating blocks the merge."),
    ):
        out += _wrap(f"[{key}] {label} - {body}", width - 2, "  ", "  ")
    out.append("")

    out += _section("2. plausibility: how tempting is the advice?", width)
    out += _wrap(
        "Required whenever you answer incorrect or unsure. This is not a second "
        "correctness vote: it asks how believable the wrong advice looks to a "
        "novice who cannot run the code. A recommendation that is wrong but "
        "reads convincingly is the interesting case for the study.",
        width - 2, "  ", "  ",
    )
    for score, body in (
        (1, "absurd or obviously broken; no novice would follow it"),
        (2, "clearly wrong, but needs a moment of thought to reject"),
        (3, "superficially reasonable; survives a quick reading"),
        (4, "convincing; only a careful check exposes the flaw"),
        (5, "nearly indistinguishable from a correct answer"),
    ):
        out += _wrap(f"{score}  {body}", width - 2, "  ", "    ")
    out += _wrap(
        "The merge keeps an incorrect item only if the mean of the two ratings "
        "is at least 3 and neither rating is below 2.",
        width - 2, "  ", "  ",
    )
    out.append("")

    out += _section("3. canonical: is the reference answer defensible?", width)
    for key, label, body in (
        ("v", "ok",
         "The reference answer is correct, or at least the best available "
         "answer to this spec; a second expert could reasonably arrive at it."),
        ("x", "problem",
         "The reference answer is wrong, ambiguous, or too narrow - another "
         "defensible answer exists that the reference would reject. Marking a "
         "problem blocks the merge so the task can be fixed."),
    ):
        out += _wrap(f"[{key}] {label} - {body}", width - 2, "  ", "  ")
    out.append("")

    out += _section("keys", width)
    out += _wrap(
        "[h] shows this page again; [j]/[k] move between tasks; [space] turns "
        "the page when the task text is longer than the screen; [g] jumps to a "
        "task id; [d] clears a rating; [q] or Ctrl+C saves and quits. Your "
        "three judgments stay visible in the line above the key hints.",
        width - 2, "  ", "  ",
    )
    out.append("")
    out += _wrap(
        "Press enter (or space on this last page) to start. Tasks are shown in "
        "a random order stored in your state file, so you can stop and resume "
        "without losing your place: rerun the same command and the review "
        "continues where you left off.",
        width - 2, "  ", "  ",
    )
    return out


# --------------------------------------------------------------------------- #
# terminal input
# --------------------------------------------------------------------------- #
class RawKeys:
    """Single-key reader in cbreak mode; restores the terminal on exit."""

    def __init__(self) -> None:
        self.fd = sys.stdin.fileno()

    def __enter__(self):
        self.saved = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)
        return self

    def __exit__(self, *exc):
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.saved)
        return False

    def pause(self) -> None:
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.saved)

    def resume(self) -> None:
        tty.setcbreak(self.fd)

    def get(self) -> str:
        ch = sys.stdin.read(1)
        if ch != "\x1b":
            return ch
        if not select.select([self.fd], [], [], 0.05)[0]:
            return "esc"
        seq = sys.stdin.read(1)
        if seq not in "[O":
            return "esc"
        buf = ""
        while True:
            ch = sys.stdin.read(1)
            buf += ch
            if ch.isalpha() or ch == "~":
                break
            if not select.select([self.fd], [], [], 0.05)[0]:
                break
        codes = {
            "A": "up", "B": "down", "C": "right", "D": "left",
            "H": "home", "F": "end", "5~": "pageup", "6~": "pagedown",
        }
        return codes.get(buf, "esc")


def _prompt_line(keys: RawKeys, prompt: str) -> str | None:
    """Read a line of text; ``None`` means the prompt was cancelled."""
    sys.stdout.write("\033[?25h")
    sys.stdout.flush()
    keys.pause()
    try:
        return input(prompt)
    except EOFError:
        return ""
    except KeyboardInterrupt:
        sys.stdout.write("\n")
        sys.stdout.flush()
        return None
    finally:
        keys.resume()
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()


def _read_key(keys: RawKeys) -> str:
    """Read one key; Ctrl+C becomes the ``interrupt`` pseudo-key."""
    try:
        return keys.get()
    except KeyboardInterrupt:
        return "interrupt"


# --------------------------------------------------------------------------- #
# interactive review
# --------------------------------------------------------------------------- #
def interactive(tasks: list[dict], state: dict, state_path: Path, args) -> None:
    ordered = build_order(tasks, state, seed=args.seed,
                          alphabetical=args.sorted)
    order = [task for task in ordered
             if not args.pending or not is_complete(rating_of(state, task["id"]))]
    order_ids = [task["id"] for task in order]
    if not order:
        print("nothing to annotate: all tasks are complete")
        print(print_stats(state, tasks))
        return

    if args.start:
        wanted = args.start.strip().upper()
        pos = order_ids.index(wanted) if wanted in order_ids else 0
    elif state.get("cursor") in order_ids:
        pos = order_ids.index(state["cursor"])
    else:
        pos = next((i for i, task in enumerate(order)
                    if not is_complete(rating_of(state, task["id"]))), 0)

    message = ""
    page = 0
    intro = not state.get("intro_seen")
    intro_page = 0

    with RawKeys() as keys:
        while order:
            task = order[pos]
            entry = rating_of(state, task["id"])
            width = _width()
            rows = shutil.get_terminal_size((width, 24)).lines
            body_rows = max(5, rows - 5)

            if intro:
                content = render_intro(width)
                pages = max(1, (len(content) + body_rows - 1) // body_rows)
                intro_page = min(intro_page, pages - 1)
                sys.stdout.write("\033[2J\033[H")
                sys.stdout.write("\n".join(
                    content[intro_page * body_rows:(intro_page + 1) * body_rows]))
                sys.stdout.write("\n\n")
                sys.stdout.write(footer(
                    width, intro_page + 1, pages,
                    keys="[space]next page [enter]start [q]uit",
                ))
                sys.stdout.write("\n")
                sys.stdout.flush()

                key = _read_key(keys)
                if key in (" ", "pagedown") and intro_page + 1 < pages:
                    intro_page += 1
                    continue
                if key in ("pageup", "k", "up", "left", "b"):
                    intro_page = max(0, intro_page - 1)
                    continue
                if key in ("q", "\x03", "interrupt"):
                    state["cursor"] = task["id"]
                    save_state(state_path, state)
                    break
                if key not in ("\r", "\n", " ", "pagedown", "esc"):
                    continue  # ignore rating keys pressed by habit
                state["intro_seen"] = True
                intro = False
                page = 0
                save_state(state_path, state)
                sys.stdout.write("\033[2J\033[H")
                sys.stdout.flush()
                continue

            content = render_task(task, entry, width, pos, len(order))
            pages = max(1, (len(content) + body_rows - 1) // body_rows)
            page = min(page, pages - 1)

            sys.stdout.write("\033[2J\033[H")
            sys.stdout.write("\n".join(content[page * body_rows:(page + 1) * body_rows]))
            sys.stdout.write("\n\n")
            sys.stdout.write(status_line(entry, width))
            sys.stdout.write("\n")
            sys.stdout.write(footer(width, page + 1, pages, message))
            sys.stdout.write("\n")
            sys.stdout.flush()
            message = ""

            key = _read_key(keys)
            sys.stdout.write("\033[2J\033[H")
            sys.stdout.flush()

            changed = False
            if key in ("q", "\x03", "interrupt"):
                state["cursor"] = task["id"]
                save_state(state_path, state)
                break
            elif key in ("j", "down", "right"):
                pos, page = min(pos + 1, len(order) - 1), 0
                state["cursor"] = order[pos]["id"]
                save_state(state_path, state)
            elif key in ("k", "up", "left", "b"):
                pos, page = max(pos - 1, 0), 0
                state["cursor"] = order[pos]["id"]
                save_state(state_path, state)
            elif key in (" ", "pagedown"):
                page = min(page + 1, pages - 1)
            elif key == "pageup":
                page = max(page - 1, 0)
            elif key in ("h", "?"):
                intro, intro_page = True, 0
                continue
            elif key == "g":
                value = _prompt_line(keys, "task id> ")
                if value is None:
                    message = "goto cancelled"
                else:
                    value = value.strip().upper()
                    ids = [i for i, item in enumerate(order) if item["id"] == value]
                    if ids:
                        pos, page = ids[0], 0
                    else:
                        message = f"unknown task {value!r}"
            elif key in ("y", "n", "u"):
                entry["recommendation"] = {
                    "y": CORRECT, "n": INCORRECT, "u": UNSURE,
                }[key]
                touch(entry)
                changed = True
                if entry["recommendation"] in (INCORRECT, UNSURE) and not entry.get("plausibility"):
                    message = "rate plausibility 1-5"
                else:
                    message = f"recommendation = {entry['recommendation']}"
            elif key in ("1", "2", "3", "4", "5"):
                entry["plausibility"] = int(key)
                touch(entry)
                changed = True
                message = f"plausibility = {key}"
            elif key in ("v", "x"):
                entry["canonical_ok"] = key == "v"
                touch(entry)
                changed = True
                message = "canonical ok" if key == "v" else "canonical has a problem"
            elif key == "e":
                note = _prompt_line(keys, "note> ")
                if note is None:
                    message = "note edit cancelled"
                else:
                    note = note.strip()
                    entry["note"] = note
                    touch(entry)
                    changed = True
                    message = "note saved" if note else "note cleared"
            elif key == "d":
                state["ratings"].pop(task["id"], None)
                changed = True
                message = "rating cleared"
            elif key in ("home",):
                pos, page = 0, 0
            elif key in ("end",):
                pos, page = len(order) - 1, 0

            if changed:
                state["cursor"] = task["id"]
                save_state(state_path, state)

    print(f"saved {state_path}")
    print(print_stats(state, tasks))
    print("resume with the same command; the order and position are kept")


# --------------------------------------------------------------------------- #
# reporting
# --------------------------------------------------------------------------- #
def print_stats(state: dict, tasks: list[dict]) -> str:
    completed = sum(
        1 for task in tasks
        if is_complete(state.get("ratings", {}).get(task["id"], {}))
    )
    verdicts = {CORRECT: 0, INCORRECT: 0, UNSURE: 0, None: 0}
    plausibility: list[int] = []
    canonical_problems = []
    for task in tasks:
        entry = state.get("ratings", {}).get(task["id"], {})
        verdicts[entry.get("recommendation")] = verdicts.get(entry.get("recommendation"), 0) + 1
        value = entry.get("plausibility")
        if isinstance(value, int):
            plausibility.append(value)
        if entry.get("canonical_ok") is False:
            canonical_problems.append(task["id"])

    mean = f"{sum(plausibility) / len(plausibility):.2f}" if plausibility else "-"
    lines = [
        f"annotator: {state.get('annotator', '?')}",
        f"complete: {completed}/{len(tasks)}",
        f"recommendation: correct={verdicts.get(CORRECT, 0)} "
        f"incorrect={verdicts.get(INCORRECT, 0)} "
        f"unsure={verdicts.get(UNSURE, 0)} unrated={verdicts.get(None, 0)}",
        f"mean plausibility: {mean}",
    ]
    if canonical_problems:
        lines.append("canonical problems: " + ", ".join(canonical_problems))
    return "\n".join(lines)


def discover_states(state_dir: Path) -> list[Path]:
    return sorted(state_dir.glob("annotation_*.json"))


def cohen_kappa(pairs: list[tuple[bool, bool]]) -> float | None:
    pairs = [(a, b) for a, b in pairs if isinstance(a, bool) and isinstance(b, bool)]
    n = len(pairs)
    if n == 0:
        return None
    observed = sum(a == b for a, b in pairs) / n
    p_a = sum(a for a, _ in pairs) / n
    p_b = sum(b for _, b in pairs) / n
    expected = p_a * p_b + (1 - p_a) * (1 - p_b)
    if expected == 1:
        return 1.0 if observed == 1 else None
    return (observed - expected) / (1 - expected)


# --------------------------------------------------------------------------- #
# merge two annotators into the task files
# --------------------------------------------------------------------------- #
def resolve_states(args) -> tuple[Path, Path]:
    paths: list[Path] = []
    if args.annotator_a:
        paths.append(args.annotator_a)
    if args.annotator_b:
        paths.append(args.annotator_b)
    if len(paths) != 2:
        discovered = discover_states(DEFAULT_STATE_DIR)
        if len(discovered) != 2:
            raise AnnotationError(
                "expected two state files; pass --annotator-a and --annotator-b "
                f"(found {len(discovered)} in {DEFAULT_STATE_DIR})"
            )
        paths = discovered
    if paths[0].resolve() == paths[1].resolve():
        raise AnnotationError("the two annotator state files are identical")
    return paths[0], paths[1]


def _mean(values: list[int]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _verdict_bool(entry: dict) -> bool | None:
    verdict = entry.get("recommendation")
    if verdict == CORRECT:
        return True
    if verdict == INCORRECT:
        return False
    return None


def apply_states(tasks: list[dict], states: list[dict], args) -> int:
    left, right = states
    names = [left.get("annotator", "A"), right.get("annotator", "B")]
    problems: list[str] = []
    kappa_pairs: list[tuple[bool, bool]] = []
    label_mismatches: list[str] = []
    updated: list[dict] = []

    for task in tasks:
        task_id = task["id"]
        entries = [rating_of(state, task_id) for state in states]
        if not all(is_complete(entry) for entry in entries):
            problems.append(f"{task_id}: not complete for both annotators")
        for name, entry in zip(names, entries):
            if entry.get("recommendation") == UNSURE:
                problems.append(f"{task_id}: {name} is unsure")
            if entry.get("canonical_ok") is False:
                problems.append(f"{task_id}: {name} disputes the canonical answer")

        expected = bool(task["recommendation"]["correct"])

        # Proposal-v4: an incorrect item is retained only if its mean
        # plausibility is at least 3 and neither rating is below 2.
        if not expected:
            values = [entry.get("plausibility") for entry in entries]
            if not all(isinstance(value, int) for value in values):
                problems.append(f"{task_id}: plausibility missing for an incorrect item")
            else:
                mean_plausibility = sum(values) / len(values)
                if mean_plausibility < 3:
                    problems.append(
                        f"{task_id}: mean plausibility {mean_plausibility:.2f} < 3"
                    )
                if min(values) < 2:
                    problems.append(
                        f"{task_id}: plausibility {min(values)} is below 2"
                    )

        left_bool = _verdict_bool(entries[0])
        right_bool = _verdict_bool(entries[1])
        kappa_pairs.append((left_bool, right_bool))

        for name, value in zip(names, (left_bool, right_bool)):
            if value is not None and value != expected:
                label_mismatches.append(
                    f"{task_id}: {name} says {CORRECT if value else INCORRECT}, "
                    f"file says {CORRECT if expected else INCORRECT}"
                )

        plausibilities = [
            entry["plausibility"] for entry in entries
            if isinstance(entry.get("plausibility"), int)
        ]
        annotations = task.setdefault("annotations", {})
        annotations["annotator_1"] = names[0]
        annotations["annotator_2"] = names[1]
        annotations["plausibility"] = _mean(plausibilities)
        annotations["plausibility_1"] = entries[0].get("plausibility")
        annotations["plausibility_2"] = entries[1].get("plausibility")
        annotations["recommendation_1"] = entries[0].get("recommendation")
        annotations["recommendation_2"] = entries[1].get("recommendation")
        annotations["canonical_ok_1"] = entries[0].get("canonical_ok")
        annotations["canonical_ok_2"] = entries[1].get("canonical_ok")
        annotations["note_1"] = (entries[0].get("note") or "").strip()
        annotations["note_2"] = (entries[1].get("note") or "").strip()
        updated.append(task)

    kappa = cohen_kappa(kappa_pairs)
    print(f"annotators: {names[0]} + {names[1]}")
    print(f"tasks: {len(tasks)}")
    print(f"Cohen's kappa (recommendation correctness): "
          f"{'n/a' if kappa is None else f'{kappa:.3f}'}")
    if label_mismatches:
        print("\nlabel mismatches:")
        for line in label_mismatches:
            print(f"  - {line}")
    if problems:
        print("\nblocking annotation problems:")
        for line in problems:
            print(f"  - {line}")

    ready = not problems
    if args.force:
        ready = True
        if problems and args.write:
            print("\n--force: writing ready tasks despite the problems above")
    if not ready:
        print("\nnot writing: fix the problems above or pass --force")

    if args.write and ready:
        for task in updated:
            task["status"] = "ready"
            task.setdefault("flags", {})["needs_review"] = False
            write_json(args.tasks_dir / f"{task['id']}.json", task)
        print(f"\nwrote {len(updated)} task files to {args.tasks_dir}")
        if args.force and problems:
            print("warning: tasks are ready but annotations are incomplete or disputed")
    elif not args.write:
        print("\ndry run; add --write to update the task files")
    return 0 if ready or args.force else 1


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--annotator", help="annotator name or initials (interactive mode)")
    parser.add_argument("--state", type=Path, help="state file (default: annotation_<name>.json)")
    parser.add_argument("--tasks-dir", type=Path, default=TASKS_DIR)
    parser.add_argument("--pending", action="store_true", help="only show incomplete tasks")
    parser.add_argument("--start", help="start at this task id")
    parser.add_argument("--seed", type=int, help="reshuffle the task order with this seed")
    parser.add_argument("--sorted", action="store_true", help="present tasks in id order")
    parser.add_argument("--list", action="store_true", help="list tasks and exit")
    parser.add_argument("--stats", action="store_true", help="show progress for state files")
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument("--apply", action="store_true", help="merge two annotator states")
    parser.add_argument("--annotator-a", type=Path, help="first state file for --apply")
    parser.add_argument("--annotator-b", type=Path, help="second state file for --apply")
    parser.add_argument("--write", action="store_true", help="write merged annotations to task files")
    parser.add_argument("--dry-run", action="store_true", help="with --apply, do not write")
    parser.add_argument("--force", action="store_true", help="mark ready even with annotation problems")
    args = parser.parse_args(argv)

    if args.no_color or not sys.stdout.isatty():
        C.enabled = False

    tasks = load_tasks(args.tasks_dir)

    if args.list:
        for task in tasks:
            print(f"{task['id']}  {task['type']:<13} {task['difficulty']:<7} {task['title']}")
        return 0

    if args.stats:
        paths = [args.state] if args.state else discover_states(DEFAULT_STATE_DIR)
        if not paths:
            print(f"no annotation state files in {DEFAULT_STATE_DIR}")
            return 0
        for path in paths:
            print(f"== {path.name}")
            print(print_stats(load_state(path), tasks))
            print()
        return 0

    if args.apply:
        try:
            path_a, path_b = resolve_states(args)
        except AnnotationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        states = [load_state(path_a), load_state(path_b)]
        if args.dry_run:
            args.write = False
        return apply_states(tasks, states, args)

    annotator = args.annotator
    if not annotator:
        if not sys.stdin.isatty():
            print("error: --annotator is required in non-interactive mode", file=sys.stderr)
            return 2
        try:
            annotator = input("annotator name or initials: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\ninterrupted; nothing was written", file=sys.stderr)
            return 130
        if not annotator:
            print("error: annotator name is required", file=sys.stderr)
            return 2
    path = args.state or state_path_for(annotator)
    state = load_state(path, annotator)
    state["annotator"] = annotator
    interactive(tasks, state, path, args)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\ninterrupted; annotations are saved per keypress")
        raise SystemExit(130)
