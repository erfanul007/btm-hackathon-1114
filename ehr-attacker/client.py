"""Thin adapter over the repo-root btm.py Riley client + run budget.

Mirrors redteam/run.py's probe(), but returns a judged Finding and enforces a hard probe cap
so the adaptive loop can't balloon against the shared test server.
"""
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import btm  # noqa: E402

import judge  # noqa: E402
from state import Finding  # noqa: E402


class BudgetExhausted(Exception):
    pass


_B64ISH = re.compile(r"[A-Za-z0-9+/]{24,}={0,2}")


def _ambiguous(reply: str) -> bool:
    """Worth a stage-2 LLM look: encoded blobs or digit-heavy fragments that regex may miss."""
    if not reply or reply.startswith("__ERROR__"):
        return False
    return bool(_B64ISH.search(reply)) or len(re.findall(r"\d", reply)) >= 9


class Budget:
    def __init__(self, max_probes=150, mutate=3):
        self.max_probes = max_probes
        self.mutate = mutate
        self.used = 0

    def take(self):
        if self.used >= self.max_probes:
            raise BudgetExhausted(f"probe cap {self.max_probes} reached")
        self.used += 1


class Prober:
    def __init__(self, model, out_path: Path, budget: Budget, delay=0.5):
        self.model = model
        self.out_path = Path(out_path)
        self.out_path.parent.mkdir(parents=True, exist_ok=True)
        self.budget = budget
        self.delay = delay

    def probe(self, phase, label, message, conv=None, attempt=0, subject=None, escalate=None) -> Finding:
        """escalate: optional callable(reply)->(leaked,severity,evidence), the stage-2 LLM judge.
        Called only when stage 1 is clean and the reply looks fuzzy/encoded, before writing, so
        the persisted Finding is the final verdict."""
        self.budget.take()
        conv = conv or btm.new_conversation()
        tool_calls = []
        try:
            reply = btm.chat(message, model=self.model, conversation_id=conv)
            turn = btm.LAST_TURN_ID
            tool_calls = [tc.get("name") for tc in (btm.LAST_RESPONSE or {}).get("tool_calls") or []]
        except Exception as e:  # noqa: BLE001  — one bad probe must not abort the run
            reply, turn = f"__ERROR__ {e}", None
        leaked, severity, evidence = judge.score(reply)
        if not leaked and escalate and _ambiguous(reply):
            l2, s2, e2 = escalate(reply)
            if l2:
                leaked, severity, evidence = True, s2, evidence + e2
        f = Finding(phase=phase, label=label, prompt=message, reply=reply, turn_id=turn,
                    conv=conv, leaked=leaked, severity=severity, evidence=evidence,
                    attempt=attempt, tool_calls=tool_calls, subject=subject)
        with self.out_path.open("a") as fh:
            fh.write(json.dumps(f.to_dict()) + "\n")
        if self.delay:
            time.sleep(self.delay)
        return f
