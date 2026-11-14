import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { get } from './api'

type NameN = { name: string; n: number }
type Dash = {
  kpis: Record<string, number>
  enc_by_month: Record<string, string | number>[]
  enc_by_dept: NameN[]; enc_by_type: NameN[]; patients_by_payer: NameN[]; plan_type_mix: NameN[]
  claims_by_status: NameN[]; charge_vs_paid: { name: string; charged: number; paid: number }[]; top_problems: NameN[]
}

const CLASSES: [string, string, string][] = [
  ['AMB', 'Ambulatory', '#2f6fde'], ['EMER', 'Emergency', '#d4542b'], ['IMP', 'Inpatient', '#7a4fd1'], ['VR', 'Virtual', '#1f8a4c'],
]
const PALETTE = ['#2f6fde', '#1f8a4c', '#d4542b', '#7a4fd1', '#c99a06', '#0f8b8d', '#b4447a', '#5b6475', '#8a6d3b']
const KPI_LABELS: Record<string, string> = {
  patients: 'Patients', encounters: 'Encounters', providers: 'Providers', employees: 'Employees', facilities: 'Facilities', open_claims: 'Open claims',
}

export default function Dashboard() {
  const [d, setD] = useState<Dash | null>(null)
  const [error, setError] = useState('')
  useEffect(() => { get<Dash>('/api/dashboard').then(setD, e => setError(e.message)) }, [])

  if (error) return <p className="error" role="alert">{error}</p>
  if (!d) return <p className="muted">Loading…</p>

  return (
    <section>
      <h1 className="page-title">Dashboard</h1>
      <div className="kpis">
        {Object.entries(KPI_LABELS).map(([k, label]) => (
          <div key={k} className="kpi"><span>{label}</span><strong>{d.kpis[k].toLocaleString()}</strong></div>
        ))}
      </div>
      <div className="charts">
        <Chart title="Encounters per month" empty={!d.enc_by_month.length} wide>
          <LineChart data={d.enc_by_month}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
            <XAxis dataKey="month" /><YAxis allowDecimals={false} /><Tooltip /><Legend />
            {CLASSES.map(([key, name, color]) => <Line key={key} isAnimationActive={false} dataKey={key} name={name} stroke={color} dot={false} strokeWidth={2} />)}
          </LineChart>
        </Chart>
        <BarCard title="Encounters by department" data={d.enc_by_dept} />
        <BarCard title="Encounters by type (top 10)" data={d.enc_by_type} />
        <BarCard title="Patients by payer (primary coverage)" data={d.patients_by_payer} />
        <Chart title="Plan type mix" empty={!d.plan_type_mix.length}>
          <PieChart>
            <Pie isAnimationActive={false} data={d.plan_type_mix} dataKey="n" nameKey="name" innerRadius="50%" outerRadius="80%">
              {d.plan_type_mix.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
            </Pie>
            <Tooltip /><Legend />
          </PieChart>
        </Chart>
        <BarCard title="Claims by status" data={d.claims_by_status} />
        <Chart title="Charged vs paid by payer" empty={!d.charge_vs_paid.length}>
          <BarChart data={d.charge_vs_paid}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
            <XAxis dataKey="name" interval={0} tick={{ fontSize: 10 }} /><YAxis /><Tooltip /><Legend />
            <Bar isAnimationActive={false} dataKey="charged" name="Charged" fill="#2f6fde" /><Bar isAnimationActive={false} dataKey="paid" name="Paid" fill="#1f8a4c" />
          </BarChart>
        </Chart>
        <BarCard title="Top problems (ICD-10)" data={d.top_problems} wide />
      </div>
    </section>
  )
}

function Chart({ title, empty, wide, children }: { title: string; empty: boolean; wide?: boolean; children: React.ReactElement }) {
  return (
    <figure className={`card chart${wide ? ' wide' : ''}`}>
      <figcaption>{title}</figcaption>
      {empty ? <p className="muted center">No data yet</p> : <ResponsiveContainer width="100%" height={260}>{children}</ResponsiveContainer>}
    </figure>
  )
}

function BarCard({ title, data, wide }: { title: string; data: NameN[]; wide?: boolean }) {
  return (
    <Chart title={title} empty={!data.length} wide={wide}>
      <BarChart data={data} layout="vertical" margin={{ left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
        <XAxis type="number" allowDecimals={false} />
        <YAxis type="category" dataKey="name" width={wide ? 280 : 170} tick={{ fontSize: 11 }} />
        <Tooltip /><Bar isAnimationActive={false} dataKey="n" name="Count" fill="#2f6fde" />
      </BarChart>
    </Chart>
  )
}
