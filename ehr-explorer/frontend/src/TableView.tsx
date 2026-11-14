import { useEffect, useState } from 'react'
import { type Meta, type Row, type Rows, fmt, get, nice, show } from './api'
import RowForm from './RowForm'

const PAGE = 50

type Props = { t: string; meta: Meta; onPatient: (id: number) => void; editPk?: string; onCloseEdit: () => void }

export default function TableView({ t, meta, onPatient, editPk, onCloseEdit }: Props) {
  const { pk, columns } = meta.tables[t]
  const [page, setPage] = useState(1)
  const [q, setQ] = useState('')
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState('')
  const [dir, setDir] = useState<'asc' | 'desc'>('asc')
  const [data, setData] = useState<Rows | null>(null)
  const [error, setError] = useState('')
  const [editing, setEditing] = useState<Row | 'new' | null>(null)
  const [reload, setReload] = useState(0)

  useEffect(() => {
    const h = setTimeout(() => { setQuery(q); setPage(1) }, 300)
    return () => clearTimeout(h)
  }, [q])

  useEffect(() => {
    const params = new URLSearchParams({ page: String(page), q: query, sort, dir })
    get<Rows>(`/api/tables/${t}?${params}`).then(d => { setData(d); setError('') }, e => setError(e.message))
  }, [t, page, query, sort, dir, reload])

  useEffect(() => {
    if (editPk) get<Row>(`/api/tables/${t}/${encodeURIComponent(editPk)}`).then(setEditing, e => setError(e.message))
  }, [t, editPk])

  function sortBy(name: string) {
    if (sort === name) setDir(dir === 'asc' ? 'desc' : 'asc')
    else { setSort(name); setDir('asc') }
  }

  function open(row: Row) {
    if (t === 'patients') onPatient(Number(row[pk]))
    else setEditing(row)
  }

  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE)) : 1

  return (
    <section className="table-view">
      <header className="toolbar">
        <h1>{nice(t)}</h1>
        <input type="search" placeholder="Search…" value={q} onChange={e => setQ(e.target.value)} aria-label={`Search ${nice(t)}`} />
        <button onClick={() => setEditing('new')}>Add</button>
      </header>
      {error && <p className="error" role="alert">{error}</p>}
      {data && data.total === 0 ? (
        <p className="empty">No rows yet — <button className="link" onClick={() => setEditing('new')}>Add</button></p>
      ) : (
        <div className="scroll">
          <table>
            <thead>
              <tr>
                {columns.map(c => (
                  <th key={c.name} aria-sort={sort === c.name ? (dir === 'asc' ? 'ascending' : 'descending') : undefined}>
                    <button className="th" onClick={() => sortBy(c.name)}>
                      {nice(c.name, !!c.fk)}{sort === c.name ? (dir === 'asc' ? ' ▲' : ' ▼') : ''}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data?.rows.map(r => (
                <tr key={show(r[pk])} onClick={() => open(r)} tabIndex={0} onKeyDown={e => e.key === 'Enter' && open(r)}>
                  {columns.map(c => {
                    const text = c.fk ? show(r[`${c.name}_label`] ?? r[c.name]) : fmt(c, r[c.name])
                    return <td key={c.name} title={text}>{text}</td>
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {data && data.total > PAGE && (
        <nav className="pager" aria-label="Pages">
          <button disabled={page <= 1} onClick={() => setPage(page - 1)}>Prev</button>
          <span>Page {page} of {pages} · {data.total} rows</span>
          <button disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</button>
        </nav>
      )}
      {editing && (
        <RowForm
          key={editing === 'new' ? 'new' : show(editing[pk])}
          t={t}
          meta={meta}
          row={editing === 'new' ? null : editing}
          onDone={changed => { setEditing(null); if (changed) setReload(n => n + 1); if (editPk) onCloseEdit() }}
        />
      )}
    </section>
  )
}
