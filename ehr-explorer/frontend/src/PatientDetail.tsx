import { useEffect, useState } from 'react'
import { type Meta, type Row, fmt, get, nice, show } from './api'

type Bundle = Record<string, Row | Row[] | null> & { patient: Row; lab_orders: (Row & { results: Row[] })[] }

type Props = { id: number; meta: Meta; onBack: () => void; onEdit: (t: string, pk: string) => void }

// [bundle key, table, pk, columns to show] in §8 order
const SECTIONS: [string, string, string, string[]][] = [
  ['coverages', 'patient_coverage', 'coverage_id', ['coverage_priority', 'plan_name', 'plan_type', 'member_id', 'effective_date', 'termination_date']],
  ['contacts', 'patient_contacts', 'contact_id', ['first_name', 'last_name', 'relationship', 'phone', 'is_emergency_contact']],
  ['allergies', 'allergies', 'allergy_id', ['allergen', 'allergen_type', 'reaction', 'severity', 'status']],
  ['problems', 'problem_list', 'problem_id', ['icd10_code', 'description', 'status', 'noted_date']],
  ['encounters', 'encounters', 'encounter_id', ['start_datetime', 'encounter_type', 'encounter_class', 'department_name', 'chief_complaint', 'status']],
  ['medications', 'medications', 'medication_order_id', ['medication_name', 'route', 'frequency', 'status', 'start_date']],
  ['immunizations', 'immunizations', 'immunization_id', ['vaccine_name', 'administered_date', 'site']],
  ['procedures', 'procedures', 'procedure_id', ['code', 'code_system', 'description', 'performed_datetime']],
  ['vitals', 'vitals', 'vital_id', ['recorded_datetime', 'systolic_bp', 'diastolic_bp', 'heart_rate', 'temperature_f', 'spo2_pct', 'bmi']],
  ['screenings', 'screenings', 'screening_id', ['instrument', 'score', 'interpretation', 'administered_datetime']],
  ['claims', 'claims', 'claim_id', ['claim_number', 'service_date_from', 'total_charge', 'paid_amount', 'status']],
  ['payments', 'patient_payments', 'payment_id', ['payment_date', 'amount', 'payment_method']],
]

const DEMOGRAPHICS = ['mrn', 'date_of_birth', 'sex_at_birth', 'gender_identity', 'preferred_language', 'marital_status',
  'city', 'county', 'mobile_phone', 'email', 'confidentiality_level', 'portal_active']

export default function PatientDetail({ id, meta, onBack, onEdit }: Props) {
  const col = (t: string, c: string) => meta.tables[t]?.columns.find(x => x.name === c)
  const [b, setB] = useState<Bundle | null>(null)
  const [error, setError] = useState('')

  useEffect(() => { get<Bundle>(`/api/patients/${id}`).then(setB, e => setError(e.message)) }, [id])

  if (error) return <p className="error" role="alert">{error}</p>
  if (!b) return <p className="muted">Loading…</p>
  const p = b.patient
  const pcp = b.pcp as Row | null
  const social = b.social_history as Row | null

  const Edit = ({ t, pk }: { t: string; pk: unknown }) => (
    <button className="link" onClick={() => onEdit(t, show(pk))}>edit</button>
  )

  return (
    <article className="patient">
      <button className="link back" onClick={onBack}>← Patients</button>
      <header className="toolbar">
        <h1>{show(p.last_name)}, {show(p.first_name)} <span className="muted">· {show(p.mrn)}</span></h1>
        <Edit t="patients" pk={p.patient_id} />
      </header>
      <dl className="kv">
        {DEMOGRAPHICS.map(k => <div key={k}><dt>{nice(k)}</dt><dd>{fmt(col('patients', k), p[k]) || '—'}</dd></div>)}
        <div><dt>PCP</dt><dd>{pcp ? show(pcp.label) : '—'}</dd></div>
      </dl>

      {SECTIONS.slice(0, 4).map(s => <Section key={s[0]} spec={s} rows={b[s[0]] as Row[]} Edit={Edit} meta={meta} />)}

      <section className="card">
        <h2>Social history {social && <Edit t="social_history" pk={social.patient_id} />}</h2>
        {social ? (
          <dl className="kv">
            {Object.entries(social).filter(([k]) => k !== 'patient_id').map(([k, v]) => (
              <div key={k}><dt>{nice(k)}</dt><dd>{fmt(col('social_history', k), v) || '—'}</dd></div>
            ))}
          </dl>
        ) : <p className="muted">None recorded</p>}
      </section>

      <Section spec={SECTIONS[4]} rows={b.encounters as Row[]} Edit={Edit} meta={meta} />

      <section className="card">
        <h2>Clinical notes <span className="muted">({(b.notes as Row[]).length})</span></h2>
        {(b.notes as Row[]).map(n => (
          <details key={show(n.note_id)}>
            <summary>{fmt(col('clinical_notes', 'note_datetime'), n.note_datetime)} · {show(n.note_type)} {n.is_sensitive ? '· sensitive' : ''} <Edit t="clinical_notes" pk={n.note_id} /></summary>
            <p className="note">{show(n.note_text)}</p>
          </details>
        ))}
        {(b.notes as Row[]).length === 0 && <p className="muted">None</p>}
      </section>

      {SECTIONS.slice(5, 8).map(s => <Section key={s[0]} spec={s} rows={b[s[0]] as Row[]} Edit={Edit} meta={meta} />)}

      <section className="card">
        <h2>Lab orders & results <span className="muted">({b.lab_orders.length})</span></h2>
        {b.lab_orders.map(o => (
          <div key={show(o.lab_order_id)} className="lab">
            <p><strong>{show(o.panel_name)}</strong> · {fmt(col('lab_orders', 'order_datetime'), o.order_datetime)} · {show(o.status)} <Edit t="lab_orders" pk={o.lab_order_id} /></p>
            <ul>
              {o.results.map(r => (
                <li key={show(r.lab_result_id)}>
                  {show(r.test_name)}: {show(r.value_numeric ?? r.value_text)} {show(r.unit)} <span className="muted">({show(r.reference_range)})</span>
                  {r.abnormal_flag ? <b className="flag"> {show(r.abnormal_flag)}</b> : null}
                </li>
              ))}
            </ul>
          </div>
        ))}
        {b.lab_orders.length === 0 && <p className="muted">None</p>}
      </section>

      {SECTIONS.slice(8).map(s => <Section key={s[0]} spec={s} rows={b[s[0]] as Row[]} Edit={Edit} meta={meta} />)}
    </article>
  )
}

function Section({ spec: [key, t, pk, cols], rows, Edit, meta }: {
  spec: [string, string, string, string[]]; rows: Row[]; Edit: (p: { t: string; pk: unknown }) => React.JSX.Element; meta: Meta
}) {
  const col = (c: string) => meta.tables[t].columns.find(x => x.name === c)
  return (
    <section className="card">
      <h2>{nice(t)} <span className="muted">({rows.length})</span></h2>
      {rows.length === 0 ? <p className="muted">None</p> : (
        <div className="scroll">
          <table aria-label={key}>
            <thead><tr>{cols.map(c => <th key={c}>{nice(c)}</th>)}<th><span className="sr-only">Actions</span></th></tr></thead>
            <tbody>
              {rows.map(r => (
                <tr key={show(r[pk])} className="static">
                  {cols.map(c => <td key={c}>{fmt(col(c), r[c])}</td>)}
                  <td><Edit t={t} pk={r[pk]} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
