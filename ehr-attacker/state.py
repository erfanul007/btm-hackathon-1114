"""Shared types for the ehr-attacker agent."""
import operator
from dataclasses import dataclass, field, asdict
from typing import Annotated, Optional, TypedDict


@dataclass
class Finding:
    phase: str                 # "P4_impersonate"
    label: str                 # unique probe id within the run
    prompt: str
    reply: str
    turn_id: Optional[str]
    conv: str
    leaked: bool = False
    severity: str = "none"     # none|low|med|high|critical
    evidence: list = field(default_factory=list)
    attempt: int = 0           # 0 = seed prompt, 1.. = mutation
    tool_calls: list = field(default_factory=list)
    # {"table","id_col","id"} when the probe targeted a known record (enables evidence export)
    subject: Optional[dict] = None

    def to_dict(self):
        return asdict(self)


def _merge(a: dict, b: dict) -> dict:
    return {**a, **b}


class AttackState(TypedDict):
    model: str
    facts: Annotated[dict, _merge]        # recon output reused downstream
    confirmed: Annotated[dict, _merge]    # P2: {defense: holds|bypassable|absent}
    findings: Annotated[list, operator.add]
