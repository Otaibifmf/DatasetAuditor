import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { auditByUrl, auditSeed, errorMessage } from '../api'
import {
  GradeBadge, ScoreRing, ScoreBar, AbandonmentBadge, TopicBadge, scoreColor, GRADE_STYLES,
} from './ScoreCard'

const DIMENSION_LABELS = {
  completeness:     'Completeness',
  freshness:        'Freshness',
  consistency:      'Consistency',
  uniqueness:       'Uniqueness',
  validity:         'Validity',
  accessibility:    'Accessibility',
  metadata_quality: 'Metadata Quality',
}

function AuditResult({ report, onClear }) {
  const navigate = useNavigate()
  const [showAll, setShowAll] = useState(false)
  const issues = report.all_issues || []
  const visibleIssues = showAll ? issues : issues.slice(0, 3)
  const gs = GRADE_STYLES[report.grade] || {}

  return (
    <div className="card space-y-5">
      {/* ── Score hero ─────────────────────────────────────── */}
      <div className="flex items-center gap-5">
        <div className="relative flex-shrink-0 flex items-center justify-center" style={{ width: 88, height: 88 }}>
          <ScoreRing score={report.overall_score} size={88} />
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className={`text-xl font-black leading-none ${scoreColor(report.overall_score)}`}>
              {report.overall_score?.toFixed(0)}
            </span>
            <span className="text-xs text-gray-400 leading-none">/100</span>
          </div>
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <GradeBadge grade={report.grade} />
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-md border ${gs.bg} ${gs.text} ${gs.border}`}>
              {report.grade === 'A' ? 'Excellent' : report.grade === 'B' ? 'Good' : report.grade === 'C' ? 'Fair' : report.grade === 'D' ? 'Poor' : 'Critical'}
            </span>
          </div>
          <h2 className="font-bold text-gray-900 leading-snug line-clamp-2 text-base">
            {report.dataset_title || report.dataset_id}
          </h2>
          <p className="text-xs text-gray-500 mt-0.5">{report.organization}</p>
          <div className="flex flex-wrap gap-1.5 mt-2">
            <TopicBadge topic={report.ml_topic} />
            <AbandonmentBadge probability={report.ml_abandoned_probability} />
          </div>
        </div>
      </div>

      {/* ── Dimension scores ──────────────────────────────── */}
      <div>
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Quality Dimensions</p>
        <div className="space-y-2.5">
          {Object.entries(DIMENSION_LABELS).map(([key, label]) => (
            <ScoreBar key={key} score={report.dimension_scores?.[key]} label={label} />
          ))}
        </div>
      </div>

      {/* ── Issues ────────────────────────────────────────── */}
      {issues.length > 0 ? (
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
            Issues Found
            <span className="ml-1.5 bg-orange-100 text-orange-700 px-1.5 py-0.5 rounded-full font-normal normal-case">
              {issues.length}
            </span>
          </p>
          <ul className="space-y-1.5">
            {visibleIssues.map((issue, i) => (
              <li key={i} className="flex gap-2 text-xs text-gray-700 bg-orange-50 rounded-lg px-3 py-2 border border-orange-100">
                <span className="text-orange-400 flex-shrink-0">⚠</span>
                {issue}
              </li>
            ))}
          </ul>
          {issues.length > 3 && (
            <button
              onClick={() => setShowAll(s => !s)}
              className="mt-2 text-xs text-brand-600 hover:underline font-medium"
            >
              {showAll ? 'Show less' : `Show ${issues.length - 3} more issues`}
            </button>
          )}
        </div>
      ) : (
        <p className="text-sm text-emerald-600 font-medium flex items-center gap-1.5">
          <span>✓</span> No issues detected
        </p>
      )}

      {/* ── Actions ───────────────────────────────────────── */}
      <div className="flex gap-2 pt-1 border-t border-gray-100">
        <button
          onClick={() => navigate(`/dataset/${report.dataset_id}`)}
          className="btn-primary flex-1 justify-center"
        >
          View Full Report
        </button>
        <button onClick={onClear} className="btn-secondary">
          Audit Another
        </button>
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [auditId, setAuditId]           = useState('')
  const [auditLoading, setAuditLoading] = useState(false)
  const [result, setResult]             = useState(null)
  const [seedText, setSeedText]         = useState('')
  const [seedLoading, setSeedLoading]   = useState(false)
  const [showSeed, setShowSeed]         = useState(false)
  const [flash, setFlash]               = useState(null)
  const [running, setRunning]           = useState(false)
  const runTimer = useRef(null)

  const handleAuditOne = async () => {
    if (!auditId.trim()) return
    setAuditLoading(true)
    setFlash(null)
    try {
      const r = await auditByUrl(auditId.trim())
      setResult(r.data.report)
      setAuditId('')
    } catch (err) {
      setFlash({ type: 'error', msg: errorMessage(err, 'Audit failed') })
    } finally {
      setAuditLoading(false)
    }
  }

  const handleSeed = async () => {
    const urls = seedText.split('\n').map(s => s.trim()).filter(Boolean)
    if (!urls.length) return
    setSeedLoading(true)
    setFlash(null)
    try {
      const r = await auditSeed(urls)
      setFlash({ type: 'success', msg: `${r.data.message} — results will appear in History shortly.` })
      setSeedText('')
      setShowSeed(false)
      setRunning(true)
      clearTimeout(runTimer.current)
      runTimer.current = setTimeout(() => setRunning(false), 30000)
    } catch (err) {
      setFlash({ type: 'error', msg: errorMessage(err, 'Seed failed') })
    } finally {
      setSeedLoading(false)
    }
  }

  const urlCount = seedText.split('\n').filter(s => s.trim()).length

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* ── Header ───────────────────────────────────────────── */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Audit Datasets</h1>
        <p className="text-gray-500 mt-1 text-sm">
          Submit a dataset for quality analysis. Past results are in{' '}
          <a href="/history" className="text-brand-600 hover:underline font-medium">History</a>.
        </p>
      </div>

      {/* ── Background running banner ─────────────────────────── */}
      {running && (
        <div className="rounded-xl bg-blue-50 border border-blue-200 px-5 py-3 flex items-center gap-3">
          <span className="w-2.5 h-2.5 bg-blue-500 rounded-full animate-pulse flex-shrink-0" />
          <p className="text-sm text-blue-700 font-medium flex-1">
            Bulk audit running in background — check{' '}
            <a href="/history" className="underline hover:no-underline">History</a> for results.
          </p>
          <button
            onClick={() => { setRunning(false); clearTimeout(runTimer.current) }}
            className="text-blue-400 hover:text-blue-600 text-lg leading-none"
          >
            ×
          </button>
        </div>
      )}

      {/* ── Flash ────────────────────────────────────────────── */}
      {flash && (
        <div className={`rounded-xl px-4 py-3 text-sm font-medium flex items-center justify-between ${
          flash.type === 'success'
            ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
            : 'bg-red-50 text-red-800 border border-red-200'
        }`}>
          <span>{flash.msg}</span>
          <button className="ml-3 opacity-60 hover:opacity-100 text-lg leading-none" onClick={() => setFlash(null)}>×</button>
        </div>
      )}

      {/* ── Audit input OR result ─────────────────────────────── */}
      {result ? (
        <AuditResult report={result} onClear={() => setResult(null)} />
      ) : (
        <div className="card">
          <p className="text-sm font-semibold text-gray-800 mb-1">Audit by URL or ID</p>
          <p className="text-xs text-gray-400 mb-3">
            Paste a link like{' '}
            <code className="bg-gray-100 px-1.5 py-0.5 rounded text-gray-600">
              https://open.data.gov.sa/en/datasets/view/my-dataset
            </code>{' '}
            or a plain dataset ID
          </p>
          <div className="flex gap-2">
            <input
              className="input flex-1"
              placeholder="URL or dataset ID…"
              value={auditId}
              onChange={e => setAuditId(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleAuditOne()}
              disabled={auditLoading}
              autoFocus
            />
            <button
              onClick={handleAuditOne}
              disabled={auditLoading || !auditId.trim()}
              className="btn-primary disabled:opacity-50"
            >
              {auditLoading
                ? <><span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" /> Auditing…</>
                : 'Audit'
              }
            </button>
          </div>
        </div>
      )}

      {/* ── Seed / Paste URLs ────────────────────────────────── */}
      <div className="card">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-semibold text-gray-800">Paste multiple dataset URLs</p>
            <p className="text-xs text-gray-400 mt-0.5">One URL or ID per line — audits run in the background</p>
          </div>
          <button onClick={() => setShowSeed(s => !s)} className="btn-secondary py-1.5 text-xs">
            {showSeed ? 'Hide ▲' : 'Expand ▼'}
          </button>
        </div>

        {showSeed && (
          <div className="mt-4 space-y-2">
            <textarea
              className="input resize-y font-mono text-xs"
              rows={6}
              placeholder={"https://open.data.gov.sa/en/datasets/view/dataset-one\nhttps://open.data.gov.sa/en/datasets/view/dataset-two\ndataset-id-three"}
              value={seedText}
              onChange={e => setSeedText(e.target.value)}
            />
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-400">
                {urlCount} URL{urlCount !== 1 ? 's' : ''} entered
              </span>
              <button
                onClick={handleSeed}
                disabled={seedLoading || !seedText.trim()}
                className="btn-primary disabled:opacity-50"
              >
                {seedLoading ? 'Starting…' : `Audit ${urlCount > 1 ? `${urlCount} datasets` : 'All'}`}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
