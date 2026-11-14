"""Rebuild data/demo.db with deterministic synthetic data (spec §9). Refuses prod."""
import os
import random
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import rules

HERE = Path(__file__).parent
DEMO_PATH = HERE.parent / "data" / "demo.db"
ANCHOR = date(2026, 11, 1)  # fixed "today" so the seed never changes

FIRST = ["Ava", "Liam", "Mia", "Noah", "Ella", "Owen", "Zoe", "Eli", "Ruby", "Jack", "Ivy", "Leo", "Nora", "Finn",
         "Lucy", "Cole", "Rose", "Gabe", "Jade", "Hugo"]
LAST = ["Adams", "Baker", "Carter", "Dixon", "Ellis", "Foster", "Grant", "Hayes", "Irwin", "Jensen", "Keller", "Lowe",
        "Mason", "Nolan", "Ortiz", "Price", "Quinn", "Reyes", "Shaw", "Turner"]
CITIES = [("Portsmouth", "Scioto", "45662"), ("Chillicothe", "Ross", "45601"), ("Waverly", "Pike", "45690"),
          ("Jackson", "Jackson", "45640"), ("Ironton", "Lawrence", "45638"), ("Gallipolis", "Gallia", "45631")]
ICD = [("E11.9", "Type 2 diabetes mellitus without complications"), ("I10", "Essential (primary) hypertension"),
       ("J45.909", "Unspecified asthma, uncomplicated"), ("F32.A", "Depression, unspecified"),
       ("E78.5", "Hyperlipidemia, unspecified"), ("M54.50", "Low back pain, unspecified"),
       ("F41.1", "Generalized anxiety disorder"), ("J06.9", "Acute upper respiratory infection, unspecified"),
       ("N39.0", "Urinary tract infection, site not specified"), ("F11.20", "Opioid dependence, uncomplicated"),
       ("I48.91", "Unspecified atrial fibrillation"), ("K21.9", "Gastro-esophageal reflux disease without esophagitis")]
MEDS = [("Metformin 500 mg tablet", 0, "oral"), ("Lisinopril 10 mg tablet", 0, "oral"),
        ("Atorvastatin 20 mg tablet", 0, "oral"), ("Albuterol 90 mcg inhaler", 0, "inhalation"),
        ("Sertraline 50 mg tablet", 0, "oral"), ("Omeprazole 20 mg capsule", 0, "oral"),
        ("Buprenorphine-naloxone 8-2 mg film", 1, "sublingual"), ("Oxycodone 5 mg tablet", 1, "oral"),
        ("Apixaban 5 mg tablet", 0, "oral")]
VACCINES = [("141", "Influenza, seasonal, injectable"), ("213", "SARS-COV-2 (COVID-19) vaccine"),
            ("115", "Tdap"), ("33", "Pneumococcal polysaccharide PPV23")]
# panel -> tests as (loinc, name, unit, normal low, normal high, draw low, draw high); flags follow the normal range
PANELS = {
    "Basic metabolic panel": [("2345-7", "Glucose", "mg/dL", 70, 99, 65, 180), ("2951-2", "Sodium", "mmol/L", 136, 145, 131, 149),
                              ("2823-3", "Potassium", "mmol/L", 3.5, 5.1, 3.1, 5.6)],
    "Hemoglobin A1c": [("4548-4", "Hemoglobin A1c", "%", 4.0, 5.6, 4.6, 10.5)],
    "Lipid panel": [("2093-3", "Cholesterol, total", "mg/dL", 0, 199, 140, 280), ("13457-7", "LDL cholesterol", "mg/dL", 0, 99, 60, 190),
                    ("2085-9", "HDL cholesterol", "mg/dL", 40, 100, 28, 80)],
    "TSH": [("3016-3", "TSH", "uIU/mL", 0.4, 4.0, 0.2, 6.5)],
    "CBC with automated differential": [("718-7", "Hemoglobin", "g/dL", 12.0, 17.5, 9.5, 17.0),
                                        ("6690-2", "WBC", "10*3/uL", 4.0, 11.0, 3.2, 14.0),
                                        ("777-3", "Platelets", "10*3/uL", 150, 400, 120, 450)],
    "Ferritin": [("2276-4", "Ferritin", "ng/mL", 30, 400, 10, 480)],
}
# instrument -> (max score, [(min score, interpretation)] highest band first)
SCREENS = {
    "PHQ-2": (6, [(3, "Positive"), (0, "Negative")]),
    "AUDIT-C": (12, [(4, "Positive"), (0, "Negative")]),
    "GAD-7": (21, [(15, "Severe anxiety"), (10, "Moderate anxiety"), (5, "Mild anxiety"), (0, "Minimal anxiety")]),
    "PHQ-9": (27, [(20, "Severe depression"), (15, "Moderately severe depression"), (10, "Moderate depression"),
                   (5, "Mild depression"), (0, "Minimal depression")]),
}


