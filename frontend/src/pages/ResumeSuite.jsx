import { useState } from 'react'
import { buildResume, modifyResume, rateResume, extractText } from '../api'
import ResumeForm from '../components/ResumeForm'
import Loading from '../components/Loading'

/* ────────────────────────────────────────────────────────────────────────────
   Helpers
   ──────────────────────────────────────────────────────────────────────────── */
const downloadPdf = (blob, filename) => {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

/* ════════════════════════════════════════════════════════════════════════════
   ResumeSuite — 3 tabs: Builder | Modifier | Rater
   ════════════════════════════════════════════════════════════════════════════ */
export default function ResumeSuite() {
  const [activeTab, setActiveTab] = useState('builder')

  // ── Builder ─────────────────────────────────────────────────────────────
  const [builderData, setBuilderData] = useState({})
  const [builderLoading, setBuilderLoading] = useState(false)
  const [builderSuccess, setBuilderSuccess] = useState('')
  const [builderError, setBuilderError] = useState('')

  // ── Modifier ────────────────────────────────────────────────────────────
  const [modInputMode, setModInputMode] = useState('upload')
  const [modFile, setModFile] = useState(null)
  const [modExtractedText, setModExtractedText] = useState('')
  const [modFormData, setModFormData] = useState({})
  const [modJD, setModJD] = useState('')
  const [modTemp, setModTemp] = useState(0.5)
  const [modLoading, setModLoading] = useState(false)
  const [modExtractLoading, setModExtractLoading] = useState(false)
  const [modSuccess, setModSuccess] = useState('')
  const [modError, setModError] = useState('')

  // ── Rater ───────────────────────────────────────────────────────────────
  const [raterInputMode, setRaterInputMode] = useState('paste')
  const [raterText, setRaterText] = useState('')
  const [raterFile, setRaterFile] = useState(null)
  const [raterJD, setRaterJD] = useState('')
  const [raterResults, setRaterResults] = useState(null)
  const [raterLoading, setRaterLoading] = useState(false)
  const [raterExtractLoading, setRaterExtractLoading] = useState(false)
  const [raterError, setRaterError] = useState('')

  // ═══════════════════════════════════════════════════════════════════════
  // HANDLERS
  // ═══════════════════════════════════════════════════════════════════════

  /* ── Builder ───────────────────────────────────────────────────────── */
  const handleBuild = async () => {
    setBuilderError(''); setBuilderSuccess('')
    if (!builderData.name || !builderData.email) {
      setBuilderError('Please fill in at least Name and Email.'); return
    }
    setBuilderLoading(true)
    try {
      const fd = new FormData()
      fd.append('raw_data', JSON.stringify(builderData))
      const res = await buildResume(fd)
      const blob = new Blob([res.data], { type: 'application/pdf' })
      const name = (builderData.name || 'Resume').replace(/\s+/g, '_')
      downloadPdf(blob, `${name}_Resume.pdf`)
      setBuilderSuccess('✅ Resume generated and downloaded!')
    } catch (err) {
      setBuilderError(err.response?.data?.detail || 'Resume generation failed.')
    } finally { setBuilderLoading(false) }
  }

  /* ── Modifier ──────────────────────────────────────────────────────── */
  const handleModExtract = async () => {
    if (!modFile) return setModError('Please upload a file first.')
    setModError(''); setModExtractLoading(true)
    try {
      const fd = new FormData(); fd.append('file', modFile)
      const { data } = await extractText(fd)
      setModExtractedText(data.text || '')
    } catch (err) {
      setModError('Text extraction failed.')
    } finally { setModExtractLoading(false) }
  }

  const handleModify = async () => {
    if (!modJD || modJD.length < 50) { setModError('Job description must be at least 50 characters.'); return }
    setModError(''); setModSuccess(''); setModLoading(true)

    try {
      const fd = new FormData()
      fd.append('job_description', modJD)
      fd.append('temperature', String(modTemp))

      if (modInputMode === 'upload') {
        fd.append('input_mode', 'upload')
        if (modExtractedText) {
          fd.append('resume_text', modExtractedText)
        } else if (modFile) {
          fd.append('file', modFile)
        } else { setModError('Upload a file or extract text first.'); setModLoading(false); return }
      } else {
        fd.append('input_mode', 'form')
        fd.append('raw_data', JSON.stringify(modFormData))
      }

      const res = await modifyResume(fd)
      const blob = new Blob([res.data], { type: 'application/pdf' })
      downloadPdf(blob, 'Modified_Resume.pdf')
      setModSuccess('✅ Modified resume downloaded!')
    } catch (err) {
      setModError(err.response?.data?.detail || 'Resume modification failed.')
    } finally { setModLoading(false) }
  }

  /* ── Rater ─────────────────────────────────────────────────────────── */
  const handleRaterExtract = async () => {
    if (!raterFile) return setRaterError('Upload a file first.')
    setRaterError(''); setRaterExtractLoading(true)
    try {
      const fd = new FormData(); fd.append('file', raterFile)
      const { data } = await extractText(fd)
      setRaterText(data.text || '')
      setRaterInputMode('paste') // show the text
    } catch (err) {
      setRaterError('Text extraction failed.')
    } finally { setRaterExtractLoading(false) }
  }

  const handleRate = async () => {
    if (!raterJD || raterJD.length < 50) { setRaterError('Job description must be at least 50 characters.'); return }
    setRaterError(''); setRaterResults(null); setRaterLoading(true)

    try {
      const fd = new FormData()
      fd.append('job_description', raterJD)
      fd.append('input_mode', raterInputMode)
      if (raterInputMode === 'upload' && raterFile) {
        fd.append('file', raterFile)
      } else {
        if (!raterText.trim()) { setRaterError('Paste resume text or upload a file.'); setRaterLoading(false); return }
        fd.append('resume_text', raterText)
        fd.append('input_mode', 'text')
      }

      const { data } = await rateResume(fd)
      setRaterResults(data)
    } catch (err) {
      setRaterError(err.response?.data?.detail || 'Rating failed.')
    } finally { setRaterLoading(false) }
  }

  // ═══════════════════════════════════════════════════════════════════════
  // RENDER
  // ═══════════════════════════════════════════════════════════════════════
  // Destructure rating results safely for display
  const sim = raterResults?.similarity || {}
  const llm = raterResults?.llm_rating || {}

  return (
    <div className="resume-page">
      <div className="page-header">
        <h1>📄 Resume Suite</h1>
        <p>Build, modify, and rate your resume with AI</p>
      </div>

      {/* Tab bar */}
      <div className="tab-bar">
        {['builder', 'modifier', 'rater'].map(t => (
          <button key={t} className={`tab-btn ${activeTab === t ? 'active' : ''}`} onClick={() => setActiveTab(t)}>
            {t === 'builder' ? '🔨 Builder' : t === 'modifier' ? '✏️ Modifier' : '⭐ Rater'}
          </button>
        ))}
      </div>

      {/* ── Builder Tab ──────────────────────────────────────────────── */}
      {activeTab === 'builder' && (
        <div className="tab-content">
          <ResumeForm prefix="builder" onDataChange={setBuilderData} />
          {builderError && <div className="error-message">{builderError}</div>}
          {builderSuccess && <div className="success-message">{builderSuccess}</div>}
          <button className="generate-btn" onClick={handleBuild} disabled={builderLoading}>
            {builderLoading ? 'Generating…' : '🚀 Generate Resume PDF'}
          </button>
          {builderLoading && <Loading message="AI is crafting your resume…" />}
        </div>
      )}

      {/* ── Modifier Tab ─────────────────────────────────────────────── */}
      {activeTab === 'modifier' && (
        <div className="tab-content">
          <div className="input-toggle">
            <button className={`toggle-option ${modInputMode === 'upload' ? 'active' : ''}`} onClick={() => setModInputMode('upload')}>📎 Upload Resume</button>
            <button className={`toggle-option ${modInputMode === 'form' ? 'active' : ''}`} onClick={() => setModInputMode('form')}>📝 Fill Form</button>
          </div>

          {modInputMode === 'upload' ? (
            <div className="form-group">
              <label className="form-label">Upload Resume (PDF / DOCX / TXT)</label>
              <input type="file" className="form-input" accept=".pdf,.docx,.txt" onChange={e => setModFile(e.target.files?.[0])} />
              <button className="submit-btn" style={{ marginTop: '0.8rem' }} onClick={handleModExtract} disabled={modExtractLoading || !modFile}>
                {modExtractLoading ? 'Extracting…' : 'Extract Text'}
              </button>
              {modExtractedText && <div className="extracted-text">{modExtractedText}</div>}
            </div>
          ) : (
            <ResumeForm prefix="modifier" onDataChange={setModFormData} />
          )}

          <div className="form-group">
            <label className="form-label">Job Description *</label>
            <textarea className="form-textarea" rows={5} placeholder="Paste the target job description here…" value={modJD} onChange={e => setModJD(e.target.value)} />
          </div>

          <div className="slider-group">
            <label className="form-label">Rewrite Creativity: <span className="slider-value">{modTemp}</span></label>
            <input type="range" min="0.2" max="0.9" step="0.1" value={modTemp} onChange={e => setModTemp(parseFloat(e.target.value))} />
          </div>

          {modError && <div className="error-message">{modError}</div>}
          {modSuccess && <div className="success-message">{modSuccess}</div>}
          <button className="generate-btn" onClick={handleModify} disabled={modLoading}>
            {modLoading ? 'Generating…' : '🚀 Generate Modified Resume'}
          </button>
          {modLoading && <Loading message="AI is rewriting your resume for this role…" />}
        </div>
      )}

      {/* ── Rater Tab ────────────────────────────────────────────────── */}
      {activeTab === 'rater' && (
        <div className="tab-content">
          <div className="input-toggle">
            <button className={`toggle-option ${raterInputMode === 'paste' ? 'active' : ''}`} onClick={() => setRaterInputMode('paste')}>📋 Paste Text</button>
            <button className={`toggle-option ${raterInputMode === 'upload' ? 'active' : ''}`} onClick={() => setRaterInputMode('upload')}>📎 Upload File</button>
          </div>

          {raterInputMode === 'paste' ? (
            <div className="form-group">
              <label className="form-label">Resume Text</label>
              <textarea className="form-textarea" rows={6} placeholder="Paste your resume text here…" value={raterText} onChange={e => setRaterText(e.target.value)} />
            </div>
          ) : (
            <div className="form-group">
              <label className="form-label">Upload Resume</label>
              <input type="file" className="form-input" accept=".pdf,.docx,.txt" onChange={e => setRaterFile(e.target.files?.[0])} />
              <button className="submit-btn" style={{ marginTop: '0.8rem' }} onClick={handleRaterExtract} disabled={raterExtractLoading || !raterFile}>
                {raterExtractLoading ? 'Extracting…' : 'Extract Text'}
              </button>
            </div>
          )}

          <div className="form-group">
            <label className="form-label">Job Description *</label>
            <textarea className="form-textarea" rows={5} placeholder="Paste the target job description here…" value={raterJD} onChange={e => setRaterJD(e.target.value)} />
          </div>

          {raterError && <div className="error-message">{raterError}</div>}
          <button className="generate-btn" onClick={handleRate} disabled={raterLoading}>
            {raterLoading ? 'Rating…' : '⭐ Rate My Resume'}
          </button>
          {raterLoading && <Loading message="Analyzing your resume against the job description…" />}

          {/* Rating Results Dashboard */}
          {raterResults && (
            <div className="rating-dashboard">
              {/* Overall Hybrid Score */}
              <div className="hybrid-score">
                <div className="hybrid-score-number">{raterResults.hybrid_score ?? 0}</div>
                <div className="hybrid-score-label">Overall Hybrid Score / 100</div>
              </div>

              {/* 5 Sub-metrics */}
              <div className="metric-grid">
                <div className="metric-card">
                  <div className="metric-value">{sim.similarity_score ?? 0}</div>
                  <div className="metric-label">Similarity</div>
                </div>
                <div className="metric-card">
                  <div className="metric-value">{llm.content_quality_score ?? 0}</div>
                  <div className="metric-label">Content</div>
                </div>
                <div className="metric-card">
                  <div className="metric-value">{llm.keyword_alignment_score ?? 0}</div>
                  <div className="metric-label">Keywords</div>
                </div>
                <div className="metric-card">
                  <div className="metric-value">{llm.ats_friendliness_score ?? 0}</div>
                  <div className="metric-label">ATS</div>
                </div>
                <div className="metric-card">
                  <div className="metric-value">{llm.formatting_score ?? 0}</div>
                  <div className="metric-label">Formatting</div>
                </div>
              </div>

              {/* Recruiter Summary */}
              {llm.summary_feedback && (
                <div className="rating-section">
                  <h4 className="rating-title">📝 Recruiter Summary</h4>
                  <p>{llm.summary_feedback}</p>
                </div>
              )}

              {/* Strengths */}
              {llm.strengths?.length > 0 && (
                <div className="rating-section">
                  <h4 className="rating-title">💪 Strengths</h4>
                  {llm.strengths.map((s, i) => <div key={i} className="strength-item">✅ {s}</div>)}
                </div>
              )}

              {/* Weaknesses */}
              {llm.weaknesses?.length > 0 && (
                <div className="rating-section">
                  <h4 className="rating-title">⚠️ Weaknesses</h4>
                  {llm.weaknesses.map((w, i) => <div key={i} className="weakness-item">⚡ {w}</div>)}
                </div>
              )}

              {/* Suggestions */}
              {llm.suggestions?.length > 0 && (
                <div className="rating-section">
                  <h4 className="rating-title">💡 Suggestions</h4>
                  {llm.suggestions.map((s, i) => <div key={i} className="suggestion-item">🔹 {s}</div>)}
                </div>
              )}

              {/* Keywords */}
              <div className="rating-section">
                <h4 className="rating-title">🔑 Matched Keywords</h4>
                <div className="keyword-list">
                  {(sim.matched_keywords || []).map((k, i) => <span key={i} className="keyword-tag matched">{k}</span>)}
                  {(!sim.matched_keywords || sim.matched_keywords.length === 0) && <span style={{ color: 'var(--text-muted)' }}>None found</span>}
                </div>
              </div>
              <div className="rating-section">
                <h4 className="rating-title">❌ Missing Keywords</h4>
                <div className="keyword-list">
                  {(sim.missing_keywords || []).map((k, i) => <span key={i} className="keyword-tag missing">{k}</span>)}
                  {(!sim.missing_keywords || sim.missing_keywords.length === 0) && <span style={{ color: 'var(--text-muted)' }}>None — great match!</span>}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
