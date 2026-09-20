import { Link } from 'react-router-dom'

export default function Home() {
  return (
    <div className="home-page">
      {/* Hero */}
      <section className="hero">
        <h1 className="hero-title">🎯 Smart Placement</h1>
        <p className="hero-subtitle">
          Your AI-powered companion for interview preparation and resume building.
          Practice with a realistic avatar, get instant feedback, and craft ATS-optimized resumes.
        </p>
        <div className="hero-cta">
          <Link to="/interview" className="cta-btn">🎤 Start Mock Interview</Link>
          <Link to="/resume" className="cta-btn cta-btn-secondary">📄 Resume Suite</Link>
        </div>
        <div className="hero-stats">
          <div><div className="hero-stat-num">🚀</div><div className="hero-stat-label">AI Powered</div></div>
          <div><div className="hero-stat-num">🎙️</div><div className="hero-stat-label">Voice Enabled</div></div>
          <div><div className="hero-stat-num">📊</div><div className="hero-stat-label">ATS Optimized</div></div>
        </div>
      </section>

      {/* Features */}
      <section className="features-section">
        <div className="features-grid">
          <div className="feature-card">
            <span className="feature-icon">🎤</span>
            <h2 className="feature-title">Mock Interview</h2>
            <p className="feature-desc">
              Practice with our AI interviewer avatar using voice or text.
              Get real-time feedback, topic-by-topic analysis, and a personalised
              learning roadmap after each session.
            </p>
            <Link to="/interview" className="feature-btn">Try Mock Interview →</Link>
          </div>
          <div className="feature-card">
            <span className="feature-icon">📄</span>
            <h2 className="feature-title">Resume Suite</h2>
            <p className="feature-desc">
              Build professional resumes from scratch, modify them for specific
              job descriptions, and rate them against ATS scoring systems —
              all powered by AI.
            </p>
            <Link to="/resume" className="feature-btn">Go to Resume Suite →</Link>
          </div>
          <div className="feature-card">
            <span className="feature-icon">📘</span>
            <h2 className="feature-title">Learning Inception</h2>
            <p className="feature-desc">
              Discover curated YouTube resources for technical skills and
              soft skill development. Browse topics, filter by level, and
              start learning instantly.
            </p>
            <Link to="/learning" className="feature-btn">Start Learning →</Link>
          </div>
          <div className="feature-card">
            <span className="feature-icon">📚</span>
            <h2 className="feature-title">Document Q&A</h2>
            <p className="feature-desc">
              Upload any document — PDF, DOCX, CSV, or text — and ask
              questions. Our RAG-powered AI retrieves answers directly
              from your document's content.
            </p>
            <Link to="/doc-qa" className="feature-btn">Try Doc Q&A →</Link>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="how-it-works">
        <h2>How It Works</h2>
        <div className="steps-grid">
          {[
            { num: 1, title: 'Upload', desc: 'Upload your resume and optionally provide a job description.' },
            { num: 2, title: 'Practice', desc: 'Answer AI-generated questions in voice or text mode.' },
            { num: 3, title: 'Get Feedback', desc: 'Receive immediate feedback after every answer.' },
            { num: 4, title: 'Improve', desc: 'Review your detailed performance report and learning roadmap.' },
          ].map(s => (
            <div key={s.num} className="step-card">
              <div className="step-num">{s.num}</div>
              <div className="step-title">{s.title}</div>
              <div className="step-desc">{s.desc}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="footer">
        <p>© {new Date().getFullYear()} Smart Placement · AI-Powered Career Platform</p>
      </footer>
    </div>
  )
}
