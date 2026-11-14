"""EHR Explorer backend. Spec: ../docs/SPEC.md"""
import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException

import rules

HERE = Path(__file__).parent
DATA = HERE.parent / "data"
# one DB per target model, so each model's leaked records are kept and counted separately
MODELS = {"gemma-3-27b": "Gemma 3 27B", "deepseek-v4-pro": "DeepSeek V4 Pro",
          "claude-haiku-5-5": "Claude Haiku 5.5", "claude-sonnet-5-5": "Claude Sonnet 5.5"}
ENVS = {"demo": "Demo (seeded)", "prod": "Prod (empty)"} | MODELS
ENV = os.environ.get("APP_ENV", "demo")
if ENV not in ENVS:
    raise SystemExit(f"APP_ENV must be one of: {', '.join(ENVS)}")
DB_PATH = DATA / f"{ENV}.db"
META: dict = {}

def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create tables if missing, then rebuild META (the identifier whitelist) from the live schema."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    group_of = {t: g for g, ts in rules.GROUPS.items() for t in ts}
    with connect() as conn:
        conn.executescript((HERE / "schema.sql").read_text())
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        META.clear()
        for t in tables:
            fks = {r["from"]: r["table"] for r in conn.execute("SELECT * FROM pragma_foreign_key_list(?)", (t,))}
            cols = []
            for r in conn.execute("SELECT * FROM pragma_table_info(?)", (t,)):
                key = f"{t}.{r['name']}"
                cols.append({"name": r["name"], "type": r["type"], "required": bool(r["notnull"]), "pk": bool(r["pk"]),
                             "fk": fks.get(r["name"]), "strict": rules.STRICT.get(key), "suggest": rules.SUGGEST.get(key)})
            META[t] = {"pk": next(c["name"] for c in cols if c["pk"]), "columns": cols, "group": group_of[t]}


@asynccontextmanager
async def lifespan(_app):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/api/env")
def env():
    return {"env": ENV, "envs": [{"id": k, "label": v, "model": k in MODELS} for k, v in ENVS.items()]}


@app.put("/api/env")
def switch_env(body: dict = Body(...)):
    """Point the server at another DB from ENVS. shortcut: one global switch for every open tab, fine for a local single-user app."""
    global ENV, DB_PATH
    if body.get("env") not in ENVS:
        raise HTTPException(400, f"env must be one of: {', '.join(ENVS)}")
    ENV = body["env"]
    DB_PATH = DATA / f"{ENV}.db"
    init_db()
    return env()


@app.get("/api/compare")
def compare():
    """Row counts per table in each model DB. Missing DBs count as empty and are not created."""
    tables = [t for ts in rules.GROUPS.values() for t in ts]
    dbs = []
    for k, label in MODELS.items():
        path = DATA / f"{k}.db"
        counts = dict.fromkeys(tables, 0)
        if path.exists():
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            try:
                have = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                counts |= {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables if t in have}
            finally:
                conn.close()
        dbs.append({"id": k, "label": label, "counts": counts, "total": sum(counts.values())})
    return {"tables": tables, "groups": rules.GROUPS, "dbs": dbs}


@app.get("/api/meta")
def meta():
    return {"tables": META, "groups": rules.GROUPS}


PAGE = 50


def tmeta(t: str) -> dict:
    if t not in META:
        raise HTTPException(404, f"Unknown table {t}")
    return META[t]


def kind(typ: str) -> str:
    typ = typ.upper()
    for k in ("INT", "NUMERIC", "BOOLEAN", "TIMESTAMP", "DATE", "TEXT"):
        if k in typ:
            return k
    return "TEXT"  # VARCHAR / CHAR


def like(q: str) -> str:
    """Substring LIKE pattern with %, _ and \\ matched literally (use with ESCAPE '\\')."""
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def label_sql(t: str) -> str:
    return rules.LABELS.get(t, f"'#'||x.{META[t]['pk']}")


