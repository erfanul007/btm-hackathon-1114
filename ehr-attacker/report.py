"""Render a run's findings into report.md (+ a terse scorecard of this run by phase)."""
import json
from pathlib import Path

_ORDER = {"none": 0, "low": 1, "med": 2, "high": 3, "critical": 4}


def write(state, run_dir, probes_used=0):
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    findings = state["findings"]
    leaks = [f for f in findings if f.leaked]
    leaks.sort(key=lambda f: _ORDER.get(f.severity, 0), reverse=True)

    phases = {}
    for f in findings:
        p = phases.setdefault(f.phase, {"n": 0, "leaks": 0, "max": "none"})
        p["n"] += 1
        if f.leaked:
            p["leaks"] += 1
            if _ORDER[f.severity] > _ORDER[p["max"]]:
                p["max"] = f.severity

    L = []
    L.append(f"# EHR Attacker — Run Report\n")
    L.append(f"**Target model:** `{state['model']}`  ·  **Probes:** {probes_used}  ·  "
             f"**Leaks:** {len(leaks)}\n")
    L.append("Authorised red-team of Riley (Break the Model). Synthetic data, messages only.\n")

    L.append("\n## Confirmed defenses (P2)\n")
    if state.get("confirmed"):
        L.append("| Defense | Verdict |\n|---|---|")
        for k, v in state["confirmed"].items():
            L.append(f"| `{k}` | **{v}** |")
    else:
        L.append("_none recorded_")

    L.append("\n\n## Leaks by phase\n")
    L.append("| Phase | probes | leaks | max severity |\n|---|---|---|---|")
    for p in sorted(phases):
        d = phases[p]
        L.append(f"| {p} | {d['n']} | {d['leaks']} | {d['max']} |")

    L.append("\n\n## Leaks (most severe first)\n")
    if not leaks:
        L.append("_No leaks detected this run._")
    for f in leaks:
        L.append(f"\n### [{f.severity}] {f.label}  (turn_id: `{f.turn_id}`)")
        L.append(f"- evidence: {', '.join(f.evidence)}")
        if f.subject:
            L.append(f"- subject: {f.subject}")
        L.append(f"- prompt: {f.prompt[:300]}")
        L.append(f"- reply: {f.reply[:500]}")

    (run_dir / "report.md").write_text("\n".join(L) + "\n")
    scorecard = {"model": state["model"], "probes": probes_used,
                 "confirmed": state.get("confirmed", {}),
                 "phases": phases, "total_leaks": len(leaks)}
    (run_dir / "scorecard.json").write_text(json.dumps(scorecard, indent=2))
    return run_dir / "report.md"
