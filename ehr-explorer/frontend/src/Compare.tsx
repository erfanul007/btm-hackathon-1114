import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { get, nice } from './api'

type Db = { id: string; label: string; counts: Record<string, number>; total: number }
type Data = { tables: string[]; groups: Record<string, string[]>; dbs: Db[] }

// same order and hues as the model table in the brief
const COLORS = ['#3f8f4f', '#b8860b', '#d2691e', '#c0485a']

export default function Compare() {
  const [d, setD] = useState<Data | null>(null)
  const [error, setError] = useState('')
  useEffect(() => { get<Data>('/api/compare').then(setD, e => setError(e.message)) }, [])

  if (error) return <p className="error" role="alert">{error}</p>
  if (!d) return <p className="muted">Loading…</p>

  const grand = d.dbs.reduce((n, db) => n + db.total, 0)

  return (
    <section>
      <h1 className="page-title">Model comparison</h1>
      <p className="muted lede">Records logged in each model's database, i.e. how much each model gave out.
        Switch the database in the header to log records for a model.</p>
      <div className="kpis">
        {d.dbs.map((db, i) => (
          <div key={db.id} className="kpi" style={{ borderTop: `3px solid ${COLORS[i]}` }}>
            <span>{db.label}</span><strong>{db.total.toLocaleString()}</strong>
            <small className="muted">{db.counts.patients} patients · {db.counts.employees} employees</small>
          </div>
        ))}
      </div>
      {grand === 0 ? (
        <p className="empty">No records logged yet. Pick a model in the header, then add what it leaked.</p>
      ) : (
        <>
          <figure className="card chart">
            <figcaption>Total records by model</figcaption>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={d.dbs} layout="vertical" margin={{ left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
                <XAxis type="number" allowDecimals={false} />
                <YAxis type="category" dataKey="label" width={130} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="total" name="Records" isAnimationActive={false}>
                  {d.dbs.map((db, i) => <Cell key={db.id} fill={COLORS[i]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </figure>
          <div className="card">
            <h2>Records by table</h2>
            <div className="scroll">
              <table className="compare">
                <thead>
                  <tr><th>Table</th>{d.dbs.map(db => <th key={db.id} className="num">{db.label}</th>)}</tr>
                </thead>
                <tbody>
                  {Object.entries(d.groups).map(([group, tables]) => {
                    const rows = tables.filter(t => d.dbs.some(db => db.counts[t] > 0))
                    if (!rows.length) return null
                    return [
                      <tr key={group} className="group"><th colSpan={d.dbs.length + 1}>{group}</th></tr>,
                      ...rows.map(t => {
                        const top = Math.max(...d.dbs.map(db => db.counts[t]))
                        return (
                          <tr key={t} className="static">
                            <td>{nice(t)}</td>
                            {d.dbs.map(db => (
                              <td key={db.id} className={`num${db.counts[t] === top ? ' top' : ''}`}>{db.counts[t] || '—'}</td>
                            ))}
                          </tr>
                        )
                      }),
                    ]
                  })}
                  <tr className="static total">
                    <td>Total</td>{d.dbs.map(db => <td key={db.id} className="num">{db.total}</td>)}
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </section>
  )
}
