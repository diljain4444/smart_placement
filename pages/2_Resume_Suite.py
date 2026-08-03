"""
2_Resume_Suite.py
────────────────────────────────────────────────────────────
Resume Suite page for the Smart Placement unified app.

Three tools in one tab-based interface:
  1) Resume Builder   — build from scratch
  2) Resume Modifier  — rewrite for a target JD
  3) Resume Rater     — hybrid keyword + AI scoring
────────────────────────────────────────────────────────────
"""

import re
import os
import sys

import streamlit as st
from pydantic import ValidationError

# Add parent directory to path so we can import backend modules
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from resume_backend import (
    generate_resume,
    generate_modified_resume,
    generate_modified_resume_from_text,
    rate_resume,
    resume_to_docx,
    resume_to_pdf,
    extract_text_from_upload,
    extract_resume_content,
)
import resume_validators as v

# ── Dark theme CSS (matches main app styling) ─────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500;600&display=swap');

html, body, .stApp, .main { background-color: #060810 !important; }
.main .block-container { padding-top: 1.5rem !important; max-width: 900px; }
section[data-testid="stSidebar"] { background-color: #0C0F1A !important; }

body, p, div, label, input, textarea, select, button, li, td, th { font-family: 'DM Sans', sans-serif; }
h1,h2,h3,h4,h5,h6 { font-family: 'Syne', sans-serif !important; color: #F0F4FF !important; font-weight: 800 !important; }
body, p, div, li, td, th { color: #B8C8E0 !important; }
[data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li { color: #B8C8E0 !important; }

[data-testid="stTextArea"] label { color: #7A8FA8 !important; font-weight: 600 !important; font-size: 0.82rem !important; }
[data-testid="stTextArea"] textarea {
    background-color: #0C1524 !important; color: #F0F4FF !important;
    border: 1px solid #1A2D45 !important; border-radius: 12px !important;
}
[data-testid="stTextInput"] input {
    background-color: #0C1524 !important; color: #F0F4FF !important;
    border: 1px solid #1A2D45 !important; border-radius: 10px !important;
}
[data-testid="stTextInput"] label { color: #7A8FA8 !important; font-weight: 600 !important; font-size: 0.82rem !important; }

[data-testid="stFileUploader"], [data-testid="stFileUploaderDropzone"] {
    background-color: #0C1524 !important; border: 2px dashed #1A2D45 !important; border-radius: 14px !important;
}
[data-testid="stFileUploader"] *, [data-testid="stFileUploaderDropzone"] * { color: #4A6380 !important; }

[data-testid="stExpander"] { background-color: #0C1524 !important; border: 1px solid #1A2D45 !important; border-radius: 12px !important; }
[data-testid="stExpander"] summary { background-color: #0C1524 !important; }
[data-testid="stExpander"] summary p, [data-testid="stExpander"] summary span { color: #B8C8E0 !important; }

.stButton button {
    background: linear-gradient(135deg, #1E3A6E, #2D5BE3) !important;
    color: #fff !important; border: none !important; border-radius: 10px !important;
    font-weight: 700 !important; font-family: 'Syne', sans-serif !important;
    box-shadow: 0 4px 20px rgba(45,91,227,0.25) !important;
}
.stButton button:hover { opacity: 0.88 !important; }

[data-testid="stAlert"], div[role="alert"] { background-color: #0C1524 !important; border: 1px solid #1A2D45 !important; border-radius: 12px !important; }
hr { border-color: #1A2D45 !important; }

/* Tab styling */
.stTabs [data-baseweb="tab-list"] { gap: 8px; background-color: #0C1524; border-radius: 12px; padding: 4px; }
.stTabs [data-baseweb="tab"] {
    background-color: transparent; border-radius: 8px; color: #7A8FA8;
    font-family: 'Syne', sans-serif; font-weight: 600; padding: 10px 20px;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #1E3A6E, #2D5BE3) !important;
    color: #fff !important;
}
.stTabs [data-baseweb="tab-panel"] { padding-top: 1.5rem; }

/* Hide heading action buttons */
[data-testid="stHeadingActionElements"] { display: none !important; }

/* Download button styling */
.stDownloadButton button {
    background: linear-gradient(135deg, #164430, #1D7A4E) !important;
    color: #fff !important; border: none !important; border-radius: 10px !important;
    font-weight: 700 !important;
}
</style>
""", unsafe_allow_html=True)


# =================================================================
# Helpers
# =================================================================
def show_hint(ok: bool, msg: str):
    """Small inline red warning shown under a field, only when invalid."""
    if not ok and msg:
        st.caption(f":red[⚠ {msg}]")


def check_required_then_min_length(value: str, min_len: int, field_name: str):
    """required() short-circuits before min_length() so an EMPTY field is
    reported as 'required', not silently accepted (min_length() alone
    treats an empty string as valid, since it only checks length when the
    field is non-empty — that's correct for optional fields, but wrong
    for JD / resume-text boxes which are mandatory)."""
    ok, msg = v.required(value, field_name)
    if ok:
        ok, msg = v.min_length(value, min_len, field_name)
    return ok, msg


# =================================================================
# Shared: repeatable-section resume form (used by Builder AND Modifier)
# =================================================================
def init_form_state(prefix: str):
    for key in ("education", "experience", "projects", "certifications"):
        skey = f"{prefix}_{key}"
        if skey not in st.session_state:
            st.session_state[skey] = []


def render_resume_form(prefix: str) -> dict:
    """
    Renders sections 1-7 (personal info through achievements) with widget
    keys namespaced by `prefix`, so Builder and Modifier never collide.
    Returns the raw_data dict built from current widget values (does NOT
    validate — call validate_resume_form() separately).
    """
    init_form_state(prefix)

    st.header("1. Personal Information")
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Full Name*", key=f"{prefix}_name")
        if name:
            show_hint(*v.validate_name(name))

        email = st.text_input("Email*", key=f"{prefix}_email")
        if email:
            show_hint(*v.validate_email_format(email))

        phone = st.text_input("Phone*", key=f"{prefix}_phone")
        if phone:
            show_hint(*v.validate_phone(phone))
    with col2:
        location = st.text_input("Location (City, Country)", key=f"{prefix}_location")

        linkedin = st.text_input("LinkedIn URL", key=f"{prefix}_linkedin")
        if linkedin:
            show_hint(*v.validate_url(linkedin, "LinkedIn URL"))

        github = st.text_input("GitHub URL", key=f"{prefix}_github")
        if github:
            show_hint(*v.validate_url(github, "GitHub URL"))

    portfolio = st.text_input("Portfolio URL", key=f"{prefix}_portfolio")
    if portfolio:
        show_hint(*v.validate_url(portfolio, "Portfolio URL"))

    raw_summary = st.text_area(
        "About yourself / career objective (optional — rough notes are fine, "
        "the AI will polish this into a final summary)",
        key=f"{prefix}_raw_summary",
    )

    st.header("2. Skills")
    skills_input = st.text_area(
        "Skills* (comma separated)",
        placeholder="Python, LangChain, FastAPI, SQL, Git",
        key=f"{prefix}_skills",
    )
    if skills_input:
        show_hint(*v.validate_comma_list(skills_input, "Skills"))

    st.header("3. Education*")
    edu_list = st.session_state[f"{prefix}_education"]
    for i, edu in enumerate(edu_list):
        with st.expander(f"Education #{i + 1}: {edu.get('degree') or 'New Entry'}", expanded=True):
            edu["degree"] = st.text_input("Degree*", value=edu.get("degree", ""), key=f"{prefix}_edu_degree_{i}")
            edu["institution"] = st.text_input("Institution*", value=edu.get("institution", ""), key=f"{prefix}_edu_inst_{i}")
            edu["location"] = st.text_input("Location", value=edu.get("location", ""), key=f"{prefix}_edu_loc_{i}")
            c1, c2, c3 = st.columns(3)
            with c1:
                edu["start_year"] = st.text_input("Start Year*", value=edu.get("start_year", ""), key=f"{prefix}_edu_start_{i}")
                if edu["start_year"]:
                    show_hint(*v.validate_year(edu["start_year"], "Start Year"))
            with c2:
                edu["end_year"] = st.text_input("End Year* (or 'Present')", value=edu.get("end_year", ""), key=f"{prefix}_edu_end_{i}")
                if edu["end_year"]:
                    show_hint(*v.validate_year(edu["end_year"], "End Year"))
            with c3:
                edu["grade"] = st.text_input("GPA / %", value=edu.get("grade", ""), key=f"{prefix}_edu_grade_{i}")
            if st.button("🗑 Remove", key=f"{prefix}_edu_remove_{i}"):
                edu_list.pop(i)
                st.rerun()

    if st.button("+ Add Education", key=f"{prefix}_edu_add"):
        edu_list.append({})
        st.rerun()

    st.header("4. Work Experience (optional)")
    exp_list = st.session_state[f"{prefix}_experience"]
    for i, exp in enumerate(exp_list):
        with st.expander(f"Experience #{i + 1}: {exp.get('role') or 'New Entry'}", expanded=True):
            exp["role"] = st.text_input("Role / Title*", value=exp.get("role", ""), key=f"{prefix}_exp_role_{i}")
            exp["company"] = st.text_input("Company*", value=exp.get("company", ""), key=f"{prefix}_exp_company_{i}")
            exp["location"] = st.text_input("Location", value=exp.get("location", ""), key=f"{prefix}_exp_loc_{i}")
            c1, c2 = st.columns(2)
            with c1:
                exp["start_date"] = st.text_input("Start Date*", value=exp.get("start_date", ""), key=f"{prefix}_exp_start_{i}")
            with c2:
                exp["end_date"] = st.text_input("End Date* (or 'Present')", value=exp.get("end_date", ""), key=f"{prefix}_exp_end_{i}")
            exp["responsibilities"] = st.text_area(
                "Responsibilities* (one per line)",
                value=exp.get("responsibilities", ""),
                key=f"{prefix}_exp_resp_{i}",
            )
            if st.button("🗑 Remove", key=f"{prefix}_exp_remove_{i}"):
                exp_list.pop(i)
                st.rerun()

    if st.button("+ Add Experience", key=f"{prefix}_exp_add"):
        exp_list.append({})
        st.rerun()

    st.header("5. Projects*")
    proj_list = st.session_state[f"{prefix}_projects"]
    for i, proj in enumerate(proj_list):
        with st.expander(f"Project #{i + 1}: {proj.get('title') or 'New Entry'}", expanded=True):
            proj["title"] = st.text_input("Title*", value=proj.get("title", ""), key=f"{prefix}_proj_title_{i}")
            proj["description"] = st.text_area(
                "Description* (raw notes are fine, the AI will polish it)",
                value=proj.get("description", ""),
                key=f"{prefix}_proj_desc_{i}",
            )
            proj["tech_stack"] = st.text_input(
                "Tech Stack* (comma separated)", value=proj.get("tech_stack", ""), key=f"{prefix}_proj_tech_{i}"
            )
            if proj["tech_stack"]:
                show_hint(*v.validate_comma_list(proj["tech_stack"], "Tech Stack"))

            proj["link"] = st.text_input("Link (GitHub / live demo, optional)", value=proj.get("link", ""), key=f"{prefix}_proj_link_{i}")
            if proj["link"]:
                show_hint(*v.validate_url(proj["link"], "Project Link"))
            if st.button("🗑 Remove", key=f"{prefix}_proj_remove_{i}"):
                proj_list.pop(i)
                st.rerun()

    if st.button("+ Add Project", key=f"{prefix}_proj_add"):
        proj_list.append({})
        st.rerun()

    st.header("6. Certifications (optional)")
    cert_list = st.session_state[f"{prefix}_certifications"]
    for i, cert in enumerate(cert_list):
        with st.expander(f"Certification #{i + 1}: {cert.get('name') or 'New Entry'}", expanded=True):
            cert["name"] = st.text_input("Certification Name*", value=cert.get("name", ""), key=f"{prefix}_cert_name_{i}")
            cert["issuer"] = st.text_input("Issuer", value=cert.get("issuer", ""), key=f"{prefix}_cert_issuer_{i}")
            cert["date"] = st.text_input("Date", value=cert.get("date", ""), key=f"{prefix}_cert_date_{i}")
            if st.button("🗑 Remove", key=f"{prefix}_cert_remove_{i}"):
                cert_list.pop(i)
                st.rerun()

    if st.button("+ Add Certification", key=f"{prefix}_cert_add"):
        cert_list.append({})
        st.rerun()

    st.header("7. Achievements / Awards (optional)")
    achievements_input = st.text_area(
        "One per line",
        placeholder="Winner - Smart India Hackathon 2025\nDean's List 2024",
        key=f"{prefix}_achievements",
    )

    return {
        "name": name,
        "email": email,
        "phone": phone,
        "location": location,
        "linkedin": linkedin,
        "github": github,
        "portfolio": portfolio,
        "raw_summary": raw_summary,
        "skills": skills_input,
        "education": edu_list,
        "experience": exp_list,
        "projects": proj_list,
        "certifications": cert_list,
        "achievements": achievements_input,
    }


def validate_resume_form(raw_data: dict) -> list:
    """Full required + format validation, mirroring backend.Resume's rules."""
    errors = []

    def check(ok_msg_tuple):
        ok, msg = ok_msg_tuple
        if not ok:
            errors.append(msg)

    check(v.validate_name(raw_data["name"]))
    check(v.validate_email_format(raw_data["email"]))
    check(v.validate_phone(raw_data["phone"]))
    check(v.validate_url(raw_data["linkedin"], "LinkedIn URL"))
    check(v.validate_url(raw_data["github"], "GitHub URL"))
    check(v.validate_url(raw_data["portfolio"], "Portfolio URL"))
    check(v.validate_comma_list(raw_data["skills"], "Skills"))

    if not raw_data["education"]:
        errors.append("At least one Education entry is required.")
    for i, edu in enumerate(raw_data["education"], 1):
        check(v.required(edu.get("degree", ""), f"Education #{i}: Degree"))
        check(v.required(edu.get("institution", ""), f"Education #{i}: Institution"))
        check(v.validate_year(edu.get("start_year", ""), f"Education #{i}: Start Year"))
        check(v.validate_year(edu.get("end_year", ""), f"Education #{i}: End Year"))

    for i, exp in enumerate(raw_data["experience"], 1):
        check(v.required(exp.get("role", ""), f"Experience #{i}: Role"))
        check(v.required(exp.get("company", ""), f"Experience #{i}: Company"))
        check(v.required(exp.get("start_date", ""), f"Experience #{i}: Start Date"))
        check(v.required(exp.get("end_date", ""), f"Experience #{i}: End Date"))
        check(v.required(exp.get("responsibilities", ""), f"Experience #{i}: Responsibilities"))

    if not raw_data["projects"]:
        errors.append("At least one Project entry is required.")
    for i, proj in enumerate(raw_data["projects"], 1):
        check(v.required(proj.get("title", ""), f"Project #{i}: Title"))
        check(v.required(proj.get("description", ""), f"Project #{i}: Description"))
        check(v.validate_comma_list(proj.get("tech_stack", ""), f"Project #{i}: Tech Stack"))
        check(v.validate_url(proj.get("link", ""), f"Project #{i}: Link"))

    for i, cert in enumerate(raw_data["certifications"], 1):
        check(v.required(cert.get("name", ""), f"Certification #{i}: Name"))

    return errors


def render_resume_result(resume, prefix: str, style: dict = None):
    """Shared result display + DOCX/PDF download buttons — used by both
    the Builder and the Modifier, since both produce a `Resume`.

    `style`, when provided, is the design extracted from the candidate's
    originally-uploaded .docx (see extract_resume_content()) — passed
    through to resume_to_docx()/resume_to_pdf() so the exported files
    resemble that original design instead of the system's default look.
    """
    st.success("✅ Resume ready")

    safe_filename = re.sub(r"[^\w\-]+", "_", resume.name).strip("_") or "resume"

    dl_col1, dl_col2 = st.columns(2)
    with dl_col1:
        st.download_button(
            "⬇️ Download as Word (.docx)",
            data=resume_to_docx(resume, style=style),
            file_name=f"{safe_filename}_Resume.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
            key=f"{prefix}_dl_docx",
        )
    with dl_col2:
        st.download_button(
            "⬇️ Download as PDF",
            data=resume_to_pdf(resume, style=style),
            file_name=f"{safe_filename}_Resume.pdf",
            mime="application/pdf",
            use_container_width=True,
            key=f"{prefix}_dl_pdf",
        )

    st.subheader(resume.name)
    contact_bits = [b for b in [resume.email, resume.phone, resume.location] if b]
    if contact_bits:
        st.caption(" | ".join(contact_bits))
    link_bits = [b for b in [resume.linkedin, resume.github, resume.portfolio] if b]
    if link_bits:
        st.caption(" | ".join(link_bits))

    st.markdown("**Summary**")
    st.write(resume.summary)

    st.markdown("**Skills**")
    st.write(", ".join(resume.skills))

    if resume.education:
        st.markdown("**Education**")
        for e in resume.education:
            st.write(f"**{e.degree}** — {e.institution} ({e.start_year}–{e.end_year})")
            if e.grade:
                st.caption(f"Grade: {e.grade}")

    if resume.experience:
        st.markdown("**Experience**")
        for e in resume.experience:
            st.write(f"**{e.role}**, {e.company} ({e.start_date}–{e.end_date})")
            for r in e.responsibilities:
                st.write(f"- {r}")

    if resume.projects:
        st.markdown("**Projects**")
        for p in resume.projects:
            st.write(f"**{p.title}**")
            st.write(p.description)
            st.caption("Tech: " + ", ".join(p.tech_stack))

    if resume.certifications:
        st.markdown("**Certifications**")
        for c in resume.certifications:
            st.write(f"- {c.name} ({c.issuer or 'N/A'}, {c.date or 'N/A'})")

    if resume.achievements:
        st.markdown("**Achievements**")
        for a in resume.achievements:
            st.write(f"- {a}")

    with st.expander("Raw structured JSON output"):
        st.json(resume.model_dump())


# =================================================================
# MODE: Resume Builder
# =================================================================
def render_builder():
    st.title("🛠️ Resume Builder")
    st.caption(
        "Fill in each section below. The backend (LangChain + PromptTemplate "
        "+ PydanticOutputParser + Groq) validates and structures everything "
        "into a final resume you can export."
    )

    raw_data = render_resume_form("builder")

    st.divider()
    if st.button("🚀 Generate Structured Resume", type="primary", key="builder_generate"):
        form_errors = validate_resume_form(raw_data)
        if form_errors:
            st.error("Please fix the following before generating:\n\n" + "\n".join(f"- {e}" for e in form_errors))
        else:
            with st.spinner("Validating and generating your structured resume..."):
                try:
                    st.session_state["builder_result"] = generate_resume(raw_data)
                    st.session_state.pop("builder_error", None)
                except ValidationError as ve:
                    st.session_state.pop("builder_result", None)
                    st.session_state["builder_error"] = f"The generated resume failed validation:\n\n{ve}"
                except Exception as e:
                    st.session_state.pop("builder_result", None)
                    st.session_state["builder_error"] = f"Something went wrong: {e}"

    if st.session_state.get("builder_error"):
        st.error(st.session_state["builder_error"])

    if st.session_state.get("builder_result"):
        render_resume_result(st.session_state["builder_result"], "builder")


# =================================================================
# MODE: Resume Modifier (JD-optimized)
# =================================================================
def render_modifier():
    st.title("🎯 Resume Modifier")
    st.caption(
        "Give the AI your resume content — either by uploading your "
        "existing resume file or filling in the form — plus the job "
        "description you're targeting. It will rewrite and reorder your "
        "resume to match what this job (and its ATS) is scanning for, "
        "using your real experience only. Nothing is fabricated."
    )

    input_mode = st.radio(
        "How do you want to provide your resume content?",
        ["Upload my existing resume (.pdf / .docx / .txt)", "Fill in the form manually"],
        key="modifier_input_mode",
        horizontal=True,
    )

    raw_data = None
    resume_text = ""
    upload_style = None
    upload_file_type = None

    if input_mode == "Fill in the form manually":
        raw_data = render_resume_form("modifier")
    else:
        uploaded = st.file_uploader(
            "Upload your existing resume*", type=["pdf", "docx", "txt"], key="modifier_upload"
        )
        if uploaded is not None:
            try:
                content = extract_resume_content(uploaded.getvalue(), uploaded.name)
                upload_style = content["style"]
                upload_file_type = content["file_type"]

                # Keying the text area on the file's name+size means a
                # fresh upload gets a fresh pre-filled box, while edits to
                # the CURRENT file's text are preserved across reruns.
                text_key = f"modifier_upload_text_{uploaded.name}_{uploaded.size}"
                resume_text = st.text_area(
                    "Extracted resume text (feel free to fix anything that "
                    "looks garbled before generating)",
                    value=content["text"],
                    height=260,
                    key=text_key,
                )
            except Exception as e:
                st.error(f"Couldn't read that file: {e}")

    st.header("Target Job Description*")
    job_description = st.text_area(
        "Paste the full job description here",
        height=220,
        placeholder="Paste the job posting text...",
        key="modifier_jd",
    )
    if job_description:
        show_hint(*v.min_length(job_description, 50, "Job Description"))

    st.header("Output Design")
    use_original_design = False
    if input_mode.startswith("Upload") and upload_file_type == "docx":
        design_choice = st.radio(
            "Which design should the final resume use?",
            ["Match my uploaded resume's design", "Use our built-in professional template"],
            key="modifier_design_choice",
        )
        use_original_design = design_choice.startswith("Match")
        if use_original_design:
            st.caption(
                "We'll carry over the font, accent color, and margins we "
                "detected from your uploaded file. This matches typography "
                "closely in the Word export; the PDF export approximates "
                "the font family (Helvetica/Times/Courier family)."
            )
    elif input_mode.startswith("Upload") and upload_file_type in ("pdf", "txt"):
        st.caption("Design-matching is only available for .docx uploads — this will use our built-in template.")
    else:
        st.caption("Your final resume will use our built-in professional template.")

    temperature = st.slider(
        "Rewrite creativity",
        min_value=0.2, max_value=0.9, value=0.5, step=0.1,
        key="modifier_temperature",
        help=(
            "Lower = stays closer to your original wording. Higher = more "
            "creative rephrasing. Either way, the AI is instructed not to "
            "invent facts, skills, or experience you didn't provide."
        ),
    )

    st.divider()
    if st.button("🎯 Generate JD-Optimized Resume", type="primary", key="modifier_generate"):
        errors = []
        jd_ok, jd_msg = check_required_then_min_length(job_description, 50, "Job Description")
        if not jd_ok:
            errors.append(jd_msg)

        if input_mode == "Fill in the form manually":
            errors = validate_resume_form(raw_data) + errors
        else:
            text_ok, text_msg = check_required_then_min_length(resume_text, 50, "Resume text")
            if not text_ok:
                errors.append(text_msg)

        if errors:
            st.error("Please fix the following before generating:\n\n" + "\n".join(f"- {e}" for e in errors))
        else:
            chosen_style = upload_style if use_original_design else None
            with st.spinner("Analyzing the job description and optimizing your resume..."):
                try:
                    if input_mode == "Fill in the form manually":
                        result = generate_modified_resume(raw_data, job_description, temperature=temperature)
                    else:
                        result = generate_modified_resume_from_text(resume_text, job_description, temperature=temperature)
                    st.session_state["modifier_result"] = result
                    st.session_state["modifier_style"] = chosen_style
                    st.session_state.pop("modifier_error", None)
                except ValidationError as ve:
                    st.session_state.pop("modifier_result", None)
                    st.session_state["modifier_error"] = f"The generated resume failed validation:\n\n{ve}"
                except Exception as e:
                    st.session_state.pop("modifier_result", None)
                    st.session_state["modifier_error"] = f"Something went wrong: {e}"

    if st.session_state.get("modifier_error"):
        st.error(st.session_state["modifier_error"])

    if st.session_state.get("modifier_result"):
        render_resume_result(
            st.session_state["modifier_result"],
            "modifier",
            style=st.session_state.get("modifier_style"),
        )


# =================================================================
# MODE: Resume Rater
# =================================================================
def render_rater():
    st.title("⭐ Resume Rater")
    st.caption(
        "Hybrid scoring: a deterministic keyword/similarity match against "
        "the job description, combined with an AI recruiter's qualitative "
        "review of your content and structure. (Note: only textual "
        "structure can be judged this way — actual visual layout, fonts, "
        "and colors aren't assessed.)"
    )

    input_mode = st.radio(
        "How do you want to provide your resume?",
        ["Paste resume text", "Upload a file (.pdf / .docx / .txt)"],
        key="rater_input_mode",
        horizontal=True,
    )

    resume_text = ""
    if input_mode == "Paste resume text":
        resume_text = st.text_area(
            "Paste your resume content*",
            height=260,
            placeholder="Paste your full resume text here...",
            key="rater_resume_text",
        )
    else:
        uploaded = st.file_uploader("Upload your resume*", type=["pdf", "docx", "txt"], key="rater_upload")
        if uploaded is not None:
            try:
                resume_text = extract_text_from_upload(uploaded)
                with st.expander("Preview extracted text"):
                    preview = resume_text[:3000] + ("..." if len(resume_text) > 3000 else "")
                    st.text(preview)
            except Exception as e:
                st.error(f"Couldn't read that file: {e}")

    job_description = st.text_area(
        "Job Description*",
        height=220,
        placeholder="Paste the job posting text...",
        key="rater_jd",
    )

    st.divider()
    if st.button("⭐ Rate My Resume", type="primary", key="rater_generate"):
        errors = []
        ok, msg = check_required_then_min_length(resume_text, 50, "Resume text")
        if not ok:
            errors.append(msg)
        ok, msg = check_required_then_min_length(job_description, 50, "Job Description")
        if not ok:
            errors.append(msg)

        if errors:
            st.error("Please fix the following before rating:\n\n" + "\n".join(f"- {e}" for e in errors))
        else:
            with st.spinner("Computing keyword match and getting the AI recruiter's review..."):
                try:
                    st.session_state["rater_result"] = rate_resume(resume_text, job_description)
                    st.session_state.pop("rater_error", None)
                except Exception as e:
                    st.session_state.pop("rater_result", None)
                    st.session_state["rater_error"] = f"Something went wrong: {e}"

    if st.session_state.get("rater_error"):
        st.error(st.session_state["rater_error"])

    if st.session_state.get("rater_result"):
        result = st.session_state["rater_result"]
        rating = result.llm_rating
        sim = result.similarity

        st.success("✅ Rating complete")

        st.metric("Overall Hybrid Score", f"{result.hybrid_score} / 100")
        st.caption("Hybrid score = 35% keyword/similarity match + 65% AI recruiter review.")

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Similarity", sim.similarity_score)
        m2.metric("Content", rating.content_quality_score)
        m3.metric("Keywords", rating.keyword_alignment_score)
        m4.metric("ATS", rating.ats_friendliness_score)
        m5.metric("Formatting", rating.formatting_score)

        st.markdown("**Recruiter's summary**")
        st.write(rating.summary_feedback)

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**✅ Strengths**")
            for s in rating.strengths:
                st.write(f"- {s}")
        with col_b:
            st.markdown("**⚠️ Weaknesses**")
            for w in rating.weaknesses:
                st.write(f"- {w}")

        if rating.suggestions:
            st.markdown("**💡 Suggestions**")
            for s in rating.suggestions:
                st.write(f"- {s}")

        missing = sorted(set(sim.missing_keywords) | set(rating.missing_keywords))
        if missing:
            st.markdown("**🔑 Keywords from the JD your resume seems to be missing**")
            st.write(", ".join(missing[:30]))

        if sim.matched_keywords:
            st.markdown("**🎯 Matched keywords**")
            st.write(", ".join(sim.matched_keywords[:30]))

        with st.expander("Raw structured rating JSON"):
            st.json(result.model_dump())


# ═══════════════════════════════════════════════════════════════════
# Page Header & Tab Navigation
# ═══════════════════════════════════════════════════════════════════
st.title("📄 AI Resume Suite")
st.caption("Build, modify, or rate your resume with AI assistance.")

tab_builder, tab_modifier, tab_rater = st.tabs([
    "🛠️ Resume Builder",
    "🎯 Resume Modifier",
    "⭐ Resume Rater",
])

with tab_builder:
    render_builder()

with tab_modifier:
    render_modifier()

with tab_rater:
    render_rater()
