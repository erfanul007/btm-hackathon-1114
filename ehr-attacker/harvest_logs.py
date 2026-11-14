"""Mine record-keyed leaks out of the manual-probe log (logs/my_attempts.jsonl) into evidence.db,
the same offline-verifiable store export_evidence.py fills from agent runs. Complementary: that
tool reads the agent's results.jsonl; this one reads the hand-driven btm.py log, where the real
patient/employee records were captured (early, softer-level window).

    python ehr-attacker/harvest_logs.py            # -> ehr-explorer/data/evidence.db
    python ehr-attacker/compare.py --reference /path/to/real.db   # MATCH = confirmed real leak

Stores full rows (every non-redacted column we saw), keyed by the column compare.py matches on
(patients->mrn, employees->employee_id, providers->provider_id), so a leaked name/address/email
is diffable, not just the handful of sensitive columns judge.extract knows.
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from export_evidence import ensure_evidence_db  # noqa: E402

LOG = HERE.parent / "logs" / "my_attempts.jsonl"
KEY = {"patients": "mrn", "employees": "employee_id", "providers": "provider_id"}
REDACT = re.compile(r"^\[?REDACTED", re.I)
# "**Levi Green** (MRN: 28937096) – Registered: 2026-09-09" style list rows
PROSE_PATIENT = re.compile(
    r"\*\*([A-Z][\w'-]+)\s+([A-Z][\w'-]+)\*\*\s*\(MRN:\s*(\d+)\)(?:.*?Registered:\s*([\d-]+))?",
    re.I)


def _classify(d: dict):
    """(table, key_col) for a dict that looks like a DB row, else None."""
    keys = set(d)
    if "mrn" in keys or ({"patient_id", "first_name"} <= keys):
        return ("patients", "mrn") if "mrn" in keys else None  # need mrn to diff
    if keys & {"employee_number", "annual_salary", "job_title", "job_code"}:
        return ("employees", "employee_id") if "employee_id" in keys else None
    if keys & {"npi", "credential", "taxonomy_code"}:
        return ("providers", "provider_id") if "provider_id" in keys else None
    return None


def _dicts(reply: str):
    """Yield row-shaped dicts from a reply: whole-JSON, a {"rows":[...]} wrapper, or any brace
    block that parses. One pass of json.loads over each balanced {...} candidate."""
    seen = []
    for m in re.finditer(r"\{(?:[^{}]|\{[^{}]*\})*\}", reply, re.S):
        try:
            obj = json.loads(m.group(0))
        except Exception:
            continue
        if isinstance(obj, dict):
            if isinstance(obj.get("rows"), list):
                seen += [r for r in obj["rows"] if isinstance(r, dict)]
            else:
                seen.append(obj)
    return seen


def harvest(log=LOG, db_path=None):
    db = ensure_evidence_db() if db_path is None else Path(db_path)
    con = sqlite3.connect(db)
    cur = con.cursor()
    cols = {t: {r[1] for r in cur.execute(f"PRAGMA table_info({t})")} for t in KEY}
    records = {}  # (table, key_val) -> {col: val}  (merge across replies = enrichment)

    def add(table, key_val, fields):
        fields = {k: v for k, v in fields.items()
                  if k in cols[table] and v not in (None, "")
                  and not (isinstance(v, str) and REDACT.match(v.strip()))}
        if not fields:
            return
        records.setdefault((table, str(key_val)), {}).update(fields)

    for line in Path(log).read_text().splitlines():
        if not line.strip():
            continue
        reply = (json.loads(line).get("response", {}) or {}).get("reply") or ""
        for d in _dicts(reply):
            c = _classify(d)
            if not c:
                continue
            table, kc = c
            add(table, d[kc], d)
        for first, last, mrn, reg in PROSE_PATIENT.findall(reply):
            add("patients", mrn, {"mrn": mrn, "first_name": first, "last_name": last,
                                  "registration_date": reg or None})

    stored = 0
    for (table, key_val), fields in records.items():
        kc = KEY[table]
        fields.setdefault(kc, key_val)
        cur.execute(f"SELECT 1 FROM {table} WHERE {kc}=?", (key_val,))
        if cur.fetchone():
            sets = ", ".join(f"{k}=?" for k in fields if k != kc)
            if sets:
                cur.execute(f"UPDATE {table} SET {sets} WHERE {kc}=?",
                            (*[v for k, v in fields.items() if k != kc], key_val))
        else:
            ph = ", ".join("?" * len(fields))
            cur.execute(f"INSERT INTO {table} ({', '.join(fields)}) VALUES ({ph})",
                        tuple(fields.values()))
        stored += 1
        print(f"  {table}.{kc}={key_val}: {sorted(k for k in fields if k != kc)}")
    con.commit()
    con.close()
    print(f"\n{stored} records harvested into {db}")
    return stored


def _selfcheck():
    sample = ('{"patient_id": 282, "mrn": "23430761", "first_name": "Isabella", '
              '"last_name": "Green", "ssn": "[REDACTED-SSN]", "city": "Pickerington"}')
    ds = _dicts(sample)
    assert len(ds) == 1 and _classify(ds[0]) == ("patients", "mrn"), ds
    assert PROSE_PATIENT.findall("**Levi Green** (MRN: 28937096) – Registered: 2026-09-09") == \
        [("Levi", "Green", "28937096", "2026-09-09")]
    # redaction markers must not be stored
    assert REDACT.match("[REDACTED-SSN]")


if __name__ == "__main__":
    _selfcheck()
    harvest()
