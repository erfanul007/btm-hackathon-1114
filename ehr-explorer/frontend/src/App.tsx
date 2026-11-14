import { useEffect, useRef, useState } from 'react'
import { type Meta, get, nice, send } from './api'
import Compare from './Compare'
import Dashboard from './Dashboard'
import PatientDetail from './PatientDetail'
import TableView from './TableView'

export type View =
  | { kind: 'dashboard' }
  | { kind: 'compare' }
  | { kind: 'table'; t: string; editPk?: string }
  | { kind: 'patient'; id: number }

// URL hash mirrors the view so Back/Forward and reload work: #/patients, #/patients/edit/12, #/patient/12
function parseHash(h: string): View {
  const [a, b, c] = h.replace(/^#\/?/, '').split('/').map(decodeURIComponent)
  if (a === 'patient' && Number(b)) return { kind: 'patient', id: Number(b) }
  if (a === 'compare') return { kind: 'compare' }
  if (a && a !== 'dashboard') return { kind: 'table', t: a, editPk: b === 'edit' ? c : undefined }
  return { kind: 'dashboard' }
}

function toHash(v: View): string {
  if (v.kind === 'patient') return `#/patient/${v.id}`
  if (v.kind === 'compare') return '#/compare'
  if (v.kind === 'table') return `#/${v.t}` + (v.editPk ? `/edit/${encodeURIComponent(v.editPk)}` : '')
  return '#/dashboard'
}

type Env = { id: string; label: string; model: boolean }
type EnvInfo = { env: string; envs: Env[] }

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null)
  const [env, setEnv] = useState('')
  const [envs, setEnvs] = useState<Env[]>([])
  const [view, setViewState] = useState<View>(() => parseHash(location.hash))
  const setView = (v: View) => { location.hash = toHash(v) }
  const prev = useRef<View | null>(null) // where an edit drawer opened from, so closing returns there
  const [error, setError] = useState('')
  const [epoch, setEpoch] = useState(0) // bumped on env switch so every view refetches

  useEffect(() => {
    get<Meta>('/api/meta').then(setMeta, e => setError(e.message))
    get<EnvInfo>('/api/env').then(d => { setEnv(d.env); setEnvs(d.envs) }, () => {})
    const onHash = () => setViewState(v => { prev.current = v; return parseHash(location.hash) })
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  async function switchEnv(next: string) {
    try {
      const d = await send<EnvInfo>('PUT', '/api/env', { env: next })
      setEnv(d.env)
      if (view.kind === 'patient') setView({ kind: 'dashboard' }) // that patient id may not exist in the other DB
      setEpoch(n => n + 1)
      setError('')
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const current = view.kind === 'table' ? view.t : view.kind

  return (
    <div className="app">
      <header className="topbar">
        <strong>EHR Explorer</strong>
        {env && (
          <label className="db-switch">
            <span className="muted">Database</span>
            <select className={`badge ${envs.find(e => e.id === env)?.model ? 'model' : env}`} value={env}
              onChange={e => switchEnv(e.target.value)}>
              <optgroup label="Models">
                {envs.filter(e => e.model).map(e => <option key={e.id} value={e.id}>{e.label}</option>)}
              </optgroup>
              <optgroup label="Other">
                {envs.filter(e => !e.model).map(e => <option key={e.id} value={e.id}>{e.label}</option>)}
              </optgroup>
            </select>
          </label>
        )}
      </header>
      <nav className="sidebar" aria-label="Tables">
        <button className={current === 'dashboard' ? 'active' : ''} onClick={() => setView({ kind: 'dashboard' })}>Dashboard</button>
        <button className={current === 'compare' ? 'active' : ''} onClick={() => setView({ kind: 'compare' })}>Model comparison</button>
        {meta && Object.entries(meta.groups).map(([group, tables]) => (
          <div key={group}>
            <h3>{group}</h3>
            {tables.map(t => (
              <button key={t} className={current === t ? 'active' : ''} onClick={() => setView({ kind: 'table', t })}>{nice(t)}</button>
            ))}
          </div>
        ))}
      </nav>
      <main key={epoch}>
        {error && <p className="error" role="alert">{error}</p>}
        {meta && view.kind === 'table' && !meta.tables[view.t] && <p className="error" role="alert">Unknown table “{view.t}”</p>}
        {meta && view.kind === 'table' && meta.tables[view.t] && (
          <TableView key={view.t + (view.editPk ?? '')} t={view.t} meta={meta} editPk={view.editPk}
            onPatient={id => setView({ kind: 'patient', id })}
            onCloseEdit={() => setView(prev.current && prev.current.kind !== 'table' ? prev.current : { kind: 'table', t: view.t })} />
        )}
        {view.kind === 'dashboard' && <Dashboard />}
        {view.kind === 'compare' && <Compare />}
        {meta && view.kind === 'patient' && (
          <PatientDetail key={view.id} id={view.id} meta={meta} onBack={() => setView({ kind: 'table', t: 'patients' })} onEdit={(t, editPk) => setView({ kind: 'table', t, editPk })} />
        )}
      </main>
    </div>
  )
}
