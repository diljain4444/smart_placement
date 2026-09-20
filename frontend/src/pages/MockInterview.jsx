import { useState, useRef, useCallback } from 'react'
import {
  processResume, startInterview, submitAnswer,
  submitVoiceAnswer, endInterview, resetInterview,
} from '../api'
import AvatarPanel from '../components/AvatarPanel'
import InterviewReport from '../components/InterviewReport'
import Loading from '../components/Loading'

/* ────────────────────────────────────────────────────────────────────────────
   MockInterview — 3-step flow: Upload → Interview → Report
   ──────────────────────────────────────────────────────────────────────────── */
export default function MockInterview() {
  // ── Flow state ──────────────────────────────────────────────────────────
  const [step, setStep] = useState('upload')          // upload | interview | report
  const [sessionId, setSessionId] = useState(null)

  // ── Upload state ────────────────────────────────────────────────────────
  const [interviewMode, setInterviewMode] = useState('resume_only')
  const [jdText, setJdText] = useState('')
  const [voiceMode, setVoiceMode] = useState(true)
  const [resumeFile, setResumeFile] = useState(null)
  const [extractedInfo, setExtractedInfo] = useState(null)
  const [jdContext, setJdContext] = useState('')

  // ── Interview state ─────────────────────────────────────────────────────
  const [currentQuestion, setCurrentQuestion] = useState(null)
  const [questionAudioB64, setQuestionAudioB64] = useState('')
  const [feedbackAudioB64, setFeedbackAudioB64] = useState('')
  const [lastFeedback, setLastFeedback] = useState(null)
  const [topicsCovered, setTopicsCovered] = useState([])
  const [topicCount, setTopicCount] = useState(0)
  const [report, setReport] = useState(null)
  const [textAnswer, setTextAnswer] = useState('')
  const [transcript, setTranscript] = useState('')

  // ── Audio/Video state ─────────────────────────────────────────────────────
  const [isAudioPlaying, setIsAudioPlaying] = useState(false)
  const [audioError, setAudioError] = useState('')
  const audioSeqRef = useRef(0)

  // ── Voice recording ─────────────────────────────────────────────────────
  const [isRecording, setIsRecording] = useState(false)
  const mediaRecorderRef = useRef(null)
  const audioChunksRef = useRef([])

  // ── Loading / Error ─────────────────────────────────────────────────────
  const [loading, setLoading] = useState(false)
  const [loadingMessage, setLoadingMessage] = useState('')
  const [error, setError] = useState(null)

  // ════════════════════════════════════════════════════════════════════════
  // HANDLERS
  // ════════════════════════════════════════════════════════════════════════

  const handleProcessResume = async () => {
    if (!resumeFile) return setError('Please upload a resume first.')
    if (interviewMode === 'resume_jd' && !jdText.trim()) return setError('Please enter a job description.')
    setError(null); setLoading(true); setLoadingMessage('Processing your resume…')

    try {
      const fd = new FormData()
      fd.append('file', resumeFile)
      fd.append('interview_mode', interviewMode)
      if (interviewMode === 'resume_jd') fd.append('jd_text', jdText)

      const { data } = await processResume(fd)
      setExtractedInfo(data.extracted_info)
      setJdContext(data.jd_context || '')
    } catch (err) {
      setError(err.response?.data?.detail || 'Error processing resume.')
    } finally { setLoading(false) }
  }

  const handleStartInterview = async () => {
    if (!extractedInfo) return

    // Unlock browser autoplay on this user gesture so the first
    // question audio can auto-play after the async API call returns.
    // A minimal silent WAV (44 bytes) played during the click context
    // tells the browser "the user intends audio playback".
    try {
      const silence = new Audio('data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=')
      await silence.play()
      silence.pause()
      silence.src = ''
    } catch (_) { /* ignore — worst case the manual play button shows */ }

    setError(null); setLoading(true); setLoadingMessage('Generating first question…')
    setAudioError('')

    try {
      const { data } = await startInterview({
        education: extractedInfo.education,
        skills: extractedInfo.skills,
        projects: extractedInfo.projects,
        interview_mode: interviewMode,
        jd_context: jdContext,
        voice_mode: voiceMode,
      })
      setSessionId(data.session_id)
      setCurrentQuestion(data.question)

      if (voiceMode && data.question && !data.question_audio_b64) {
        setAudioError('Audio generation unavailable. Question displayed as text.')
      }
      audioSeqRef.current += 1
      setQuestionAudioB64(data.question_audio_b64 || '')
      setFeedbackAudioB64('')
      setStep('interview')
    } catch (err) {
      setError(err.response?.data?.detail || 'Error starting interview.')
    } finally { setLoading(false) }
  }

  // ── Handle answer response (shared by text + voice) ─────────────────────
  const handleAnswerResponse = (data) => {
    setAudioError('')
    if (data.is_complete) {
      setReport(data.report)
      setStep('report')
    } else {
      setCurrentQuestion(data.next_question)
      setLastFeedback(data.feedback)
      setTopicsCovered(data.topics_covered || [])
      setTopicCount(data.topic_count || 0)

      if (voiceMode && data.next_question && !data.question_audio_b64) {
        setAudioError('Audio generation unavailable. Question displayed as text.')
      }
      audioSeqRef.current += 1
      setQuestionAudioB64(data.question_audio_b64 || '')
      setFeedbackAudioB64(data.feedback_audio_b64 || '')
    }
  }

  const handleTextSubmit = async () => {
    if (!textAnswer.trim()) return
    setError(null); setLoading(true); setLoadingMessage('Evaluating your answer…')
    setTranscript('')

    try {
      const { data } = await submitAnswer({
        session_id: sessionId,
        answer: textAnswer,
      })
      setTextAnswer('')
      handleAnswerResponse(data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Error submitting answer.')
    } finally { setLoading(false) }
  }

  // ── Voice recording via MediaRecorder API ───────────────────────────────
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/mp4',
      })
      mediaRecorderRef.current = mediaRecorder
      audioChunksRef.current = []

      mediaRecorder.ondataavailable = e => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data)
      }
      mediaRecorder.onstop = async () => {
        const blob = new Blob(audioChunksRef.current, { type: mediaRecorder.mimeType })
        stream.getTracks().forEach(t => t.stop())
        await handleVoiceSubmit(blob)
      }
      mediaRecorder.start()
      setIsRecording(true)
      setError(null)
    } catch (err) {
      console.error('Microphone error:', err)
      setError('Could not access microphone. Please check permissions.')
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop()
      setIsRecording(false)
    }
  }

  const handleVoiceSubmit = async (blob) => {
    setLoading(true); setLoadingMessage('Transcribing & evaluating…')

    try {
      const fd = new FormData()
      fd.append('audio', blob, 'answer.webm')
      fd.append('session_id', sessionId)

      const { data } = await submitVoiceAnswer(fd)
      setTranscript(data.transcript || '')
      handleAnswerResponse(data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Error processing voice answer.')
    } finally { setLoading(false) }
  }

  const handleEndInterview = async () => {
    setError(null); setLoading(true); setLoadingMessage('Generating comprehensive report…')

    try {
      const { data } = await endInterview({ session_id: sessionId })
      setReport(data.report)
      setTopicsCovered(data.topics_covered || topicsCovered)
      setStep('report')
    } catch (err) {
      setError(err.response?.data?.detail || 'Error ending interview.')
    } finally { setLoading(false) }
  }

  const handleNewInterview = async () => {
    try { await resetInterview({ session_id: sessionId }) } catch (_) {}
    setStep('upload')
    setSessionId(null)
    setExtractedInfo(null)
    setJdContext('')
    setJdText('')
    setReport(null)
    setTopicCount(0)
    setTopicsCovered([])
    setCurrentQuestion(null)
    setLastFeedback(null)
    setQuestionAudioB64('')
    setFeedbackAudioB64('')
    setTranscript('')
    setTextAnswer('')
    setResumeFile(null)
    setError(null)
    setIsAudioPlaying(false)
    setAudioError('')
    audioSeqRef.current = 0
  }

  // ── Audio state callback from AvatarPanel ──────────────────────────────
  const handleAudioStateChange = useCallback((playing) => {
    setIsAudioPlaying(playing)
  }, [])

  // ── Compute avatar state ──────────────────────────────────────────────
  // Priority: recording > audio playing > question displayed (text mode) > waiting
  const computedAvatarState = isRecording
    ? 'new_hearing'
    : isAudioPlaying
      ? 'new_final_question'
      : 'new_waiting'

  // In text mode, show question video while question is freshly displayed
  const isShowingQuestion = !voiceMode && !!currentQuestion && !isRecording && !isAudioPlaying

  // ════════════════════════════════════════════════════════════════════════
  // RENDER
  // ════════════════════════════════════════════════════════════════════════
  return (
    <div className="interview-page">
      {loading && <Loading message={loadingMessage} fullScreen />}

      {error && (
        <div className="error-message">
          {error}
          <button style={{ float: 'right', background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }} onClick={() => setError(null)}>✕</button>
        </div>
      )}

      {/* Step indicators */}
      <div className="page-header">
        <h1>Mock Interview</h1>
        <p>AI-powered interview practice with real-time feedback</p>
      </div>

      <div className="step-nav">
        <div className={`step-indicator ${step === 'upload' ? 'active' : (step !== 'upload') ? 'done' : ''}`}>1. Setup</div>
        <div className={`step-indicator ${step === 'interview' ? 'active' : step === 'report' ? 'done' : ''}`}>2. Interview</div>
        <div className={`step-indicator ${step === 'report' ? 'active' : ''}`}>3. Report</div>
      </div>

      {/* ── STEP 1: Upload ──────────────────────────────────────────────── */}
      {step === 'upload' && (
        <div className="upload-section">
          <div>
            {/* Interview mode selector */}
            <div className="mode-selector">
              <h3>Interview Mode</h3>
              <div className="mode-options">
                <div className={`mode-option ${interviewMode === 'resume_only' ? 'active' : ''}`} onClick={() => setInterviewMode('resume_only')}>
                  <strong>Resume Only</strong>
                  <p>General interview based on your profile</p>
                </div>
                <div className={`mode-option ${interviewMode === 'resume_jd' ? 'active' : ''}`} onClick={() => setInterviewMode('resume_jd')}>
                  <strong>Resume + JD</strong>
                  <p>Tailored interview for a specific role</p>
                </div>
              </div>
            </div>

            {/* JD input (conditional) */}
            {interviewMode === 'resume_jd' && (
              <div className="form-group">
                <label className="form-label">Job Description *</label>
                <textarea className="form-textarea" placeholder="Paste the job description here…" value={jdText} onChange={e => setJdText(e.target.value)} rows={5} />
              </div>
            )}

            {/* File upload */}
            <div className="file-upload">
              <label>Upload your resume (PDF or DOCX)</label>
              <input type="file" accept=".pdf,.docx" onChange={e => setResumeFile(e.target.files?.[0] || null)} />
              {resumeFile && <div className="file-info">✓ {resumeFile.name}</div>}
            </div>

            <button className="generate-btn" onClick={handleProcessResume} disabled={!resumeFile || loading}>
              Process Resume
            </button>

            {/* After processing: show profile + mode toggle + start button */}
            {extractedInfo && (
              <>
                <div className="mode-toggle" style={{ marginTop: '1.5rem' }}>
                  <button className={`toggle-btn ${voiceMode ? 'active' : ''}`} onClick={() => setVoiceMode(true)}>Voice Mode</button>
                  <button className={`toggle-btn ${!voiceMode ? 'active' : ''}`} onClick={() => setVoiceMode(false)}>Text Mode</button>
                </div>
                <button className="generate-btn" onClick={handleStartInterview} disabled={loading} style={{ marginTop: '1rem' }}>
                  Start Interview
                </button>
              </>
            )}
          </div>

          {/* Profile card (right side) */}
          {extractedInfo && (
            <div className="profile-card">
              <h3>Extracted Profile</h3>
              <div className="profile-section">
                <h4>Education</h4>
                <p>{extractedInfo.education}</p>
              </div>
              <div className="profile-section">
                <h4>Skills</h4>
                <div className="skill-tags">
                  {(extractedInfo.skills || []).map((s, i) => <span key={i} className="skill-tag">{s}</span>)}
                </div>
              </div>
              <div className="profile-section">
                <h4>Projects</h4>
                <div className="skill-tags">
                  {(extractedInfo.projects || []).map((p, i) => <span key={i} className="project-tag">{p}</span>)}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── STEP 2: Interview ───────────────────────────────────────────── */}
      {step === 'interview' && (
        <div className="interview-section">
          {/* Left: Avatar */}
          <div>
            <AvatarPanel
              avatarState={computedAvatarState}
              feedbackAudioB64={feedbackAudioB64}
              questionAudioB64={questionAudioB64}
              isRecording={isRecording}
              isShowingQuestion={isShowingQuestion}
              onAudioStateChange={handleAudioStateChange}
              audioSeqId={audioSeqRef.current}
            />
          </div>

          {/* Right: Question + Answer */}
          <div>
            {/* Audio error notice */}
            {audioError && (
              <div className="error-message" style={{ background: 'rgba(245,158,11,0.1)', borderColor: 'rgba(245,158,11,0.3)', color: '#FCD34D' }}>
                {audioError}
                <button style={{ float: 'right', background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }} onClick={() => setAudioError('')}>✕</button>
              </div>
            )}

            {/* Feedback from last answer */}
            {lastFeedback && (
              <div className="feedback-card">
                <span className="feedback-label">Feedback</span>
                {lastFeedback}
              </div>
            )}

            {/* Transcript (voice mode) */}
            {transcript && (
              <div className="transcript-display">
                <strong>Your answer:</strong> {transcript}
              </div>
            )}

            {/* Current question */}
            {currentQuestion && (
              <div className="question-card">
                <strong>Question:</strong> {currentQuestion}
              </div>
            )}

            {/* Answer input */}
            <div className="answer-section">
              {voiceMode ? (
                <div style={{ textAlign: 'center' }}>
                  <button
                    className={`record-btn ${isRecording ? 'recording' : ''}`}
                    onClick={isRecording ? stopRecording : startRecording}
                    disabled={loading}
                  >
                    {isRecording ? '■' : '●'}
                  </button>
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '0.5rem' }}>
                    {isRecording ? 'Recording… Click to stop' : 'Click to start recording'}
                  </p>
                </div>
              ) : (
                <>
                  <textarea className="text-answer" value={textAnswer} onChange={e => setTextAnswer(e.target.value)} placeholder="Type your answer here…" rows={4} />
                  <button className="submit-btn" onClick={handleTextSubmit} disabled={!textAnswer.trim() || loading}>
                    Submit Answer
                  </button>
                </>
              )}
            </div>

            {/* Progress bar */}
            <div className="progress-section">
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${Math.min(100, (topicCount / 5) * 100)}%` }} />
              </div>
              <div className="progress-label">Topics covered: {topicCount} / 5 {topicCount < 3 && '(min 3 to end)'}</div>
            </div>

            {/* End interview */}
            <button className="end-btn" onClick={handleEndInterview} disabled={topicCount < 3 || loading}>
              {topicCount < 3 ? `Cover ${3 - topicCount} more topic(s) to end` : 'End Interview'}
            </button>
          </div>
        </div>
      )}

      {/* ── STEP 3: Report ──────────────────────────────────────────────── */}
      {step === 'report' && report && (
        <div>
          <div className="done-banner">
            <h2>Interview Complete</h2>
            <p>Great job! Review your detailed performance report below.</p>
          </div>
          <InterviewReport report={report} />
          <button className="new-interview-btn" onClick={handleNewInterview}>
            Start New Interview
          </button>
        </div>
      )}
    </div>
  )
}
