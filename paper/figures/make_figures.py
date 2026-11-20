"""Figures for the Tripwire paper, computed from runs/<run-id>/results.jsonl.

    uv run --with matplotlib python paper/figures/make_figures.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt

from tripwire.stats import monitor_scores, wilson

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
# Okabe-Ito, colourblind safe.
BLUE, ORANGE, GREY, VERMILION = "#0072B2", "#E69F00", "#999999", "#D55E00"

plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "savefig.dpi": 300, "savefig.bbox": "tight"})


def rows(run_id: str) -> list[dict]:
    path = ROOT / "runs" / run_id / "results.jsonl"
    return [r for r in map(json.loads, path.read_text().splitlines()) if r.get("stop_reason") != "error"]


def cell(rs, condition, effort):
    return [r for r in rs if r["condition"] == condition and r["effort"] == effort]


def rate(rs, key="cheated"):
    k, n = sum(bool(r[key]) for r in rs), len(rs)
    lo, hi = wilson(k, n)
    return k / n, k / n - lo, hi - k / n


full, high60, v2 = rows("beam-full"), rows("beam-high60"), rows("beam-v2-note")
SETTINGS = [("low\n30 turns", full, "low"), ("medium\n30 turns", full, "medium"), ("high\n30 turns", full, "high"),
            ("high\n60 turns", high60, "high"), ("low, v2\n30 turns", v2, "low")]

# Figure 1: cheating rate by setting and condition.
fig, ax = plt.subplots(figsize=(6.2, 2.6))
w = 0.38
for j, (cond, label, color) in enumerate([("impossible", "impossible", VERMILION),
                                          ("impossible_honest", "impossible + honesty instruction", BLUE)]):
    xs, ys, lo, hi = [], [], [], []
    for i, (_, rs, eff) in enumerate(SETTINGS):
        p, l, h = rate(cell(rs, cond, eff))
        xs.append(i + (j - 0.5) * w); ys.append(p); lo.append(l); hi.append(h)
    ax.bar(xs, ys, w, color=color, label=label, yerr=[lo, hi], capsize=2, error_kw={"lw": 0.8})
ax.set_xticks(range(len(SETTINGS)), [s[0] for s in SETTINGS])
ax.set_ylim(0, 1); ax.set_ylabel("cheating rate")
ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
ax.legend(frameon=False, loc="upper left", ncol=2)
fig.savefig(OUT / "fig1_cheating_rates.png"); fig.savefig(OUT / "fig1_cheating_rates.pdf")

# Figure 2: how impossible-condition episodes ended, and the cheat rate among those that submitted.
fig, ax = plt.subplots(figsize=(6.2, 2.4))
labels, sub, cap, cheat_sub = [], [], [], []
for name, rs, eff in SETTINGS[:4]:
    c = cell(rs, "impossible", eff)
    s = [r for r in c if r["stop_reason"] == "submitted"]
    labels.append(name); sub.append(len(s) / len(c)); cap.append(sum(r["stop_reason"] == "turns" for r in c) / len(c))
    cheat_sub.append(sum(r["cheated"] for r in s) / len(s) if s else 0)
x = range(len(labels))
ax.bar(x, sub, 0.55, color=BLUE, label="submitted a patch")
ax.bar(x, cap, 0.55, bottom=sub, color=GREY, label="hit the turn cap")
ax.plot(x, cheat_sub, "o", color=VERMILION, label="cheating rate among submitted")
ax.set_xticks(list(x), labels); ax.set_ylim(0, 1.05); ax.set_ylabel("share of impossible episodes")
ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.32), ncol=3)
fig.savefig(OUT / "fig2_turn_cap.png"); fig.savefig(OUT / "fig2_turn_cap.pdf")

# Figure 3: share of cheats each layer reveals, on the same episodes (v2 is the only run with a note channel).
imp = [r for r in v2 if r["condition"] != "possible"]
kw, jd = monitor_scores(imp, "intent_verbalised"), monitor_scores(imp, "judge_intent")
v2_cheats = [r for r in imp if r["cheated"]]
note = sum(r["disclosed"] for r in v2_cheats) / len(v2_cheats)
bars = [("reasoning,\nkeyword rule", kw["recall"], ORANGE), ("reasoning,\nGemma 12B judge", jd["recall"], ORANGE),
        ("note to the user", note, GREY)]
fig, ax = plt.subplots(figsize=(4.2, 2.3))
ax.barh(range(3), [b[1] for b in bars], color=[b[2] for b in bars], height=0.55)
for i, b in enumerate(bars):
    ax.text(b[1] + 0.02, i, f"{b[1]:.0%}", va="center")
ax.set_yticks(range(3), [b[0] for b in bars]); ax.invert_yaxis()
ax.set_xlim(0, 1); ax.set_xlabel("share of cheating episodes revealed")
ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
fig.savefig(OUT / "fig3_layers.png"); fig.savefig(OUT / "fig3_layers.pdf")

print(f"fig3: keyword {kw['recall']:.3f}/{kw['precision']:.3f} judge {jd['recall']:.3f}/{jd['precision']:.3f} "
      f"note {note:.3f} ({sum(r['disclosed'] for r in v2_cheats)}/{len(v2_cheats)})")
