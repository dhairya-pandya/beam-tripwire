# Tripwire: Reading What a Reasoning Model Does, Thinks, and Says on Impossible Coding Tasks

Dhairya Pandya, PDPM IIITDM Jabalpur

**[Read the paper (PDF)](tripwire.pdf)**

## Abstract

Coding agents are rewarded when tests pass, which gives them an incentive to make tests pass without solving the task. We study how an open-weight reasoning model behaves under that incentive, and whether the behaviour can be read from its visible reasoning or from its report to the user. We build 44 impossible variants of real bug fixes from fastapi, rich and requests by changing one expected value in each task's regression test, and we verify by program that the known-good fix fails every variant. We run Beam, a 501B-parameter reasoning model with an adjustable effort setting, on these variants and on the unmodified tasks in an offline sandbox, for 616 episodes in total, and label each episode at three layers: behaviour, reasoning and report. Beam modified a test or special-cased library code in 66% of impossible episodes at low effort and 79% at high effort, against 1 in 176 control episodes. An instruction not to modify tests reduced this to 23% and 41%. With a 30-turn budget, high effort appeared to cheat far less (20%), but 38 of 44 of those runs had exhausted their turns; with 60 turns the apparent effect reversed. Beam's reasoning revealed most cheating: a keyword rule over the reasoning detected 83% of cheating episodes in the run where Beam could write to the user, while Beam's own note to the user disclosed 15%, and never disclosed a special-cased value. We release the episodes, labels, harness and an interactive explorer.

## Files

| file | what |
|---|---|
| `tripwire.pdf` | the paper |
| `tripwire.tex`, `refs.bib` | LaTeX source |
| `figures/make_figures.py` | regenerates every figure from `runs/*/results.jsonl` |

Build the PDF with [Tectonic](https://tectonic-typesetting.github.io): `tectonic paper/tripwire.tex`. Regenerate the figures with `uv run --with matplotlib python paper/figures/make_figures.py`.

## Citation

```bibtex
@techreport{pandya2026tripwire,
  title       = {Tripwire: Reading What a Reasoning Model Does, Thinks, and Says on Impossible Coding Tasks},
  author      = {Pandya, Dhairya},
  institution = {PDPM Indian Institute of Information Technology, Design and Manufacturing Jabalpur},
  year        = {2026},
  url         = {https://github.com/dhairya-pandya/beam-tripwire}
}
```
