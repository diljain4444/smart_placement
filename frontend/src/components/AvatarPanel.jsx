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

export default function AvatarPanel({
  avatarState = 'new_waiting',
  feedbackAudioB64 = '',
  questionAudioB64 = '',
  isRecording = false,
  isShowingQuestion = false,
  onAudioStateChange,
  audioSeqId = 0,
}) {
  const [currentState, setCurrentState] = useState(avatarState)
  const [autoplayBlocked, setAutoplayBlocked] = useState(false)
  const [hasReplayAudio, setHasReplayAudio] = useState(false)
  const audioRef = useRef(null)         // current Audio object
  const prevSeqId = useRef(-1)
  const isPlayingRef = useRef(false)
  const pendingAudioRef = useRef({ fb64: '', qb64: '' })

  // Stable ref for callback to avoid dependency churn
  const cbRef = useRef(onAudioStateChange)
  useEffect(() => { cbRef.current = onAudioStateChange }, [onAudioStateChange])

  // ── Stop any currently playing audio ──────────────────────────────────────
  const stopAudio = useCallback(() => {
    const a = audioRef.current
    if (a) {
      a.onended = null
      a.onerror = null
      a.pause()
      a.src = ''
      audioRef.current = null
    }
    isPlayingRef.current = false
  }, [])

  // ── Play a single base64 audio clip, returns a promise ────────────────────
  const playClip = useCallback((b64) => {
    return new Promise((resolve) => {
      if (!b64) return resolve()

      // Create a brand-new Audio object for each clip
      const audio = new Audio(`data:audio/mpeg;base64,${b64}`)
      audioRef.current = audio

      audio.onended = () => {
        console.log('[AvatarPanel] Clip ended')
        resolve()
      }
      audio.onerror = (e) => {
        console.error('[AvatarPanel] Clip error:', e)
        resolve()
      }

      audio.play()
        .then(() => setAutoplayBlocked(false))
        .catch((err) => {
          console.warn('[AvatarPanel] Autoplay blocked:', err.message)
          setAutoplayBlocked(true)
          resolve()
        })
    })
  }, [])

  // ── Play feedback then question audio ─────────────────────────────────────
  const playSequence = useCallback(async (fb64, qb64) => {
    stopAudio()
    setAutoplayBlocked(false)
    isPlayingRef.current = true

    setCurrentState('new_final_question')
    cbRef.current?.(true)

    console.log(`[AvatarPanel] Playing sequence — feedback: ${fb64 ? fb64.length : 0} chars, question: ${qb64 ? qb64.length : 0} chars`)

    if (fb64) await playClip(fb64)
    if (isPlayingRef.current && qb64) await playClip(qb64)

    isPlayingRef.current = false
    cbRef.current?.(false)
    setCurrentState('new_waiting')
    console.log('[AvatarPanel] Sequence complete, back to waiting')
  }, [stopAudio, playClip])

  // ── Manual play / replay ──────────────────────────────────────────────────
  const handleManualPlay = useCallback(() => {
    const { fb64, qb64 } = pendingAudioRef.current
    setAutoplayBlocked(false)
    if (fb64 || qb64) playSequence(fb64, qb64)
  }, [playSequence])

  // ── Trigger playback when audioSeqId changes (new question) ───────────────
  useEffect(() => {
    if (audioSeqId > 0 && audioSeqId !== prevSeqId.current) {
      prevSeqId.current = audioSeqId
      const fb64 = feedbackAudioB64 || ''
      const qb64 = questionAudioB64 || ''
      pendingAudioRef.current = { fb64, qb64 }
      setHasReplayAudio(!!(fb64 || qb64))
      if (fb64 || qb64) {
        console.log(`[AvatarPanel] New audio seqId=${audioSeqId}, triggering playback`)
        playSequence(fb64, qb64)
      }
    }
  }, [audioSeqId, feedbackAudioB64, questionAudioB64, playSequence])

  // ── Recording overrides ───────────────────────────────────────────────────
  useEffect(() => {
    if (isRecording) {
      stopAudio()
      setCurrentState('new_hearing')
    } else if (currentState === 'new_hearing') {
      setCurrentState('new_waiting')
    }
  }, [isRecording, stopAudio]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Text mode: show question video ────────────────────────────────────────
  useEffect(() => {
    if (isShowingQuestion && !isRecording && !isPlayingRef.current) {
      setCurrentState('new_final_question')
    } else if (!isShowingQuestion && !isRecording && !isPlayingRef.current && currentState === 'new_final_question') {
      setCurrentState('new_waiting')
    }
  }, [isShowingQuestion, isRecording]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Cleanup on unmount ────────────────────────────────────────────────────
  useEffect(() => () => { stopAudio() }, [stopAudio])

  const cfg = STATE_CFG[currentState] || STATE_CFG.new_waiting

  return (
    <div
      className="avatar-panel"
      style={{
        borderColor: cfg.border,
        boxShadow: `0 0 36px ${cfg.glow}, 0 8px 44px rgba(0,0,0,0.65)`,
      }}
    >
      {/* Video container */}
      <div className="avatar-video-container">
        {['new_final_question', 'new_waiting', 'new_hearing'].map(s => (
          <video
            key={s}
            className={`avatar-video ${currentState === s ? 'visible' : ''}`}
            src={`/videos/${s}.mp4`}
            autoPlay loop muted playsInline preload="auto"
          />
        ))}

        {/* LIVE badge */}
        <div className="live-badge"><span className="live-dot" />LIVE</div>

        {/* Name tag */}
        <div className="name-tag">
          <div className="name-tag-name">Sarah Mitchell</div>
          <div className="name-tag-title">Senior Technical Recruiter</div>
        </div>

        {/* Speaking equalizer */}
        {currentState === 'new_final_question' && (
          <div className="speak-bars">
            {[1,2,3,4,5].map(i => <div key={i} className="speak-bar" style={{ animationDelay: `${i*0.1}s` }} />)}
          </div>
        )}

        {/* Wave equalizer + mic */}
        {currentState === 'new_hearing' && (
          <>
            <div className="wave-bars">
              {[1,2,3,4,5].map(i => <div key={i} className="wave-bar" style={{ animationDelay: `${i*0.12}s` }} />)}
            </div>
            <div className="mic-overlay">🎙️</div>
          </>
        )}
      </div>

      {/* Autoplay blocked */}
      {autoplayBlocked && (
        <button className="manual-play-btn" onClick={handleManualPlay}>
          🚀 Start Interview
        </button>
      )}

      {/* Replay (visible when not playing and audio exists) */}
      {!autoplayBlocked && hasReplayAudio && currentState === 'new_waiting' && (
        <button className="manual-play-btn" onClick={handleManualPlay}>
          🔁 Replay Question Audio
        </button>
      )}

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
