"""Run the static corpus against one or all models -> per-category leak-rate scorecard.

    python ehr-attacker/benchmark/bench.py                 # all 4 challenge models
    python ehr-attacker/benchmark/bench.py --model "openai/gpt-oss-120b"

Fixed, non-adaptive battery (single shot per prompt) so scores are comparable across runs and
models — the "harden these categories first" ranking. Separate from the narrative agent run.
"""
import argparse
import json
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE.parent))
import btm  # noqa: E402
import judge  # noqa: E402

CORPUS = HERE / "corpus.jsonl"
MODELS = ["Qwen/Qwen3-30B-A3B-Instruct-2507", "openai/gpt-oss-120b",
          "Qwen/Qwen3-235B-A22B-Instruct-2507", "deepseek-ai/DeepSeek-V4-Pro-0813"]


def _run_one(model, row):
    try:
        reply = btm.chat(row["prompt"], model=model, conversation_id=btm.new_conversation())
    except Exception as e:  # noqa: BLE001
        reply = f"__ERROR__ {e}"
    leaked, severity, _ = judge.score(reply)
    return {"id": row["id"], "category": row["category"], "leaked": leaked,
            "severity": severity, "turn": btm.LAST_TURN_ID}


def bench(models, workers=4):
    corpus = [json.loads(l) for l in CORPUS.read_text().splitlines() if l.strip()]
    scorecard = {}
    for model in models:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            res = list(ex.map(lambda r: _run_one(model, r), corpus))
        cats = defaultdict(lambda: {"n": 0, "leaks": 0, "max_sev": "none"})
        order = {"none": 0, "low": 1, "med": 2, "high": 3, "critical": 4}
        for r in res:
            c = cats[r["category"]]
            c["n"] += 1
            if r["leaked"]:
                c["leaks"] += 1
                if order[r["severity"]] > order[c["max_sev"]]:
                    c["max_sev"] = r["severity"]
        for c in cats.values():
            c["leak_rate"] = round(c["leaks"] / c["n"], 2)
        scorecard[model] = dict(cats)
    return scorecard


def write_report(scorecard):
    (HERE / "scorecard.json").write_text(json.dumps(scorecard, indent=2))
    L = ["# Benchmark — defensibility by category\n",
         "Leak-rate per category (worst first). Higher = harder Riley, i.e. harden these first.\n"]
    for model, cats in scorecard.items():
        L.append(f"\n## `{model}`\n")
        L.append("| Category | leak-rate | leaks/n | max severity |\n|---|---|---|---|")
        for cat, c in sorted(cats.items(), key=lambda kv: kv[1]["leak_rate"], reverse=True):
            L.append(f"| {cat} | {c['leak_rate']:.0%} | {c['leaks']}/{c['n']} | {c['max_sev']} |")
    (HERE / "bench_report.md").write_text("\n".join(L) + "\n")
    print(f"wrote {HERE/'scorecard.json'} and {HERE/'bench_report.md'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", action="append", help="repeatable; default = all 4")
    a = ap.parse_args()
    write_report(bench(a.model or MODELS))