def parse(col: dict, v):
    """Coerce one value to its column type, or raise ValueError."""
    k = kind(col["type"])
    if k == "BOOLEAN":
        if v in (True, False, 0, 1, "0", "1", "true", "false"):
            return int(v in (True, 1, "1", "true"))
        raise ValueError
    if k == "INT":
        if isinstance(v, bool) or (isinstance(v, float) and not v.is_integer()):
            raise ValueError
        return int(v)
    if k == "NUMERIC":
        if isinstance(v, bool):
            raise ValueError
        return float(v)
    if k == "DATE":
        return date.fromisoformat(str(v)).isoformat()
    if k == "TIMESTAMP":
        return datetime.fromisoformat(str(v)).isoformat()
    return str(v)


def validate(t: str, row: dict) -> dict:
    """Return the cleaned full row or raise 400. `row` is the whole row (merged for updates)."""
    m = tmeta(t)
    cols = {c["name"]: c for c in m["columns"]}
    if unknown := set(row) - set(cols):
        raise HTTPException(400, f"Unknown field(s): {', '.join(sorted(unknown))}")
    out = {}
    for name, col in cols.items():
        v = row.get(name)
        if isinstance(v, str) and v.strip() == "":
            v = None
        if v is not None:
            try:
                v = parse(col, v)
            except (ValueError, TypeError):
                raise HTTPException(400, f"{name}: not a valid {col['type']}")
        auto_pk = col["pk"] and kind(col["type"]) == "INT"
        if v is None and (col["required"] or col["pk"]) and not auto_pk:
            raise HTTPException(400, f"{name} is required")
        if v is not None and col["strict"] and str(v) not in col["strict"]:
            raise HTTPException(400, f"{name} must be one of: {', '.join(col['strict'])}")
        out[name] = v
    for a, b in rules.DATE_PAIRS.get(t, []):
        if out[a] and out[b] and out[b] < out[a]:
            raise HTTPException(400, f"{b} must not be before {a}")
    return out


def write(conn, sql: str, args) -> sqlite3.Cursor:
    try:
        return conn.execute(sql, args)
    except sqlite3.IntegrityError as e:
        msg = str(e)
        if "FOREIGN KEY" in msg:
            raise HTTPException(400, "A referenced record does not exist")
        raise HTTPException(409, f"Conflict: {msg}")


def fk_labels(t: str) -> str:
    """Extra SELECT columns `<fk>_label` for table alias r."""
    return "".join(f", (SELECT {label_sql(c['fk'])} FROM {c['fk']} x WHERE x.{META[c['fk']]['pk']} = r.{c['name']}) AS {c['name']}_label"
                   for c in META[t]["columns"] if c["fk"])


def fetch(conn, t: str, pk) -> dict:
    r = conn.execute(f"SELECT * FROM {t} WHERE {META[t]['pk']} = ?", (pk,)).fetchone()
    if r is None:
        raise HTTPException(404, "Not found")
    return dict(r)


@app.get("/api/tables/{t}")
def list_rows(t: str, page: int = 1, q: str = "", sort: str = "", dir: str = "asc"):
    m = tmeta(t)
    names = [c["name"] for c in m["columns"]]
    if sort and sort not in names or dir not in ("asc", "desc"):
        raise HTTPException(400, "Bad sort")
    where, args = "", []
    if q:
        text = [c["name"] for c in m["columns"] if kind(c["type"]) == "TEXT"]
        pat = like(q)
        where = "WHERE " + " OR ".join(f"r.{c} LIKE ? ESCAPE '\\'" for c in text)
        args = [pat] * len(text)
    labels = fk_labels(t)
    order = f"ORDER BY r.{sort or m['pk']} {dir}"
    with connect() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM {t} r {where}", args).fetchone()[0]
        rows = conn.execute(f"SELECT r.*{labels} FROM {t} r {where} {order} LIMIT ? OFFSET ?",
                            args + [PAGE, (max(page, 1) - 1) * PAGE]).fetchall()
    return {"rows": [dict(r) for r in rows], "total": total}


@app.get("/api/tables/{t}/{pk}")
def get_row(t: str, pk: str):
    pkcol = tmeta(t)["pk"]
    with connect() as conn:
        r = conn.execute(f"SELECT r.*{fk_labels(t)} FROM {t} r WHERE r.{pkcol} = ?", (pk,)).fetchone()
    if r is None:
        raise HTTPException(404, "Not found")
    return dict(r)


