#!/usr/bin/env python3
"""Interactive reviewer for MBPP tasks.

Shows one task per screen in a readable layout (prompt, code with line
numbers, tests) and records a decision: accept / reject / undecided.

State is kept in ``review_state.json`` next to this script, so the review is
resumable. Accepted tasks can be exported as a JSONL subset, ready to be
turned into pilot benchmark task files.

Examples
--------
    python review.py                     # interactive review, resume where left
    python review.py --filter pending    # only undecided tasks
    python review.py --list              # one-line overview of every task
    python review.py --stats             # decision counters
    python review.py --export accepted.jsonl
    python review.py --export-md accepted.md
    python review.py --start 240 --search heapq
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import select
import shutil
import signal
import sys
import termios
import textwrap
import tty
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_TASKS = HERE / "mbpp.jsonl"
DEFAULT_STATE = HERE / "review_state.json"

ACCEPT, REJECT = "accept", "reject"
MARK = {ACCEPT: "✓", REJECT: "✗", None: "·"}
FILTERS = ["all", "pending", "accepted", "rejected"]


# --------------------------------------------------------------------------- #
# data and state
# --------------------------------------------------------------------------- #
def load_tasks(path: Path) -> list[dict]:
    tasks = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                tasks.append(json.loads(line))
    if not tasks:
        raise SystemExit(f"no tasks in {path}")
    return tasks


def load_state(path: Path) -> dict:
    if path.exists():
        with path.open(encoding="utf-8") as fh:
            state = json.load(fh)
    else:
        state = {}
    state.setdefault("version", 1)
    state.setdefault("cursor", None)
    state.setdefault("decisions", {})
    return state


def save_state(path: Path, state: dict) -> None:
    state["updated"] = _dt.datetime.now().isoformat(timespec="seconds")
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)


def decision_of(state: dict, task_id: int) -> str | None:
    return state["decisions"].get(str(task_id), {}).get("decision")


def set_decision(state: dict, task_id: int, decision: str | None) -> None:
    key = str(task_id)
    if decision is None:
        state["decisions"].pop(key, None)
        return
    entry = state["decisions"].setdefault(key, {})
    entry["decision"] = decision
    entry["updated"] = _dt.datetime.now().isoformat(timespec="seconds")


def set_note(state: dict, task_id: int, note: str) -> None:
    key = str(task_id)
    if not note:
        state["decisions"].get(key, {}).pop("note", None)
        return
    state["decisions"].setdefault(key, {})["note"] = note


# --------------------------------------------------------------------------- #
# colours
# --------------------------------------------------------------------------- #
class C:
    enabled = True

    @classmethod
    def _w(cls, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if cls.enabled else text

    @classmethod
    def bold(cls, t): return cls._w("1", t)
    @classmethod
    def dim(cls, t): return cls._w("2", t)
    @classmethod
    def red(cls, t): return cls._w("31", t)
    @classmethod
    def green(cls, t): return cls._w("32", t)
    @classmethod
    def yellow(cls, t): return cls._w("33", t)
    @classmethod
    def cyan(cls, t): return cls._w("36", t)
    @classmethod
    def inverted(cls, t): return cls._w("7", t)


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #
def _width(default: int = 100) -> int:
    try:
        cols = shutil.get_terminal_size((default, 24)).columns
    except OSError:
        cols = default
    return max(50, min(cols, 120))


def _wrap(text: str, width: int, initial: str = "", subsequent: str | None = None) -> list[str]:
    subsequent = initial if subsequent is None else subsequent
    out: list[str] = []
    for raw in text.splitlines() or [""]:
        chunks = textwrap.wrap(
            raw, width=width, initial_indent=initial, subsequent_indent=subsequent,
            break_long_words=False, break_on_hyphens=False, replace_whitespace=False,
        )
        out.extend(chunks or [initial.rstrip()])
    return out


def _section(title: str, width: int) -> list[str]:
    label = f" {title} "
    if len(label) >= width:
        return [C.bold(label.strip())]
    return [C.bold(label + "─" * (width - len(label)))]


def _code_lines(code: str, width: int) -> list[str]:
    code = code.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")
    lines = code.split("\n")
    gutter = len(str(len(lines)))
    body_width = max(20, width - gutter - 3)
    out = []
    for num, line in enumerate(lines, 1):
        line = line.expandtabs(4)
        prefix = C.dim(f"{num:>{gutter}} │ ")
        cont = C.dim(f"{'':>{gutter}} │ ")
        wrapped = textwrap.wrap(
            line, width=body_width, break_long_words=False, break_on_hyphens=False,
            replace_whitespace=False,
        ) or [""]
        out.append(prefix + wrapped[0])
        out.extend(cont + part for part in wrapped[1:])
    return out


def render_card(task: dict, state: dict, width: int, index: int, total: int,
                filter_name: str) -> list[str]:
    tid = task["task_id"]
    decision = decision_of(state, tid)
    badge = {
        ACCEPT: C.green("[accepted]"),
        REJECT: C.red("[rejected]"),
        None: C.dim("[pending]"),
    }[decision]

    code_lines = task["code"].count("\n") + 1
    tests = task.get("test_list") or []
    meta = (f"task {index + 1}/{total} · filter={filter_name} · "
            f"{len(tests)} tests · {code_lines} code lines")
    head = f"{C.bold(f'MBPP #{tid}')}  {badge}  {C.dim(meta)}"

    out = [head, ""]
    out += _section("task", width)
    out += _wrap(task["text"].strip(), width - 2, initial="  ", subsequent="  ")
    out.append("")

    out += _section("code", width)
    out += _code_lines(task["code"], width)

    setup = (task.get("test_setup_code") or "").strip()
    if setup:
        out.append("")
        out += _section("setup", width)
        out += _code_lines(setup, width)

    out.append("")
    out += _section(f"tests ({len(tests)})", width)
    for test in tests:
        out += _wrap(test.strip(), width - 4, initial="  • ", subsequent="    ")

    challenge = task.get("challenge_test_list") or []
    if challenge:
        out.append("")
        out += _section(f"challenge tests ({len(challenge)})", width)
        for test in challenge:
            out += _wrap(test.strip(), width - 4, initial="  • ", subsequent="    ")

    note = state["decisions"].get(str(tid), {}).get("note")
    if note:
        out.append("")
        out += _section("note", width)
        out += _wrap(note, width - 2, initial="  ", subsequent="  ")
    return out


def footer(width: int, page: int, pages: int, extra: str = "") -> str:
    if extra:
        keys = ("[a]ccept  [r]eject  [u]ndo  [j/k]move  [space]page  "
                "[g]oto  [/]find  [f]ilter  [e]note  [q]uit")
        prefix = extra + "  " + C.dim("│") + "  "
    else:
        keys = ("[a]ccept  [r]eject  [u]ndo  [j/k]next/prev task  [space]page  "
                "[g]oto  [/]find  [f]ilter  [e]note  [q]uit")
        prefix = ""
    pageinfo = f"page {page}/{pages}"
    room = width - len(keys) - len(pageinfo) - len(prefix) - 2
    if room < 1:
        pageinfo, room = "", width - len(keys) - len(prefix) - 2
    pad = max(1, room)
    return C.dim(prefix) + C.dim(keys) + " " * pad + C.dim(pageinfo)


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
        """Restore cooked mode for line input."""
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.saved)

    def resume(self) -> None:
        tty.setcbreak(self.fd)

    def get(self) -> str:
        ch = sys.stdin.read(1)
        if ch != "\x1b":
            return ch
        # Arrow / home / end / page escape sequences.
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
        codes = {"A": "up", "B": "down", "C": "right", "D": "left",
                 "H": "home", "F": "end", "5~": "pageup", "6~": "pagedown"}
        return codes.get(buf, "esc")


def _prompt_line(keys: "RawKeys", prompt: str) -> str:
    """Read a line with the terminal temporarily back in cooked mode."""
    sys.stdout.write("\033[?25h")
    sys.stdout.flush()
    keys.pause()
    try:
        return input(prompt)
    except EOFError:
        return ""
    finally:
        keys.resume()
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()


# --------------------------------------------------------------------------- #
# interactive review
# --------------------------------------------------------------------------- #
def interactive(tasks: list[dict], state: dict, state_path: Path, args) -> None:
    by_id = {t["task_id"]: t for t in tasks}
    order = sorted(tasks, key=lambda t: t["task_id"])
    flt = args.filter
    query = (args.search or "").lower()

    def matches(task: dict) -> bool:
        if flt == "pending" and decision_of(state, task["task_id"]) is not None:
            return False
        if flt == "accepted" and decision_of(state, task["task_id"]) != ACCEPT:
            return False
        if flt == "rejected" and decision_of(state, task["task_id"]) != REJECT:
            return False
        if query:
            hay = (task["text"] + "\n" + task["code"]).lower()
            if query not in hay:
                return False
        return True

    view: list[dict] = []
    pos = 0

    def rebuild(anchor_id: int | None = None) -> None:
        nonlocal view, pos
        view = [t for t in order if matches(t)]
        if not view:
            pos = 0
            return
        if anchor_id is not None:
            pos = next((i for i, t in enumerate(view) if t["task_id"] >= anchor_id), len(view) - 1)
        else:
            pos = 0

    start_id = args.start or state.get("cursor")
    rebuild()
    if start_id is not None and view:
        pos = next((i for i, t in enumerate(view) if t["task_id"] >= start_id), 0)
    if not view:
        print(f"no tasks match filter={flt!r}"
              + (f" search={query!r}" if query else ""))
        print(print_summary(tasks, state))
        return

    def remember() -> None:
        if view:
            state["cursor"] = view[pos]["task_id"]

    message = ""
    page = 0

    with RawKeys() as keys:
        while view:
            task = view[pos]
            width = _width()
            rows = shutil.get_terminal_size((width, 24)).lines
            content = render_card(task, state, width, pos, len(view), flt)
            body_rows = max(5, rows - 3)
            pages = max(1, (len(content) + body_rows - 1) // body_rows)
            page = min(page, pages - 1)

            sys.stdout.write("\033[2J\033[H")  # clear + home
            chunk = content[page * body_rows:(page + 1) * body_rows]
            sys.stdout.write("\n".join(chunk))
            sys.stdout.write("\n\n")
            sys.stdout.write(footer(width, page + 1, pages, message))
            sys.stdout.write("\n")
            sys.stdout.flush()
            message = ""

            key = keys.get()
            sys.stdout.write("\033[2J\033[H")
            sys.stdout.flush()

            if key in ("q", "\x03"):
                break
            if key in ("j", "down", "right", "n", "\r"):
                pos, page = min(pos + 1, len(view) - 1), 0
            elif key in ("k", "up", "left", "b"):
                pos, page = max(pos - 1, 0), 0
            elif key in (" ", "pagedown"):
                page = min(page + 1, pages - 1)
            elif key in ("pageup",):
                page = max(page - 1, 0)
            elif key == "home":
                pos, page = 0, 0
            elif key == "end":
                pos, page = len(view) - 1, 0
            elif key in ("a", "y"):
                set_decision(state, task["task_id"], ACCEPT)
                message = C.green(f"accepted #{task['task_id']}")
                pos, page = min(pos + 1, len(view) - 1), 0
                if flt != "all":
                    anchor = view[pos]["task_id"] if view else None
                    rebuild(anchor)
                remember()
                save_state(state_path, state)
            elif key == "r":
                set_decision(state, task["task_id"], REJECT)
                message = C.red(f"rejected #{task['task_id']}")
                pos, page = min(pos + 1, len(view) - 1), 0
                if flt != "all":
                    anchor = view[pos]["task_id"] if view else None
                    rebuild(anchor)
                remember()
                save_state(state_path, state)
            elif key == "u":
                set_decision(state, task["task_id"], None)
                message = C.yellow(f"# {task['task_id']} is pending again")
                remember()
                save_state(state_path, state)
                if flt != "all":
                    anchor = view[pos]["task_id"] if view else None
                    rebuild(anchor)
            elif key == "f":
                previous = flt
                flt = FILTERS[(FILTERS.index(flt) + 1) % len(FILTERS)]
                rebuild(task["task_id"])
                page = 0
                if view:
                    message = C.cyan(f"filter = {flt}")
                else:
                    flt = previous
                    rebuild(task["task_id"])
                    message = C.yellow(f"nothing in filter={FILTERS[(FILTERS.index(flt) + 1) % len(FILTERS)]}")
            elif key == "g":
                raw = _prompt_line(keys, "\ngoto id> ").strip()
                if raw.isdigit() and int(raw) in by_id:
                    if not matches(by_id[int(raw)]):
                        flt, query = "all", ""
                        rebuild()
                    pos = next(i for i, t in enumerate(view) if t["task_id"] == int(raw))
                    page = 0
            elif key == "/":
                raw = _prompt_line(keys, "\nsearch> ").strip().lower()
                if raw:
                    old_query = query
                    query, flt = raw, "all"
                    rebuild(task["task_id"])
                    page = 0
                    if view:
                        message = C.cyan(f"search = {raw!r} ({len(view)} matches)")
                    else:
                        query = old_query
                        rebuild(task["task_id"])
                        message = C.red(f"no match for {raw!r}")
                elif raw == "":
                    query = ""
                    rebuild(task["task_id"])
            elif key == "e":
                current = state["decisions"].get(str(task["task_id"]), {}).get("note", "")
                raw = _prompt_line(keys, f"\nnote [{current}] (empty=clear)> ")
                if raw.strip():
                    set_note(state, task["task_id"], raw.strip())
                elif raw == "":
                    set_note(state, task["task_id"], "")
                save_state(state_path, state)
            elif key == "?":
                message = C.cyan("a/y accept · r reject · u undo · e note · g goto · / find · f filter")
            remember()
            save_state(state_path, state)

    sys.stdout.write("\033[?25h")
    print(print_summary(tasks, state))


def print_summary(tasks: list[dict], state: dict) -> str:
    acc = sum(1 for t in tasks if decision_of(state, t["task_id"]) == ACCEPT)
    rej = sum(1 for t in tasks if decision_of(state, t["task_id"]) == REJECT)
    pending = len(tasks) - acc - rej
    return (f"reviewed: {acc + rej}/{len(tasks)}  "
            f"accepted: {acc}  rejected: {rej}  pending: {pending}")


# --------------------------------------------------------------------------- #
# non-interactive modes
# --------------------------------------------------------------------------- #
def line_mode(tasks: list[dict], state: dict, state_path: Path, args) -> None:
    """Fallback for pipes/redirected input: print a card, read a command."""
    order = sorted(tasks, key=lambda t: t["task_id"])
    start = args.start or state.get("cursor") or 0
    pos = next((i for i, t in enumerate(order) if t["task_id"] >= start), 0)
    width = _width()

    while pos < len(order):
        task = order[pos]
        content = render_card(task, state, width, pos, len(order), "all")
        print("\n".join(content))
        try:
            cmd = input("\n[a]ccept [r]eject [s]kip [b]ack [n]ote [g]id [q]uit > ").strip()
        except EOFError:
            break
        if cmd in ("a", "y"):
            set_decision(state, task["task_id"], ACCEPT)
            save_state(state_path, state)
            pos += 1
        elif cmd == "r":
            set_decision(state, task["task_id"], REJECT)
            save_state(state_path, state)
            pos += 1
        elif cmd == "b":
            pos = max(0, pos - 1)
        elif cmd == "q":
            break
        elif cmd.startswith("g") and cmd[1:].strip().isdigit():
            target = int(cmd[1:].strip())
            pos = next((i for i, t in enumerate(order) if t["task_id"] >= target), pos)
        elif cmd.startswith("n"):
            raw = input("note> ").strip()
            set_note(state, task["task_id"], "" if raw == "-" else raw)
            save_state(state_path, state)
        else:
            pos += 1
        state["cursor"] = task["task_id"]
        save_state(state_path, state)
    print(print_summary(tasks, state))


def list_mode(tasks: list[dict], state: dict) -> None:
    width = _width()
    for task in sorted(tasks, key=lambda t: t["task_id"]):
        dec = decision_of(state, task["task_id"])
        colour = {ACCEPT: C.green, REJECT: C.red, None: C.dim}[dec]
        mark = colour(f" {MARK[dec]} ")
        text = " ".join(task["text"].split())
        room = max(20, width - 32)
        if len(text) > room:
            text = text[:room - 1] + "…"
        meta = f"{len(task['test_list'])}t {task['code'].count(chr(10)) + 1:>2}l"
        print(f"{mark} #{task['task_id']:>4}  {meta:>6}  {text}")
    print()
    print(print_summary(tasks, state))


def export_jsonl(tasks: list[dict], state: dict, dest: Path) -> None:
    chosen = [t for t in sorted(tasks, key=lambda t: t["task_id"])
              if decision_of(state, t["task_id"]) == ACCEPT]
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8") as fh:
        for task in chosen:
            fh.write(json.dumps(task, ensure_ascii=False) + "\n")
    notes = {str(t["task_id"]): state["decisions"].get(str(t["task_id"]), {}).get("note")
             for t in chosen if state["decisions"].get(str(t["task_id"]), {}).get("note")}
    print(f"wrote {len(chosen)} accepted tasks to {dest}")
    if notes:
        sidecar = dest.with_suffix(".notes.json")
        sidecar.write_text(json.dumps(notes, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
        print(f"wrote {len(notes)} notes to {sidecar}")


def export_md(tasks: list[dict], state: dict, dest: Path) -> None:
    chosen = [t for t in sorted(tasks, key=lambda t: t["task_id"])
              if decision_of(state, t["task_id"]) == ACCEPT]
    lines = ["# Selected MBPP tasks", ""]
    for task in chosen:
        tid = task["task_id"]
        note = state["decisions"].get(str(tid), {}).get("note")
        lines += [f"## MBPP #{tid}", "", task["text"].strip(), "", "```python",
                  task["code"].replace("\r\n", "\n").rstrip(), "```", "", "Tests:", "",
                  "```python"]
        lines += [t.strip() for t in task["test_list"]]
        lines += ["```", ""]
        if note:
            lines += [f"> note: {note}", ""]
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(chosen)} accepted tasks to {dest}")


# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Review MBPP tasks and pick which to add to the pilot benchmark.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""examples:
  python review.py                     interactive review, resume where you left
  python review.py --filter pending    only undecided tasks
  python review.py --search heapq      pre-filter by text/code substring
  python review.py --list              one-line overview of every task
  python review.py --stats             decision counters
  python review.py --export accepted.jsonl
  python review.py --export-md accepted.md
""",
    )
    ap.add_argument("--tasks", type=Path, default=DEFAULT_TASKS, help="input JSONL")
    ap.add_argument("--state", type=Path, default=DEFAULT_STATE, help="decisions file")
    ap.add_argument("--filter", choices=FILTERS, default="all",
                    help="which tasks to show interactively (default: all)")
    ap.add_argument("--search", default=None, help="only tasks containing this text")
    ap.add_argument("--start", type=int, default=None, help="start at this task id")
    ap.add_argument("--list", action="store_true", help="print a one-line overview and exit")
    ap.add_argument("--stats", action="store_true", help="print counters and exit")
    ap.add_argument("--export", type=Path, metavar="JSONL",
                    help="write accepted tasks as a JSONL subset and exit")
    ap.add_argument("--export-md", type=Path, metavar="MD",
                    help="write accepted tasks as a Markdown review sheet and exit")
    ap.add_argument("--no-color", action="store_true", help="disable ANSI colours")
    args = ap.parse_args(argv)

    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    C.enabled = not args.no_color and sys.stdout.isatty()
    tasks = load_tasks(args.tasks)
    state = load_state(args.state)

    if args.export:
        export_jsonl(tasks, state, args.export)
        return 0
    if args.export_md:
        export_md(tasks, state, args.export_md)
        return 0
    if args.list:
        list_mode(tasks, state)
        return 0
    if args.stats:
        print(print_summary(tasks, state))
        return 0

    if not sys.stdin.isatty():
        line_mode(tasks, state, args.state, args)
        return 0

    try:
        interactive(tasks, state, args.state, args)
    except KeyboardInterrupt:
        print()
        print(print_summary(tasks, state))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
