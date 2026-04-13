import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getLeaderboard } from '../api'
import { ScoreBar, scoreColor } from './ScoreCard'

function Medal({ rank }) {
  if (rank === 1) return <span className="text-2xl">🥇</span>
  if (rank === 2) return <span className="text-2xl">🥈</span>
  if (rank === 3) return <span className="text-2xl">🥉</span>
  return <span className="text-sm text-gray-400 w-6 inline-block text-center font-medium">{rank}</span>
}

const PODIUM_BG = [
  'from-amber-50 to-yellow-100 border-amber-200',
  'from-gray-50 to-slate-100 border-slate-200',
  'from-orange-50 to-amber-50 border-orange-200',
]

export default function Leaderboard() {
  const navigate = useNavigate()
  const [orgs, setOrgs] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getLeaderboard()
      .then(r => setOrgs(r.data))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Ministry Leaderboard</h1>
        <p className="text-gray-500 mt-1 text-sm">
          Ranked by average data quality score across all published datasets
        </p>
      </div>

      {loading ? (
        <div className="py-24 text-center text-gray-400">
          <div className="w-6 h-6 border-2 border-brand-400 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          Loading…
        </div>
      ) : orgs.length === 0 ? (
        <div className="card py-12 text-center text-gray-400">
          No data yet. Run a bulk audit first.
        </div>
      ) : (
        <>
          {/* ── Top 3 Podium ─────────────────────────────────── */}
          <div className="grid sm:grid-cols-3 gap-4">
            {orgs.slice(0, 3).map((org, i) => (
              <div
                key={org.organization_id}
                className={`rounded-2xl border bg-gradient-to-b p-5 text-center ${PODIUM_BG[i]}`}
              >
                <div className="mb-2"><Medal rank={i + 1} /></div>
                <div className="font-semibold text-gray-800 text-sm leading-snug line-clamp-2 min-h-[2.5rem]">
                  {org.organization_name || org.organization_id}
                </div>
                <div className={`text-4xl font-black mt-3 ${scoreColor(org.avg_score)}`}>
                  {org.avg_score}
                </div>
                <div className="text-xs text-gray-400 mb-2">avg / 100</div>
                <div className="w-full h-1.5 bg-white/60 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${org.avg_score}%`,
                      backgroundColor: org.avg_score >= 80 ? '#10b981' : org.avg_score >= 65 ? '#f59e0b' : '#ef4444'
                    }}
                  />
                </div>
                <div className="text-xs text-gray-500 mt-2">
                  {org.dataset_count} dataset{org.dataset_count !== 1 ? 's' : ''}
                </div>
              </div>
            ))}
          </div>

          {/* ── Full Table ───────────────────────────────────── */}
          <div className="card p-0 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-100">
                  <th className="table-header w-10">#</th>
                  <th className="table-header">Organization</th>
                  <th className="table-header hidden sm:table-cell w-60">Avg Score</th>
                  <th className="table-header text-right w-24">Datasets</th>
                  <th className="table-header text-right hidden md:table-cell w-28">Min / Max</th>
                </tr>
              </thead>
              <tbody>
                {orgs.map((org, i) => (
                  <tr key={org.organization_id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3">
                      <Medal rank={i + 1} />
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-medium text-gray-800">
                        {org.organization_name || org.organization_id}
                      </span>
                    </td>
                    <td className="px-4 py-3 hidden sm:table-cell">
                      <ScoreBar score={org.avg_score} />
                    </td>
                    <td className="px-4 py-3 text-right text-gray-600 tabular-nums">
                      {org.dataset_count}
                    </td>
                    <td className="px-4 py-3 text-right text-gray-400 text-xs hidden md:table-cell tabular-nums">
                      {org.min_score} / {org.max_score}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* ── Needs Improvement callout ────────────────────── */}
          {orgs.length >= 5 && (
            <div className="rounded-xl bg-red-50 border border-red-200 px-5 py-4">
              <p className="text-sm font-semibold text-red-800 mb-1">⚠ Needs Improvement</p>
              <p className="text-sm text-red-700">
                The lowest-scoring organization is{' '}
                <strong>{orgs[orgs.length - 1].organization_name}</strong> with an
                average score of <strong>{orgs[orgs.length - 1].avg_score}/100</strong> across{' '}
                {orgs[orgs.length - 1].dataset_count} datasets.
              </p>
            </div>
          )}
        </>
      )}
    </div>
  )
}
