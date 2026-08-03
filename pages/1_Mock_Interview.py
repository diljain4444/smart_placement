"""
1_Mock_Interview.py
─────────────────────────────────────────────────────────────
Mock Interview page for the Smart Placement unified app.

All session-state keys are prefixed with ``iv_`` so they
never collide with the Resume Suite page.
─────────────────────────────────────────────────────────────
"""

import streamlit as st
import os
import sys
import tempfile
import uuid
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from langgraph.types import Command
import streamlit.components.v1 as components

# Add parent directory to path so we can import backend modules
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from interview_backend import (
    preprocess, preprocess_jd, information_retrival, workflow,
    question_to_audio_b64, text_to_audio_b64, transcribe_audio,
)
from avatar_component_for_interview import render_avatar_panel

# ── Session State Defaults ────────────────────────────────────────────────────
_DEFAULTS = {
    "iv_page": "upload",
    "iv_thread_id": None,
    "iv_extracted_info": None,
    "iv_current_question": None,
    "iv_interview_complete": False,
    "iv_review_final": None,
    "iv_interview_started": False,
    "iv_answer_key": 0,
    "iv_last_feedback": None,
    "iv_show_done_banner": False,
    "iv_audio_answer": None,
    "iv_voice_mode": True,
    "iv_current_audio_b64": "",
    "iv_current_feedback_b64": "",
    "iv_interview_mode": "resume_only",
    "iv_jd_text": "",
    "iv_jd_context": "",
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── LangGraph Helpers ─────────────────────────────────────────────────────────
def _cfg():
    return {"configurable": {"thread_id": st.session_state.iv_thread_id}}


def get_current_question():
    try:
        gs = workflow.get_state(_cfg())
        for task in gs.tasks:
            if hasattr(task, "interrupts") and task.interrupts:
                return task.interrupts[0].value
    except Exception:
        pass
    return None


def get_graph_values():
    try:
        return workflow.get_state(_cfg()).values
    except Exception:
        return {}


# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500;600&display=swap');
@import url('https://fonts.googleapis.com/icon?family=Material+Icons|Material+Icons+Sharp|Material+Icons+Outlined');

html, body { background-color: #060810 !important; }
.stApp { background-color: #060810 !important; font-family: 'DM Sans', sans-serif !important; }
.main { background-color: #060810 !important; }
.main .block-container { background-color: #060810 !important; padding-top: 1.2rem !important; max-width: 1200px; }
section[data-testid="stSidebar"] { background-color: #0C0F1A !important; }

body, p, div, label, input, textarea, select, button, li, td, th { font-family: 'DM Sans', sans-serif; }
h1,h2,h3,h4,h5,h6 { font-family: 'Syne', sans-serif !important; color: #F0F4FF !important; font-weight: 800 !important; }

body, p, div, li, td, th { color: #B8C8E0 !important; }
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li { color: #B8C8E0 !important; font-weight: 400 !important; }

[data-testid="stTextArea"] label { color: #7A8FA8 !important; font-weight: 600 !important; font-size: 0.82rem !important; letter-spacing: 0.06em; text-transform: uppercase; }
[data-testid="stTextArea"] textarea {
    background-color: #0C1524 !important; color: #F0F4FF !important;
    border: 1px solid #1A2D45 !important; border-radius: 12px !important;
    caret-color: #5B8DEF !important;
}
[data-testid="stTextArea"] textarea:focus { border-color: #5B8DEF !important; box-shadow: 0 0 0 3px rgba(91,141,239,0.15) !important; }
[data-testid="stTextArea"] textarea::placeholder { color: #2A3D55 !important; }

[data-testid="stFileUploader"], [data-testid="stFileUploaderDropzone"] {
    background-color: #0C1524 !important; border: 2px dashed #1A2D45 !important; border-radius: 14px !important;
}
[data-testid="stFileUploader"] *, [data-testid="stFileUploaderDropzone"] * { color: #4A6380 !important; }
[data-testid="stFileUploaderDropzone"]:hover { border-color: #5B8DEF !important; }
[data-testid="stFileUploaderFile"] { background-color: #0F1E35 !important; border: 1px solid #1A2D45 !important; border-radius: 8px !important; }
[data-testid="stFileUploaderFile"] * { color: #B8C8E0 !important; }

[data-testid="stExpander"] { background-color: #0C1524 !important; border: 1px solid #1A2D45 !important; border-radius: 12px !important; }
[data-testid="stExpander"] summary { background-color: #0C1524 !important; }
[data-testid="stExpander"] summary p, [data-testid="stExpander"] summary span { color: #B8C8E0 !important; }
[data-testid="stExpanderDetails"] { background-color: #0C1524 !important; }

[data-testid="stAlert"], div[role="alert"] { background-color: #0C1524 !important; border: 1px solid #1A2D45 !important; border-radius: 12px !important; }
[data-testid="stAlert"] * { color: #B8C8E0 !important; }

.stButton button {
    background: linear-gradient(135deg, #1E3A6E, #2D5BE3) !important;
    color: #fff !important; border: none !important; border-radius: 10px !important;
    font-weight: 700 !important; font-family: 'Syne', sans-serif !important;
    letter-spacing: 0.02em;
    box-shadow: 0 4px 20px rgba(45,91,227,0.25) !important;
    transition: all 0.2s ease !important;
}
.stButton button:hover { opacity: 0.88 !important; transform: translateY(-1px) !important; }
[data-testid="stBaseButton-secondary"] button {
    background: #0C1524 !important; color: #5B8DEF !important; border: 1.5px solid #1A3A6E !important;
}

[data-testid="stSpinner"] p { color: #7A8FA8 !important; }
hr { border-color: #1A2D45 !important; }

[data-testid="stHeadingActionElements"],
[data-testid="stHeadingActionElements"] *,
[data-testid="stHeadingWithActionElements"] a,
[data-testid="stHeadingWithActionElements"] button,
[data-testid="stHeadingWithActionElements"] svg,
.stHeading a, .stHeading button,
h1 a, h2 a, h3 a, h4 a, h5 a, h6 a,
button[title*="clipboard"], button[aria-label*="clipboard"],
button[title*="link"], button[aria-label*="link"] {
    display: none !important; visibility: hidden !important;
    width: 0 !important; height: 0 !important; overflow: hidden !important;
}

[data-testid="stExpander"] summary span,
[data-testid="stExpander"] summary svg { flex-shrink: 0; }

.main-header {
    text-align: center;
    background: linear-gradient(160deg, #060D1F 0%, #0A1A3A 40%, #0D2060 80%, #1029A0 100%);
    padding: 36px 28px; border-radius: 20px; margin-bottom: 28px;
    border: 1px solid #1A3A7A;
    box-shadow: 0 8px 40px rgba(29,64,200,0.20), inset 0 1px 0 rgba(255,255,255,0.05);
    position: relative; overflow: hidden;
}
.main-header::before {
    content: ''; position: absolute; top: -50%; left: -50%; width: 200%; height: 200%;
    background: radial-gradient(circle at 60% 40%, rgba(91,141,239,0.08) 0%, transparent 60%);
    pointer-events: none;
}
.main-header h1 { margin: 0 0 8px 0; font-size: 2.2rem; font-weight: 800; color: #fff !important; letter-spacing: -0.5px; }
.main-header p { margin: 0; font-size: 0.95rem; color: #7A9FCF !important; font-weight: 400; }

.step-active { background: linear-gradient(135deg, #1E3A8A, #2D5BE3); color: #fff; text-align: center; padding: 12px 6px; border-radius: 12px; font-weight: 700; font-size: 0.85rem; font-family: 'Syne', sans-serif; box-shadow: 0 4px 16px rgba(45,91,227,0.35); }
.step-inactive { background: #0C1524; color: #2E4060; text-align: center; padding: 12px 6px; border-radius: 12px; font-weight: 600; font-size: 0.85rem; border: 1px solid #1A2D45; }
.step-done { background: #0C1524; color: #4A7AB5; text-align: center; padding: 12px 6px; border-radius: 12px; font-weight: 600; font-size: 0.85rem; border: 1px solid #1A3A6E; cursor: pointer; }

.question-card { background: linear-gradient(135deg, #080E1E 0%, #0D1A3A 100%); border-left: 4px solid #3B6BE8; padding: 22px 26px; border-radius: 14px; font-size: 16px; font-weight: 500; line-height: 1.7; color: #D8E8FF !important; margin-bottom: 20px; border-top: 1px solid #1A3060; border-right: 1px solid #1A3060; border-bottom: 1px solid #1A3060; box-shadow: 0 4px 24px rgba(29,64,200,0.15); }

.score-card { background: #0C1524; border: 1px solid #1A2D45; border-radius: 16px; padding: 22px 16px; text-align: center; box-shadow: 0 2px 12px rgba(0,0,0,0.30); }
.score-card .sc-label { font-size: 0.72rem; color: #4A6380; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; }
.score-card .sc-value { font-size: 2.4rem; font-weight: 800; color: #5B8DEF; margin: 8px 0 6px; font-family: 'Syne', sans-serif; }
.sc-badge { font-size: 0.70rem; font-weight: 700; padding: 3px 14px; border-radius: 20px; display: inline-block; }
.badge-green { background: #051A10; color: #4ADE80; border: 1px solid #166534; }
.badge-amber { background: #1A1000; color: #FCD34D; border: 1px solid #92400E; }
.badge-red   { background: #1A0505; color: #F87171; border: 1px solid #7F1D1D; }

.sec-hdr { font-size: 0.78rem; font-weight: 700; color: #3B6BE8; border-bottom: 1px solid #1A2D45; padding-bottom: 8px; margin: 22px 0 14px; letter-spacing: 0.12em; text-transform: uppercase; font-family: 'Syne', sans-serif; }

.strength-item { background: #051A10; border-left: 3px solid #22C55E; padding: 10px 16px; border-radius: 10px; margin: 6px 0; font-size: 0.91rem; color: #86EFAC !important; border-top: 1px solid #14532D; border-right: 1px solid #14532D; border-bottom: 1px solid #14532D; }
.weakness-item { background: #1A0E00; border-left: 3px solid #F59E0B; padding: 10px 16px; border-radius: 10px; margin: 6px 0; font-size: 0.91rem; color: #FCD34D !important; border-top: 1px solid #451A03; border-right: 1px solid #451A03; border-bottom: 1px solid #451A03; }
.rec-item { background: #050F1A; border-left: 3px solid #3B82F6; padding: 10px 16px; border-radius: 10px; margin: 6px 0; font-size: 0.91rem; color: #93C5FD !important; border-top: 1px solid #1E3A5F; border-right: 1px solid #1E3A5F; border-bottom: 1px solid #1E3A5F; }

.topic-card { background: #0C1524; border-radius: 12px; padding: 14px 18px; margin: 10px 0; border: 1px solid #1A2D45; }
.topic-card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.topic-name { color: #D0E0FF; font-weight: 700; font-size: 0.90rem; }
.topic-score { font-weight: 800; font-size: 1.05rem; font-family: 'Syne', sans-serif; }
.topic-bar-bg { background: #1A2D45; border-radius: 6px; height: 7px; width: 100%; }
.topic-bar-fill { height: 7px; border-radius: 6px; }
.topic-grade { color: #4A6380; font-size: 0.74rem; margin-top: 6px; font-weight: 600; }

.feedback-card {
    background: linear-gradient(135deg, #030E07 0%, #051A0C 100%);
    border-left: 4px solid #22C55E; padding: 16px 22px 18px; border-radius: 14px;
    font-size: 14.5px; line-height: 1.75; color: #86EFAC !important; margin-bottom: 20px;
    border-top: 1px solid #14532D; border-right: 1px solid #14532D; border-bottom: 1px solid #14532D;
}
.feedback-label { font-size: 0.68rem; font-weight: 800; color: #22C55E !important; text-transform: uppercase; letter-spacing: 0.12em; margin-bottom: 8px; display: block; }

.done-banner {
    background: linear-gradient(135deg, #030E07 0%, #051A0C 60%, #072010 100%);
    border: 1.5px solid #22C55E; border-radius: 20px; padding: 40px 32px; text-align: center;
    box-shadow: 0 8px 40px rgba(34,197,94,0.18); margin: 24px 0;
}
.done-banner h2 { color: #4ADE80 !important; font-size: 1.9rem; font-weight: 800; margin: 0 0 12px 0; }
.done-banner p  { color: #86EFAC !important; font-size: 1rem; margin: 0; line-height: 1.7; }

.mode-toggle { display: flex; gap: 10px; margin-bottom: 16px; }
</style>
""", unsafe_allow_html=True)


# ── Navigation Bar ────────────────────────────────────────────────────────────
def render_nav():
    steps = [
        ("📄 Resume Upload", "upload",    True),
        ("🎤 Interview",     "interview", st.session_state.iv_interview_started and not st.session_state.iv_interview_complete),
        ("📊 Report",        "report",    st.session_state.iv_interview_complete),
    ]
    cols = st.columns(3)
    for col, (label, key, accessible) in zip(cols, steps):
        if st.session_state.iv_page == key:
            col.markdown(f'<div class="step-active">{label}</div>', unsafe_allow_html=True)
        elif accessible:
            if col.button(label, key=f"iv_nav_{key}", use_container_width=True):
                st.session_state.iv_page = key
                st.rerun()
        else:
            col.markdown(f'<div class="step-inactive">{label}</div>', unsafe_allow_html=True)
    st.markdown("---")


# ═══════════════════════════════════════════════════════════════════════════════
# VOICE INTERVIEW — AUDIO PLAYER
# ═══════════════════════════════════════════════════════════════════════════════

def play_audio_sequence(feedback_b64: str, question_b64: str) -> None:
    if not feedback_b64 and not question_b64:
        return
    html_code = f"""<!DOCTYPE html>
<html><head><style>body{{margin:0;padding:0;background:transparent;}}</style></head>
<body><script>
(function() {{
  var fb64 = "{feedback_b64}";
  var qb64 = "{question_b64}";
  function playB64(b64, onEnd) {{
    if (!b64) {{ if (onEnd) onEnd(); return; }}
    var a = new Audio("data:audio/mp3;base64," + b64);
    if (onEnd) a.addEventListener('ended', onEnd);
    a.play().catch(function() {{ if (onEnd) onEnd(); }});
  }}
  playB64(fb64, function() {{ playB64(qb64, null); }});
}})();
</script></body></html>"""
    components.html(html_code, height=0)


def play_question_audio(audio_b64: str) -> None:
    play_audio_sequence("", audio_b64)


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — RESUME UPLOAD
# ═══════════════════════════════════════════════════════════════════════════════
def page_upload():
    st.markdown(
        '<div class="main-header">'
        "<h1>🎯 AI Interview System</h1>"
        "<p>Upload your resume · Answer questions by voice · Get your detailed report</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    render_nav()

    left, right = st.columns([1.2, 0.8], gap="large")

    with left:
        # ── Interview Mode Selector ─────────────────────────────────────────
        st.subheader("🧭 Interview Mode")
        mode_choice = st.radio(
            "Choose how questions should be generated",
            options=["Resume Only", "Resume + Job Description"],
            horizontal=True,
            index=0 if st.session_state.iv_interview_mode == "resume_only" else 1,
            key="iv_mode_selector",
            label_visibility="collapsed",
        )
        st.session_state.iv_interview_mode = (
            "resume_only" if mode_choice == "Resume Only" else "resume_jd"
        )

        if st.session_state.iv_interview_mode == "resume_jd":
            st.session_state.iv_jd_text = st.text_area(
                "Paste the Job Description",
                value=st.session_state.iv_jd_text,
                height=170,
                placeholder="Paste the full job description here (required skills, responsibilities, experience level, etc.)…",
                key="iv_jd_textarea",
            )

        st.subheader("📄 Upload Your Resume")
        uploaded = st.file_uploader(
            "Supported formats: PDF, DOCX",
            type=["pdf", "docx"],
            help="Your resume is only used locally for this session.",
            key="iv_file_uploader",
        )

        if uploaded:
            st.success(f"✅ Ready: **{uploaded.name}**")

            jd_missing = (
                st.session_state.iv_interview_mode == "resume_jd"
                and not st.session_state.iv_jd_text.strip()
            )
            if jd_missing:
                st.warning("⚠️ Please paste the Job Description above to continue in Resume + Job Description mode.")

            if st.button("🔍 Process Resume", type="primary", use_container_width=True, disabled=jd_missing):
                with st.spinner("Extracting education, skills, and projects from your resume…"):
                    suffix = "." + uploaded.name.rsplit(".", 1)[-1].lower()
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        tmp.write(uploaded.getbuffer())
                        tmp_path = tmp.name

                    context = preprocess(tmp_path)
                    info = information_retrival(context)
                    st.session_state.iv_extracted_info = info

                    if st.session_state.iv_interview_mode == "resume_jd":
                        st.session_state.iv_jd_context = preprocess_jd(st.session_state.iv_jd_text)
                    else:
                        st.session_state.iv_jd_context = ""
                st.rerun()

        # Mode toggle + Start Interview
        info = st.session_state.iv_extracted_info
        if info:
            st.markdown("---")
            col_v, col_t = st.columns(2)
            with col_v:
                if st.button("🎤 Voice Mode", use_container_width=True,
                             type="primary" if st.session_state.iv_voice_mode else "secondary"):
                    st.session_state.iv_voice_mode = True
                    st.rerun()
            with col_t:
                if st.button("⌨️ Text Mode", use_container_width=True,
                             type="secondary" if st.session_state.iv_voice_mode else "primary"):
                    st.session_state.iv_voice_mode = False
                    st.rerun()

            mode_label = "🎤 Voice Interview" if st.session_state.iv_voice_mode else "⌨️ Text Interview"
            st.info(f"Selected: **{mode_label}**")

            if st.button("🚀 Start Interview", type="primary", use_container_width=True):
                with st.spinner("Initialising your interview session…"):
                    thread_id = str(uuid.uuid4())
                    st.session_state.iv_thread_id = thread_id
                    cfg = {"configurable": {"thread_id": thread_id}}

                    workflow.invoke(
                        {
                            "education": info.education,
                            "skills": info.skills,
                            "projects": info.projects,
                            "interview_mode": st.session_state.iv_interview_mode,
                            "jd_context": st.session_state.get("iv_jd_context", ""),
                            "history": [],
                            "current_depth": 0,
                            "covered_topics": [],
                            "follow_up_required": False,
                            "over": False,
                        },
                        config=cfg,
                    )

                    question = get_current_question()
                    st.session_state.iv_current_question = question

                    if st.session_state.iv_voice_mode and question:
                        with st.spinner("Generating audio for first question…"):
                            st.session_state.iv_current_audio_b64 = question_to_audio_b64(question)
                    else:
                        st.session_state.iv_current_audio_b64 = ""

                    st.session_state.iv_interview_started = True
                    st.session_state.iv_page = "interview"
                st.rerun()

    with right:
        info = st.session_state.iv_extracted_info
        if info:
            st.subheader("📋 Extracted Profile")

            with st.expander("🎓 Education", expanded=True):
                st.write(info.education if info.education else "_Not found_")

            with st.expander("🛠️ Skills", expanded=True):
                if info.skills:
                    for s in info.skills:
                        st.markdown(f"• {s}")
                else:
                    st.write("_No skills found_")

            with st.expander("💼 Projects", expanded=True):
                if info.projects:
                    for p in info.projects:
                        st.markdown(f"• {p}")
                else:
                    st.write("_No projects found_")

            if st.session_state.iv_interview_mode == "resume_jd" and st.session_state.get("iv_jd_context"):
                with st.expander("🧭 Job Description (used for questions)", expanded=False):
                    st.write(st.session_state.iv_jd_context)
        else:
            st.info("👆 Upload and process your resume to see the extracted profile here.")


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — INTERVIEW
# ═══════════════════════════════════════════════════════════════════════════════
def page_interview():
    st.markdown(
        '<div class="main-header"><h1>🎤 Interview in Progress</h1>'
        '<p>Answer naturally — your voice is captured and transcribed automatically</p></div>',
        unsafe_allow_html=True,
    )
    render_nav()

    # ── Done banner ───────────────────────────────────────────────────────────
    if st.session_state.get("iv_show_done_banner"):
        st.markdown(
            '<div class="done-banner">'
            '<h2>🎉 Interview Complete!</h2>'
            '<p>Great effort! Your AI-powered performance report has been generated.<br>'
            'Click below to view your detailed analysis, scores, strengths, weaknesses, and personalised learning roadmap.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        _, btn_col, _ = st.columns([1.5, 1, 1.5])
        with btn_col:
            if st.button("📊 View My Report →", type="primary", use_container_width=True):
                st.session_state.iv_show_done_banner = False
                st.session_state.iv_page = "report"
                st.rerun()
        return

    cfg = _cfg()
    gv = get_graph_values()
    topics_covered = list(set(gv.get("covered_topics", [])))
    n_topics = len(topics_covered)
    can_end   = n_topics >= 3

    # ── Pre-compute avatar state ──────────────────────────────────────────────
    _has_audio = bool(
        st.session_state.get("iv_current_audio_b64")
        or st.session_state.get("iv_current_feedback_b64")
    )
    if _has_audio:
        _istate = "new_final_question"
        _fb64   = st.session_state.iv_current_feedback_b64
        _qb64   = st.session_state.iv_current_audio_b64
        st.session_state.iv_current_audio_b64   = ""
        st.session_state.iv_current_feedback_b64 = ""
    else:
        _istate = "new_waiting"
        _fb64   = ""
        _qb64   = ""

    # ── Two-column layout ─────────────────────────────────────────────────────
    left_col, right_col = st.columns([5, 7], gap="large")

    with left_col:
        render_avatar_panel(
            state=_istate,
            feedback_b64=_fb64,
            question_b64=_qb64,
            height=520,
        )

    with right_col:
        question = st.session_state.iv_current_question or "Preparing your next question…"
        st.markdown(
            f'<div class="question-card">❓ &nbsp;{question}</div>',
            unsafe_allow_html=True,
        )

        # ── VOICE MODE ────────────────────────────────────────────────────────
        if st.session_state.iv_voice_mode:
            st.markdown(
                '<div style="margin:14px 0 6px;font-size:0.78rem;font-weight:700;'
                'color:#3B6BE8;text-transform:uppercase;letter-spacing:0.1em;">'
                '🎙️ Record Your Answer</div>',
                unsafe_allow_html=True,
            )

            audio_data = st.audio_input(
                "Click the microphone to start recording, click again to stop",
                key=f"iv_audio_{st.session_state.iv_answer_key}",
            )

            if audio_data is not None:
                with st.spinner("🔄 Transcribing your voice answer…"):
                    transcript = transcribe_audio(audio_data.read())

                if transcript:
                    st.success(f"📝 **Transcribed:** {transcript}")
                    _submit_answer(transcript, can_end=False)
                else:
                    st.warning("⚠️ Could not transcribe audio. Please try again or switch to text mode.")

            # Progress indicator
            if n_topics > 0:
                st.markdown("<br>", unsafe_allow_html=True)
                prog_cols = st.columns(5)
                for i, col in enumerate(prog_cols):
                    if i < n_topics:
                        col.markdown(
                            '<div style="height:6px;background:linear-gradient(90deg,#1E3A8A,#3B6BE8);border-radius:3px;"></div>',
                            unsafe_allow_html=True
                        )
                    else:
                        col.markdown(
                            '<div style="height:6px;background:#1A2D45;border-radius:3px;"></div>',
                            unsafe_allow_html=True
                        )
                st.caption(f"Topics covered: {n_topics} / 5")

            # Manual end option
            st.markdown("---")
            end_col1, end_col2 = st.columns([3, 1])
            with end_col2:
                if st.button(
                    "🏁 End Interview",
                    disabled=not can_end,
                    use_container_width=True,
                    help="Cover at least 3 topics to unlock",
                ):
                    with st.spinner("Generating your report…"):
                        workflow.update_state(cfg, {"over": True})
                        last_ans = gv.get("user_answer", "End interview")
                        workflow.invoke(Command(resume=last_ans), config=cfg)
                    gs = workflow.get_state(cfg)
                    review = gs.values.get("review_final")
                    if review:
                        st.session_state.iv_review_final = review
                        st.session_state.iv_interview_complete = True
                        st.session_state.iv_show_done_banner = True
                        st.session_state.iv_last_feedback = None
                    st.rerun()

            if not can_end:
                st.caption(f"💡 Cover {3 - n_topics} more topic(s) to unlock end interview")

        # ── TEXT MODE ─────────────────────────────────────────────────────────
        else:
            answer = st.text_area(
                "Your Answer:",
                height=160,
                placeholder="Type your detailed answer here…",
                key=f"iv_answer_{st.session_state.iv_answer_key}",
            )
            answer_ready = bool(answer.strip())

            col_submit, col_end = st.columns([2, 1])
            with col_submit:
                submit = st.button(
                    "📨 Submit Answer",
                    type="primary",
                    use_container_width=True,
                    disabled=not answer_ready,
                )
            with col_end:
                end_btn = st.button(
                    "🏁 End & Get Report",
                    type="secondary",
                    use_container_width=True,
                    disabled=not (can_end and answer_ready),
                    help="Cover at least 3 topics to unlock",
                )

            if not can_end:
                st.info(f"💡 Cover **{3 - n_topics}** more topic(s) to unlock the final report.")

            if submit and answer_ready:
                _submit_answer(answer.strip(), can_end=False)

            if end_btn and answer_ready and can_end:
                _submit_answer(answer.strip(), can_end=True)

        # ── Conversation history ──────────────────────────────────────────────
        history = gv.get("history", [])
        if history:
            st.markdown("---")
            with st.expander(f"📜 Conversation History ({len(history)} exchange{'s' if len(history) != 1 else ''})", expanded=False):
                for i, entry in enumerate(history, 1):
                    st.markdown(f"**{i}.**")
                    st.code(entry, language=None)


def _submit_answer(answer: str, can_end: bool):
    """Shared submit logic for both voice and text modes."""
    cfg = _cfg()

    if can_end:
        with st.spinner("Generating your report — this may take 30–60 seconds…"):
            workflow.update_state(cfg, {"over": True})
            workflow.invoke(Command(resume=answer), config=cfg)
            st.session_state.iv_answer_key += 1

        gs = workflow.get_state(cfg)
        review = gs.values.get("review_final")
        if review:
            st.session_state.iv_review_final = review
            st.session_state.iv_interview_complete = True
            st.session_state.iv_show_done_banner = True
            st.session_state.iv_last_feedback = None
        else:
            st.error("❌ Report generation failed. Please try again.")
        st.rerun()

    else:
        with st.spinner("Evaluating your answer…"):
            workflow.invoke(Command(resume=answer), config=cfg)
            st.session_state.iv_answer_key += 1

        gs = workflow.get_state(cfg)
        st.session_state.iv_last_feedback = gs.values.get("feedback") or None

        if not gs.next:
            review = gs.values.get("review_final")
            if review is not None:
                st.session_state.iv_review_final = review
                st.session_state.iv_interview_complete = True
                st.session_state.iv_show_done_banner = True
                st.session_state.iv_last_feedback = None
            else:
                st.error("❌ Report generation failed.")
        else:
            next_q = None
            for task in gs.tasks:
                if hasattr(task, "interrupts") and task.interrupts:
                    next_q = task.interrupts[0].value
                    break
            st.session_state.iv_current_question = next_q

            # Pre-generate feedback audio + next question audio
            if st.session_state.iv_voice_mode:
                feedback_text = st.session_state.iv_last_feedback or ""
                with st.spinner("Preparing audio…"):
                    st.session_state.iv_current_feedback_b64 = text_to_audio_b64(feedback_text) if feedback_text else ""
                    st.session_state.iv_current_audio_b64 = question_to_audio_b64(next_q) if next_q else ""
            else:
                st.session_state.iv_current_feedback_b64 = ""
                st.session_state.iv_current_audio_b64 = ""

        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — REPORT DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
def page_report():
    st.markdown(
        '<div class="main-header"><h1>📊 Interview Performance Report</h1>'
        '<p>Your detailed AI-powered analysis</p></div>',
        unsafe_allow_html=True,
    )
    render_nav()

    if not st.session_state.iv_interview_complete or not st.session_state.iv_review_final:
        st.error(
            "⚠️ Report not available yet. Complete the interview (minimum 3 topics) before viewing."
        )
        gc1, gc2 = st.columns(2)
        with gc1:
            if st.button("← Back to Interview", use_container_width=True):
                st.session_state.iv_page = "interview"
                st.rerun()
        with gc2:
            if st.button("← Back to Upload", use_container_width=True):
                st.session_state.iv_page = "upload"
                st.rerun()
        return

    r = st.session_state.iv_review_final

    def _badge(v):
        if v >= 7:   return "badge-green", "Strong"
        elif v >= 5: return "badge-amber", "Average"
        else:        return "badge-red",   "Needs Work"

    # ── Score cards ────────────────────────────────────────────────────────────
    st.markdown('<p class="sec-hdr">🏆 Overall Performance</p>', unsafe_allow_html=True)
    sc1, sc2, sc3 = st.columns(3, gap="medium")
    for col, lbl, val in [
        (sc1, "Overall Rating",  r.overall_rating),
        (sc2, "Communication",   r.communication_score),
        (sc3, "Confidence",      r.confidence_score),
    ]:
        bc, bt = _badge(val)
        col.markdown(
            f'<div class="score-card">'
            f'<div class="sc-label">{lbl}</div>'
            f'<div class="sc-value">{val:.1f}'
            f'<span style="font-size:1rem;color:#2E4060;font-weight:500">/10</span></div>'
            f'<span class="sc-badge {bc}">{bt}</span></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Charts ─────────────────────────────────────────────────────────────────
    ch_l, ch_r = st.columns([3, 2], gap="large")

    with ch_l:
        st.markdown('<p class="sec-hdr">📊 Topic Ratings</p>', unsafe_allow_html=True)
        if r.topic:
            for t in r.topic:
                val = float(t.rating)
                pct = int(val * 10)
                if val >= 7:   clr, grade = "#22C55E", "Strong"
                elif val >= 5: clr, grade = "#F59E0B", "Average"
                else:          clr, grade = "#EF4444", "Needs Work"
                st.markdown(
                    f"""<div class="topic-card">
                        <div class="topic-card-header">
                            <span class="topic-name">{t.topic_name}</span>
                            <span class="topic-score" style="color:{clr};">{val:.1f} / 10</span>
                        </div>
                        <div class="topic-bar-bg">
                            <div class="topic-bar-fill" style="width:{pct}%;background:{clr};"></div>
                        </div>
                        <div class="topic-grade">{grade}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )

    with ch_r:
        st.markdown('<p class="sec-hdr">📈 Score Summary</p>', unsafe_allow_html=True)
        s_labels = ["Overall", "Comms", "Confidence"]
        s_values = [r.overall_rating, r.communication_score, r.confidence_score]
        s_colors = ["#3B6BE8", "#F59E0B", "#22C55E"]

        fig2, ax2 = plt.subplots(figsize=(3.2, 3.0))
        fig2.patch.set_facecolor("#0C1524")
        ax2.set_facecolor("#0C1524")
        b2 = ax2.bar(s_labels, s_values, color=s_colors, width=0.4, edgecolor="#0C1524", linewidth=0.8)
        ax2.set_ylim(0, 12)
        ax2.set_ylabel("Score", fontsize=8.5, color="#4A6380")
        ax2.tick_params(labelsize=8.5, colors="#4A6380")
        for sp in ["top", "right"]: ax2.spines[sp].set_visible(False)
        ax2.spines["left"].set_color("#1A2D45")
        ax2.spines["bottom"].set_color("#1A2D45")
        ax2.axhline(7, color="#22C55E", linestyle="--", alpha=0.35, lw=0.9)
        ax2.axhline(5, color="#F59E0B", linestyle="--", alpha=0.35, lw=0.9)
        for bar, val in zip(b2, s_values):
            ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2,
                     f"{val:.1f}", ha="center", fontsize=9, fontweight="bold", color="#D0E0FF")
        fig2.tight_layout(pad=0.7)
        st.pyplot(fig2, use_container_width=True)
        plt.close(fig2)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Topic analysis ─────────────────────────────────────────────────────────
    if r.topic:
        st.markdown('<p class="sec-hdr">🔍 Topic Analysis</p>', unsafe_allow_html=True)
        for t in r.topic:
            icon = "🟢" if t.rating >= 7 else "🟡" if t.rating >= 5 else "🔴"
            with st.expander(f"{icon}  {t.topic_name}  —  {t.rating:.1f} / 10", expanded=False):
                st.markdown(f"💡 **Key Gap:** {t.weakness}")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Strengths & Weaknesses ─────────────────────────────────────────────────
    sw_l, sw_r = st.columns(2, gap="large")
    with sw_l:
        st.markdown('<p class="sec-hdr">💪 Strengths</p>', unsafe_allow_html=True)
        for s in r.overall_strength:
            st.markdown(f'<div class="strength-item">✅ {s}</div>', unsafe_allow_html=True)
    with sw_r:
        st.markdown('<p class="sec-hdr">⚠️ Areas to Improve</p>', unsafe_allow_html=True)
        for w in r.overall_weakness:
            st.markdown(f'<div class="weakness-item">⚡ {w}</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Recommendations ────────────────────────────────────────────────────────
    st.markdown('<p class="sec-hdr">💡 Top Recommendations</p>', unsafe_allow_html=True)
    for i, rec in enumerate(r.top_recommendation, 1):
        st.markdown(f'<div class="rec-item">🔹 <b>{i}.</b> {rec}</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Learning Roadmap ───────────────────────────────────────────────────────
    st.markdown('<p class="sec-hdr">🗺️ Personalised Learning Roadmap</p>', unsafe_allow_html=True)
    for rm in r.road_map:
        with st.expander(f"📚  {rm.topic_name}  ·  ⏱ {rm.duration_it_takes}", expanded=False):
            rc, rr = st.columns(2, gap="medium")
            with rc:
                st.markdown("**Concepts to Learn:**")
                for c in rm.concepts_to_learn:
                    st.markdown(f"• {c}")
            with rr:
                st.markdown("**Best Resources:**")
                for res in rm.best_resource:
                    st.markdown(f"• {res}")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Reset ──────────────────────────────────────────────────────────────────
    _, btn_col, _ = st.columns([2, 1, 2])
    with btn_col:
        if st.button("🔄 Start a New Interview", type="primary", use_container_width=True):
            for k in list(st.session_state.keys()):
                if k.startswith("iv_"):
                    del st.session_state[k]
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTER
# ═══════════════════════════════════════════════════════════════════════════════
_page = st.session_state.iv_page

if _page == "upload":
    page_upload()
elif _page == "interview":
    if not st.session_state.iv_interview_started:
        st.session_state.iv_page = "upload"
        st.rerun()
    else:
        page_interview()
elif _page == "report":
    page_report()