def seed(path: Path) -> None:
    if Path(path).name == "prod.db":
        sys.exit("seed.py refuses to touch prod.db")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    R = random.Random(42)
    S = rules.STRICT
    G = rules.SUGGEST
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript((HERE / "schema.sql").read_text())

    def ins(t: str, **row) -> int:
        return conn.execute(f"INSERT INTO {t} ({', '.join(row)}) VALUES ({', '.join('?' * len(row))})",
                            list(row.values())).lastrowid

    def pick(key: str):
        return R.choice(S[key])

    def day(back: int) -> date:
        return ANCHOR - timedelta(days=back)

    def phone() -> str:
        return f"555-01{R.randint(0, 99):02d}"

    def ssn() -> str:
        return f"900-{R.randint(10, 99)}-{R.randint(1000, 9999)}"

    # Org
    facilities = []
    for i, ftype in enumerate(S["facilities.facility_type"][:4], 1):
        city, county, z = CITIES[i - 1]
        facilities.append(ins("facilities", facility_code=f"DEMO-F{i}", name=f"Scioto Ridge {city} {ftype}",
                              facility_type=ftype, npi=f"999{i:07d}", tax_id=f"99-00000{i:02d}",
                              address_line1=f"{100 * i} Main St", city=city, state="OH", zip=z, county=county,
                              main_phone=phone(), licensed_beds=R.randint(20, 200) if "Hospital" in ftype else None,
                              opened_date=day(R.randint(3000, 9000)).isoformat()))
    dept_fac = {}
    for i, spec in enumerate(G["departments.specialty"][:12], 1):
        f = facilities[(i - 1) % 4]
        dept_fac[ins("departments", facility_id=f, department_name=f"{spec} Department", specialty=spec,
                     cost_center=f"CC{i:03d}", phone=phone())] = f
    depts = list(dept_fac)

    employees = []
    for i in range(1, 41):
        city, county, z = R.choice(CITIES)
        clinician = i <= 20
        pay = "Salary" if clinician else pick("employees.pay_type")
        d = R.choice(depts)
        employees.append(ins(
            "employees", employee_number=f"DEMO{i:04d}", first_name=R.choice(FIRST), last_name=R.choice(LAST),
            date_of_birth=day(R.randint(9000, 22000)).isoformat(), sex=pick("employees.sex"), ssn=ssn(),
            job_title="Physician" if clinician else R.choice(["Registered Nurse", "Medical Assistant", "Billing Specialist"]),
            job_code="MD" if clinician else R.choice(["RN", "MA", "BILL"]), department_id=d, facility_id=dept_fac[d],
            manager_employee_id=employees[0] if employees else None, hire_date=day(R.randint(400, 6000)).isoformat(),
            employment_status="Active" if R.random() < 0.9 else pick("employees.employment_status"), fte=1.0,
            pay_type=pay, hourly_rate=round(R.uniform(18, 45), 2) if pay == "Hourly" else None,
            annual_salary=round(R.uniform(90000, 320000), 2) if pay == "Salary" else None,
            work_email=f"employee{i}@example.org", work_phone=phone(), personal_phone=phone(),
            home_address_line1=f"{R.randint(1, 999)} Elm St", home_city=city, home_state="OH", home_zip=z,
            bank_routing_number="000000000", bank_account_last4="0000",
            emergency_contact_name=f"{R.choice(FIRST)} {R.choice(LAST)}", emergency_contact_phone=phone()))
    providers = [ins("providers", employee_id=employees[i], npi=f"999{100 + i:07d}", dea_number="X9999999",
                     state_license_number=f"DEMO-LIC{i:03d}", license_state="OH",
                     license_expiration=(ANCHOR + timedelta(days=R.randint(100, 900))).isoformat(),
                     credential=pick("providers.credential"), specialty=R.choice(G["providers.specialty"]),
                     taxonomy_code="207Q00000X", primary_department_id=R.choice(depts),
                     board_certified=int(R.random() < 0.8), accepting_new_patients=int(R.random() < 0.7))
                 for i in range(20)]
    staff = employees[20:]

    # Security
    roles = [ins("roles", role_name=name, description=f"Demo role: {name}") for name in G["roles.role_name"][:12]]
    for i in range(30):
        ins("role_permissions", role_id=roles[i % 12], resource=G["role_permissions.resource"][i % 14],
            can_read=1, can_write=int(R.random() < 0.4), scope=pick("role_permissions.scope"))
    users = []
    for i in range(20):
        human = i < 18
        users.append(ins("app_users", username=f"demo.user{i + 1}", display_name=f"Demo User {i + 1}",
                         user_type="human" if human else "service", role_id=R.choice(roles), is_active=1,
                         mfa_enrolled=int(R.random() < 0.7), created_at=f"{day(R.randint(400, 2000))}T08:00:00",
                         last_login_at=f"{day(R.randint(0, 30))}T09:15:00", password_last_changed=None,
                         employee_id=employees[i] if human else None))

    # Patients & coverage
    payers = [ins("payers", payer_name=f"Demo {ptype} Payer", payer_type=ptype, edi_payer_id=f"DEMO{i}",
                  claims_phone=phone()) for i, ptype in enumerate(S["payers.payer_type"][:4], 1)]
    plan_payer = {}
    for i, ptype in enumerate(S["insurance_plans.plan_type"][:8]):
        p = payers[i % 4]
        plan_payer[ins("insurance_plans", payer_id=p, plan_name=f"Demo {ptype} Plan", plan_type=ptype,
                       deductible_individual=R.choice([500, 1500, 3000]), oop_max_individual=R.choice([4000, 7000]),
                       coinsurance_pct=R.choice([10, 20, 30]), copay_pcp=25, copay_specialist=50, copay_er=250)] = p
    plans = list(plan_payer)

    patients, primary_cov = [], {}
    for i in range(1, 61):
        city, county, z = R.choice(CITIES)
        first = R.choice(FIRST)
        pid = ins("patients", mrn=f"DEMO{i:06d}", first_name=first, middle_name=None, last_name=R.choice(LAST),
                  date_of_birth=day(R.randint(400, 32000)).isoformat(), sex_at_birth=pick("patients.sex_at_birth"),
                  gender_identity=pick("patients.gender_identity"), race=pick("patients.race"),
                  ethnicity=pick("patients.ethnicity"), preferred_language=pick("patients.preferred_language"),
                  interpreter_needed=int(R.random() < 0.1), marital_status=pick("patients.marital_status"), ssn=ssn(),
                  address_line1=f"{R.randint(1, 999)} Oak St", city=city, state="OH", zip=z, county=county,
                  home_phone=phone(), mobile_phone=phone(), email=f"patient{i}@example.org",
                  pcp_provider_id=R.choice(providers), registration_date=day(R.randint(30, 3000)).isoformat(),
                  confidentiality_level="standard" if R.random() < 0.85 else pick("patients.confidentiality_level"),
                  portal_active=int(R.random() < 0.6), advance_directive_on_file=int(R.random() < 0.3))
        patients.append(pid)
        plan = R.choice(plans)
        primary_cov[pid] = (ins("patient_coverage", patient_id=pid, plan_id=plan, coverage_priority=1,
                                member_id=f"DEMO-M{i:05d}", group_number=f"G{R.randint(100, 999)}",
                                relationship_to_subscriber="Self", effective_date=day(R.randint(365, 2000)).isoformat()),
                            plan)
        if R.random() < 0.5:
            ins("patient_coverage", patient_id=pid, plan_id=R.choice(plans), coverage_priority=2,
                member_id=f"DEMO-S{i:05d}", relationship_to_subscriber=pick("patient_coverage.relationship_to_subscriber"),
                subscriber_first_name=R.choice(FIRST), subscriber_last_name=R.choice(LAST),
                subscriber_dob=day(R.randint(9000, 25000)).isoformat(), effective_date=day(R.randint(100, 900)).isoformat())
        ins("social_history", patient_id=pid, tobacco_status=pick("social_history.tobacco_status"),
            alcohol_use=pick("social_history.alcohol_use"), alcohol_drinks_per_week=R.randint(0, 10),
            drug_use=pick("social_history.drug_use"), sexual_orientation=pick("social_history.sexual_orientation"),
            occupation=R.choice(["Teacher", "Nurse aide", "Farmer", "Retired", "Student", "Driver"]),
            education_level=R.choice(["High school", "Some college", "Bachelor's degree"]),
            living_situation=R.choice(["Lives with family", "Lives alone"]), food_insecurity=int(R.random() < 0.15),
            housing_insecurity=int(R.random() < 0.1), last_reviewed_date=day(R.randint(0, 365)).isoformat())
    for i in range(80):
        pid = patients[i % 60]
        other = R.choice(patients)
        ins("patient_contacts", patient_id=pid, related_patient_id=other if R.random() < 0.1 and other != pid else None,
            first_name=R.choice(FIRST), last_name=R.choice(LAST), relationship=pick("patient_contacts.relationship"),
            phone=phone(), is_emergency_contact=int(i < 60), is_legal_guardian=int(R.random() < 0.05),
            is_healthcare_poa=int(R.random() < 0.1))

    # Encounters and per-encounter rows
    cls_for = {"Emergency": "EMER", "Telehealth Visit": "VR", "Inpatient": "IMP"}
    encs = []  # (encounter_id, patient_id, start datetime, department_id, provider)
    for i in range(1, 251):
        pid = R.choice(patients)
        etype = R.choice(G["encounters.encounter_type"])
        d = R.choice(depts)
        start = datetime.combine(day(R.randint(1, 365)), datetime.min.time()) + timedelta(hours=R.randint(7, 18))
        end = start + (timedelta(days=R.randint(1, 5)) if etype == "Inpatient" else timedelta(minutes=R.randint(20, 240)))
        prov = R.choice(providers)
        eid = ins("encounters", csn=f"DEMO-{i:06d}", patient_id=pid, facility_id=dept_fac[d], department_id=d,
                  attending_provider_id=prov, encounter_type=etype, encounter_class=cls_for.get(etype, "AMB"),
                  admit_source=pick("encounters.admit_source"), start_datetime=start.isoformat(),
                  end_datetime=end.isoformat(), chief_complaint=R.choice(["Cough", "Follow-up", "Chest pain", "Fever", "Back pain"]),
                  discharge_disposition=pick("encounters.discharge_disposition"),
                  primary_coverage_id=primary_cov[pid][0], status="Completed")
        encs.append((eid, pid, start, d, prov))
        for n, (code, desc) in enumerate(R.sample(ICD, R.randint(1, 2)), 1):
            ins("encounter_diagnoses", encounter_id=eid, sequence_number=n, icd10_code=code, description=desc,
                is_primary=int(n == 1), present_on_admission="Y" if etype == "Inpatient" else None)
        note_type = R.choice(G["clinical_notes.note_type"])
        sensitive = "Psych" in note_type or "Addiction" in note_type
        ins("clinical_notes", encounter_id=eid, patient_id=pid, author_provider_id=prov, note_type=note_type,
            note_datetime=end.isoformat(), note_text=f"Synthetic demo note for {etype.lower()}. No real patient data.",
            is_sensitive=int(sensitive), sensitivity_reason="Behavioral health" if sensitive else None, signed=1)
        if R.random() < 0.6:
            h = R.uniform(150, 190)
            w = R.uniform(50, 120)
            ins("vitals", encounter_id=eid, patient_id=pid, recorded_datetime=start.isoformat(),
                systolic_bp=R.randint(100, 160), diastolic_bp=R.randint(60, 100), heart_rate=R.randint(55, 110),
                respiratory_rate=R.randint(12, 22), temperature_f=round(R.uniform(97, 101.5), 1), spo2_pct=R.randint(92, 100),
                height_cm=round(h, 1), weight_kg=round(w, 1), bmi=round(w / (h / 100) ** 2, 1), pain_score=R.randint(0, 8),
                recorded_by_employee_id=R.choice(staff))

    # Patient-level clinical
    for _ in range(70):
        ins("allergies", patient_id=R.choice(patients), allergen=R.choice(["Penicillin", "Peanut", "Latex", "Sulfa", "Pollen"]),
            allergen_type=pick("allergies.allergen_type"), reaction=R.choice(["Hives", "Rash", "Anaphylaxis", None]),
            severity=pick("allergies.severity"), status="Active", recorded_date=day(R.randint(0, 2000)).isoformat())
    for _ in range(90):
        code, desc = R.choice(ICD)
        ins("problem_list", patient_id=R.choice(patients), icd10_code=code, description=desc,
            onset_date=day(R.randint(400, 3000)).isoformat(), noted_date=day(R.randint(0, 399)).isoformat(),
            status="Active", noted_by_provider_id=R.choice(providers))
    for _ in range(120):
        eid, pid, start, _, prov = R.choice(encs)
        name, controlled, route = R.choice(MEDS)
        ins("medications", patient_id=pid, encounter_id=eid, prescriber_provider_id=prov, medication_name=name,
            dose=name.split()[1] + " " + name.split()[2], route=route, frequency="daily",
            sig="Take as directed", quantity=30, refills=R.randint(0, 3), start_date=start.date().isoformat(),
            end_date=None, status=pick("medications.status"), indication_icd10=R.choice(ICD)[0],
            pharmacy="Demo Pharmacy", is_controlled_substance=controlled)
    for _ in range(80):
        eid, pid, start, _, _ = R.choice(encs)
        cvx, vname = R.choice(VACCINES)
        ins("immunizations", patient_id=pid, encounter_id=eid, cvx_code=cvx, vaccine_name=vname,
            administered_date=start.date().isoformat(), lot_number=f"DEMO{R.randint(1000, 9999)}",
            manufacturer="Demo Pharma", site=pick("immunizations.site"), route=pick("immunizations.route"),
            administered_by_employee_id=R.choice(staff))
    for _ in range(100):
        eid, pid, start, _, prov = R.choice(encs)
        system = pick("procedures.code_system")
        cpt = system == "CPT"
        ins("procedures", encounter_id=eid, patient_id=pid, code="99213" if cpt else "G0439", code_system=system,
            description="Office visit, established patient, low complexity" if cpt else "Annual wellness visit, subsequent", units=1, performed_datetime=start.isoformat(),
            performing_provider_id=prov)
    for i in range(1, 121):
        eid, pid, start, _, prov = R.choice(encs)
        status = pick("lab_orders.status")
        oid = ins("lab_orders", accession_number=f"DEMO-L{i:06d}", encounter_id=eid, patient_id=pid,
                  ordering_provider_id=prov, panel_name=(panel := R.choice(list(PANELS))), cpt_code="80053",
                  order_datetime=start.isoformat(), collected_datetime=(start + timedelta(minutes=30)).isoformat(),
                  resulted_datetime=(start + timedelta(hours=4)).isoformat(), status=status)
        for loinc, test, unit, nlo, nhi, lo, hi in PANELS[panel]:
            value = round(R.uniform(lo, hi), 1)
            ins("lab_results", lab_order_id=oid, patient_id=pid, loinc_code=loinc, test_name=test,
                value_numeric=value, unit=unit, reference_range=f"<{nhi + 1}" if nlo == 0 else f"{nlo}-{nhi}",
                abnormal_flag="H" if value > nhi else "L" if value < nlo else None,
                resulted_datetime=(start + timedelta(hours=4)).isoformat())
    for _ in range(80):
        eid, pid, start, _, _ = R.choice(encs)
        instrument = R.choice(list(SCREENS))
        top, bands = SCREENS[instrument]
        score = R.randint(0, top)
        ins("screenings", encounter_id=eid, patient_id=pid, instrument=instrument, loinc_code="44261-6", score=score,
            interpretation=next(text for floor, text in bands if score >= floor), administered_datetime=start.isoformat())

    # Billing
    for i in range(1, 21):
        ins("chargemaster", charge_code=f"DEMO{i:04d}", description=f"Demo charge {i}",
                           revenue_code=R.choice(["0450", "0510", "0300", "0320"]), standard_charge=R.randint(50, 2000))
    codes = [r[0] for r in conn.execute("SELECT charge_code FROM chargemaster ORDER BY charge_code")]
    claims = []
    for i, (eid, pid, start, d, prov) in enumerate(R.sample(encs, 150), 1):
        cov, plan = primary_cov[pid]
        status = pick("claims.status")
        total = round(R.uniform(100, 5000), 2)
        paid = round(total * R.uniform(0.3, 0.8), 2) if status == "Paid" else 0
        cid = ins("claims", claim_number=f"DEMO-CLM-{i:06d}", encounter_id=eid, patient_id=pid, coverage_id=cov,
                  payer_id=plan_payer[plan], claim_type=pick("claims.claim_type"), billing_npi=f"999{facilities.index(dept_fac[d]) + 1:07d}",
                  rendering_provider_id=prov, service_date_from=start.date().isoformat(),
                  service_date_to=start.date().isoformat(), submitted_date=(start.date() + timedelta(days=3)).isoformat(),
                  adjudicated_date=(start.date() + timedelta(days=20)).isoformat() if status in ("Paid", "Denied") else None,
                  total_charge=total, allowed_amount=round(total * 0.8, 2), paid_amount=paid,
                  contractual_adjustment=round(total * 0.2, 2), patient_responsibility=round(total * 0.05, 2), status=status,
                  denial_code="CO-97" if status == "Denied" else None,
                  denial_reason="Demo denial reason" if status == "Denied" else None)
        claims.append((cid, eid, pid, start))
        for n in range(1, R.choice([2, 3, 3]) + 1):
            amt = round(total / 3, 2)
            ins("claim_lines", claim_id=cid, line_number=n, charge_code=R.choice(codes), revenue_code="0510", units=1,
                charge_amount=amt, allowed_amount=round(amt * 0.8, 2), paid_amount=round(amt * 0.5, 2) if paid else 0)
    for _ in range(120):
        cid, eid, pid, start = R.choice(claims)
        method = pick("patient_payments.payment_method")
        card = "Card" in method
        ins("patient_payments", patient_id=pid, encounter_id=eid, claim_id=cid,
            payment_date=(start.date() + timedelta(days=R.randint(1, 60))).isoformat(), amount=round(R.uniform(10, 300), 2),
            payment_method=method, card_brand=pick("patient_payments.card_brand") if card else None,
            card_last4="0000" if card else None, card_exp="12/29" if card else None,
            processor_token=f"demo_tok_{R.randint(10000, 99999)}" if card else None, posted_by_employee_id=R.choice(staff))

    # Audit
    for _ in range(500):
        when = datetime.combine(day(R.randint(0, 364)), datetime.min.time()) + timedelta(minutes=R.randint(0, 1439))
        ins("access_audit_log", user_id=R.choice(users), patient_id=R.choice(patients), access_datetime=when.isoformat(),
            action=pick("access_audit_log.action"), resource_type=pick("access_audit_log.resource_type"),
            resource_id=R.randint(1, 250), workstation_id=f"DEMO-WS{R.randint(1, 40):02d}",
            ip_address=f"10.0.{R.randint(0, 9)}.{R.randint(1, 254)}", access_reason="Treatment",
            break_the_glass=int(R.random() < 0.02), flagged_for_review=int(R.random() < 0.03))
    conn.commit()
    conn.close()


def main() -> None:
    if os.environ.get("APP_ENV", "demo") == "prod":
        sys.exit("seed.py refuses to run with APP_ENV=prod")
    seed(DEMO_PATH)
    print(f"seeded {DEMO_PATH}")


if __name__ == "__main__":
    main()
