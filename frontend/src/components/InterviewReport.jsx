import { useState } from 'react'
//  
/* ────────────────────────────────────────────────────────────────────────────
   InterviewReport — Complete performance report dashboard.
   ──────────────────────────────────────────────────────────────────────────── */

function Badge({ value }) {
  if (value >= 7) return <span className="score-badge badge-green">Strong</span>
  if (value >= 5) return <span className="score-badge badge-amber">Average</span>
  return <span className="score-badge badge-red">Needs Work</span>
}

function barColor(v) {
  if (v >= 7) return '#22C55E'
  if (v >= 5) return '#F59E0B'
  return '#EF4444'
}

function Expandable({ title, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className={`expandable ${open ? 'open' : ''}`}>
      <div className="expandable-header" onClick={() => setOpen(!open)}>
        <span>{title}</span>
        <span>{open ? '▾' : '▸'}</span>
      </div>
      {open && <div className="expandable-content">{children}</div>}
    </div>
  )
}

export default function InterviewReport({ report }) {
  if (!report) return <p style={{ color: '#7A8FA8' }}>No report data available.</p>

  const r = report

  return (
    <div className="report-dashboard">
      <div className="report-header">
        <h2>Interview Performance Report</h2>
        <p>Your detailed AI-powered analysis</p>
      </div>

      {/* ── Score Cards ─────────────────────────────────────────────────── */}
      <div className="score-cards">
        {[
          { label: 'Overall Rating', value: r.overall_rating },
          { label: 'Communication', value: r.communication_score },
          { label: 'Confidence', value: r.confidence_score },
        ].map((s, i) => (
          <div key={i} className="score-card">
            <div className="score-label">{s.label}</div>
            <div className="score-value" style={{ color: barColor(s.value) }}>
              {(s.value ?? 0).toFixed(1)}<span className="score-unit">/10</span>
            </div>
            <Badge value={s.value ?? 0} />
          </div>
        ))}
      </div>

      {/* ── Topic Ratings ───────────────────────────────────────────────── */}
      {r.topic && r.topic.length > 0 && (
        <div className="topic-ratings">
          <h3 className="section-heading">Topic Ratings</h3>
          {r.topic.map((t, i) => {
            const pct = Math.min(100, (t.rating ?? 0) * 10)
            const clr = barColor(t.rating ?? 0)
            const grade = t.rating >= 7 ? 'Strong' : t.rating >= 5 ? 'Average' : 'Needs Work'
            return (
              <div key={i} className="topic-card">
                <div className="topic-header">
                  <span className="topic-name">{t.topic_name}</span>
                  <span className="topic-score" style={{ color: clr }}>{(t.rating ?? 0).toFixed(1)} / 10</span>
                </div>
                <div className="topic-bar">
                  <div className="topic-bar-fill" style={{ width: `${pct}%`, background: clr }} />
                </div>
                <div className="topic-grade">{grade}</div>
              </div>
            )
          })}
        </div>
      )}

      {/* ── Score Summary Bar Chart ─────────────────────────────────────── */}
      <div className="chart-section">
        <h3 className="section-heading">Score Summary</h3>
        <div className="bar-chart">
          {[
            { label: 'Overall', value: r.overall_rating, color: '#3B6BE8' },
            { label: 'Communication', value: r.communication_score, color: '#F59E0B' },
            { label: 'Confidence', value: r.confidence_score, color: '#22C55E' },
          ].map((b, i) => (
            <div key={i} className="bar-row">
              <span className="bar-label">{b.label}</span>
              <div className="bar-track">
                <div className="bar-fill" style={{ width: `${(b.value ?? 0) * 10}%`, background: b.color }} />
              </div>
              <span className="bar-value">{(b.value ?? 0).toFixed(1)}</span>
            </div>
          ))}
        </div>
      </div>

      {/* ── Topic Analysis ──────────────────────────────────────────────── */}
      {r.topic && r.topic.length > 0 && (
        <div className="analysis-section">
          <h3 className="section-heading">Topic Analysis</h3>
          {r.topic.map((t, i) => {
            const icon = '●'
            return (
              <Expandable key={i} title={`${icon}  ${t.topic_name}  —  ${(t.rating ?? 0).toFixed(1)} / 10`}>
                <p><strong>Key Gap:</strong> {t.weakness}</p>
              </Expandable>
            )
          })}
        </div>
      )}

      {/* ── Strengths & Weaknesses ──────────────────────────────────────── */}
      <div className="strengths-weaknesses">
        <div className="sw-column">
          <h3 className="sw-title">Strengths</h3>
          {(r.overall_strength || []).map((s, i) => (
            <div key={i} className="strength-item">{s}</div>
          ))}
        </div>
        <div className="sw-column">
          <h3 className="sw-title">Areas to Improve</h3>
          {(r.overall_weakness || []).map((w, i) => (
            <div key={i} className="weakness-item">{w}</div>
          ))}
        </div>
      </div>

      {/* ── Recommendations ─────────────────────────────────────────────── */}
      {r.top_recommendation && r.top_recommendation.length > 0 && (
        <div className="recommendations">
          <h3 className="section-heading">Top Recommendations</h3>
          {r.top_recommendation.map((rec, i) => (
            <div key={i} className="rec-item"><strong>{i + 1}.</strong> {rec}</div>
          ))}
        </div>
      )}

      {/* ── Learning Roadmap ────────────────────────────────────────────── */}
      {r.road_map && r.road_map.length > 0 && (
        <div className="roadmap-section">
          <h3 className="section-heading">Personalised Learning Roadmap</h3>
          {r.road_map.map((rm, i) => (
            <Expandable key={i} title={`${rm.topic_name}  ·  ${rm.duration_it_takes}`}>
              <div className="roadmap-content">
                <div>
                  <strong>Concepts to Learn:</strong>
                  <ul className="concept-list">
                    {(rm.concepts_to_learn || []).map((c, j) => <li key={j}>{c}</li>)}
                  </ul>
                </div>
                <div>
                  <strong>Best Resources:</strong>
                  <ul className="resource-list">
                    {(rm.best_resource || []).map((res, j) => <li key={j}>{res}</li>)}
                  </ul>
                </div>
              </div>
            </Expandable>
          ))}
        </div>
      )}
    </div>
  )
}
