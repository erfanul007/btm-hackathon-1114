import { useEffect, useId, useState } from 'react'
import { type Col, type Meta, type Row, get, kind, nice, send, show } from './api'

type Props = { t: string; meta: Meta; row: Row | null; onDone: (changed: boolean) => void }

const PATIENT_CONFIRM =
  'Delete this patient and their contacts, coverage, allergies, problems, social history, medications, immunizations and payments?'

export default function RowForm({ t, meta, row, onDone }: Props) {
  const { pk, columns } = meta.tables[t]
  const isNew = row === null
  const [values, setValues] = useState<Row>(() => {
    if (row) return { ...row }
    return Object.fromEntries(columns.filter(c => kind(c.type) === 'BOOLEAN').map(c => [c.name, false]))
  })
  const [error, setError] = useState('')
  const set = (name: string, v: unknown) => setValues(prev => ({ ...prev, [name]: v }))

  // integer PKs are assigned by SQLite; a text PK (chargemaster) is typed on create only
  const editable = columns.filter(c => !(c.pk && (kind(c.type) === 'INT' || !isNew)))

  async function save(e: React.FormEvent) {
    e.preventDefault()
    const body = Object.fromEntries(editable.map(c => [c.name, values[c.name] ?? null]))
    try {
      if (isNew) await send('POST', `/api/tables/${t}`, body)
      else await send('PUT', `/api/tables/${t}/${encodeURIComponent(show(row![pk]))}`, body)
      onDone(true)
    } catch (err) {
      setError((err as Error).message)
    }
  }

  async function remove() {
    if (!confirm(t === 'patients' ? PATIENT_CONFIRM : 'Delete this row?')) return
    try {
      await send('DELETE', `/api/tables/${t}/${encodeURIComponent(show(row![pk]))}`)
      onDone(true)
    } catch (err) {
      setError((err as Error).message)
    }
  }

  return (
    <aside className="drawer" aria-label={`${isNew ? 'Add' : 'Edit'} ${nice(t)}`}>
      <form onSubmit={save}>
        <header className="drawer-head">
          <h2>{isNew ? `Add ${nice(t)}` : `${nice(t)} #${show(row![pk])}`}</h2>
          <button type="button" className="ghost" onClick={() => onDone(false)} aria-label="Close">✕</button>
        </header>
        {error && <p className="error" role="alert">{error}</p>}
        {!isNew && <p className="muted">{nice(pk)}: {show(row![pk])}</p>}
        {editable.map(c => (
          <label key={c.name} className={kind(c.type) === 'BOOLEAN' ? 'field check' : 'field'}>
            <span>{nice(c.name, !!c.fk)}{c.required && <b aria-label="required"> *</b>}</span>
            <Field t={t} col={c} value={values[c.name]} label={show(values[`${c.name}_label`])} onChange={v => set(c.name, v)} />
          </label>
        ))}
        <footer className="drawer-foot">
          <button type="submit">Save</button>
          {!isNew && <button type="button" className="danger" onClick={remove}>Delete</button>}
        </footer>
      </form>
    </aside>
  )
}

function Field({ t, col, value, label, onChange }: { t: string; col: Col; value: unknown; label: string; onChange: (v: unknown) => void }) {
  const k = kind(col.type)
  if (col.fk) return <FkInput target={col.fk} value={value} label={label} onChange={onChange} />
  if (k === 'BOOLEAN') return <input type="checkbox" checked={value === true || value === 1} onChange={e => onChange(e.target.checked)} />
  if (col.strict)
    return (
      <select value={show(value)} onChange={e => onChange(e.target.value)} required={col.required}>
        <option value="">—</option>
        {col.strict.map(v => <option key={v} value={v}>{v}</option>)}
      </select>
    )
  if (k === 'TEXT') return <textarea rows={4} value={show(value)} onChange={e => onChange(e.target.value)} />
  if (k === 'INT' || k === 'NUMERIC')
    return <input type="number" step={k === 'INT' ? 1 : 'any'} value={show(value)} onChange={e => onChange(e.target.value)} />
  if (k === 'DATE') return <input type="date" value={show(value).slice(0, 10)} onChange={e => onChange(e.target.value)} />
  if (k === 'TIMESTAMP')
    return <input type="datetime-local" value={show(value).slice(0, 16)} onChange={e => onChange(e.target.value)} />
  const listId = col.suggest ? `${t}-${col.name}-list` : undefined
  return (
    <>
      <input value={show(value)} list={listId} onChange={e => onChange(e.target.value)} />
      {col.suggest && <datalist id={listId}>{col.suggest.map(v => <option key={v} value={v} />)}</datalist>}
    </>
  )
}

/** Searchable FK picker: type to search labels, pick one to set the id. */
function FkInput({ target, value, label, onChange }: { target: string; value: unknown; label: string; onChange: (v: unknown) => void }) {
  const [text, setText] = useState(label || show(value))
  const [opts, setOpts] = useState<{ id: unknown; label: string }[]>([])
  const listId = useId()

  useEffect(() => {
    const h = setTimeout(() => {
      get<{ id: unknown; label: string }[]>(`/api/options/${target}?q=${encodeURIComponent(text)}`).then(setOpts, () => setOpts([]))
    }, 250)
    return () => clearTimeout(h)
  }, [target, text])

  function pick(v: string) {
    setText(v)
    if (v === '') return onChange(null)
    const hit = opts.find(o => o.label === v)
    if (hit) onChange(hit.id)
  }

  return (
    <>
      <input value={text} list={listId} placeholder={`Search ${nice(target)}…`} onChange={e => pick(e.target.value)} />
      <datalist id={listId}>{opts.map(o => <option key={show(o.id)} value={o.label} />)}</datalist>
      {!text && value != null && <small className="muted">ID {show(value)}</small>}
    </>
  )
}
