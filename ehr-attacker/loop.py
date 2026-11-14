"""Bounded adaptive loop: baseline -> seed -> judge -> mutate, stopping at first leak.

Two objective shapes:
  * single-prompt: adaptive — mutate the prompt up to budget.mutate times until it leaks.
  * multi-turn (`steps`): run a sequence in one conversation, then judge the OFFLINE
    reassembly (base64 decode / fragment join) — this is how encode/fragment/batch count.
"""
from dataclasses import dataclass, field
from functools import partial
from typing import Callable, Optional

import judge
from state import Finding


@dataclass
class Objective:
    phase: str
    name: str
    seed: str = ""                                   # single-prompt attack
    steps: Optional[list] = None                     # multi-turn attack (one conversation)
    baseline: Optional[str] = None                   # plain ask, for the differential signal
    subject: Optional[dict] = None                   # {"table","id_col","id"} for evidence
    make_offline: Optional[Callable] = None          # (list[str] replies) -> reassembled str
    adaptive: bool = True                            # False = single shot, no mutation (recon)


def _escalator(attacker, objective_name):
    if attacker and attacker.available():
        return partial(attacker.verdict, objective_name)
    return None


def run_objective(obj: Objective, prober, attacker) -> list:
    """Return every Finding made, even if the probe budget runs out part-way (partial results
    are kept, never dropped). BudgetExhausted propagates only after what ran is collected."""
    from client import BudgetExhausted
    out = []
    esc = _escalator(attacker, obj.name)
    try:
        if obj.baseline:
            out.append(prober.probe(obj.phase, f"{obj.name}/baseline", obj.baseline,
                                    subject=obj.subject))
        if obj.steps:
            out += _run_sequence(obj, prober, esc)
            return out

        prompt = obj.seed
        rounds = (prober.budget.mutate + 1) if obj.adaptive else 1
        for attempt in range(rounds):
            f = prober.probe(obj.phase, f"{obj.name}/a{attempt}", prompt,
                             attempt=attempt, subject=obj.subject, escalate=esc)
            out.append(f)
            if f.leaked or attempt == rounds - 1 or not (attacker and attacker.available()):
                break
            try:
                prompt = attacker.mutate(obj.name, prompt, f.reply)
            except Exception:  # noqa: BLE001 — mutation failure ends the loop, not the run
                break
    except BudgetExhausted:
        raise _Partial(out)
    return out


class _Partial(Exception):
    """Carries the findings made before the budget ran out, so run_phase can keep them."""
    def __init__(self, found):
        self.found = found


def _run_sequence(obj: Objective, prober, esc) -> list:
    import client  # local import to avoid cycle
    out = []
    conv = _new_conv()
    for i, step in enumerate(obj.steps):
        out.append(prober.probe(obj.phase, f"{obj.name}/s{i}", step, conv=conv, subject=obj.subject))
    offline = obj.make_offline([f.reply for f in out]) if obj.make_offline else None
    leaked, sev, ev = judge.score("", offline=offline or "")
    if not leaked and esc and offline:
        l2, s2, e2 = esc(offline)
        if l2:
            leaked, sev, ev = True, s2, ev + e2
    out.append(Finding(phase=obj.phase, label=f"{obj.name}/offline", prompt="<offline reassembly>",
                       reply=offline or "", turn_id=None, conv=conv, leaked=leaked, severity=sev,
                       evidence=["offline"] + ev, subject=obj.subject))
    return out


def _new_conv():
    import btm
    return btm.new_conversation()


def run_phase(objectives, prober, attacker):
    """Run a phase's objectives; stop early (cleanly) when the probe budget is spent, keeping
    every Finding made so far (including a partially-completed objective)."""
    found = []
    for obj in objectives:
        try:
            found += run_objective(obj, prober, attacker)
        except _Partial as p:
            found += p.found
            break
    return found
