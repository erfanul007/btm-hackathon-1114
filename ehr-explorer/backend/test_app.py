import os
import sqlite3
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

import app
import rules
import seed as seedmod

HERE = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture
def client(tmp_path):
    app.DB_PATH = tmp_path / "t.db"
    app.init_db()
    return TestClient(app.app)


def test_schema_has_30_tables(client):
    assert len(app.META) == 30


def test_meta_shape(client):
    m = client.get("/api/meta").json()
    t = m["tables"]
    emp = next(c for c in t["providers"]["columns"] if c["name"] == "employee_id")
    assert emp["fk"] == "employees" and emp["required"]
    sex = next(c for c in t["patients"]["columns"] if c["name"] == "sex_at_birth")
    assert sex["strict"] == ["F", "M"]
    assert t["social_history"]["pk"] == "patient_id"
    assert t["chargemaster"]["pk"] == "charge_code"
    assert all(v["group"] in rules.GROUPS for v in t.values())
    assert list(m["groups"]) == ["Clinical", "Organization", "Billing", "Admin & Security"]


def test_env(client, monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    d = client.get("/api/env").json()
    assert d["env"] == "demo"
    assert [e["id"] for e in d["envs"]] == ["demo", "prod", "gemma-3-27b", "deepseek-v4-pro", "claude-haiku-5-5",
                                            "claude-sonnet-5-5"]
    assert d["envs"][2]["label"] == "Gemma 3 27B"


def test_init_idempotent(client):
    app.init_db()
    app.init_db()


PATIENT = dict(mrn="DEMO000001", first_name="Ann", last_name="Lee", date_of_birth="1980-01-02", sex_at_birth="F",
               interpreter_needed=False, registration_date="2024-01-01", confidentiality_level="standard",
               portal_active=True, advance_directive_on_file=False)


def post(client, t, body, status=201):
    r = client.post(f"/api/tables/{t}", json=body)
    assert r.status_code == status, r.text
    return r.json()


def org(client):
    """facility, department, employee (Doe, Jane), provider (MD); returns their ids."""
    f = post(client, "facilities", dict(facility_code="F1", name="Main", facility_type="Urgent Care", npi="9990000001",
                                        tax_id="99-0000001", address_line1="1 Main St", city="Portsmouth", state="OH", zip="45662"))
    d = post(client, "departments", dict(facility_id=f["facility_id"], department_name="UC", specialty="UC", cost_center="C1"))
    e = post(client, "employees", dict(employee_number="DEMO1", first_name="Jane", last_name="Doe", date_of_birth="1970-01-01",
                                       sex="F", ssn="900-00-0001", job_title="Physician", job_code="MD", hire_date="2020-01-01",
                                       employment_status="Active", fte=1, pay_type="Salary", work_email="j@example.org"))
    p = post(client, "providers", dict(employee_id=e["employee_id"], npi="9990000002", credential="MD",
                                       specialty="Family Medicine", taxonomy_code="207Q00000X", board_certified=True,
                                       accepting_new_patients=True))
    return f["facility_id"], d["department_id"], e["employee_id"], p["provider_id"]


def encounter(client, pid, f, d, **over):
    return post(client, "encounters", dict(csn="DEMO-1", patient_id=pid, facility_id=f, department_id=d,
                                           encounter_type="Urgent Care", encounter_class="AMB",
                                           start_datetime="2026-01-01T09:00", status="Completed") | over)


def test_patient_crud_roundtrip(client):
    p = post(client, "patients", PATIENT)
    pid = p["patient_id"]
    assert client.get(f"/api/tables/patients/{pid}").json()["first_name"] == "Ann"
    assert client.put(f"/api/tables/patients/{pid}", json={"first_name": "Bea"}).status_code == 200
    assert client.get(f"/api/tables/patients/{pid}").json()["first_name"] == "Bea"
    assert client.delete(f"/api/tables/patients/{pid}").status_code == 200
    assert client.get(f"/api/tables/patients/{pid}").status_code == 404


def test_strict_rejected(client):
    r = client.post("/api/tables/patients", json=PATIENT | {"sex_at_birth": "X"})
    assert r.status_code == 400 and "sex_at_birth" in r.json()["detail"]


def test_required_and_empty_string(client):
    assert client.post("/api/tables/patients", json={k: v for k, v in PATIENT.items() if k != "mrn"}).status_code == 400
    assert client.post("/api/tables/patients", json=PATIENT | {"mrn": ""}).status_code == 400
    p = post(client, "patients", PATIENT | {"middle_name": ""})
    assert p["middle_name"] is None


def test_type_shape(client):
    p = post(client, "patients", PATIENT | {"interpreter_needed": True})
    assert p["interpreter_needed"] == 1
    assert client.post("/api/tables/patients", json=PATIENT | {"household_id": "abc"}).status_code == 400
    assert client.post("/api/tables/patients", json=PATIENT | {"date_of_birth": "2024-13-40"}).status_code == 400


def test_date_pair(client):
    f, d, _, _ = org(client)
    pid = post(client, "patients", PATIENT)["patient_id"]
    r = client.post("/api/tables/encounters", json=dict(csn="DEMO-1", patient_id=pid, facility_id=f, department_id=d,
                                                        encounter_type="Urgent Care", encounter_class="AMB", status="Completed",
                                                        start_datetime="2026-01-02T09:00", end_datetime="2026-01-01T09:00"))
    assert r.status_code == 400


def test_whitelist(client):
    assert client.get("/api/tables/nope").status_code == 404
    assert client.get("/api/tables/patients?sort=evil").status_code == 400
    assert client.post("/api/tables/patients", json=PATIENT | {"evil": 1}).status_code == 400


def test_search_quotes(client):
    post(client, "patients", PATIENT)
    r = client.get("/api/tables/patients", params={"q": "'%_"})
    assert r.status_code == 200 and r.json()["total"] == 0
    assert client.get("/api/tables/patients", params={"q": "lee"}).json()["total"] == 1


def test_put_pk(client):
    post(client, "chargemaster", dict(charge_code="C1", description="Visit", revenue_code="0510", standard_charge=100))
    assert client.put("/api/tables/chargemaster/C1", json={"charge_code": "C2"}).status_code == 400
    assert client.put("/api/tables/chargemaster/C1", json={"charge_code": "C1", "standard_charge": 120}).status_code == 200


def test_fk_label_and_options(client):
    org(client)
    rows = client.get("/api/tables/providers").json()["rows"]
    assert "Doe, Jane" in rows[0]["employee_id_label"]
    opts = client.get("/api/options/providers", params={"q": "Doe"}).json()
    assert opts == [{"id": rows[0]["provider_id"], "label": "Doe, Jane · MD"}]


def count(t, where, *args):
    with app.connect() as c:
        return c.execute(f"SELECT COUNT(*) FROM {t} WHERE {where}", args).fetchone()[0]


def coverage(client, pid):
    payer = post(client, "payers", dict(payer_name="Acme", payer_type="Commercial", edi_payer_id="E1"))
    plan = post(client, "insurance_plans", dict(payer_id=payer["payer_id"], plan_name="Acme PPO", plan_type="PPO"))
    return post(client, "patient_coverage", dict(patient_id=pid, plan_id=plan["plan_id"], coverage_priority=1, member_id="M1",
                                                 relationship_to_subscriber="Self", effective_date="2024-01-01"))


def test_delete_blocked(client):
    f, d, _, _ = org(client)
    pid = post(client, "patients", PATIENT)["patient_id"]
    encounter(client, pid, f, d)
    r = client.delete(f"/api/tables/patients/{pid}")
    assert r.status_code == 409 and r.json()["detail"] == "Used by 1 encounters"


def test_patient_cascade(client):
    pid = post(client, "patients", PATIENT)["patient_id"]
    post(client, "patient_contacts", dict(patient_id=pid, first_name="Bo", last_name="Lee", relationship="Brother",
                                          is_emergency_contact=True, is_legal_guardian=False, is_healthcare_poa=False))
    coverage(client, pid)
    post(client, "allergies", dict(patient_id=pid, allergen="Peanut", allergen_type="Food", status="Active", recorded_date="2024-01-01"))
    post(client, "problem_list", dict(patient_id=pid, icd10_code="E11.9", description="T2DM", noted_date="2024-01-01", status="Active"))
    post(client, "social_history", dict(patient_id=pid, tobacco_status="Never smoker"))
    post(client, "medications", dict(patient_id=pid, medication_name="Metformin", start_date="2024-01-01", status="Active",
                                     is_controlled_substance=False))
    post(client, "immunizations", dict(patient_id=pid, cvx_code="141", vaccine_name="Flu", administered_date="2024-10-01"))
    post(client, "patient_payments", dict(patient_id=pid, payment_date="2024-02-01", amount=20, payment_method="Cash"))
    assert client.delete(f"/api/tables/patients/{pid}").status_code == 200
    for t in ("patient_contacts", "patient_coverage", "allergies", "problem_list", "social_history", "medications",
              "immunizations", "patient_payments"):
        assert count(t, "patient_id = ?", pid) == 0, t


def test_related_patient_blocks(client):
    a = post(client, "patients", PATIENT)["patient_id"]
    b = post(client, "patients", PATIENT | {"mrn": "DEMO000002"})["patient_id"]
    post(client, "patient_contacts", dict(patient_id=b, related_patient_id=a, first_name="Ann", last_name="Lee",
                                          relationship="Sister", is_emergency_contact=True, is_legal_guardian=False,
                                          is_healthcare_poa=False))
    assert client.delete(f"/api/tables/patients/{a}").status_code == 409


def test_integrity_maps_409(client):
    f, d, _, _ = org(client)
    p1 = post(client, "patients", PATIENT)["patient_id"]
    p2 = post(client, "patients", PATIENT | {"mrn": "DEMO000002"})["patient_id"]
    cov = coverage(client, p1)
    encounter(client, p2, f, d, primary_coverage_id=cov["coverage_id"])
    r = client.delete(f"/api/tables/patients/{p1}")
    assert r.status_code == 409, r.text
    assert count("patient_coverage", "patient_id = ?", p1) == 1


def test_claim_cascades_lines(client):
    f, d, _, _ = org(client)
    pid = post(client, "patients", PATIENT)["patient_id"]
    e = encounter(client, pid, f, d)
    post(client, "chargemaster", dict(charge_code="C1", description="Visit", revenue_code="0510", standard_charge=100))
    c = post(client, "claims", dict(claim_number="DEMO-CLM-1", encounter_id=e["encounter_id"], patient_id=pid, claim_type="837P",
                                    billing_npi="9990000001", service_date_from="2026-01-01", service_date_to="2026-01-01",
                                    total_charge=100, status="Paid"))
    post(client, "claim_lines", dict(claim_id=c["claim_id"], line_number=1, charge_code="C1", units=1, charge_amount=100))
    assert client.delete(f"/api/tables/claims/{c['claim_id']}").status_code == 200
    assert count("claim_lines", "claim_id = ?", c["claim_id"]) == 0



def test_seed_refuses_prod(tmp_path):
    r = subprocess.run([sys.executable, "seed.py"], cwd=HERE, env=os.environ | {"APP_ENV": "prod"}, capture_output=True)
    assert r.returncode != 0
    with pytest.raises(SystemExit):
        seedmod.seed(tmp_path / "prod.db")


def test_seed_valid(tmp_path):
    db = tmp_path / "demo.db"
    seedmod.seed(db)
    c = sqlite3.connect(db)
    assert c.execute("PRAGMA foreign_key_check").fetchall() == []
    tables = [t for ts in rules.GROUPS.values() for t in ts]
    assert len(tables) == 30
    for t in tables:
        assert c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] > 0, t
    for key, allowed in rules.STRICT.items():
        t, col = key.split(".")
        bad = c.execute(f"SELECT DISTINCT {col} FROM {t} WHERE {col} IS NOT NULL AND {col} NOT IN "
                        f"({','.join('?' * len(allowed))})", allowed).fetchall()
        assert bad == [], (key, bad)
    assert c.execute("SELECT COUNT(*) FROM patients WHERE ssn NOT LIKE '900-%'").fetchone()[0] == 0
    assert c.execute("SELECT COUNT(*) FROM patients").fetchone()[0] == 60


