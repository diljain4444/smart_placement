import { useState, useEffect, useRef, useCallback } from 'react'

/* ────────────────────────────────────────────────────────────────────────────
   AvatarPanel — 3-state video avatar with sequential audio playback.
   States: new_final_question | new_waiting | new_hearing
   ──────────────────────────────────────────────────────────────────────────── */

const STATE_CFG = {
  new_final_question: { border: '#22C55E', glow: 'rgba(34,197,94,0.35)', label: 'Asking Question', color: '#4ADE80' },
  new_waiting:        { border: '#4A5568', glow: 'rgba(74,99,128,0.20)', label: 'Waiting for Response', color: '#94A3B8' },
  new_hearing:        { border: '#3B6BE8', glow: 'rgba(59,107,232,0.35)', label: 'Listening…', color: '#93C5FD' },
}

export default function AvatarPanel({ avatarState = 'new_waiting', feedbackAudioB64 = '', questionAudioB64 = '', isRecording = false }) {
  const [currentState, setCurrentState] = useState(avatarState)
  const audioRef = useRef(null)
  const prevAudioKey = useRef('')

  // ── Play audio sequence when new audio arrives ─────────────────────────────
  const playSequence = useCallback(async (fb64, qb64) => {
    const playClip = (b64) => new Promise(resolve => {
      if (!b64 || !audioRef.current) return resolve()
      audioRef.current.src = `data:audio/mp3;base64,${b64}`
      audioRef.current.onended = resolve
      audioRef.current.onerror = resolve
      audioRef.current.play().catch(resolve)
    })

    setCurrentState('new_final_question')
    await playClip(fb64)
    await playClip(qb64)
    setCurrentState('new_waiting')
  }, [])

  useEffect(() => {
    const key = `${feedbackAudioB64?.slice(0, 20)}|${questionAudioB64?.slice(0, 20)}`
    if ((feedbackAudioB64 || questionAudioB64) && key !== prevAudioKey.current) {
      prevAudioKey.current = key
      playSequence(feedbackAudioB64, questionAudioB64)
    }
  }, [feedbackAudioB64, questionAudioB64, playSequence])

  // ── Recording state syncs to hearing ───────────────────────────────────────
  useEffect(() => {
    if (isRecording) setCurrentState('new_hearing')
    else if (currentState === 'new_hearing') setCurrentState('new_waiting')
  }, [isRecording]) // eslint-disable-line react-hooks/exhaustive-deps

  const cfg = STATE_CFG[currentState] || STATE_CFG.new_waiting

  return (
    <div
      className="avatar-panel"
      style={{
        borderColor: cfg.border,
        boxShadow: `0 0 36px ${cfg.glow}, 0 8px 44px rgba(0,0,0,0.65)`,
      }}
    >
      <audio ref={audioRef} style={{ display: 'none' }} />

      {/* Video container */}
      <div className="avatar-video-container">
        {['new_final_question', 'new_waiting', 'new_hearing'].map(s => (
          <video
            key={s}
            className={`avatar-video ${currentState === s ? 'visible' : ''}`}
            src={`/videos/${s}.mp4`}
            autoPlay loop muted playsInline
          />
        ))}

        {/* LIVE badge */}
        <div className="live-badge"><span className="live-dot" />LIVE</div>

        {/* Name tag */}
        <div className="name-tag">
          <div className="name-tag-name">Sarah Mitchell</div>
          <div className="name-tag-title">Senior Technical Recruiter</div>
        </div>

        {/* Speaking equalizer (green, visible in new_final_question) */}
        {currentState === 'new_final_question' && (
          <div className="speak-bars">
            {[1,2,3,4,5].map(i => <div key={i} className="speak-bar" style={{ animationDelay: `${i*0.1}s` }} />)}
          </div>
        )}

        {/* Wave equalizer + mic (blue, visible in new_hearing) */}
        {currentState === 'new_hearing' && (
          <>
            <div className="wave-bars">
              {[1,2,3,4,5].map(i => <div key={i} className="wave-bar" style={{ animationDelay: `${i*0.12}s` }} />)}
            </div>
            <div className="mic-overlay">🎙️</div>
          </>
        )}
      </div>

      {/* Status bar */}
      <div className="status-bar">
        <div className="status-info">
          <div className="status-avatar">👔</div>
          <div>
            <div className="status-name">Sarah Mitchell</div>
            <div className="status-title">Senior Technical Recruiter</div>
          </div>
        </div>
        <div className="status-pill" style={{ color: cfg.color, borderColor: `${cfg.border}40` }}>
          <span className="status-dot" style={{ backgroundColor: cfg.border }} />
          {cfg.label}
        </div>
      </div>
    </div>
  )
}
