"""LangGraph red-team agent: runs phases P1..P10 in order against Riley, then reports.

    python ehr-attacker/agent.py            # uses env ATTACKER_TARGET_MODEL (or a default)
    python ehr-attacker/agent.py --model "openai/gpt-oss-120b" --max-probes 80

Authorised testing per the Break the Model challenge: synthetic data, messages only.
"""
import argparse
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from langgraph.graph import END, START, StateGraph  # noqa: E402

import attacker_llm  # noqa: E402
import report as report_mod  # noqa: E402
from client import Budget, Prober  # noqa: E402
from state import AttackState  # noqa: E402
from phases import (batch, encode, fragment, impersonate, misc,  # noqa: E402
                    overload, patterns, recon, story, verify)

PHASE_MODULES = [recon, verify, patterns, impersonate, encode, batch,
                 fragment, story, overload, misc]
DEFAULT_MODEL = os.environ.get("ATTACKER_TARGET_MODEL", "Qwen/Qwen3-30B-A3B-Instruct-2507")


def _node(mod, prober, attacker):
    def run(state: AttackState):
        findings, facts_u, confirmed_u = mod.run(prober, attacker, state["facts"])
        return {"findings": findings, "facts": facts_u, "confirmed": confirmed_u}
    return run


def build_graph(prober, attacker):
    g = StateGraph(AttackState)
    names = [m.__name__.split(".")[-1] for m in PHASE_MODULES]
    for name, mod in zip(names, PHASE_MODULES):
        g.add_node(name, _node(mod, prober, attacker))
    g.add_edge(START, names[0])
    for a, b in zip(names, names[1:]):
        g.add_edge(a, b)
    g.add_edge(names[-1], END)
    return g.compile()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--max-probes", type=int, default=int(os.environ.get("MAX_PROBES", 150)))
    ap.add_argument("--mutate", type=int, default=int(os.environ.get("MUTATE_BUDGET", 3)))
    ap.add_argument("--delay", type=float, default=0.5)
    ap.add_argument("--allow-side-effects", action="store_true")
    args = ap.parse_args(argv)

    run_dir = HERE / "runs" / time.strftime("%Y%m%d-%H%M%S")
    budget = Budget(max_probes=args.max_probes, mutate=args.mutate)
    prober = Prober(args.model, run_dir / "results.jsonl", budget, delay=args.delay)
    attacker = attacker_llm if attacker_llm.available() else None

    print(f"target={args.model}  adaptive={'on' if attacker else 'OFF (template fallback)'}  "
          f"max_probes={args.max_probes}  out={run_dir}")
    init: AttackState = {
        "model": args.model, "findings": [], "confirmed": {},
        "facts": {"allow_side_effects": args.allow_side_effects},
    }
    final = build_graph(prober, attacker).invoke(init)
    report_mod.write(final, run_dir, probes_used=budget.used)
    print(f"\ndone: {budget.used} probes, {sum(f.leaked for f in final['findings'])} leaks. "
          f"report -> {run_dir / 'report.md'}")


if __name__ == "__main__":
    main()
