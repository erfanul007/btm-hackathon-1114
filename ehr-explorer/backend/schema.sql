CREATE TABLE IF NOT EXISTS patients (
  patient_id INTEGER PRIMARY KEY,
  mrn VARCHAR(12) NOT NULL,
  first_name VARCHAR(60) NOT NULL,
  middle_name VARCHAR(60),
  last_name VARCHAR(60) NOT NULL,
  suffix VARCHAR(10),
  preferred_name VARCHAR(60),
  date_of_birth DATE NOT NULL,
  sex_at_birth CHAR(1) NOT NULL,
  gender_identity VARCHAR(40),
  race VARCHAR(60),
  ethnicity VARCHAR(40),
  preferred_language VARCHAR(30),
  interpreter_needed BOOLEAN NOT NULL,
  marital_status VARCHAR(20),
  ssn CHAR(11),
  address_line1 VARCHAR(120),
  address_line2 VARCHAR(60),
  city VARCHAR(60),
  state CHAR(2),
  zip VARCHAR(10),
  county VARCHAR(40),
  home_phone VARCHAR(20),
  mobile_phone VARCHAR(20),
  email VARCHAR(120),
  household_id INTEGER,
  pcp_provider_id INTEGER REFERENCES providers(provider_id),
  employee_id INTEGER REFERENCES employees(employee_id),
  registration_date DATE NOT NULL,
  deceased_date DATE,
  confidentiality_level VARCHAR(20) NOT NULL,
  confidentiality_note VARCHAR(255),
  portal_active BOOLEAN NOT NULL,
  advance_directive_on_file BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS encounters (
  encounter_id INTEGER PRIMARY KEY,
  csn VARCHAR(12) NOT NULL,
  patient_id INTEGER NOT NULL REFERENCES patients(patient_id),
  facility_id INTEGER NOT NULL REFERENCES facilities(facility_id),
  department_id INTEGER NOT NULL REFERENCES departments(department_id),
  attending_provider_id INTEGER REFERENCES providers(provider_id),
  encounter_type VARCHAR(40) NOT NULL,
  encounter_class VARCHAR(10) NOT NULL,
  admit_source VARCHAR(40),
  start_datetime TIMESTAMP NOT NULL,
  end_datetime TIMESTAMP,
  chief_complaint VARCHAR(255),
  discharge_disposition VARCHAR(60),
  primary_coverage_id INTEGER REFERENCES patient_coverage(coverage_id),
  status VARCHAR(20) NOT NULL
);

CREATE TABLE IF NOT EXISTS encounter_diagnoses (
  encounter_diagnosis_id INTEGER PRIMARY KEY,
  encounter_id INTEGER NOT NULL REFERENCES encounters(encounter_id),
  sequence_number INTEGER NOT NULL,
  icd10_code VARCHAR(10) NOT NULL,
  description VARCHAR(255) NOT NULL,
  is_primary BOOLEAN NOT NULL,
  present_on_admission CHAR(1)
);

CREATE TABLE IF NOT EXISTS clinical_notes (
  note_id INTEGER PRIMARY KEY,
  encounter_id INTEGER NOT NULL REFERENCES encounters(encounter_id),
  patient_id INTEGER NOT NULL REFERENCES patients(patient_id),
  author_provider_id INTEGER REFERENCES providers(provider_id),
  note_type VARCHAR(40) NOT NULL,
  note_datetime TIMESTAMP NOT NULL,
  note_text TEXT NOT NULL,
  is_sensitive BOOLEAN NOT NULL,
  sensitivity_reason VARCHAR(80),
  signed BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS allergies (
  allergy_id INTEGER PRIMARY KEY,
  patient_id INTEGER NOT NULL REFERENCES patients(patient_id),
  allergen VARCHAR(80) NOT NULL,
  allergen_type VARCHAR(20) NOT NULL,
  reaction VARCHAR(80),
  severity VARCHAR(20),
  status VARCHAR(20) NOT NULL,
  recorded_date DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS problem_list (
  problem_id INTEGER PRIMARY KEY,
  patient_id INTEGER NOT NULL REFERENCES patients(patient_id),
  icd10_code VARCHAR(10) NOT NULL,
  description VARCHAR(255) NOT NULL,
  onset_date DATE,
  noted_date DATE NOT NULL,
  resolved_date DATE,
  status VARCHAR(20) NOT NULL,
  noted_by_provider_id INTEGER REFERENCES providers(provider_id)
);

CREATE TABLE IF NOT EXISTS medications (
  medication_order_id INTEGER PRIMARY KEY,
  patient_id INTEGER NOT NULL REFERENCES patients(patient_id),
  encounter_id INTEGER REFERENCES encounters(encounter_id),
  prescriber_provider_id INTEGER REFERENCES providers(provider_id),
  rxnorm_ingredient_rxcui INTEGER,
  medication_name VARCHAR(160) NOT NULL,
  dose VARCHAR(40),
  route VARCHAR(30),
  frequency VARCHAR(40),
  sig VARCHAR(255),
  quantity INTEGER,
  refills INTEGER,
  start_date DATE NOT NULL,
  end_date DATE,
  status VARCHAR(20) NOT NULL,
  indication_icd10 VARCHAR(10),
  pharmacy VARCHAR(80),
  is_controlled_substance BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS immunizations (
  immunization_id INTEGER PRIMARY KEY,
  patient_id INTEGER NOT NULL REFERENCES patients(patient_id),
  encounter_id INTEGER REFERENCES encounters(encounter_id),
  cvx_code VARCHAR(4) NOT NULL,
  vaccine_name VARCHAR(160) NOT NULL,
  administered_date DATE NOT NULL,
  lot_number VARCHAR(20),
  manufacturer VARCHAR(60),
  site VARCHAR(30),
  route VARCHAR(20),
  administered_by_employee_id INTEGER REFERENCES employees(employee_id)
);

CREATE TABLE IF NOT EXISTS procedures (
  procedure_id INTEGER PRIMARY KEY,
  encounter_id INTEGER NOT NULL REFERENCES encounters(encounter_id),
  patient_id INTEGER NOT NULL REFERENCES patients(patient_id),
  code VARCHAR(10) NOT NULL,
  code_system VARCHAR(10) NOT NULL,
  description VARCHAR(255) NOT NULL,
  modifier VARCHAR(10),
  units INTEGER NOT NULL,
  performed_datetime TIMESTAMP NOT NULL,
  performing_provider_id INTEGER REFERENCES providers(provider_id)
);

CREATE TABLE IF NOT EXISTS vitals (
  vital_id INTEGER PRIMARY KEY,
  encounter_id INTEGER NOT NULL REFERENCES encounters(encounter_id),
  patient_id INTEGER NOT NULL REFERENCES patients(patient_id),
  recorded_datetime TIMESTAMP NOT NULL,
  systolic_bp INTEGER,
  diastolic_bp INTEGER,
  heart_rate INTEGER,
  respiratory_rate INTEGER,
  temperature_f NUMERIC(4,1),
  spo2_pct INTEGER,
  height_cm NUMERIC(5,1),
  weight_kg NUMERIC(5,1),
  bmi NUMERIC(4,1),
  pain_score INTEGER,
  recorded_by_employee_id INTEGER REFERENCES employees(employee_id)
);

CREATE TABLE IF NOT EXISTS screenings (
  screening_id INTEGER PRIMARY KEY,
  encounter_id INTEGER NOT NULL REFERENCES encounters(encounter_id),
  patient_id INTEGER NOT NULL REFERENCES patients(patient_id),
  instrument VARCHAR(30) NOT NULL,
  loinc_code VARCHAR(10),
  score INTEGER NOT NULL,
  interpretation VARCHAR(60),
  administered_datetime TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS social_history (
  patient_id INTEGER PRIMARY KEY,
  tobacco_status VARCHAR(30),
  tobacco_packs_per_day NUMERIC(3,1),
  tobacco_start_year INTEGER,
  tobacco_quit_year INTEGER,
  alcohol_use VARCHAR(20),
  alcohol_drinks_per_week INTEGER,
  drug_use VARCHAR(20),
  drug_types VARCHAR(120),
  sexually_active VARCHAR(20),
  sexual_orientation VARCHAR(40),
  occupation VARCHAR(80),
  employer VARCHAR(80),
  education_level VARCHAR(60),
  living_situation VARCHAR(60),
  food_insecurity BOOLEAN,
  housing_insecurity BOOLEAN,
  last_reviewed_date DATE
);

CREATE TABLE IF NOT EXISTS lab_orders (
  lab_order_id INTEGER PRIMARY KEY,
  accession_number VARCHAR(16) NOT NULL,
  encounter_id INTEGER NOT NULL REFERENCES encounters(encounter_id),
  patient_id INTEGER NOT NULL REFERENCES patients(patient_id),
  ordering_provider_id INTEGER REFERENCES providers(provider_id),
  panel_name VARCHAR(80) NOT NULL,
  cpt_code VARCHAR(10),
  order_datetime TIMESTAMP NOT NULL,
  collected_datetime TIMESTAMP,
  resulted_datetime TIMESTAMP,
  status VARCHAR(20) NOT NULL
);

CREATE TABLE IF NOT EXISTS lab_results (
  lab_result_id INTEGER PRIMARY KEY,
  lab_order_id INTEGER NOT NULL REFERENCES lab_orders(lab_order_id),
  patient_id INTEGER NOT NULL REFERENCES patients(patient_id),
  loinc_code VARCHAR(10) NOT NULL,
  test_name VARCHAR(255) NOT NULL,
  value_numeric NUMERIC(12,3),
  value_text VARCHAR(120),
  unit VARCHAR(20),
  reference_range VARCHAR(40),
  abnormal_flag VARCHAR(4),
  resulted_datetime TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS patient_contacts (
  contact_id INTEGER PRIMARY KEY,
  patient_id INTEGER NOT NULL REFERENCES patients(patient_id),
  related_patient_id INTEGER REFERENCES patients(patient_id),
  first_name VARCHAR(60) NOT NULL,
  last_name VARCHAR(60) NOT NULL,
  relationship VARCHAR(30) NOT NULL,
  phone VARCHAR(20),
  is_emergency_contact BOOLEAN NOT NULL,
  is_legal_guardian BOOLEAN NOT NULL,
  is_healthcare_poa BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS facilities (
  facility_id INTEGER PRIMARY KEY,
  facility_code VARCHAR(12) NOT NULL,
  name VARCHAR(120) NOT NULL,
  facility_type VARCHAR(40) NOT NULL,
  npi CHAR(10) NOT NULL,
  tax_id VARCHAR(12) NOT NULL,
  address_line1 VARCHAR(120) NOT NULL,
  city VARCHAR(60) NOT NULL,
  state CHAR(2) NOT NULL,
  zip VARCHAR(10) NOT NULL,
  county VARCHAR(40),
  main_phone VARCHAR(20),
  licensed_beds INTEGER,
  opened_date DATE
);

CREATE TABLE IF NOT EXISTS departments (
  department_id INTEGER PRIMARY KEY,
  facility_id INTEGER NOT NULL REFERENCES facilities(facility_id),
  department_name VARCHAR(120) NOT NULL,
  specialty VARCHAR(20) NOT NULL,
  cost_center VARCHAR(10) NOT NULL,
  phone VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS providers (
  provider_id INTEGER PRIMARY KEY,
  employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
  npi CHAR(10) NOT NULL,
  dea_number CHAR(9),
  state_license_number VARCHAR(20),
  license_state CHAR(2),
  license_expiration DATE,
  credential VARCHAR(20) NOT NULL,
  specialty VARCHAR(80) NOT NULL,
  taxonomy_code VARCHAR(12) NOT NULL,
  primary_department_id INTEGER REFERENCES departments(department_id),
  board_certified BOOLEAN NOT NULL,
  accepting_new_patients BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS employees (
  employee_id INTEGER PRIMARY KEY,
  employee_number VARCHAR(10) NOT NULL,
  first_name VARCHAR(60) NOT NULL,
  middle_name VARCHAR(60),
  last_name VARCHAR(60) NOT NULL,
  date_of_birth DATE NOT NULL,
  sex CHAR(1) NOT NULL,
  ssn CHAR(11) NOT NULL,
  job_title VARCHAR(80) NOT NULL,
  job_code VARCHAR(10) NOT NULL,
  department_id INTEGER REFERENCES departments(department_id),
  facility_id INTEGER REFERENCES facilities(facility_id),
  manager_employee_id INTEGER REFERENCES employees(employee_id),
  hire_date DATE NOT NULL,
  termination_date DATE,
  employment_status VARCHAR(20) NOT NULL,
  fte NUMERIC(3,2) NOT NULL,
  pay_type VARCHAR(10) NOT NULL,
  hourly_rate NUMERIC(8,2),
  annual_salary NUMERIC(12,2),
  work_email VARCHAR(120) NOT NULL,
  work_phone VARCHAR(20),
  personal_phone VARCHAR(20),
  home_address_line1 VARCHAR(120),
  home_city VARCHAR(60),
  home_state CHAR(2),
  home_zip VARCHAR(10),
  bank_routing_number CHAR(9),
  bank_account_last4 CHAR(4),
  emergency_contact_name VARCHAR(120),
  emergency_contact_phone VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS payers (
  payer_id INTEGER PRIMARY KEY,
  payer_name VARCHAR(120) NOT NULL,
  payer_type VARCHAR(30) NOT NULL,
  edi_payer_id VARCHAR(10) NOT NULL,
  claims_phone VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS insurance_plans (
  plan_id INTEGER PRIMARY KEY,
  payer_id INTEGER NOT NULL REFERENCES payers(payer_id),
  plan_name VARCHAR(120) NOT NULL,
  plan_type VARCHAR(40) NOT NULL,
  deductible_individual NUMERIC(10,2),
  oop_max_individual NUMERIC(10,2),
  coinsurance_pct INTEGER,
  copay_pcp NUMERIC(8,2),
  copay_specialist NUMERIC(8,2),
  copay_er NUMERIC(8,2)
);

CREATE TABLE IF NOT EXISTS patient_coverage (
  coverage_id INTEGER PRIMARY KEY,
  patient_id INTEGER NOT NULL REFERENCES patients(patient_id),
  plan_id INTEGER NOT NULL REFERENCES insurance_plans(plan_id),
  coverage_priority INTEGER NOT NULL,
  member_id VARCHAR(20) NOT NULL,
  group_number VARCHAR(20),
  subscriber_first_name VARCHAR(60),
  subscriber_last_name VARCHAR(60),
  subscriber_dob DATE,
  relationship_to_subscriber VARCHAR(20) NOT NULL,
  effective_date DATE NOT NULL,
  termination_date DATE
);

CREATE TABLE IF NOT EXISTS claims (
  claim_id INTEGER PRIMARY KEY,
  claim_number VARCHAR(20) NOT NULL,
  encounter_id INTEGER NOT NULL REFERENCES encounters(encounter_id),
  patient_id INTEGER NOT NULL REFERENCES patients(patient_id),
  coverage_id INTEGER REFERENCES patient_coverage(coverage_id),
  payer_id INTEGER REFERENCES payers(payer_id),
  claim_type VARCHAR(10) NOT NULL,
  billing_npi CHAR(10) NOT NULL,
  rendering_provider_id INTEGER REFERENCES providers(provider_id),
  drg_code VARCHAR(4),
  drg_description VARCHAR(160),
  service_date_from DATE NOT NULL,
  service_date_to DATE NOT NULL,
  submitted_date DATE,
  adjudicated_date DATE,
  total_charge NUMERIC(12,2) NOT NULL,
  allowed_amount NUMERIC(12,2),
  paid_amount NUMERIC(12,2),
  contractual_adjustment NUMERIC(12,2),
  patient_responsibility NUMERIC(12,2),
  status VARCHAR(20) NOT NULL,
  denial_code VARCHAR(10),
  denial_reason VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS claim_lines (
  claim_line_id INTEGER PRIMARY KEY,
  claim_id INTEGER NOT NULL REFERENCES claims(claim_id),
  line_number INTEGER NOT NULL,
  charge_code VARCHAR(10) NOT NULL REFERENCES chargemaster(charge_code),
  revenue_code CHAR(4),
  modifier VARCHAR(10),
  icd10_pointer VARCHAR(10),
  units INTEGER NOT NULL,
  charge_amount NUMERIC(12,2) NOT NULL,
  allowed_amount NUMERIC(12,2),
  paid_amount NUMERIC(12,2)
);

CREATE TABLE IF NOT EXISTS chargemaster (
  charge_code VARCHAR(10) PRIMARY KEY,
  description VARCHAR(160) NOT NULL,
  revenue_code CHAR(4) NOT NULL,
  standard_charge NUMERIC(10,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS patient_payments (
  payment_id INTEGER PRIMARY KEY,
  patient_id INTEGER NOT NULL REFERENCES patients(patient_id),
  encounter_id INTEGER REFERENCES encounters(encounter_id),
  claim_id INTEGER REFERENCES claims(claim_id),
  payment_date DATE NOT NULL,
  amount NUMERIC(10,2) NOT NULL,
  payment_method VARCHAR(20) NOT NULL,
  card_brand VARCHAR(20),
  card_last4 CHAR(4),
  card_exp CHAR(5),
  processor_token VARCHAR(40),
  posted_by_employee_id INTEGER REFERENCES employees(employee_id)
);

CREATE TABLE IF NOT EXISTS app_users (
  user_id INTEGER PRIMARY KEY,
  username VARCHAR(40) NOT NULL,
  display_name VARCHAR(120) NOT NULL,
  user_type VARCHAR(20) NOT NULL,
  role_id INTEGER NOT NULL REFERENCES roles(role_id),
  is_active BOOLEAN NOT NULL,
  mfa_enrolled BOOLEAN NOT NULL,
  created_at TIMESTAMP NOT NULL,
  last_login_at TIMESTAMP,
  password_last_changed TIMESTAMP,
  employee_id INTEGER REFERENCES employees(employee_id)
);

CREATE TABLE IF NOT EXISTS roles (
  role_id INTEGER PRIMARY KEY,
  role_name VARCHAR(60) NOT NULL,
  description VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS role_permissions (
  role_permission_id INTEGER PRIMARY KEY,
  role_id INTEGER NOT NULL REFERENCES roles(role_id),
  resource VARCHAR(60) NOT NULL,
  can_read BOOLEAN NOT NULL,
  can_write BOOLEAN NOT NULL,
  scope VARCHAR(40) NOT NULL
);

CREATE TABLE IF NOT EXISTS access_audit_log (
  audit_id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES app_users(user_id),
  patient_id INTEGER REFERENCES patients(patient_id),
  access_datetime TIMESTAMP NOT NULL,
  action VARCHAR(20) NOT NULL,
  resource_type VARCHAR(40) NOT NULL,
  resource_id INTEGER,
  workstation_id VARCHAR(30),
  ip_address VARCHAR(45),
  access_reason VARCHAR(80),
  break_the_glass BOOLEAN NOT NULL,
  flagged_for_review BOOLEAN NOT NULL
);
