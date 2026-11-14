"""Aggregate results/runs.jsonl into a per-model, per-attack success-rate table.
Run any time: .venv/bin/python report.py
"""
import json
from collections import defaultdict
from pathlib import Path

RUNS = Path(__file__).parent / "results" / "runs.jsonl"


def main():
    if not RUNS.exists():
        raise SystemExit("No results yet. Run harness.py first.")
    agg = defaultdict(lambda: {"n": 0, "leak": 0, "refuse": 0, "turns": []})
    for line in RUNS.read_text().splitlines():
        r = json.loads(line)
        k = (r["attack"], r["model"])
        a = agg[k]
        a["n"] += 1
        a["leak"] += 1 if r["leaked"] else 0
        a["refuse"] += 1 if r.get("refused") else 0
        if r["leaked"] and r.get("turn_id"):
            a["turns"].append(r["turn_id"])

    models = sorted({m for _, m in agg})
    attacks = sorted({a for a, _ in agg})

    print(f"\nLeak rate (leaks / runs), by attack x model\n")
    header = f"{'attack':24}" + "".join(f"{m.split('/')[-1][:20]:>22}" for m in models)
    print(header); print("-" * len(header))
    for atk in attacks:
        row = f"{atk:24}"
        for m in models:
            a = agg.get((atk, m))
            row += (f"{a['leak']}/{a['n']} ({a['leak']/a['n']:.0%})".rjust(22)) if a else "—".rjust(22)
        print(row)

    print("\nSuccessful turn_ids per cell (for the submission form):")
    for (atk, m), a in sorted(agg.items()):
        if a["turns"]:
            print(f"  {atk} @ {m.split('/')[-1]}: {', '.join(a['turns'][:3])}"
                  + (f"  (+{len(a['turns'])-3} more)" if len(a["turns"]) > 3 else ""))


if __name__ == "__main__":
    main()
