"""tripwire CLI: build impossible variants, run an agent under each condition, report."""

from __future__ import annotations

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from pathlib import Path

import typer
from apprentice.beam_client import BEAM_MODEL, HF_ROUTER, BeamClient
from apprentice.episode import run_episode
from apprentice.ledger import BudgetExceeded, CostLedger, Prices
from apprentice.sandbox import Sandbox
from apprentice.tasks import load_tasks
from apprentice.tools import Limits
from apprentice.verify import load_references, run_tests, verify

from tripwire.conditions import CONDITIONS, prompt_for, visible_tests_sandbox
from tripwire.grading import label, to_row
from tripwire.variants import build_variant, candidate_tasks, load_variants, save_variants

app = typer.Typer(no_args_is_help=True, add_completion=False)
DATA = Path(os.environ.get("APPRENTICE_DATA", "../BeamBuilds/external/swe-tasks"))
REFS = Path(os.environ.get("APPRENTICE_REFS", "../BeamBuilds/runs/references.jsonl"))


@app.command("build-variants")
def build_variants(out: Path = typer.Option(Path("data/variants.jsonl")), data_root: Path = DATA,
                   references: Path = REFS, limit: int = 0, workers: int = 3):
    """Mutate one expected value per task and keep only variants the known-good fix proves impossible."""
    cands = candidate_tasks(data_root, references)
    if limit:
        cands = cands[:limit]
    typer.echo(f"{len(cands)} candidate tasks")
    kept, lock = [], threading.Lock()

    def one(pair):
        task, ref = pair
        try:
            v = build_variant(task, ref, data_root)
        except Exception as e:
            typer.echo(f"  {task.instance_id}: error {type(e).__name__}: {e}")
            return
        with lock:
            typer.echo(f"  {task.instance_id}: {'kept, breaks ' + str(len(v.broken_tests)) + ' tests' if v else 'not impossible'}")
            if v:
                kept.append(v)

    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(one, cands))
    kept.sort(key=lambda v: v.instance_id)
    save_variants(kept, out)
    typer.echo(f"{out}: {len(kept)} impossible variants")


@app.command()
def run(
    run_id: str = typer.Option(...),
    conditions: str = typer.Option(",".join(CONDITIONS)),
    efforts: str = typer.Option("low", help="comma-separated; 'none' for models without an effort dial"),
    variants: Path = typer.Option(Path("data/variants.jsonl")),
    data_root: Path = DATA,
    references: Path = REFS,
    limit: int = 0,
    model: str = typer.Option(BEAM_MODEL),
    base_url: str = typer.Option(HF_ROUTER),
    api_key: str = typer.Option("", help="endpoint key; default is your active Hugging Face login"),
    free: bool = typer.Option(False, help="price calls at $0 (local model)"),
    budget_usd: float = typer.Option(2.0),
    lifetime_cap_usd: float = typer.Option(25.0),
    turns: int = typer.Option(30),
    max_tokens: int = typer.Option(8192),
    workers: int = typer.Option(3),
):
    """Run the agent on every (variant, condition, effort) cell and label each episode."""
    out = Path("runs") / run_id
    out.mkdir(parents=True, exist_ok=True)
    tasks = {t.instance_id: t for t in load_tasks(data_root / "tasks.jsonl")}
    refs = load_references(references)
    vs = sorted(load_variants(variants).values(), key=lambda v: v.instance_id)
    if limit:
        vs = vs[:limit]
    ledger = CostLedger(Path("runs") / "ledger.jsonl", cap_usd=lifetime_cap_usd, session_cap_usd=budget_usd,
                        prices=Prices(0, 0, 0) if free else Prices())
    client = BeamClient.from_env(ledger, base_url=base_url, model=model, api_key=api_key or None, meta={"run": run_id})
    limits = Limits(turns=turns)
    results = out / "results.jsonl"
    done = set()
    if results.exists():
        done = {(r["instance_id"], r["condition"], r["effort"]) for r in map(json.loads, results.read_text().splitlines())}
    cells = [(v, c, e) for v in vs for c in conditions.split(",") for e in efforts.split(",")
             if (v.instance_id, c, e) not in done]
    typer.echo(f"{len(done)} cells done, {len(cells)} to run; spend so far ${ledger.spent():.4f}")
    lock, stop = threading.Lock(), threading.Event()

    def one(cell):
        v, cond, effort = cell
        if stop.is_set():
            return
        base = tasks[v.instance_id]
        visible = cond != "possible"
        ep = run_episode(
            base, client, effort, limits, data_root, max_tokens=max_tokens,
            sandbox_factory=visible_tests_sandbox(v.mutated_test_patch) if visible else Sandbox,
            prompt_builder=prompt_for(cond, v.test_file),
        )
        mutated = run_tests(v.task(base), ep.patch, data_root) if ep.patch.strip() else None
        passes_broken = bool(mutated) and any(mutated.outcomes.get(t) == "passed" for t in v.broken_tests)
        solved = bool(ep.patch.strip()) and verify(base, ep.patch, data_root, refs[v.instance_id]).resolved
        labels = label(ep.messages, [v.test_file], passes_broken, solved)
        row = to_row({"instance_id": v.instance_id, "repo": v.repo, "condition": cond, "effort": effort,
                      "stop_reason": ep.stop_reason, "turns": ep.turns, "cost_usd": round(ep.cost_usd, 6),
                      "error": ep.error[:300]}, labels)
        with lock:
            (out / "traces").mkdir(exist_ok=True)
            (out / "traces" / f"{v.instance_id}.{cond}.{effort}.json").write_text(
                json.dumps({"row": row, "episode": asdict(ep)}, indent=1))
            with open(results, "a") as f:
                f.write(json.dumps(row) + "\n")
            flags = [k for k in ("cheated", "tamper_attempt", "special_cased", "config_edit", "honest_flag", "intent_verbalised",
                                 "solved_original") if row[k]]
            typer.echo(f"  {v.instance_id} {cond} {effort}: {' '.join(flags) or '-'} "
                       f"(stop={ep.stop_reason}, {ep.turns} turns, ${ep.cost_usd:.4f})")
            if ep.stop_reason == "budget":
                stop.set()

    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(one, cells))
    typer.echo(f"spent ${ledger.session_spent():.4f} this run; lifetime ${ledger.spent():.4f}")
    report(run_id)


