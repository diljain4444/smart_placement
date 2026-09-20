"""
frontend.py
Streamlit test UI for roadmap_backend.py

Install:
    pip install streamlit

Run:
    streamlit run frontend.py
(make sure roadmap_backend.py is in the same folder, and GROQ_API_KEY is set)
"""

import streamlit as st
from roadmap import generate_roadmap

st.set_page_config(page_title="Placement Roadmap Generator", layout="centered")
st.title("🎯 Placement Roadmap Generator")
st.caption("Test UI for the LangGraph roadmap backend (Groq · openai/gpt-oss-120b)")

with st.form("roadmap_form"):
    st.subheader("1. Where you are right now")
    col1, col2 = st.columns(2)
    with col1:
        year = st.selectbox("Year", ["1st year", "2nd year", "3rd year", "4th year"], index=2)
        dsa_problems_solved = st.selectbox(
            "DSA problems solved", ["<50", "50-150", "150-300", "300+"], index=1
        )
        projects_count = st.number_input("Projects completed", min_value=0, max_value=50, value=2)
    with col2:
        branch = st.text_input("Branch", value="AI & Data Science")
        known_skills = st.multiselect(
            "Known languages / frameworks",
            ["Python", "Java", "C++", "JavaScript", "React", "FastAPI",
             "Django", "LangChain", "LangGraph", "SQL", "TensorFlow", "PyTorch"],
            default=["Python"],
        )
        certifications = st.text_input("Certifications (optional)", value="")

    st.markdown("**CS fundamentals confidence**")
    conf_options = ["not started", "familiar", "strong"]
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        os_confidence = st.selectbox("OS", conf_options, index=1)
    with c2:
        dbms_confidence = st.selectbox("DBMS", conf_options, index=1)
    with c3:
        cn_confidence = st.selectbox("CN", conf_options, index=1)
    with c4:
        oops_confidence = st.selectbox("OOP", conf_options, index=1)

    st.subheader("2. Where you want to go")
    col3, col4 = st.columns(2)
    with col3:
        target_role = st.selectbox(
            "Target role",
            ["SDE", "AI/ML Engineer", "Data Analyst", "Data Scientist", "Other"],
        )
        placement_mode = st.radio("Placement mode", ["On-campus", "Off-campus"])
    with col4:
        company_tier = st.selectbox(
            "Company tier",
            ["Service-based", "Product-based (mid-tier)", "FAANG / top product", "Startups"],
        )
        dream_companies = st.text_input("Dream companies (optional)", value="")

    st.subheader("3. Constraints")
    col5, col6 = st.columns(2)
    with col5:
        hours_per_week = st.number_input("Hours available per week", min_value=1, max_value=80, value=12)
    with col6:
        has_deadline = st.checkbox("I have a fixed deadline", value=False)
        deadline = None
        if has_deadline:
            deadline_date = st.date_input("Deadline")
            deadline = deadline_date.isoformat()

    learning_style = st.selectbox(
        "Preferred learning style", ["Videos", "Docs", "Practice-first", "Mixed"], index=2
    )

    submitted = st.form_submit_button("Generate Roadmap")

if submitted:
    user_input = {
        "year": year,
        "branch": branch,
        "dsa_problems_solved": dsa_problems_solved,
        "known_skills": known_skills,
        "os_confidence": os_confidence,
        "dbms_confidence": dbms_confidence,
        "cn_confidence": cn_confidence,
        "oops_confidence": oops_confidence,
        "projects_count": projects_count,
        "certifications": certifications,
        "target_role": target_role,
        "company_tier": company_tier,
        "placement_mode": placement_mode,
        "dream_companies": dream_companies,
        "hours_per_week": hours_per_week,
        "deadline": deadline,
        "learning_style": learning_style,
    }

    with st.spinner("Generating your roadmap..."):
        try:
            output = generate_roadmap(user_input)
        except Exception as e:
            st.error(f"Something went wrong: {e}")
            output = None

    if output:
        st.success("Roadmap generated!")
        st.markdown("### Gap Summary")
        st.write(output["gap_summary"])
        st.markdown(f"**Weekly time commitment:** {output['weekly_time_commitment']}")

        st.markdown("### Roadmap Phases")
        priority_badge = {"high": "🔴", "medium": "🟡", "low": "🟢"}

        for i, phase in enumerate(output["phases"], start=1):
            badge = priority_badge.get(phase["priority"], "⚪")
            header = f"Phase {i}: {phase['phase_name']}  ({phase['duration_weeks']} wks)  {badge}"
            with st.expander(header):
                st.markdown(f"**Priority:** {phase['priority'].title()}")
                st.markdown(f"**Topics:** {', '.join(phase['topics'])}")
                st.markdown(f"**Milestone:** {phase['milestone']}")
                if phase.get("suggested_project"):
                    st.markdown(f"**Suggested project:** {phase['suggested_project']}")
                st.markdown(f"**Why this order:** {phase['why_this_order']}")