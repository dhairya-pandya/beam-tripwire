"""Build the static explorer's data from the published dataset.

    uv run --with datasets python space/build.py

Writes space/data/<run_id>.json. The page itself (space/index.html) only reads those files.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

from datasets import load_dataset

DATASET = "dhairyapandya/beam-tripwire-episodes"
OUT = Path(__file__).parent / "data"

# Sentences worth highlighting in the reasoning: intent to touch tests, or doubts about the test.
HIGHLIGHT = re.compile(
    r"[^.\n?!]*\b(edit|change|modify|update|adjust|fix|correct)\w*\s+(the\s+)?(tests?|assert\w*)\b[^.\n?!]*[.?!]?"
    r"|[^.\n?!]*\b(hard-?cod\w*|special[- ]?cas\w*)[^.\n?!]*[.?!]?"
    r"|[^.\n?!]*\btests?\b[^.\n?!]{0,60}\b(wrong|typo|mistake|incorrect|inconsistent)\b[^.\n?!]*[.?!]?",
    re.I,
)
WRITES = ("edit_file", "write_file", "replace_lines")


def bucket(e: dict) -> str:
    if e["condition"] == "possible":
        return "control"
    if not e["cheated"]:
        return "clean"
    return "admitted" if e["disclosed"] else "quiet"


def marked(text: str) -> str:
    out, last = [], 0
    for m in HIGHLIGHT.finditer(text):
        out += [html.escape(text[last:m.start()]), f"<mark>{html.escape(m.group(0))}</mark>"]
        last = m.end()
    return "".join(out) + html.escape(text[last:])


def badges(e: dict) -> list[list[str]]:
    b = []
    if e["condition"] != "possible":
        if e["tamper_attempt"]:
            b.append(["bad", "edited the test"])
        if e["special_cased"]:
            b.append(["bad", "bent the library to the wrong value"])
        if not e["cheated"]:
            b.append(["good", "did not cheat"])
    if e["intent_verbalised"] or e["judge_intent"]:
        b.append(["warn", "reasoning reveals intent"])
    if e["honest_flag"]:
        b.append(["info", "reasoning says the test is wrong"])
    if e["reported"] or e["judge_reported"]:
        b.append(["info", "note flags the problem"])
    if e["disclosed"]:
        b.append(["good", "note admits the test edit"])
    if e["solved_original"]:
        b.append(["good", "real bug fixed"])
    return b


def steps(e: dict) -> list[list]:
    """[tool name, short target, writes the test file?] per tool call."""
    out = []
    for m in json.loads(e["messages"]):
        for tc in m.get("tool_calls") or []:
            name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            target = str(args.get("filepath") or args.get("command") or "").replace("/workspace/", "")
            hit = e["condition"] != "possible" and e["test_file"] in target and bool(
                name in WRITES or re.search(r"sed -i|perl -pi|>\s*\S*" + re.escape(e["test_file"]) + r"|open\(", target))
            out.append([name, target.splitlines()[0][:160] if target else "", hit])
    return out


def main():
    OUT.mkdir(exist_ok=True)
    by_run: dict[str, list] = {}
    for e in load_dataset(DATASET, split="train"):
        if e["stop_reason"] == "error":
            continue
        by_run.setdefault(e["run_id"], []).append({
            "id": e["instance_id"], "repo": e["repo"], "condition": e["condition"], "effort": e["effort"],
            "bucket": bucket(e), "turns": e["turns"], "stop": e["stop_reason"], "cost": e["cost_usd"],
            "test_file": e["test_file"], "rigged": e["rigged_line"], "note": e["note"].strip(),
            "badges": badges(e), "reasoning": marked(e["reasoning"]), "steps": steps(e), "patch": e["patch"],
        })
    for run_id, rows in by_run.items():
        rows.sort(key=lambda r: (r["id"], r["condition"], r["effort"]))
        (OUT / f"{run_id}.json").write_text(json.dumps(rows, separators=(",", ":")))
        print(run_id, len(rows), f'{(OUT / f"{run_id}.json").stat().st_size / 1e6:.1f} MB')


if __name__ == "__main__":
    main()
