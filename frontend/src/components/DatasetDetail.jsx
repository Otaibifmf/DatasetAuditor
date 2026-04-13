import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { getDatasetDetail, getDatasetHistory, auditDataset, getPdfUrl } from '../api'
import { GradeBadge, ScoreNumber, ScoreRing, DimensionScores, AbandonmentBadge, TopicBadge, scoreColor } from './ScoreCard'

const CLUSTER_LABELS = {
  0: { label: 'High Quality',     cls: 'bg-emerald-100 text-emerald-800 border border-emerald-200' },
  1: { label: 'Acceptable',       cls: 'bg-amber-100   text-amber-800   border border-amber-200'   },
  2: { label: 'Poor Quality',     cls: 'bg-orange-100  text-orange-800  border border-orange-200'  },
  3: { label: 'Critical Issues',  cls: 'bg-red-100     text-red-800     border border-red-200'     },
}

function IssueList({ issues }) {
  if (!issues?.length) {
    return (
      <div className="flex items-center gap-2 text-sm text-emerald-600 font-medium">
        <span className="text-emerald-500">✓</span>
        No issues detected — dataset looks clean
      </div>
    )
  }
  return (
    <ul className="space-y-2">
      {issues.map((issue, i) => (
        <li key={i} className="flex gap-2.5 text-sm text-gray-700 bg-orange-50 rounded-lg px-3 py-2.5 border border-orange-100">
          <span className="text-orange-500 flex-shrink-0 mt-0.5">⚠</span>
          <span>{issue}</span>
        </li>
      ))}
    </ul>
  )
}

function DetailCard({ title, data }) {
  const entries = Object.entries(data).filter(([k, v]) => {
    if (k === 'issues' || k === 'column_missing') return false
    if (typeof v === 'object' && v !== null) return false
    return true
  })
  if (!entries.length) return null
  return (
    <div className="card-sm">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">{title}</h3>
      <dl className="space-y-1.5">
        {entries.map(([k, v]) => {
          const display = typeof v === 'boolean' ? (v ? 'Yes' : 'No')
            : typeof v === 'number' ? v.toFixed(2)
            : String(v || '—')
          return (
            <div key={k} className="flex justify-between items-baseline gap-2 text-xs">
              <dt className="text-gray-500 capitalize">{k.replace(/_/g, ' ')}</dt>
              <dd className="font-medium text-gray-800 text-right">{display}</dd>
            </div>
          )
        })}
      </dl>
    </div>
  )
}

export default function DatasetDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [detail, setDetail] = useState(null)
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [reauditing, setReauditing] = useState(false)
  const [error, setError] = useState(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [d, h] = await Promise.all([getDatasetDetail(id), getDatasetHistory(id)])
      setDetail(d.data)
      setHistory(h.data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load dataset')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [id])

  const handleReaudit = async () => {
    setReauditing(true)
    try {
      await auditDataset(id)
      await load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Re-audit failed')
    } finally {
      setReauditing(false)
    }
  }

  if (loading) {
    return (
      <div className="py-24 text-center text-gray-400">
        <div className="w-8 h-8 border-2 border-brand-400 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        Loading audit data…
      </div>
    )
  }

  if (error) {
    return (
      <div className="card text-center py-12">
        <p className="text-red-600 font-medium mb-4">{error}</p>
        <div className="flex gap-3 justify-center">
          <button onClick={handleReaudit} disabled={reauditing} className="btn-primary">
            {reauditing ? 'Auditing…' : 'Audit Now'}
          </button>
          <button onClick={() => navigate(-1)} className="btn-secondary">← Back</button>
        </div>
      </div>
    )
  }

  const cluster = CLUSTER_LABELS[detail.ml_quality_cluster]
  const auditedDate = detail.audited_at
    ? new Date(detail.audited_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
    : null

  return (
    <div className="space-y-6">
      {/* ── Back + Actions ──────────────────────────────────── */}
      <div className="flex items-center gap-3 flex-wrap">
        <button onClick={() => navigate(-1)} className="btn-secondary">← Back</button>
        <div className="ml-auto flex gap-2">
          <button onClick={handleReaudit} disabled={reauditing} className="btn-primary disabled:opacity-50">
            {reauditing
              ? <><span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" /> Re-auditing…</>
              : 'Re-audit Now'
            }
          </button>
          <a href={getPdfUrl(id)} target="_blank" rel="noopener noreferrer" className="btn-secondary">
            ↓ PDF Report
          </a>
        </div>
      </div>

      {/* ── Hero Card ───────────────────────────────────────── */}
      <div className="card">
        <div className="flex items-start gap-6 flex-wrap">
          {/* Score Ring */}
          <div className="relative flex-shrink-0 flex items-center justify-center" style={{ width: 100, height: 100 }}>
            <ScoreRing score={detail.overall_score} size={100} />
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className={`text-2xl font-black leading-none ${scoreColor(detail.overall_score)}`}>
                {detail.overall_score?.toFixed(0)}
              </span>
              <span className="text-xs text-gray-400 leading-none">/ 100</span>
            </div>
          </div>

          {/* Title + meta */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <GradeBadge grade={detail.grade} size="md" />
              {auditedDate && (
                <span className="text-xs text-gray-400">Audited {auditedDate}</span>
              )}
            </div>
            <h1 className="text-xl font-bold text-gray-900 leading-snug">
              {detail.title || detail.dataset_id}
            </h1>
            <p className="text-sm text-gray-500 mt-1">{detail.organization}</p>
            <div className="flex flex-wrap gap-2 mt-2.5">
              <TopicBadge topic={detail.ml_topic} />
              {cluster && (
                <span className={`badge text-xs font-medium ${cluster.cls}`}>
                  {cluster.label}
                </span>
              )}
              <AbandonmentBadge probability={detail.ml_abandoned_probability} />
            </div>
          </div>
        </div>
      </div>

      {/* ── Dimensions + Issues (2-col) ─────────────────────── */}
      <div className="grid md:grid-cols-2 gap-6">
        <div className="card">
          <h2 className="section-title">Quality Dimensions</h2>
          <DimensionScores scores={detail.dimension_scores} />
        </div>

        <div className="card">
          <h2 className="section-title flex items-center gap-2">
            Issues Found
            {detail.all_issues?.length > 0 && (
              <span className="bg-orange-100 text-orange-700 text-xs px-2 py-0.5 rounded-full font-normal">
                {detail.all_issues.length}
              </span>
            )}
          </h2>
          <IssueList issues={detail.all_issues} />
        </div>
      </div>

      {/* ── Score History ────────────────────────────────────── */}
      {history.length > 1 && (
        <div className="card">
          <h2 className="section-title">Score History</h2>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={history.map(h => ({
              date: h.audited_at?.slice(0, 10),
              score: h.overall_score,
            }))} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
              <Tooltip
                contentStyle={{ borderRadius: '8px', border: '1px solid #e5e7eb', fontSize: 12 }}
                formatter={v => [`${v.toFixed(1)}/100`, 'Score']}
              />
              <Line
                type="monotone"
                dataKey="score"
                stroke="#2563eb"
                strokeWidth={2.5}
                dot={{ r: 4, fill: '#2563eb', strokeWidth: 0 }}
                activeDot={{ r: 6 }}
                name="Overall Score"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* ── Drill-down Details ───────────────────────────────── */}
      {detail.details && (
        <div>
          <h2 className="section-title text-gray-700">Dimension Details</h2>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {Object.entries(detail.details).map(([key, val]) => {
              if (!val) return null
              const label = key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
              return <DetailCard key={key} title={label} data={val} />
            })}
          </div>
        </div>
      )}
    </div>
  )
}
