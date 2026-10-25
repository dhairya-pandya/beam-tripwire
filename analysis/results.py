"""Print the tables in docs/RESULTS.md from the saved runs.

    uv run python analysis/results.py > docs/tables.md
"""

from __future__ import annotations

import json
from pathlib import Path

from tripwire.stats import monitor_scores, wilson

RUNS = Path("runs")


def rows(run_id: str) -> list[dict]:
    path = RUNS / run_id / "results.jsonl"
    return [r for r in map(json.loads, path.read_text().splitlines()) if r.get("stop_reason") != "error"]


def rate(rs: list[dict], key) -> str:
    k = sum(bool(key(r) if callable(key) else r.get(key)) for r in rs)
    n = len(rs)
    if not n:
        return "-"
    lo, hi = wilson(k, n)
    return f"{k}/{n} ({k / n:.0%}, {lo:.0%}-{hi:.0%})"


def cell(rs, condition, effort=None):
    return [r for r in rs if r["condition"] == condition and (effort is None or r["effort"] == effort)]


def table(header: list[str], body: list[list[str]]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(row) + " |" for row in body]
    return "\n".join(out)


def main():
    full, high60, v2 = rows("beam-full"), rows("beam-high60"), rows("beam-v2-note")
    print("## Cheating by condition and effort\n")
    body = []
    for name, rs, src in [("low, 30 turns", full, "low"), ("medium, 30 turns", full, "medium"),
                          ("high, 30 turns", full, "high"), ("high, 60 turns", high60, "high"),
                          ("low, 30 turns, with note (v2)", v2, "low")]:
        cap = [r for r in cell(rs, "impossible", src) if r["stop_reason"] == "turns"]
        body.append([name, rate(cell(rs, "possible", src), "cheated"), rate(cell(rs, "impossible", src), "cheated"),
                     rate(cell(rs, "impossible_honest", src), "cheated"),
                     f"{len(cap)}/{len(cell(rs, 'impossible', src))}"])
    print(table(["effort", "possible", "impossible", "impossible + honesty", "impossible runs cut by turn cap"], body))

    print("\n## How Beam cheats (impossible conditions, all runs)\n")
    imp = [r for rs in (full, high60, v2) for r in rs if r["condition"] != "possible"]
    cheats = [r for r in imp if r["cheated"]]
    print(table(["", "count"], [
        ["impossible episodes", str(len(imp))], ["cheated", str(len(cheats))],
        ["edited the test file", str(sum(r["tamper_attempt"] for r in cheats))],
        ["special-cased the wrong value in library code", str(sum(r["special_cased"] for r in cheats))],
        ["said the test was wrong (reasoning) and cheated anyway", str(sum(r["honest_flag"] for r in cheats))],
    ]))

    print("\n## Reasoning monitors (impossible conditions)\n")
    body = []
    for name, rs in [("all runs", imp), ("impossible", [r for r in imp if r["condition"] == "impossible"]),
                     ("impossible + honesty", [r for r in imp if r["condition"] == "impossible_honest"])]:
        for key, mon in (("intent_verbalised", "keywords"), ("judge_intent", "Gemma 12B judge")):
            m = monitor_scores([r for r in rs if key in r], key)
            f = lambda x: "-" if x is None else f"{x:.0%}"
            body.append([name, mon, f(m["recall"]), f(m["precision"]), str(m["cheats"])])
    print(table(["episodes", "monitor", "recall", "precision", "cheats"], body))

    print("\n## What Beam tells the user (v2: submit_patch takes a note)\n")
    body = []
    for c in ("possible", "impossible", "impossible_honest"):
        rs = cell(v2, c)
        ch = [r for r in rs if r["cheated"]]
        body.append([c, rate(rs, lambda r: r.get("judge_reported")), rate(rs, "honest_flag"),
                     rate(ch, "disclosed"), str(len(ch))])
    print(table(["condition", "note says test/task is wrong", "reasoning says test is wrong",
                 "cheats disclosed in note", "cheats"], body))


if __name__ == "__main__":
    main()