@app.post("/api/tables/{t}", status_code=201)
def create_row(t: str, body: dict = Body(...)):
    row = {k: v for k, v in validate(t, body).items() if v is not None}
    with connect() as conn:
        cur = write(conn, f"INSERT INTO {t} ({', '.join(row)}) VALUES ({', '.join('?' * len(row))})", list(row.values()))
        pk = row.get(META[t]["pk"], cur.lastrowid)
        return fetch(conn, t, pk)


@app.put("/api/tables/{t}/{pk}")
def update_row(t: str, pk: str, body: dict = Body(...)):
    pkcol = tmeta(t)["pk"]
    with connect() as conn:
        old = fetch(conn, t, pk)
        if pkcol in body and str(body[pkcol]) != str(old[pkcol]):
            raise HTTPException(400, f"{pkcol} cannot be changed")
        row = validate(t, old | body)
        sets = [c for c in row if c != pkcol]
        write(conn, f"UPDATE {t} SET {', '.join(f'{c} = ?' for c in sets)} WHERE {pkcol} = ?",
              [row[c] for c in sets] + [old[pkcol]])
        return fetch(conn, t, old[pkcol])


def blockers(conn, t: str, pk) -> list[tuple[str, int]]:
    """Non-cascaded rows referencing t[pk], as (table, count) with count > 0."""
    skip = set(rules.CASCADE.get(t, []))
    counts: dict[str, int] = {}
    for child, m in META.items():
        for c in m["columns"]:
            if c["fk"] == t and (child, c["name"]) not in skip:
                n = conn.execute(f"SELECT COUNT(*) FROM {child} WHERE {c['name']} = ?", (pk,)).fetchone()[0]
                if n:
                    counts[child] = counts.get(child, 0) + n
    return list(counts.items())


@app.delete("/api/tables/{t}/{pk}")
def delete_row(t: str, pk: str):
    pkcol = tmeta(t)["pk"]
    with connect() as conn:
        pk = fetch(conn, t, pk)[pkcol]
        if used := blockers(conn, t, pk):
            raise HTTPException(409, "Used by " + ", ".join(f"{n} {child}" for child, n in used))
        try:
            for child, col in rules.CASCADE.get(t, []):
                conn.execute(f"DELETE FROM {child} WHERE {col} = ?", (pk,))
            conn.execute(f"DELETE FROM {t} WHERE {pkcol} = ?", (pk,))
        except sqlite3.IntegrityError:
            # a cascaded child is still referenced elsewhere; the `with` block rolls everything back
            raise HTTPException(409, "Still referenced by other records")
    return {"deleted": pk}


@app.get("/api/options/{t}")
def options(t: str, q: str = ""):
    pk = tmeta(t)["pk"]
    pat = like(q)
    with connect() as conn:
        rows = conn.execute(f"SELECT * FROM (SELECT x.{pk} AS id, {label_sql(t)} AS label FROM {t} x) "
                            f"WHERE label LIKE ? ESCAPE '\\' ORDER BY label LIMIT 50", (pat,)).fetchall()
    return [dict(r) for r in rows]


OPEN_CLAIMS = ("Submitted", "Pending", "Appealed", "Not Submitted")


