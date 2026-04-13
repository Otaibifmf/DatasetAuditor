import { useState, useEffect } from 'react'
import {
  AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar,
} from 'recharts'
import { getTrends, getStats } from '../api'

const WINDOWS = [
  { value: 30,  label: '30d' },
  { value: 90,  label: '90d' },
  { value: 180, label: '6mo' },
  { value: 365, label: '1yr' },
]

const GRADE_COLORS = { A: '#10b981', B: '#84cc16', C: '#f59e0b', D: '#f97316', F: '#ef4444' }

function Section({ title, children }) {
  return (
    <div className="card">
      <h2 className="section-title">{title}</h2>
      {children}
    </div>
  )
}

const EMPTY = (msg) => (
  <p className="text-gray-400 text-sm text-center py-10">{msg}</p>
)

export default function TrendView() {
  const [days, setDays] = useState(90)
  const [trends, setTrends] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    Promise.all([getTrends(days), getStats()])
      .then(([t, s]) => {
        setTrends(t.data)
        setStats(s.data)
      })
      .finally(() => setLoading(false))
  }, [days])

  const gradeData = stats
    ? Object.entries(stats.grade_distribution || {}).sort().map(([grade, count]) => ({ grade, count }))
    : []

  return (
    <div className="space-y-6">
      {/* ── Header ───────────────────────────────────────────── */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Quality Trends</h1>
          <p className="text-gray-500 mt-1 text-sm">Platform-wide data quality over time</p>
        </div>
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
          {WINDOWS.map(w => (
            <button
              key={w.value}
              onClick={() => setDays(w.value)}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
                days === w.value
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {w.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="py-24 text-center text-gray-400">
          <div className="w-6 h-6 border-2 border-brand-400 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          Loading…
        </div>
      ) : (
        <>
          {/* ── Summary Stats ────────────────────────────────── */}
          {stats && (
            <div className="grid sm:grid-cols-3 gap-4">
              {[
                { label: 'Total Datasets', value: stats.total_datasets },
                { label: 'Platform Avg Score', value: `${stats.avg_score}/100` },
                { label: 'Organizations', value: stats.total_organizations },
              ].map(({ label, value }) => (
                <div key={label} className="card text-center">
                  <div className="text-3xl font-black text-brand-700">{value}</div>
                  <div className="text-sm text-gray-500 mt-1">{label}</div>
                </div>
              ))}
            </div>
          )}

          {/* ── Average Score Over Time ──────────────────────── */}
          <Section title="Average Quality Score Over Time">
            {trends.length < 2 ? EMPTY('Not enough data yet — run more audits over time to see trends.') : (
              <ResponsiveContainer width="100%" height={280}>
                <AreaChart data={trends} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="scoreGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#3b82f6" stopOpacity={0.15} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="day" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                  <Tooltip
                    contentStyle={{ borderRadius: '8px', border: '1px solid #e5e7eb', fontSize: 12 }}
                    formatter={v => [`${v.toFixed(1)}/100`, 'Avg Score']}
                    labelFormatter={l => `Date: ${l}`}
                  />
                  <Area type="monotone" dataKey="avg_score" stroke="#3b82f6" strokeWidth={2.5}
                    fill="url(#scoreGrad)" name="Avg Score" dot={false} activeDot={{ r: 5 }} />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </Section>

          {/* ── Audits Per Day ──────────────────────────────── */}
          <Section title="Audits Per Day">
            {trends.length < 2 ? EMPTY('Run audits to see activity over time.') : (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={trends} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="day" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                  <Tooltip
                    contentStyle={{ borderRadius: '8px', border: '1px solid #e5e7eb', fontSize: 12 }}
                    cursor={{ fill: '#eff6ff' }}
                  />
                  <Bar dataKey="audits" fill="#6366f1" radius={[4, 4, 0, 0]} name="Audits" maxBarSize={32} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </Section>

          {/* ── Grade Distribution ──────────────────────────── */}
          {gradeData.length > 0 && (
            <Section title="Grade Distribution (All Time)">
              <div className="flex items-end gap-3 h-44">
                {gradeData.map(({ grade, count }) => {
                  const maxCount = Math.max(...gradeData.map(g => g.count))
                  const heightPct = maxCount ? (count / maxCount) * 100 : 0
                  return (
                    <div key={grade} className="flex-1 flex flex-col items-center gap-1">
                      <span className="text-sm font-semibold text-gray-600 tabular-nums">{count}</span>
                      <div
                        className="w-full rounded-t-lg transition-all duration-700"
                        style={{
                          height: `${Math.max(4, heightPct)}%`,
                          backgroundColor: GRADE_COLORS[grade] || '#94a3b8',
                        }}
                      />
                      <span className="text-sm font-black" style={{ color: GRADE_COLORS[grade] }}>
                        {grade}
                      </span>
                    </div>
                  )
                })}
              </div>
            </Section>
          )}
        </>
      )}
    </div>
  )
}
