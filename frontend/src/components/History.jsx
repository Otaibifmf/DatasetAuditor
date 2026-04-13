import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { getDatasets, getStats, getTrends } from '../api'
import { GradeBadge, ScoreNumber, GRADE_STYLES } from './ScoreCard'

const GRADE_ORDER = ['A', 'B', 'C', 'D', 'F']

const GRADE_COLORS = {
  A: '#10b981', B: '#84cc16', C: '#f59e0b', D: '#f97316', F: '#ef4444',
}

const SCORE_BANDS = [
  { label: 'Excellent', range: '80–100', min: 80,  max: 100, color: '#10b981' },
  { label: 'Good',      range: '65–79',  min: 65,  max: 79,  color: '#84cc16' },
  { label: 'Fair',      range: '50–64',  min: 50,  max: 64,  color: '#f59e0b' },
  { label: 'Poor',      range: '35–49',  min: 35,  max: 49,  color: '#f97316' },
  { label: 'Critical',  range: '0–34',   min: 0,   max: 34,  color: '#ef4444' },
]

function relativeTime(isoString) {
  if (!isoString) return '—'
  const diff = Date.now() - new Date(isoString).getTime()
  const mins  = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days  = Math.floor(diff / 86400000)
  if (mins  < 2)   return 'just now'
  if (mins  < 60)  return `${mins}m ago`
  if (hours < 24)  return `${hours}h ago`
  if (days  < 7)   return `${days}d ago`
  return new Date(isoString).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

function GradeDistributionBar({ distribution, total }) {
  return (
    <div className="space-y-3">
      {GRADE_ORDER.map((grade) => {
        const count = distribution[grade] || 0
        const pct = total > 0 ? (count / total) * 100 : 0
        const s = GRADE_STYLES[grade]
        return (
          <div key={grade} className="flex items-center gap-3">
            <span className={`w-7 h-7 inline-flex items-center justify-center rounded-lg text-xs font-black border ${s.bg} ${s.text} ${s.border} flex-shrink-0`}>
              {grade}
            </span>
            <div className="flex-1 h-4 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-700"
                style={{ width: `${pct}%`, backgroundColor: GRADE_COLORS[grade] }}
              />
            </div>
            <span className="text-sm font-semibold tabular-nums text-gray-700 w-8 text-right">{count}</span>
            <span className="text-xs text-gray-400 w-10 text-right tabular-nums">
              {pct.toFixed(1)}%
            </span>
          </div>
        )
      })}
    </div>
  )
}

function ScoreBandBar({ datasets }) {
  if (!datasets.length) return (
    <p className="text-gray-400 text-sm text-center py-4">No data yet.</p>
  )
  const counts = SCORE_BANDS.map(b => ({
    ...b,
    count: datasets.filter(d => d.overall_score >= b.min && d.overall_score <= b.max).length,
  }))
  const total = counts.reduce((s, b) => s + b.count, 0) || 1
  return (
    <div className="space-y-3">
      {counts.map((b) => (
        <div key={b.label} className="flex items-center gap-3">
          <div className="w-20 flex-shrink-0">
            <span className="text-sm font-medium text-gray-700">{b.label}</span>
            <span className="block text-xs text-gray-400">{b.range}</span>
          </div>
          <div className="flex-1 h-4 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-700"
              style={{ width: `${(b.count / total) * 100}%`, backgroundColor: b.color }}
            />
          </div>
          <span className="text-sm font-semibold tabular-nums text-gray-700 w-8 text-right">{b.count}</span>
          <span className="text-xs text-gray-400 w-10 text-right tabular-nums">
            {((b.count / total) * 100).toFixed(1)}%
          </span>
        </div>
      ))}
    </div>
  )
}

const PAGE_SIZE = 20
const GRADE_FILTERS = ['', 'A', 'B', 'C', 'D', 'F']

export default function History() {
  const navigate = useNavigate()
  const [stats, setStats] = useState(null)
  const [trends, setTrends] = useState([])
  const [datasets, setDatasets] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [gradeFilter, setGradeFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [tableLoading, setTableLoading] = useState(false)

  // Load stats + trends once
  useEffect(() => {
    Promise.all([getStats(), getTrends(365)]).then(([s, t]) => {
      setStats(s.data)
      setTrends(t.data)
      setLoading(false)
    })
  }, [])

  // Load paginated recent audits
  useEffect(() => {
    setTableLoading(true)
    getDatasets({ sort: 'date_desc', page, page_size: PAGE_SIZE, grade: gradeFilter || undefined })
      .then(r => {
        setDatasets(r.data.datasets)
        setTotal(r.data.total)
      })
      .finally(() => setTableLoading(false))
  }, [page, gradeFilter])

  const gradeTotal = stats
    ? GRADE_ORDER.reduce((s, g) => s + (stats.grade_distribution[g] || 0), 0)
    : 0

  const pageCount = Math.ceil(total / PAGE_SIZE)

  return (
    <div className="space-y-8">
      {/* ── Header ───────────────────────────────────────────── */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Audit History</h1>
        <p className="text-gray-500 mt-1">
          Complete record of all quality audits — grade distributions, score bands, and recent activity
        </p>
      </div>

      {loading ? (
        <div className="py-24 text-center text-gray-400">Loading history…</div>
      ) : (
        <>
          {/* ── Summary Stats ────────────────────────────────── */}
          {stats && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {[
                { label: 'Total Audited',    value: stats.total_datasets,      color: 'text-brand-700' },
                { label: 'Avg Quality Score', value: `${stats.avg_score}/100`, color: 'text-brand-700' },
                { label: 'Organizations',    value: stats.total_organizations, color: 'text-brand-700' },
                {
                  label: 'Top Grade (A)',
                  value: stats.grade_distribution['A'] ?? 0,
                  color: 'text-emerald-600',
                  sub: `of ${gradeTotal} total`,
                },
              ].map(({ label, value, color, sub }) => (
                <div key={label} className="card text-center">
                  <div className={`text-3xl font-black ${color}`}>{value}</div>
                  <div className="text-sm font-medium text-gray-600 mt-1">{label}</div>
                  {sub && <div className="text-xs text-gray-400 mt-0.5">{sub}</div>}
                </div>
              ))}
            </div>
          )}

          {/* ── Grade Distribution + Score Bands ─────────────── */}
          <div className="grid md:grid-cols-2 gap-6">
            <div className="card">
              <h2 className="section-title">Grade Distribution</h2>
              {stats && gradeTotal > 0
                ? <GradeDistributionBar distribution={stats.grade_distribution} total={gradeTotal} />
                : <p className="text-gray-400 text-sm text-center py-4">No data yet.</p>
              }
            </div>
            <div className="card">
              <h2 className="section-title">Score Band Distribution</h2>
              <ScoreBandBar datasets={datasets} />
            </div>
          </div>

          {/* ── Audit Activity Chart ──────────────────────────── */}
          {trends.length >= 2 && (
            <div className="card">
              <h2 className="section-title">Audit Activity Over Time</h2>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={trends} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
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
            </div>
          )}

          {/* ── Recent Audits Table ───────────────────────────── */}
          <div className="card p-0 overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
              <h2 className="font-semibold text-gray-800">
                Recent Audits
                {total > 0 && (
                  <span className="ml-2 text-xs font-normal text-gray-400">{total} datasets</span>
                )}
              </h2>
              <select
                value={gradeFilter}
                onChange={e => { setGradeFilter(e.target.value); setPage(1) }}
                className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                {GRADE_FILTERS.map(g => (
                  <option key={g} value={g}>{g || 'All Grades'}</option>
                ))}
              </select>
            </div>

            {tableLoading ? (
              <div className="py-12 text-center text-gray-400">Loading…</div>
            ) : datasets.length === 0 ? (
              <div className="py-12 text-center text-gray-400">
                No audit records found. Run an audit to get started.
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50">
                    <th className="table-header">Dataset</th>
                    <th className="table-header hidden md:table-cell">Organization</th>
                    <th className="table-header hidden lg:table-cell">Topic</th>
                    <th className="table-header text-center">Grade</th>
                    <th className="table-header text-right">Score</th>
                    <th className="table-header text-right hidden sm:table-cell">Audited</th>
                  </tr>
                </thead>
                <tbody>
                  {datasets.map((ds) => (
                    <tr
                      key={ds.dataset_id}
                      className="table-row"
                      onClick={() => navigate(`/dataset/${ds.dataset_id}`)}
                    >
                      <td className="px-4 py-3">
                        <div className="font-medium text-gray-900 line-clamp-1">
                          {ds.title || ds.dataset_id}
                        </div>
                        <div className="text-xs text-gray-400 mt-0.5 font-mono truncate">
                          {ds.dataset_id}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-gray-500 hidden md:table-cell">
                        <span className="line-clamp-1 text-xs">{ds.organization || '—'}</span>
                      </td>
                      <td className="px-4 py-3 hidden lg:table-cell">
                        {ds.ml_topic && (
                          <span className="inline-block bg-brand-50 text-brand-700 px-2 py-0.5 rounded-full text-xs border border-brand-100">
                            {ds.ml_topic}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <GradeBadge grade={ds.grade} />
                      </td>
                      <td className="px-4 py-3 text-right">
                        <ScoreNumber score={ds.overall_score} />
                      </td>
                      <td className="px-4 py-3 text-right text-xs text-gray-400 hidden sm:table-cell whitespace-nowrap">
                        {relativeTime(ds.audited_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {/* Pagination */}
            {pageCount > 1 && (
              <div className="flex items-center justify-between px-6 py-4 border-t border-gray-100">
                <span className="text-xs text-gray-500">
                  Page {page} of {pageCount}
                </span>
                <div className="flex gap-2">
                  <button
                    disabled={page === 1}
                    onClick={() => setPage(p => p - 1)}
                    className="btn-secondary disabled:opacity-40 text-xs py-1.5 px-3"
                  >
                    ← Prev
                  </button>
                  <button
                    disabled={page === pageCount}
                    onClick={() => setPage(p => p + 1)}
                    className="btn-secondary disabled:opacity-40 text-xs py-1.5 px-3"
                  >
                    Next →
                  </button>
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