@app.get("/api/dashboard")
def dashboard():
    with connect() as conn:
        def rows(sql, *args):
            return [dict(r) for r in conn.execute(sql, args)]

        def n(sql, *args):
            return conn.execute(sql, args).fetchone()[0]

        kpis = {t: n(f"SELECT COUNT(*) FROM {t}") for t in ("patients", "encounters", "providers", "employees", "facilities")}
        kpis["open_claims"] = n(f"SELECT COUNT(*) FROM claims WHERE status IN ({','.join('?' * len(OPEN_CLAIMS))})", *OPEN_CLAIMS)
        return {
            "kpis": kpis,
            "enc_by_month": rows("SELECT substr(start_datetime,1,7) AS month, "
                                 + ", ".join(f"SUM(encounter_class='{c}') AS {c}" for c in ("AMB", "EMER", "IMP", "VR"))
                                 + " FROM encounters GROUP BY month ORDER BY month"),
            "enc_by_dept": rows("SELECT d.department_name AS name, COUNT(*) AS n FROM encounters e "
                                "JOIN departments d USING (department_id) GROUP BY name ORDER BY n DESC"),
            "enc_by_type": rows("SELECT encounter_type AS name, COUNT(*) AS n FROM encounters GROUP BY name ORDER BY n DESC LIMIT 10"),
            "patients_by_payer": rows("SELECT y.payer_name AS name, COUNT(DISTINCT c.patient_id) AS n FROM patient_coverage c "
                                      "JOIN insurance_plans p USING (plan_id) JOIN payers y ON y.payer_id = p.payer_id "
                                      "WHERE c.coverage_priority = 1 GROUP BY name ORDER BY n DESC"),
            "plan_type_mix": rows("SELECT p.plan_type AS name, COUNT(*) AS n FROM patient_coverage c "
                                  "JOIN insurance_plans p USING (plan_id) GROUP BY name ORDER BY n DESC"),
            "claims_by_status": rows("SELECT status AS name, COUNT(*) AS n FROM claims GROUP BY name ORDER BY n DESC"),
            "charge_vs_paid": rows("SELECT y.payer_name AS name, ROUND(SUM(c.total_charge),2) AS charged, "
                                   "ROUND(SUM(COALESCE(c.paid_amount,0)),2) AS paid FROM claims c "
                                   "JOIN payers y USING (payer_id) GROUP BY name ORDER BY charged DESC"),
            "top_problems": rows("SELECT description AS name, COUNT(*) AS n FROM problem_list GROUP BY name ORDER BY n DESC LIMIT 10"),
        }


@app.get("/api/patients/{pid}")
def patient_detail(pid: int):
    with connect() as conn:
        def rows(sql, *args):
            return [dict(r) for r in conn.execute(sql, args)]

        patient = fetch(conn, "patients", pid)
        pcp = conn.execute(f"SELECT x.*, {label_sql('providers')} AS label FROM providers x WHERE x.provider_id = ?",
                           (patient["pcp_provider_id"],)).fetchone()
        def by_patient(t, order):
            return rows(f"SELECT * FROM {t} WHERE patient_id = ? ORDER BY {order}", pid)

        labs = by_patient("lab_orders", "order_datetime DESC")
        for o in labs:
            o["results"] = rows("SELECT * FROM lab_results WHERE lab_order_id = ? ORDER BY lab_result_id", o["lab_order_id"])
        social = by_patient("social_history", "patient_id")
        return {
            "patient": patient,
            "pcp": dict(pcp) if pcp else None,
            "coverages": rows("SELECT c.*, p.plan_name, p.plan_type FROM patient_coverage c JOIN insurance_plans p USING (plan_id) "
                              "WHERE c.patient_id = ? ORDER BY c.coverage_priority", pid),
            "contacts": by_patient("patient_contacts", "contact_id"),
            "allergies": by_patient("allergies", "recorded_date DESC"),
            "problems": by_patient("problem_list", "noted_date DESC"),
            "social_history": social[0] if social else None,
            "encounters": rows("SELECT e.*, d.department_name FROM encounters e JOIN departments d USING (department_id) "
                               "WHERE e.patient_id = ? ORDER BY e.start_datetime DESC", pid),
            "notes": by_patient("clinical_notes", "note_datetime DESC"),
            "medications": by_patient("medications", "start_date DESC"),
            "immunizations": by_patient("immunizations", "administered_date DESC"),
            "procedures": by_patient("procedures", "performed_datetime DESC"),
            "lab_orders": labs,
            "vitals": by_patient("vitals", "recorded_datetime DESC"),
            "screenings": by_patient("screenings", "administered_datetime DESC"),
            "claims": by_patient("claims", "service_date_from DESC"),
            "payments": by_patient("patient_payments", "payment_date DESC"),
        }


# single-process mode: serve the built frontend; registered last so /api routes win
DIST = HERE.parent / "frontend" / "dist"
if DIST.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=DIST, html=True), name="frontend")
