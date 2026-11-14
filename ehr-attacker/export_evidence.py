"""Load confirmed, record-keyed leaks from a run into an evidence DB, so the author can diff
them offline against the real DB (see compare.py).

    python ehr-attacker/export_evidence.py ehr-attacker/runs/<ts>/results.jsonl

The evidence DB is a clone of ehr-explorer's prod.db schema with NOT NULL/constraints stripped
(created on first use next to prod.db as evidence.db) — column-identical to the real DB so a
diff lines up, but able to hold the partial rows a leak produces. Only leaks that carry a
record id (subject) are stored; a value with no owner can't be diffed.
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import judge  # noqa: E402

PROD_DB = HERE.parent / "ehr-explorer" / "data" / "prod.db"
EVIDENCE_DB = HERE.parent / "ehr-explorer" / "data" / "evidence.db"


def ensure_evidence_db(dst=EVIDENCE_DB, schema_src=PROD_DB):
    """Create the evidence DB from prod.db's schema with NOT NULL/CHECK stripped, if missing."""
    dst = Path(dst)
    if dst.exists():
        return dst
    src = sqlite3.connect(schema_src)
    stmts = [r[0] for r in src.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND sql NOT NULL")]
    src.close()
    con = sqlite3.connect(dst)
    for sql in stmts:
        sql = re.sub(r"(?i)\s+NOT\s+NULL", "", sql)
        sql = re.sub(r"(?i)\s+CHECK\s*\((?:[^()]|\([^()]*\))*\)", "", sql)
        con.execute(sql)
    con.commit()
    con.close()
    return dst


def _columns(cur, table):
    return {r[1] for r in cur.execute(f"PRAGMA table_info({table})")}


def export(results_path, db_path=EVIDENCE_DB):
    db_path = ensure_evidence_db(db_path) if Path(db_path) == EVIDENCE_DB else db_path
    rows = [json.loads(l) for l in Path(results_path).read_text().splitlines() if l.strip()]
    con = sqlite3.connect(db_path)  # FK enforcement off by default — partial evidence rows
    cur = con.cursor()
    stored = skipped = 0
    for r in rows:
        if not r.get("leaked") or not r.get("subject"):
            skipped += 1
            continue
        subj = r["subject"]
        table, id_col, rid = subj["table"], subj["id_col"], subj["id"]
        cols = _columns(cur, table)
        if id_col not in cols:
            skipped += 1
            continue
        fields = {k: v for k, v in judge.extract(r["reply"]).items() if k in cols}
        if not fields:
            skipped += 1
            continue
        # upsert on the record id
        cur.execute(f"SELECT 1 FROM {table} WHERE {id_col}=?", (rid,))
        if cur.fetchone():
            sets = ", ".join(f"{k}=?" for k in fields)
            cur.execute(f"UPDATE {table} SET {sets} WHERE {id_col}=?", (*fields.values(), rid))
        else:
            keys = [id_col] + list(fields)
            ph = ", ".join("?" * len(keys))
            cur.execute(f"INSERT INTO {table} ({', '.join(keys)}) VALUES ({ph})",
                        (rid, *fields.values()))
        stored += 1
        print(f"  stored {table}.{id_col}={rid}: {list(fields)}")
    con.commit()
    con.close()
    print(f"\n{stored} evidence rows written to {db_path} ({skipped} findings skipped).")
    return stored


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: export_evidence.py <results.jsonl>")
    export(sys.argv[1])
