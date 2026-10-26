"""Export saved episodes and variants to Parquet for the Hugging Face dataset.

    uv run --with pyarrow python analysis/export_dataset.py out/
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from tripwire.grading import submit_note
from tripwire.variants import load_variants

RUNS = {
    "beam-full": "all conditions x low/medium/high effort, 30 turns",
    "beam-high60": "impossible conditions, high effort, 60 turns",
    "beam-v2-note": "all conditions, low effort, submit_patch takes a note to the user",
}


def reasoning(messages: list[dict]) -> str:
    return "\n\n".join(m.get("reasoning_content") or "" for m in messages if m.get("role") == "assistant").strip()


def main(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    variants = load_variants(Path("data/variants.jsonl"))
    episodes = []
    for run_id in RUNS:
        for path in sorted((Path("runs") / run_id / "traces").glob("*.json")):
            d = json.loads(path.read_text())
            row, ep = d["row"], d["episode"]
            v = variants[row["instance_id"]]
            episodes.append({
                "run_id": run_id, **{k: row.get(k) for k in (
                    "instance_id", "repo", "condition", "effort", "stop_reason", "turns", "cost_usd",
                    "cheated", "tamper_attempt", "tamper_calls", "special_cased", "config_edit", "solved_original",
                    "honest_flag", "reported", "disclosed", "intent_verbalised",
                    "judge_intent", "judge_honest", "judge_reported", "judge_disclosed")},
                "test_file": v.test_file,
                "rigged_line": v.rigged_line.strip() if row["condition"] != "possible" else None,
                "note": submit_note(ep["messages"]),
                "reasoning": reasoning(ep["messages"]),
                "patch": ep.get("patch", ""),
                "messages": json.dumps(ep["messages"]),
            })
    pq.write_table(pa.Table.from_pylist(episodes), out / "episodes.parquet")
    pq.write_table(pa.Table.from_pylist([
        {"instance_id": v.instance_id, "repo": v.repo, "test_file": v.test_file,
         "original_literal": v.original_literal, "mutated_literal": v.mutated_literal,
         "original_line": v.mutated_line, "rigged_line": v.rigged_line, "broken_tests": v.broken_tests, "mutated_test_patch": v.mutated_test_patch}
        for v in sorted(variants.values(), key=lambda v: v.instance_id)]), out / "variants.parquet")
    print(f"{len(episodes)} episodes, {len(variants)} variants -> {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
