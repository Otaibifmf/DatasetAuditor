export const GRADE_STYLES = {
  A: { bg: 'bg-emerald-100', text: 'text-emerald-800', border: 'border-emerald-200', hex: '#10b981' },
  B: { bg: 'bg-lime-100',    text: 'text-lime-800',    border: 'border-lime-200',    hex: '#84cc16' },
  C: { bg: 'bg-amber-100',   text: 'text-amber-800',   border: 'border-amber-200',   hex: '#f59e0b' },
  D: { bg: 'bg-orange-100',  text: 'text-orange-800',  border: 'border-orange-200',  hex: '#f97316' },
  F: { bg: 'bg-red-100',     text: 'text-red-800',     border: 'border-red-200',     hex: '#ef4444' },
}

export const scoreColor = (score) => {
  if (score >= 80) return 'text-emerald-600'
  if (score >= 65) return 'text-amber-600'
  if (score >= 50) return 'text-orange-500'
  return 'text-red-600'
}

export const barColor = (score) => {
  if (score >= 80) return 'bg-emerald-500'
  if (score >= 65) return 'bg-amber-500'
  if (score >= 50) return 'bg-orange-500'
  return 'bg-red-500'
}

export function GradeBadge({ grade, size = 'md' }) {
  const s = GRADE_STYLES[grade] || { bg: 'bg-gray-100', text: 'text-gray-500', border: 'border-gray-200' }
  const sz = size === 'lg' ? 'text-3xl font-black w-14 h-14' : 'text-sm font-bold w-8 h-8'
  return (
    <span className={`inline-flex items-center justify-center rounded-xl border-2 ${s.bg} ${s.text} ${s.border} ${sz}`}>
      {grade || '?'}
    </span>
  )
}

export function ScoreNumber({ score, size = 'md' }) {
  const sz = size === 'lg' ? 'text-5xl font-black' : 'text-xl font-bold'
  return (
    <span className={`${sz} ${scoreColor(score)}`}>
      {typeof score === 'number' ? score.toFixed(1) : '—'}
    </span>
  )
}

/** Circular progress ring for the detail header */
export function ScoreRing({ score, size = 100 }) {
  const stroke = 8
  const r = (size - stroke) / 2
  const circ = 2 * Math.PI * r
  const offset = circ - (Math.max(0, Math.min(100, score || 0)) / 100) * circ
  const color = score >= 80 ? '#10b981' : score >= 65 ? '#f59e0b' : score >= 50 ? '#f97316' : '#ef4444'
  return (
    <svg width={size} height={size} className="-rotate-90">
      <circle cx={size / 2} cy={size / 2} r={r}
        fill="none" stroke="#f3f4f6" strokeWidth={stroke} />
      <circle cx={size / 2} cy={size / 2} r={r}
        fill="none" stroke={color} strokeWidth={stroke}
        strokeDasharray={circ} strokeDashoffset={offset}
        strokeLinecap="round"
        style={{ transition: 'stroke-dashoffset 0.6s ease' }} />
    </svg>
  )
}

export function ScoreBar({ score, label, className = '' }) {
  const pct = Math.max(0, Math.min(100, score || 0))
  return (
    <div className={`flex items-center gap-3 ${className}`}>
      {label && <span className="text-sm text-gray-600 w-36 flex-shrink-0">{label}</span>}
      <div className="flex-1 h-2.5 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColor(pct)}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`text-sm font-semibold w-10 text-right tabular-nums ${scoreColor(pct)}`}>
        {pct.toFixed(0)}
      </span>
    </div>
  )
}

const DIMENSION_LABELS = {
  completeness:     'Completeness',
  freshness:        'Freshness',
  consistency:      'Consistency',
  uniqueness:       'Uniqueness',
  validity:         'Validity',
  accessibility:    'Accessibility',
  metadata_quality: 'Metadata Quality',
}

export function DimensionScores({ scores = {} }) {
  return (
    <div className="space-y-3">
      {Object.entries(DIMENSION_LABELS).map(([key, label]) => (
        <ScoreBar key={key} score={scores[key]} label={label} />
      ))}
    </div>
  )
}

export function AbandonmentBadge({ probability }) {
  if (probability == null) return null
  const pct = Math.round(probability * 100)
  const { label, cls } = pct > 70
    ? { label: 'High Abandonment Risk', cls: 'bg-red-50 text-red-700 border border-red-200' }
    : pct > 40
    ? { label: 'Medium Abandonment Risk', cls: 'bg-amber-50 text-amber-700 border border-amber-200' }
    : { label: 'Low Abandonment Risk', cls: 'bg-emerald-50 text-emerald-700 border border-emerald-200' }
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium ${cls}`}>
      {label} · {pct}%
    </span>
  )
}

export function TopicBadge({ topic }) {
  if (!topic) return null
  return (
    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-brand-50 text-brand-700 border border-brand-100">
      {topic}
    </span>
  )
}