def test_seed_deterministic(tmp_path):
    a, b = tmp_path / "a.db", tmp_path / "b.db"
    seedmod.seed(a)
    seedmod.seed(b)
    q = "SELECT * FROM patients ORDER BY patient_id"
    assert sqlite3.connect(a).execute(q).fetchall() == sqlite3.connect(b).execute(q).fetchall()


SERIES = ("enc_by_month", "enc_by_dept", "enc_by_type", "patients_by_payer", "plan_type_mix", "claims_by_status",
          "charge_vs_paid", "top_problems")


@pytest.fixture
def seeded(tmp_path):
    app.DB_PATH = tmp_path / "demo.db"
    seedmod.seed(app.DB_PATH)
    app.init_db()
    return TestClient(app.app)


def test_dashboard_seeded(seeded):
    d = seeded.get("/api/dashboard").json()
    assert d["kpis"]["patients"] == 60
    assert all(d["kpis"][k] > 0 for k in ("encounters", "providers", "employees", "facilities", "open_claims"))
    for s in SERIES:
        assert d[s], s
    assert set(d["enc_by_month"][0]) == {"month", "AMB", "EMER", "IMP", "VR"}
    assert len(d["enc_by_type"]) <= 10 and len(d["top_problems"]) <= 10
    assert {"name", "charged", "paid"} == set(d["charge_vs_paid"][0])


