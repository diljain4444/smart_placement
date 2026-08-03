"""
main.py
─────────────────────────────────────────────────────────────
Unified entry-point for Smart Placement.

Run with:
    streamlit run main.py
─────────────────────────────────────────────────────────────
"""

import streamlit as st

# ── Page Config (ONLY place this is called) ───────────────────────────────────
st.set_page_config(
    page_title="Smart Placement",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500;600&display=swap');

html, body, .stApp, .main { background-color: #060810 !important; }
.main .block-container { padding-top: 2rem !important; max-width: 1100px; }
section[data-testid="stSidebar"] { background-color: #0C0F1A !important; }

body, p, div, label, li, td, th { font-family: 'DM Sans', sans-serif; color: #B8C8E0 !important; }
h1,h2,h3,h4,h5,h6 { font-family: 'Syne', sans-serif !important; color: #F0F4FF !important; font-weight: 800 !important; }

/* Hide heading action buttons */
[data-testid="stHeadingActionElements"],
[data-testid="stHeadingActionElements"] * { display: none !important; visibility: hidden !important; }

/* Hero banner */
.hero-banner {
    text-align: center;
    background: linear-gradient(160deg, #060D1F 0%, #0A1A3A 40%, #0D2060 80%, #1029A0 100%);
    padding: 52px 32px 48px;
    border-radius: 22px;
    margin-bottom: 36px;
    border: 1px solid #1A3A7A;
    box-shadow: 0 8px 48px rgba(29,64,200,0.22), inset 0 1px 0 rgba(255,255,255,0.05);
    position: relative;
    overflow: hidden;
}
.hero-banner::before {
    content: '';
    position: absolute; top: -50%; left: -50%; width: 200%; height: 200%;
    background: radial-gradient(circle at 55% 35%, rgba(91,141,239,0.09) 0%, transparent 65%);
    pointer-events: none;
}
.hero-banner h1 { margin: 0 0 10px; font-size: 2.6rem; color: #fff !important; letter-spacing: -0.5px; }
.hero-banner p  { margin: 0; font-size: 1.05rem; color: #7A9FCF !important; font-weight: 400; max-width: 620px; margin: 0 auto; line-height: 1.7; }

/* Feature cards */
.feature-card {
    background: linear-gradient(160deg, #0A1225 0%, #0D1A3A 100%);
    border: 1.5px solid #1A2D55;
    border-radius: 18px;
    padding: 36px 28px 32px;
    text-align: center;
    transition: all 0.3s ease;
    box-shadow: 0 4px 24px rgba(0,0,0,0.35);
    height: 100%;
}
.feature-card:hover { border-color: #3B6BE8; box-shadow: 0 8px 36px rgba(59,107,232,0.2); }
.feature-card .card-icon { font-size: 3rem; margin-bottom: 14px; display: block; }
.feature-card h3 { color: #D0E0FF !important; font-size: 1.35rem; margin: 0 0 12px; font-family: 'Syne', sans-serif !important; font-weight: 700 !important; }
.feature-card p  { color: #6A8AAB !important; font-size: 0.92rem; line-height: 1.65; margin: 0; }

/* Sidebar styling */
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #7A9FCF !important; }

.stat-row {
    display: flex; justify-content: center; gap: 48px; margin: 28px 0 4px;
}
.stat-item {
    text-align: center;
}
.stat-item .stat-num { font-family: 'Syne', sans-serif; font-size: 1.4rem; font-weight: 800; color: #5B8DEF !important; }
.stat-item .stat-label { font-size: 0.78rem; color: #4A6380 !important; margin-top: 2px; text-transform: uppercase; letter-spacing: 0.08em; }

/* Link button styling */
.stPageLink > a {
    background: linear-gradient(135deg, #1E3A6E, #2D5BE3) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-family: 'Syne', sans-serif !important;
    box-shadow: 0 4px 20px rgba(45,91,227,0.25) !important;
    transition: all 0.2s ease !important;
    padding: 0.6rem 1.4rem !important;
}
.stPageLink > a:hover { opacity: 0.88 !important; transform: translateY(-1px) !important; }

hr { border-color: #1A2D45 !important; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar branding ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🎯 Smart Placement")
    st.caption("AI-Powered Interview & Resume Platform")
    st.markdown("---")
    st.markdown(
        "**Navigation**\n\n"
        "Use the pages above to switch between\n"
        "Mock Interview and Resume Suite."
    )
    st.markdown("---")
    st.caption("Built for academic demonstration")

# ── Hero Banner ───────────────────────────────────────────────────────────────
st.markdown(
    '<div class="hero-banner">'
    '<h1>🎯 Smart Placement</h1>'
    '<p>Your AI-powered companion for interview preparation and resume building. '
    'Practice mock interviews with real-time voice interaction, build ATS-friendly '
    'resumes, and get instant AI-powered feedback — all in one place.</p>'
    '<div class="stat-row">'
    '<div class="stat-item"><div class="stat-num">AI</div><div class="stat-label">Powered</div></div>'
    '<div class="stat-item"><div class="stat-num">Voice</div><div class="stat-label">Enabled</div></div>'
    '<div class="stat-item"><div class="stat-num">ATS</div><div class="stat-label">Optimized</div></div>'
    '</div>'
    '</div>',
    unsafe_allow_html=True,
)

# ── Feature Cards ─────────────────────────────────────────────────────────────
col1, col2 = st.columns(2, gap="large")

with col1:
    st.markdown(
        '<div class="feature-card">'
        '<span class="card-icon">🎤</span>'
        '<h3>Mock Interview</h3>'
        '<p>Upload your resume, choose an interview mode (Resume-only or Resume + Job Description), '
        'and face AI-generated interview questions. Answer via voice or text, '
        'get real-time feedback, and receive a comprehensive performance report with scores, '
        'strengths, weaknesses, and a personalised learning roadmap.</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.page_link("pages/1_Mock_Interview.py", label="🚀  Start Mock Interview", use_container_width=True)

with col2:
    st.markdown(
        '<div class="feature-card">'
        '<span class="card-icon">📄</span>'
        '<h3>Resume Suite</h3>'
        '<p>Build a professional, ATS-friendly resume from scratch with AI assistance, '
        'modify your existing resume to align with a specific job description, '
        'or rate your resume against a job posting with hybrid keyword-matching '
        'and AI recruiter-style scoring. Download as PDF or Word.</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.page_link("pages/2_Resume_Suite.py", label="📄  Open Resume Suite", use_container_width=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    '<div style="text-align:center;padding:8px 0;">'
    '<p style="font-size:0.82rem;color:#3A536A !important;margin:0;">'
    'Smart Placement · AI-Powered Interview & Resume Platform · College Project</p>'
    '</div>',
    unsafe_allow_html=True,
)
