export type Col = {
  name: string; type: string; required: boolean; pk: boolean
  fk: string | null; strict: string[] | null; suggest: string[] | null
}
export type TableMeta = { pk: string; columns: Col[]; group: string }
export type Meta = { tables: Record<string, TableMeta>; groups: Record<string, string[]> }
export type Row = Record<string, unknown>
export type Rows = { rows: Row[]; total: number }

export async function send<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `Request failed (${res.status})`)
  return data as T
}

export const get = <T,>(path: string) => send<T>('GET', path)

/** Mirrors backend kind(): which input a column gets. */
export function kind(type: string): 'INT' | 'NUMERIC' | 'BOOLEAN' | 'TIMESTAMP' | 'DATE' | 'TEXT' | 'STRING' {
  const t = type.toUpperCase()
  for (const k of ['INT', 'NUMERIC', 'BOOLEAN', 'TIMESTAMP', 'DATE', 'TEXT'] as const) if (t.includes(k)) return k
  return 'STRING'
}

export const show = (v: unknown) => (v === null || v === undefined ? '' : String(v))

const WORDS: Record<string, string> = {
  id: 'ID', mrn: 'MRN', csn: 'CSN', npi: 'NPI', dea: 'DEA', ssn: 'SSN', bmi: 'BMI', spo2: 'SpO₂', cpt: 'CPT', loinc: 'LOINC',
  cvx: 'CVX', drg: 'DRG', edi: 'EDI', fte: 'FTE', ip: 'IP', mfa: 'MFA', oop: 'OOP', pcp: 'PCP', er: 'ER', poa: 'POA',
  icd10: 'ICD-10', rxnorm: 'RxNorm', rxcui: 'RxCUI', pct: '%', bp: 'BP', dob: 'DOB', hdhp: 'HDHP', f: '°F', cm: 'cm', kg: 'kg',
}

/** Display name for a column or table: date_of_birth -> Date of birth, patient_id (FK) -> Patient. */
export function nice(name: string, fk = false): string {
  const words = name.replace(fk ? /_id$/ : /$^/, '').split('_')
  return words.map((w, i) => WORDS[w] ?? (i === 0 ? w[0].toUpperCase() + w.slice(1) : w)).join(' ')
}

/** Display value by column type: booleans as Yes/No, timestamps without the T and seconds. */
export function fmt(col: Col | undefined, v: unknown): string {
  if (v === null || v === undefined || v === '') return ''
  const k = col ? kind(col.type) : ''
  if (k === 'BOOLEAN') return v === 1 || v === true ? 'Yes' : 'No'
  if (k === 'TIMESTAMP') return String(v).slice(0, 16).replace('T', ' ')
  return String(v)
}