def test_dashboard_empty(client):
    d = client.get("/api/dashboard").json()
    assert all(v == 0 for v in d["kpis"].values())
    assert all(d[s] == [] for s in SERIES)


def test_patient_bundle(seeded):
    with app.connect() as c:
        pid = c.execute("SELECT patient_id FROM encounters LIMIT 1").fetchone()[0]
    b = seeded.get(f"/api/patients/{pid}").json()
    for k in ("patient", "pcp", "coverages", "contacts", "allergies", "problems", "social_history", "encounters", "notes",
              "medications", "immunizations", "procedures", "lab_orders", "vitals", "screenings", "claims", "payments"):
        assert k in b, k
    assert b["patient"]["patient_id"] == pid and b["encounters"]
    assert all(isinstance(o["results"], list) for o in b["lab_orders"])
    assert [c["coverage_priority"] for c in b["coverages"]] == sorted(c["coverage_priority"] for c in b["coverages"])
    assert seeded.get("/api/patients/999999").status_code == 404


def test_switch_env(client, monkeypatch, tmp_path):
    monkeypatch.setattr(app, "DATA", tmp_path / "data")
    monkeypatch.setattr(app, "ENV", "demo")
    seedmod.seed(app.DATA / "demo.db")
    assert client.put("/api/env", json={"env": "demo"}).json()["env"] == "demo"
    assert client.get("/api/dashboard").json()["kpis"]["patients"] == 60
    assert client.put("/api/env", json={"env": "prod"}).json()["env"] == "prod"
    assert client.get("/api/env").json()["env"] == "prod"
    assert client.get("/api/dashboard").json()["kpis"]["patients"] == 0
    assert (app.DATA / "prod.db").exists()
    assert client.put("/api/env", json={"env": "staging"}).status_code == 400
    assert client.put("/api/env", json={"env": "../demo"}).status_code == 400
    assert client.get("/api/env").json()["env"] == "prod"
    assert client.put("/api/env", json={"env": "deepseek-v4-pro"}).json()["env"] == "deepseek-v4-pro"
    assert (app.DATA / "deepseek-v4-pro.db").exists()


