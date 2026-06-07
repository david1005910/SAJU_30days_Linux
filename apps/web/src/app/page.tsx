'use client'

import { useEffect, useState, useCallback } from 'react'

const API = 'http://localhost:8001'

type Episode = {
  id: string
  number: number
  title: string
  goal: string
  status: string
  totalCost: number
  updatedAt: string
}

type CurriculumDay = {
  day: number
  title: string
  goal: string
  keywords: string[]
}

const STATUS_COLOR: Record<string, string> = {
  QUEUED:    '#64748b',
  RUNNING:   '#f59e0b',
  REVIEW:    '#3b82f6',
  APPROVED:  '#10b981',
  PUBLISHED: '#6366f1',
  FAILED:    '#ef4444',
}

const STATUS_LABEL: Record<string, string> = {
  QUEUED:    '대기',
  RUNNING:   '처리중',
  REVIEW:    '검토대기',
  APPROVED:  '승인됨',
  PUBLISHED: '게시됨',
  FAILED:    '실패',
}

export default function Dashboard() {
  const [curriculum, setCurriculum] = useState<{ episodes: CurriculumDay[] } | null>(null)
  const [episodes, setEpisodes] = useState<Episode[]>([])
  const [apiOk, setApiOk] = useState<boolean | null>(null)
  const [creating, setCreating] = useState<number | null>(null)
  const [approving, setApproving] = useState<string | null>(null)

  const fetchEpisodes = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/episodes`)
      if (r.ok) setEpisodes((await r.json()).episodes)
    } catch {}
  }, [])

  useEffect(() => {
    Promise.all([
      fetch(`${API}/`).then(r => setApiOk(r.ok)).catch(() => setApiOk(false)),
      fetch(`${API}/api/curriculum`).then(r => r.json()).then(setCurriculum).catch(() => {}),
      fetchEpisodes(),
    ])
  }, [fetchEpisodes])

  // Poll every 3s while any episode is RUNNING or QUEUED
  useEffect(() => {
    const active = episodes.some(e => e.status === 'RUNNING' || e.status === 'QUEUED')
    if (!active) return
    const id = setInterval(fetchEpisodes, 3000)
    return () => clearInterval(id)
  }, [episodes, fetchEpisodes])

  async function createEpisode(day: number) {
    setCreating(day)
    try {
      const r = await fetch(`${API}/api/episodes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ curriculum_day: day }),
      })
      if (r.ok) await fetchEpisodes()
    } catch {}
    setCreating(null)
  }

  async function approveEpisode(id: string) {
    setApproving(id)
    try {
      const r = await fetch(`${API}/api/episodes/${id}/approve`, { method: 'POST' })
      if (r.ok) await fetchEpisodes()
    } catch {}
    setApproving(null)
  }

  // Map episode number → episode for quick lookup
  const epByNum = Object.fromEntries(episodes.map(e => [e.number, e]))

  const s: Record<string, React.CSSProperties> = {
    page:    { minHeight: '100vh', padding: '24px', maxWidth: '1280px', margin: '0 auto' },
    header:  { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '28px', paddingBottom: '16px', borderBottom: '1px solid #1e293b' },
    title:   { fontSize: '24px', fontWeight: 700, color: '#f1f5f9' },
    stats:   { display: 'flex', gap: '16px', marginBottom: '28px' },
    statBox: { flex: 1, background: '#1e293b', borderRadius: '8px', padding: '16px', border: '1px solid #334155', textAlign: 'center' as const },
    statNum: { fontSize: '28px', fontWeight: 700, color: '#f1f5f9' },
    statLabel: { fontSize: '12px', color: '#64748b', marginTop: '4px' },
    section: { marginBottom: '28px' },
    secTitle: { fontSize: '13px', fontWeight: 600, color: '#64748b', textTransform: 'uppercase' as const, letterSpacing: '0.08em', marginBottom: '12px' },
    epCard:  { background: '#1e293b', borderRadius: '8px', padding: '14px 16px', border: '1px solid #334155', display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' },
    grid:    { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '12px' },
    card:    { background: '#1e293b', borderRadius: '8px', padding: '16px', border: '1px solid #334155' },
  }

  const badge = (color: string, text: string) => (
    <span style={{ padding: '3px 10px', borderRadius: '4px', fontSize: '11px', fontWeight: 700,
                   background: color + '22', color, letterSpacing: '0.03em' }}>{text}</span>
  )

  const apiBadge = apiOk === null
    ? <span style={{ padding: '4px 12px', borderRadius: '9999px', fontSize: '12px', fontWeight: 600, background: '#334155', color: '#94a3b8' }}>연결 중...</span>
    : apiOk
    ? <span style={{ padding: '4px 12px', borderRadius: '9999px', fontSize: '12px', fontWeight: 700, background: '#064e3b', color: '#34d399' }}>API 정상</span>
    : <span style={{ padding: '4px 12px', borderRadius: '9999px', fontSize: '12px', fontWeight: 700, background: '#450a0a', color: '#f87171' }}>API 오프라인</span>

  const running = episodes.filter(e => e.status === 'RUNNING' || e.status === 'QUEUED')
  const review  = episodes.filter(e => e.status === 'REVIEW')
  const done    = episodes.filter(e => e.status === 'APPROVED' || e.status === 'PUBLISHED')
  const totalCost = episodes.reduce((s, e) => s + (e.totalCost || 0), 0)

  return (
    <div style={s.page}>
      {/* Header */}
      <div style={s.header}>
        <div>
          <h1 style={s.title}>사주공학 대시보드</h1>
          <p style={{ fontSize: '13px', color: '#64748b', marginTop: '4px' }}>YouTube 30일 커리큘럼 자동화 파이프라인</p>
        </div>
        {apiBadge}
      </div>

      {/* Stats */}
      <div style={s.stats}>
        {[
          { num: curriculum?.episodes?.length ?? 0, label: '총 커리큘럼' },
          { num: episodes.length, label: '생성된 에피소드' },
          { num: running.length, label: '처리중', color: '#f59e0b' },
          { num: review.length,  label: '승인 대기', color: '#3b82f6' },
          { num: `$${totalCost.toFixed(3)}`, label: '총 비용', color: '#34d399' },
          { num: '8단계', label: '파이프라인', color: '#f59e0b' },
        ].map((s2, i) => (
          <div key={i} style={s.statBox}>
            <div style={{ ...s.statNum, color: (s2 as any).color || '#f1f5f9' }}>{s2.num}</div>
            <div style={s.statLabel}>{s2.label}</div>
          </div>
        ))}
      </div>

      {/* Running episodes */}
      {running.length > 0 && (
        <div style={s.section}>
          <div style={s.secTitle}>파이프라인 처리중</div>
          {running.map(ep => (
            <div key={ep.id} style={s.epCard}>
              <div>
                <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
                               background: STATUS_COLOR[ep.status], marginRight: 8,
                               animation: 'pulse 1.5s infinite' }} />
                <strong style={{ fontSize: 14 }}>Day {ep.number}: {ep.title}</strong>
                <div style={{ fontSize: 12, color: '#64748b', marginTop: 3 }}>{ep.goal}</div>
              </div>
              {badge(STATUS_COLOR[ep.status], STATUS_LABEL[ep.status])}
            </div>
          ))}
        </div>
      )}

      {/* Review queue */}
      {review.length > 0 && (
        <div style={s.section}>
          <div style={s.secTitle}>승인 대기 ({review.length})</div>
          {review.map(ep => (
            <div key={ep.id} style={{ ...s.epCard, border: '1px solid #3b82f655' }}>
              <div>
                <strong style={{ fontSize: 14 }}>Day {ep.number}: {ep.title}</strong>
                <div style={{ fontSize: 12, color: '#64748b', marginTop: 3 }}>
                  비용: ${(ep.totalCost || 0).toFixed(3)} | {ep.goal}
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                {badge(STATUS_COLOR.REVIEW, STATUS_LABEL.REVIEW)}
                <button
                  onClick={() => approveEpisode(ep.id)}
                  disabled={approving === ep.id}
                  style={{ padding: '6px 16px', background: approving === ep.id ? '#334155' : '#10b981',
                           color: '#fff', border: 'none', borderRadius: 6,
                           cursor: approving === ep.id ? 'not-allowed' : 'pointer',
                           fontWeight: 700, fontSize: 13 }}
                >
                  {approving === ep.id ? '승인중...' : '✓ 승인'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Completed */}
      {done.length > 0 && (
        <div style={s.section}>
          <div style={s.secTitle}>완료됨</div>
          {done.map(ep => (
            <div key={ep.id} style={s.epCard}>
              <div>
                <strong style={{ fontSize: 14 }}>Day {ep.number}: {ep.title}</strong>
                <div style={{ fontSize: 12, color: '#64748b', marginTop: 3 }}>
                  비용: ${(ep.totalCost || 0).toFixed(3)}
                </div>
              </div>
              {badge(STATUS_COLOR[ep.status], STATUS_LABEL[ep.status])}
            </div>
          ))}
        </div>
      )}

      {/* Curriculum grid */}
      <div style={s.section}>
        <div style={s.secTitle}>30일 커리큘럼</div>
        {!curriculum ? (
          <p style={{ color: '#64748b' }}>로딩 중...</p>
        ) : (
          <div style={s.grid}>
            {curriculum.episodes.map(ep => {
              const existing = epByNum[ep.day]
              const isRunning = existing?.status === 'RUNNING' || existing?.status === 'QUEUED'
              return (
                <div key={ep.day} style={{ ...s.card, border: existing ? `1px solid ${STATUS_COLOR[existing.status]}44` : '1px solid #334155' }}>
                  <div style={{ fontSize: 11, color: '#64748b', marginBottom: 2 }}>Day {ep.day}</div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: '#f1f5f9', marginBottom: 4 }}>{ep.title}</div>
                  <div style={{ fontSize: 12, color: '#64748b', marginBottom: 10 }}>{ep.goal}</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: 4, marginBottom: 12 }}>
                    {ep.keywords?.slice(0, 4).map(k => (
                      <span key={k} style={{ background: '#0f172a', padding: '2px 8px', borderRadius: 4, fontSize: 11, color: '#94a3b8' }}>{k}</span>
                    ))}
                  </div>
                  {existing && (
                    <div style={{ marginBottom: 8 }}>
                      {badge(STATUS_COLOR[existing.status], STATUS_LABEL[existing.status])}
                    </div>
                  )}
                  <button
                    onClick={() => createEpisode(ep.day)}
                    disabled={creating === ep.day || isRunning}
                    style={{ width: '100%', padding: '8px', borderRadius: 6, border: 'none',
                             cursor: (creating === ep.day || isRunning) ? 'not-allowed' : 'pointer',
                             fontSize: 13, fontWeight: 600,
                             background: isRunning ? '#1e293b' : creating === ep.day ? '#334155' : '#3b82f6',
                             color: (creating === ep.day || isRunning) ? '#475569' : '#fff' }}
                  >
                    {creating === ep.day ? '생성 중...' : isRunning ? '처리중...' : existing ? '재생성' : '에피소드 생성'}
                  </button>
                </div>
              )
            })}
          </div>
        )}
      </div>

      <div style={{ textAlign: 'center', padding: '24px', color: '#1e293b', fontSize: 12 }}>
        FastAPI: localhost:8001 | PostgreSQL: localhost:5432 | Redis: localhost:6379
      </div>
    </div>
  )
}