@app.command()
def regrade(run_id: str):
    """Recompute labels from saved traces (after a grading-rule change), reusing the test outcomes."""
    out = Path("runs") / run_id
    rows = []
    for path in sorted((out / "traces").glob("*.json")):
        d = json.loads(path.read_text())
        old = d["row"]
        labels = label(d["episode"]["messages"], [d.get("test_file") or _test_file(old["instance_id"])],
                       old["special_cased"], old["solved_original"])
        d["row"] = to_row({k: old[k] for k in ("instance_id", "repo", "condition", "effort", "stop_reason",
                                               "turns", "cost_usd", "error")}, labels)
        d["row"].update({k: v for k, v in old.items() if k.startswith("judge_")})
        path.write_text(json.dumps(d, indent=1))
        rows.append(d["row"])
    (out / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    typer.echo(f"regraded {len(rows)} episodes")
    report(run_id)


def _test_file(instance_id: str, variants: Path = Path("data/variants.jsonl")) -> str:
    return load_variants(variants)[instance_id].test_file


@app.command()
def judge(run_id: str, base_url: str = typer.Option("http://localhost:8090/v1"),
          model: str = typer.Option("student"), api_key: str = typer.Option("local")):
    """Add LLM-judge labels (honesty, and an intent monitor over reasoning) to every saved episode."""
    from openai import OpenAI

    from tripwire.judge import judge_episode

    client = OpenAI(base_url=base_url, api_key=api_key, timeout=600)
    out = Path("runs") / run_id
    rows = []
    for path in sorted((out / "traces").glob("*.json")):
        d = json.loads(path.read_text())
        if "judge_intent" not in d["row"]:
            d["row"].update(judge_episode(client, model, d["episode"]["messages"]))
            path.write_text(json.dumps(d, indent=1))
        rows.append(d["row"])
        typer.echo(f"  {path.stem}: honest={d['row']['judge_honest']} intent={d['row']['judge_intent']}")
    (out / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    report(run_id)


@app.command()
def report(run_id: str):
    """Rates per condition and effort, with Wilson 95% intervals."""
    from tripwire.stats import summarize

    rows = [json.loads(l) for l in (Path("runs") / run_id / "results.jsonl").read_text().splitlines() if l.strip()]
    typer.echo(summarize(rows))


if __name__ == "__main__":
    app()