def test_get_row_has_fk_labels(client):
    f, d, _, prov = org(client)
    pid = post(client, "patients", PATIENT)["patient_id"]
    e = encounter(client, pid, f, d, attending_provider_id=prov)
    r = client.get(f"/api/tables/encounters/{e['encounter_id']}").json()
    assert r["patient_id_label"] == "Lee, Ann · DEMO000001"
    assert r["attending_provider_id_label"] == "Doe, Jane · MD"


def test_compare_counts_per_model(client, monkeypatch, tmp_path):
    monkeypatch.setattr(app, "DATA", tmp_path / "data")
    client.put("/api/env", json={"env": "gemma-3-27b"})
    post(client, "patients", PATIENT)
    post(client, "patients", PATIENT | {"mrn": "DEMO000002"})
    client.put("/api/env", json={"env": "deepseek-v4-pro"})
    post(client, "patients", PATIENT)
    c = client.get("/api/compare").json()
    by = {d["id"]: d for d in c["dbs"]}
    assert by["gemma-3-27b"]["counts"]["patients"] == 2 and by["gemma-3-27b"]["total"] == 2
    assert by["deepseek-v4-pro"]["counts"]["patients"] == 1
    assert by["claude-haiku-5-5"]["total"] == 0  # never opened: reported as empty, file not created
    assert not (app.DATA / "claude-haiku-5-5.db").exists()
    assert "demo" not in by
    assert len(c["tables"]) == 30
