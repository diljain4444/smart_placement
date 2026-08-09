
import os
import re
import io
import math
from functools import lru_cache
import unicodedata
from xml.sax.saxutils import escape as _xml_escape
from typing import List, Optional

from dotenv import load_dotenv
load_dotenv()

from pydantic import BaseModel, Field, EmailStr, field_validator, model_validator

from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.messages import AIMessage
from langchain_groq import ChatGroq

# ---- Document export dependencies (DOCX + PDF) ----
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem, HRFlowable,
)

# ---- Resume Rater: reading uploaded .pdf resumes ----
import pypdf


# =================================================================
# 1. PYDANTIC SCHEMA (this IS the resume data model — validated,
#    and reusable later for PDF/DOCX generation)
# =================================================================

class Education(BaseModel):
    degree: str = Field(..., min_length=2, description="e.g. B.Tech in AI & Data Science")
    institution: str = Field(..., min_length=2)
    location: Optional[str] = None
    start_year: str
    end_year: str
    grade: Optional[str] = Field(default=None, description="GPA or percentage")

    @field_validator("start_year", "end_year")
    @classmethod
    def validate_year(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^\d{4}$", v) and v.lower() != "present":
            raise ValueError("Year must be a 4-digit year (e.g. 2023) or 'Present'")
        return v


class Experience(BaseModel):
    role: str = Field(..., min_length=2)
    company: str = Field(..., min_length=2)
    location: Optional[str] = None
    start_date: str
    end_date: str = Field(..., description="e.g. 'Jan 2024' or 'Present'")
    responsibilities: List[str] = Field(..., min_length=1)


class Project(BaseModel):
    title: str = Field(..., min_length=2)
    description: str = Field(..., min_length=5)
    tech_stack: List[str] = Field(..., min_length=1)
    link: Optional[str] = None

    @field_validator("link")
    @classmethod
    def validate_link(cls, v: Optional[str]) -> Optional[str]:
        if v and not v.strip():
            return None
        if v and not v.startswith(("http://", "https://")):
            v = "https://" + v.strip()
        return v


class Certification(BaseModel):
    name: str = Field(..., min_length=2)
    issuer: Optional[str] = None
    date: Optional[str] = None


class Resume(BaseModel):
    # ---- Personal info ----
    name: str = Field(..., min_length=2)
    email: EmailStr
    phone: str
    location: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None

    # ---- Content ----
    summary: str = Field(..., min_length=20, description="Polished 2-4 line professional summary")
    skills: List[str] = Field(..., min_length=1)
    education: List[Education] = Field(..., min_length=1)
    experience: List[Experience] = Field(default_factory=list)
    projects: List[Project] = Field(..., min_length=1)
    certifications: List[Certification] = Field(default_factory=list)
    achievements: List[str] = Field(default_factory=list)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        digits = re.sub(r"\D", "", v)
        if len(digits) < 10:
            raise ValueError("Phone number must contain at least 10 digits")
        return v.strip()

    @field_validator("linkedin", "github", "portfolio")
    @classmethod
    def normalize_url(cls, v: Optional[str]) -> Optional[str]:
        if not v or not v.strip():
            return None
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            v = "https://" + v
        return v

    @field_validator("skills")
    @classmethod
    def dedupe_skills(cls, v: List[str]) -> List[str]:
        seen, cleaned = set(), []
        for s in v:
            s = s.strip()
            if s and s.lower() not in seen:
                seen.add(s.lower())
                cleaned.append(s)
        if not cleaned:
            raise ValueError("At least one skill is required")
        return cleaned

    @model_validator(mode="after")
    def check_experience_or_projects(self):
        if not self.experience and not self.projects:
            raise ValueError("Resume must include at least one project or one work experience")
        return self


# ---- Resume Rater schemas ----

class KeywordMatch(BaseModel):
    """Pure lexical / statistical half of the hybrid rating — no LLM involved."""
    similarity_score: int = Field(..., ge=0, le=100, description="Cosine similarity between resume and JD term-frequency vectors, 0-100")
    matched_keywords: List[str] = Field(default_factory=list)
    missing_keywords: List[str] = Field(default_factory=list)


class ResumeRating(BaseModel):
    """The LLM/qualitative half of the hybrid rating — a recruiter-style review."""
    overall_score: int = Field(..., ge=0, le=100, description="Holistic 0-100 fit score for this exact job description")
    content_quality_score: int = Field(..., ge=0, le=100)
    keyword_alignment_score: int = Field(..., ge=0, le=100)
    ats_friendliness_score: int = Field(..., ge=0, le=100)
    formatting_score: int = Field(..., ge=0, le=100, description="Structure/organization/clarity inferred from the resume text")
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    missing_keywords: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    summary_feedback: str = Field(..., min_length=20)


class HybridRating(BaseModel):
    """Final combined result returned by rate_resume()."""
    hybrid_score: int = Field(..., ge=0, le=100)
    similarity: KeywordMatch
    llm_rating: ResumeRating


# =================================================================
# 2. OUTPUT PARSER (Pydantic format instructions go INTO the prompt)
# =================================================================

parser = PydanticOutputParser(pydantic_object=Resume)
rating_parser = PydanticOutputParser(pydantic_object=ResumeRating)


# =================================================================
# 3. PROMPT TEMPLATE (plain PromptTemplate, not ChatPromptTemplate)
# =================================================================

RESUME_PROMPT_TEXT = """You are an expert, meticulous professional resume writer.

You are given a candidate's RAW, possibly messy or incomplete information.
Turn it into a clean, professional, ATS-friendly resume.

STRICT RULES:
- Do NOT invent facts (companies, technologies, numbers, dates, employers)
  that are not present or clearly implied in the raw input below.
- Write a crisp, 2-4 line professional summary based on the candidate's
  skills, education, experience, and projects.
- Clean up and de-duplicate the skills list; fix casing
  (e.g. "python" -> "Python", "fastapi" -> "FastAPI").
- Rewrite each project description into 1-3 professional,
  impact-oriented lines.
- Rewrite each experience entry's responsibilities into clear,
  action-verb-led bullet points.
- If a field says "Not provided" or "None provided", output it as an
  empty value in the schema rather than fabricating content.
- Use only plain keyboard punctuation: a single ASCII hyphen "-" for all
  dashes and hyphenation (never en dashes, em dashes, or other dash
  variants), straight quotes (' and "), and three periods "..." for an
  ellipsis. Do not use typographic/"smart" punctuation.
- Return ONLY the JSON object described below. No preamble, no
  markdown code fences, no explanation, no <reasoning> or <think> tags.

Candidate Raw Data
-------------------
Name: {name}
Email: {email}
Phone: {phone}
Location: {location}
LinkedIn: {linkedin}
GitHub: {github}
Portfolio: {portfolio}
Rough self-summary / objective (if any): {raw_summary}

Skills (raw, comma separated): {skills}

Education:
{education}

Work Experience:
{experience}

Projects:
{projects}

Certifications:
{certifications}

Achievements:
{achievements}

{format_instructions}
"""
# MODIFIER_FROM_TEXT_PROMPT_TEXT
PROMPT = PromptTemplate(
    template=RESUME_PROMPT_TEXT,
    input_variables=[
        "name", "email", "phone", "location", "linkedin", "github",
        "portfolio", "raw_summary", "skills", "education", "experience",
        "projects", "certifications", "achievements",
    ],
    partial_variables={"format_instructions": parser.get_format_instructions()},
)


# Small repair prompt used only if the first JSON output fails to
# parse/validate — asks the LLM to correct its own output. This
# replaces langchain.output_parsers.OutputFixingParser so we don't
# depend on the full `langchain` meta-package.
FIX_PROMPT_TEXT = """The JSON output below was supposed to follow this schema:

{format_instructions}

Attempted output:
{raw_output}

It failed with this error:
{error}

Return ONLY a corrected JSON object that fixes the error and matches
the schema exactly. No preamble, no markdown code fences, no
explanation.
"""

FIX_PROMPT = PromptTemplate(
    template=FIX_PROMPT_TEXT,
    input_variables=["raw_output", "error"],
    partial_variables={"format_instructions": parser.get_format_instructions()},
)

FIX_RATING_PROMPT = PromptTemplate(
    template=FIX_PROMPT_TEXT,
    input_variables=["raw_output", "error"],
    partial_variables={"format_instructions": rating_parser.get_format_instructions()},
)


# ---- Modifier prompt: same Resume schema, JD-aware rewrite rules ----

MODIFIER_PROMPT_TEXT = """You are an expert resume writer and ATS (Applicant
Tracking System) optimization specialist.

You are given a candidate's RAW resume content/structure AND a target job
description. Rewrite and restructure the resume so it scores as highly as
possible with both automated ATS keyword scanners AND a human recruiter
screening for THIS specific role — without ever fabricating facts.

STRICT RULES:
- Do NOT invent companies, technologies, numbers, dates, employers, or
  skills that are not present or clearly implied in the raw input below.
- Read the job description and identify its key requirements, must-have
  skills, and recurring terminology (the words an ATS is likely scanning
  for).
- Naturally weave that job-description terminology into the summary,
  skills list, and bullet points — but ONLY where the candidate's real
  background genuinely supports it. Do not claim skills the candidate
  doesn't have.
- Reorder the skills list so the most job-relevant skills (that the
  candidate actually has) appear first.
- Rewrite the professional summary (2-4 lines) to explicitly position the
  candidate for this exact role, echoing the job description's language.
- Rewrite each project/experience bullet with strong action verbs and,
  wherever the raw data supports it, quantifiable impact — phrased close
  to how the job description describes that kind of work.
- Reorder experience and projects so the entries most relevant to this
  job description come first.
- If a field says "Not provided" or "None provided", output it as an
  empty value in the schema rather than fabricating content.
- Use only plain keyboard punctuation: a single ASCII hyphen "-" for all
  dashes and hyphenation (never en dashes, em dashes, or other dash
  variants), straight quotes (' and "), and three periods "..." for an
  ellipsis. Do not use typographic/"smart" punctuation.
- Return ONLY the JSON object described below. No preamble, no
  markdown code fences, no explanation, no <reasoning> or <think> tags.

Target Job Description
-------------------------
{job_description}

Candidate Raw Data
-------------------
Name: {name}
Email: {email}
Phone: {phone}
Location: {location}
LinkedIn: {linkedin}
GitHub: {github}
Portfolio: {portfolio}
Rough self-summary / objective (if any): {raw_summary}

Skills (raw, comma separated): {skills}

Education:
{education}

Work Experience:
{experience}

Projects:
{projects}

Certifications:
{certifications}

Achievements:
{achievements}

{format_instructions}
"""

MODIFIER_PROMPT = PromptTemplate(
    template=MODIFIER_PROMPT_TEXT,
    input_variables=[
        "job_description", "name", "email", "phone", "location", "linkedin",
        "github", "portfolio", "raw_summary", "skills", "education",
        "experience", "projects", "certifications", "achievements",
    ],
    partial_variables={"format_instructions": parser.get_format_instructions()},
)


# ---- Rater prompt: qualitative recruiter-style review ----

RATING_PROMPT_TEXT = """You are a senior technical recruiter with 15+ years of
experience screening resumes for this exact kind of role. You are honest and
specific, not diplomatically vague — a good resume should score high, a weak
one should score low.

Evaluate the candidate's resume against the target job description below,
the way you would during a real initial screen.

Job Description
-----------------
{job_description}

Candidate's Resume (raw text, exactly as submitted)
------------------------------------------------------
{resume_text}

Score every *_score field from 0 (very poor) to 100 (excellent):
- content_quality_score: clarity, impact, quantification, relevance of the
  actual content (independent of the job description).
- keyword_alignment_score: how well the resume's language and skills match
  what this specific job description is asking for.
- ats_friendliness_score: likelihood this resume would pass an automated
  ATS keyword/section-parsing scan for this role.
- formatting_score: judge this ONLY from the text itself — section
  organization, use of clear bullet points, conciseness, lack of clutter or
  redundancy. You cannot see fonts, colors, or visual layout, so do not
  guess about those; base this purely on textual structure.
- overall_score: your holistic verdict on this candidate's fit for this job,
  based on everything above.

Also list specific missing_keywords: important terms/skills from the job
description that this resume does not currently contain.

Be concrete in strengths, weaknesses, and suggestions — refer to actual
content from the resume, not generic advice.

{format_instructions}
"""

RATING_PROMPT = PromptTemplate(
    template=RATING_PROMPT_TEXT,
    input_variables=["job_description", "resume_text"],
    partial_variables={"format_instructions": rating_parser.get_format_instructions()},
)


# =================================================================
# 4. LLM (plain ChatGroq — no with_structured_output)
# =================================================================

llm = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.5,
)


@lru_cache(maxsize=8)
def _get_llm(temperature: float) -> ChatGroq:
    """
    Returns a ChatGroq instance pinned to the given temperature, cached so
    repeated calls at the same temperature don't re-instantiate the client.
    Used by the Modifier so the user can dial "how much creative liberty"
    the rewrite takes (still bounded by the strict no-fabrication rules in
    the prompt itself — temperature only affects phrasing, not facts).
    """
    temperature = round(float(temperature), 2)
    return ChatGroq(
        model="openai/gpt-oss-120b",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=temperature,
    )


# =================================================================
# 5. Helpers — turn raw list-of-dict form data into readable text
#    blocks for the prompt (PromptTemplate variables must be strings)
# =================================================================

def _format_education(items: List[dict]) -> str:
    if not items:
        return "None provided"
    lines = []
    for i, e in enumerate(items, 1):
        lines.append(
            f"{i}. Degree: {e.get('degree','')} | Institution: {e.get('institution','')} | "
            f"Location: {e.get('location','')} | Years: {e.get('start_year','')}-{e.get('end_year','')} | "
            f"Grade: {e.get('grade','')}"
        )
    return "\n".join(lines)


def _format_experience(items: List[dict]) -> str:
    if not items:
        return "None provided"
    lines = []
    for i, e in enumerate(items, 1):
        resp = e.get("responsibilities", "")
        if isinstance(resp, str):
            resp = "; ".join(line.strip() for line in resp.splitlines() if line.strip())
        lines.append(
            f"{i}. Role: {e.get('role','')} | Company: {e.get('company','')} | "
            f"Location: {e.get('location','')} | Duration: {e.get('start_date','')} to "
            f"{e.get('end_date','')} | Responsibilities: {resp}"
        )
    return "\n".join(lines)


def _format_projects(items: List[dict]) -> str:
    if not items:
        return "None provided"
    lines = []
    for i, p in enumerate(items, 1):
        lines.append(
            f"{i}. Title: {p.get('title','')} | Description: {p.get('description','')} | "
            f"Tech: {p.get('tech_stack','')} | Link: {p.get('link','')}"
        )
    return "\n".join(lines)


def _format_certifications(items: List[dict]) -> str:
    if not items:
        return "None provided"
    lines = []
    for i, c in enumerate(items, 1):
        lines.append(f"{i}. {c.get('name','')} - {c.get('issuer','')} ({c.get('date','')})")
    return "\n".join(lines)


def _format_achievements(raw: str) -> str:
    if not raw or not raw.strip():
        return "None provided"
    items = [line.strip() for line in raw.splitlines() if line.strip()]
    return "\n".join(f"- {a}" for a in items) if items else "None provided"


def _extract_text(message: AIMessage) -> str:
    """
    Safely flatten an AIMessage's content into a plain string.

    Most models return `message.content` as a plain string. Some
    reasoning-capable models (e.g. openai/gpt-oss-120b on Groq) return
    it as a list of content blocks instead (reasoning block + text
    block). This pulls out just the actual answer text either way,
    which is what was producing the 'TextAccessor' error before.
    """
    content = message.content

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") in ("text", "output_text"):
                parts.append(block.get("text", ""))
        if parts:
            return "".join(parts)

    # Last-resort fallback for any other shape
    return str(content)


def _parse_with_retry(raw_text: str, max_retries: int = 1) -> Resume:
    """
    Tries to parse `raw_text` into a validated `Resume`. If parsing or
    validation fails, re-asks the LLM (up to `max_retries` times) to
    correct its own output, using the actual error message.
    """
    attempt_text = raw_text
    last_error: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            return parser.parse(attempt_text)
        except Exception as e:
            last_error = e
            if attempt == max_retries:
                break
            fix_prompt = FIX_PROMPT.format(raw_output=attempt_text, error=str(e))
            ai_message = llm.invoke(fix_prompt)
            attempt_text = _extract_text(ai_message)

    raise last_error


def _parse_rating_with_retry(raw_text: str, max_retries: int = 1) -> ResumeRating:
    """Same self-correcting retry loop as _parse_with_retry, bound to the
    ResumeRating schema/parser instead of Resume."""
    attempt_text = raw_text
    last_error: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            return rating_parser.parse(attempt_text)
        except Exception as e:
            last_error = e
            if attempt == max_retries:
                break
            fix_prompt = FIX_RATING_PROMPT.format(raw_output=attempt_text, error=str(e))
            ai_message = llm.invoke(fix_prompt)
            attempt_text = _extract_text(ai_message)

    raise last_error


# =================================================================
# 6. Core function called by the Streamlit frontend
# =================================================================

def generate_resume(raw_data: dict) -> Resume:
    """
    raw_data keys expected:
        name, email, phone, location, linkedin, github, portfolio,
        raw_summary, skills (str),
        education (list[dict]), experience (list[dict]),
        projects (list[dict]), certifications (list[dict]),
        achievements (str, one item per line)

    Returns a validated `Resume` pydantic object, or raises:
        - ValueError                 -> missing GROQ_API_KEY
        - pydantic.ValidationError   -> final output failed schema validation
          after the auto-fix retry also failed
    """
    prompt_vars = {
        "name": raw_data.get("name", ""),
        "email": raw_data.get("email", ""),
        "phone": raw_data.get("phone", ""),
        "location": raw_data.get("location") or "Not provided",
        "linkedin": raw_data.get("linkedin") or "Not provided",
        "github": raw_data.get("github") or "Not provided",
        "portfolio": raw_data.get("portfolio") or "Not provided",
        "raw_summary": raw_data.get("raw_summary") or "Not provided",
        "skills": raw_data.get("skills", ""),
        "education": _format_education(raw_data.get("education", [])),
        "experience": _format_experience(raw_data.get("experience", [])),
        "projects": _format_projects(raw_data.get("projects", [])),
        "certifications": _format_certifications(raw_data.get("certifications", [])),
        "achievements": _format_achievements(raw_data.get("achievements", "")),
    }

    # Explicit steps (rather than piping everything with `|`) so the
    # AIMessage -> text conversion is fully under our control.
    formatted_prompt = PROMPT.format(**prompt_vars)
    ai_message: AIMessage = llm.invoke(formatted_prompt)
    raw_text = _extract_text(ai_message)

    result: Resume = _parse_with_retry(raw_text)
    return result


def generate_modified_resume(raw_data: dict, job_description: str, temperature: float = 0.5) -> Resume:
    """
    Same raw_data shape as generate_resume(), PLUS a target job_description
    string. Returns a validated `Resume` — rewritten/reordered/keyword-
    aligned to that job description, without fabricating facts.

    `temperature` controls how much creative liberty the rewrite takes with
    phrasing (0.2 = conservative/close to the original wording, 0.8 = more
    creative rephrasing) — it never overrides the strict no-fabrication
    rules baked into the prompt itself.

    Reuses the exact same Resume schema, parser, and DOCX/PDF export
    functions as the plain builder, since the output shape is identical.
    """
    if not job_description or not job_description.strip():
        raise ValueError("A job description is required to generate a JD-optimized resume.")

    prompt_vars = {
        "job_description": job_description.strip(),
        "name": raw_data.get("name", ""),
        "email": raw_data.get("email", ""),
        "phone": raw_data.get("phone", ""),
        "location": raw_data.get("location") or "Not provided",
        "linkedin": raw_data.get("linkedin") or "Not provided",
        "github": raw_data.get("github") or "Not provided",
        "portfolio": raw_data.get("portfolio") or "Not provided",
        "raw_summary": raw_data.get("raw_summary") or "Not provided",
        "skills": raw_data.get("skills", ""),
        "education": _format_education(raw_data.get("education", [])),
        "experience": _format_experience(raw_data.get("experience", [])),
        "projects": _format_projects(raw_data.get("projects", [])),
        "certifications": _format_certifications(raw_data.get("certifications", [])),
        "achievements": _format_achievements(raw_data.get("achievements", "")),
    }

    formatted_prompt = MODIFIER_PROMPT.format(**prompt_vars)
    active_llm = _get_llm(temperature)
    ai_message: AIMessage = active_llm.invoke(formatted_prompt)
    raw_text = _extract_text(ai_message)

    result: Resume = _parse_with_retry(raw_text)
    return result


# ---- Modifier prompt variant: candidate provides an EXISTING resume as
#      raw text (uploaded file) instead of the structured form ----

MODIFIER_FROM_TEXT_PROMPT_TEXT = """You are an expert resume writer and ATS
(Applicant Tracking System) optimization specialist.

You are given the RAW TEXT of a candidate's EXISTING resume — extracted
from their uploaded file, so headings, spacing, or bullet symbols may be
imperfect or missing — AND a target job description. Infer the candidate's
structured information from this raw text and rewrite it into a clean,
professional, ATS-friendly resume optimized for the target role.

STRICT RULES:
- Do NOT invent companies, technologies, numbers, dates, employers,
  degrees, or skills that are not present or clearly implied in the raw
  resume text below. Only reorganize, rephrase, and re-emphasize what is
  already there.
- Read the job description and identify its key requirements, must-have
  skills, and recurring terminology (the words an ATS is likely scanning
  for).
- Naturally weave that job-description terminology into the summary,
  skills list, and bullet points — but ONLY where the candidate's real
  background genuinely supports it. Do not claim skills the candidate
  doesn't have.
- Reorder the skills list, and reorder experience/projects, so the most
  job-relevant items (that the candidate actually has) appear first.
- Rewrite the professional summary (2-4 lines) to explicitly position the
  candidate for this exact role, echoing the job description's language.
- Rewrite each bullet point with strong action verbs and, wherever the raw
  text supports it, quantifiable impact — phrased close to how the job
  description describes that kind of work.
- If a field is missing entirely from the raw text (e.g. no phone number,
  no LinkedIn URL), leave that field empty in the output schema rather
  than fabricating one.
- Use only plain keyboard punctuation: a single ASCII hyphen "-" for all
  dashes and hyphenation (never en dashes, em dashes, or other dash
  variants), straight quotes (' and "), and three periods "..." for an
  ellipsis. Do not use typographic/"smart" punctuation.
- Return ONLY the JSON object described below. No preamble, no markdown
  code fences, no explanation, no <reasoning> or <think> tags.

Target Job Description
-------------------------
{job_description}

Candidate's Existing Resume (raw text extracted from their uploaded file)
------------------------------------------------------------------------
{resume_text}

{format_instructions}
"""

MODIFIER_FROM_TEXT_PROMPT = PromptTemplate(
    template=MODIFIER_FROM_TEXT_PROMPT_TEXT,
    input_variables=["job_description", "resume_text"],
    partial_variables={"format_instructions": parser.get_format_instructions()},
)


def generate_modified_resume_from_text(resume_text: str, job_description: str, temperature: float = 0.5) -> Resume:
    """
    Modifier path for when the candidate UPLOADS an existing resume instead
    of filling the form. `resume_text` is the raw text already extracted
    from their file (see extract_resume_content()). Returns a validated
    `Resume`, rewritten and reordered to match the job description, without
    fabricating anything beyond what's in the original text.
    """
    if not resume_text or not resume_text.strip():
        raise ValueError("Resume text is required.")
    if not job_description or not job_description.strip():
        raise ValueError("A job description is required to generate a JD-optimized resume.")

    formatted_prompt = MODIFIER_FROM_TEXT_PROMPT.format(
        resume_text=resume_text.strip(),
        job_description=job_description.strip(),
    )
    active_llm = _get_llm(temperature)
    ai_message: AIMessage = active_llm.invoke(formatted_prompt)
    raw_text = _extract_text(ai_message)

    result: Resume = _parse_with_retry(raw_text)
    return result


# =================================================================
# 7. Resume Rater — hybrid scoring:
#      (a) pure lexical/statistical similarity (no LLM, no network)
#      (b) LLM recruiter-style qualitative review
#    combined into one HybridRating.
# =================================================================

# Small stopword list — filtered out before keyword extraction / similarity
# so common filler words don't drown out the actual skills/terms that matter.
_STOPWORDS = set("""
a an the and or but if while with without within into onto to of in on for
at by from as is are was were be been being this that these those it its
your you we our us they their them he she his her i my me will would
should could can may might shall must not no nor do does did doing have
has had having than then so such more most other some any all each every
both few also too very etc using use used via per year years experience
experienced responsible responsibility responsibilities requirement
requirements job role work team including include includes across ability
skill skills strong excellent good knowledge understanding demonstrated
proven new join joining looking seeking candidate candidates plus preferred
required must nice about company our we're re
""".split())

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.#-]{1,}")


def _tokenize(text: str) -> List[str]:
    raw = (w.lower().rstrip(".") for w in _WORD_RE.findall(text or ""))
    return [w for w in raw if w and w not in _STOPWORDS and len(w) > 1]


def _term_frequency(tokens: List[str]) -> dict:
    tf: dict = {}
    for t in tokens:
        tf[t] = tf.get(t, 0) + 1
    return tf


def _cosine_similarity(tf_a: dict, tf_b: dict) -> float:
    common = set(tf_a) & set(tf_b)
    dot = sum(tf_a[t] * tf_b[t] for t in common)
    norm_a = math.sqrt(sum(v * v for v in tf_a.values()))
    norm_b = math.sqrt(sum(v * v for v in tf_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _extract_keywords(text: str, top_n: int = 25) -> List[str]:
    tf = _term_frequency(_tokenize(text))
    ranked = sorted(tf.items(), key=lambda kv: (-kv[1], kv[0]))
    return [w for w, _ in ranked[:top_n]]


def compute_similarity_metrics(resume_text: str, job_description: str) -> KeywordMatch:
    """
    Pure-Python TF cosine similarity + keyword coverage — no external ML
    dependency, no network call. This is the deterministic half of the
    hybrid rating; it can't be gamed by LLM phrasing alone.
    """
    resume_tokens = _tokenize(resume_text)
    jd_tokens = _tokenize(job_description)

    sim = _cosine_similarity(_term_frequency(resume_tokens), _term_frequency(jd_tokens))
    similarity_score = round(sim * 100)

    jd_keywords = _extract_keywords(job_description, top_n=25)
    resume_word_set = set(resume_tokens)
    matched = [k for k in jd_keywords if k in resume_word_set]
    missing = [k for k in jd_keywords if k not in resume_word_set]

    return KeywordMatch(
        similarity_score=similarity_score,
        matched_keywords=matched,
        missing_keywords=missing,
    )


def generate_llm_rating(resume_text: str, job_description: str) -> ResumeRating:
    """The qualitative half — a structured, recruiter-style LLM review."""
    formatted_prompt = RATING_PROMPT.format(
        resume_text=resume_text.strip(),
        job_description=job_description.strip(),
    )
    ai_message: AIMessage = llm.invoke(formatted_prompt)
    raw_text = _extract_text(ai_message)
    return _parse_rating_with_retry(raw_text)


def rate_resume(resume_text: str, job_description: str) -> HybridRating:
    """
    Core function called by the Streamlit frontend for the Resume Rater.

    Combines the deterministic similarity score with the LLM's holistic
    score into one hybrid_score (35% similarity / 65% LLM judgement —
    the LLM leads since it understands synonyms/context that raw keyword
    overlap misses, but the lexical score keeps it anchored to the JD's
    actual vocabulary).
    """
    if not resume_text or not resume_text.strip():
        raise ValueError("Resume text is required.")
    if not job_description or not job_description.strip():
        raise ValueError("Job description is required.")

    similarity = compute_similarity_metrics(resume_text, job_description)
    llm_rating = generate_llm_rating(resume_text, job_description)

    hybrid_score = round(0.35 * similarity.similarity_score + 0.65 * llm_rating.overall_score)

    return HybridRating(hybrid_score=hybrid_score, similarity=similarity, llm_rating=llm_rating)


def _extract_docx_style(doc: "Document") -> dict:
    """
    Best-effort extraction of an uploaded .docx resume's visual identity —
    body font/size, an accent color (picked up from a bold/large run, e.g.
    the candidate's name or a section heading), and page margins — so a
    regenerated document can be styled to resemble the original instead of
    always falling back to the system's default navy template.

    This is a heuristic, not a full layout parser: it can't reconstruct
    columns, tables-as-layout, or embedded graphics. It only carries over
    typography (font family, sizes) and one accent color. Falls back to
    the system defaults for anything it can't confidently detect.
    """
    body_font, body_size = None, None
    accent_color, name_size = None, None
    seen_body = False

    for p in doc.paragraphs[:80]:
        for r in p.runs:
            if not r.text or not r.text.strip():
                continue
            size = r.font.size
            if r.bold and size and size.pt >= 14 and accent_color is None:
                if r.font.color and r.font.color.rgb:
                    accent_color = r.font.color.rgb
                name_size = size
            elif not seen_body and size and 8 <= size.pt <= 12:
                body_size = size
                if r.font.name:
                    body_font = r.font.name
                seen_body = True
        if seen_body and accent_color is not None:
            break

    sec = doc.sections[0] if doc.sections else None

    return {
        "body_font": body_font or "Calibri",
        "body_size": body_size or Pt(10.5),
        "accent_color": accent_color,  # RGBColor or None -> caller uses default navy
        "name_size": name_size or Pt(22),
        "top_margin": sec.top_margin if sec and sec.top_margin else Inches(0.6),
        "bottom_margin": sec.bottom_margin if sec and sec.bottom_margin else Inches(0.6),
        "left_margin": sec.left_margin if sec and sec.left_margin else Inches(0.7),
        "right_margin": sec.right_margin if sec and sec.right_margin else Inches(0.7),
    }


def extract_resume_content(file_bytes: bytes, filename: str) -> dict:
    """
    Reads an uploaded resume file (.pdf, .docx, or .txt) and returns:
        {
            "text": str,                 # plain extracted text
            "file_type": "docx"|"pdf"|"txt",
            "style": dict | None,        # only populated for .docx uploads
        }
    `style` (when present) can be passed straight into resume_to_docx() /
    resume_to_pdf() so the Modifier can offer "keep my original design" as
    an alternative to the system's built-in template.
    """
    name = (filename or "").lower()

    if name.endswith(".txt"):
        return {"text": file_bytes.decode("utf-8", errors="ignore"), "file_type": "txt", "style": None}

    if name.endswith(".docx"):
        doc = Document(io.BytesIO(file_bytes))
        text = "\n".join(p.text for p in doc.paragraphs)
        style = _extract_docx_style(doc)
        return {"text": text, "file_type": "docx", "style": style}

    if name.endswith(".pdf"):
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        return {"text": text, "file_type": "pdf", "style": None}

    raise ValueError("Unsupported file type. Please upload a .pdf, .docx, or .txt file.")


def extract_text_from_upload(uploaded_file) -> str:
    """
    Accepts a Streamlit UploadedFile (.pdf, .docx, or .txt) and returns its
    plain text content, for the Resume Rater's "upload a file" input mode.
    """
    data = uploaded_file.read()
    return extract_resume_content(data, getattr(uploaded_file, "name", ""))["text"]


# =================================================================
# 8. Document export — DOCX and PDF (both built in-memory, no disk
#    writes, so the Streamlit frontend can wire them straight into
#    st.download_button).
# =================================================================

_NAVY = RGBColor(0x1F, 0x3B, 0x57)
_NAVY_HEX = colors.HexColor("#1F3B57")
_GRAY_HEX = colors.HexColor("#555555")


def _hex(rgb: RGBColor) -> str:
    """RGBColor -> 'RRGGBB' hex string (for OXML border colors)."""
    return "%02X%02X%02X" % (rgb[0], rgb[1], rgb[2])


def resume_to_docx(resume: Resume, style: Optional[dict] = None) -> io.BytesIO:
    """
    Renders a validated `Resume` into a clean, ATS-friendly .docx file.
    Returns an in-memory BytesIO buffer ready for st.download_button.

    `style`, if provided (see extract_resume_content()), carries over the
    body font/size, accent color, and margins detected from a candidate's
    originally-uploaded .docx — used by the Modifier's "keep my original
    design" option. Any key missing from `style` falls back to the
    system's default look.
    """
    style = style or {}
    body_font = style.get("body_font") or "Calibri"
    body_size = style.get("body_size") or Pt(10.5)
    accent = style.get("accent_color") or _NAVY
    name_size = style.get("name_size") or Pt(22)
    top_m = style.get("top_margin") or Inches(0.6)
    bottom_m = style.get("bottom_margin") or Inches(0.6)
    left_m = style.get("left_margin") or Inches(0.7)
    right_m = style.get("right_margin") or Inches(0.7)

    doc = Document()

    normal = doc.styles["Normal"]
    normal.font.name = body_font
    normal.font.size = body_size

    for section in doc.sections:
        section.top_margin = top_m
        section.bottom_margin = bottom_m
        section.left_margin = left_m
        section.right_margin = right_m

    def add_section_heading(text: str):
        h = doc.add_paragraph()
        h.paragraph_format.space_before = Pt(12)
        h.paragraph_format.space_after = Pt(4)
        run = h.add_run(text.upper())
        run.bold = True
        run.font.size = Pt(12)
        run.font.color.rgb = accent
        # thin bottom border under the heading, like a horizontal rule
        pPr = h._p.get_or_add_pPr()
        pBdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "6")
        bottom.set(qn("w:space"), "1")
        bottom.set(qn("w:color"), _hex(accent))
        pBdr.append(bottom)
        pPr.append(pBdr)

    def small_italic(text: str, size: float = 9.5):
        p = doc.add_paragraph()
        r = p.add_run(text)
        r.italic = True
        r.font.size = Pt(size)
        r.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
        return p

    # ---- Header: name, contact, links ----
    name_p = doc.add_paragraph()
    name_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    name_run = name_p.add_run(resume.name)
    name_run.bold = True
    name_run.font.size = name_size
    name_run.font.color.rgb = accent

    contact_bits = [b for b in [resume.email, resume.phone, resume.location] if b]
    if contact_bits:
        p = doc.add_paragraph(" | ".join(contact_bits))
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.runs[0].font.size = Pt(10)

    link_bits = [b for b in [resume.linkedin, resume.github, resume.portfolio] if b]
    if link_bits:
        p = doc.add_paragraph(" | ".join(link_bits))
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.runs[0].font.size = Pt(9.5)
        p.runs[0].font.color.rgb = RGBColor(0x44, 0x44, 0x44)

    # ---- Summary ----
    if resume.summary:
        add_section_heading("Summary")
        doc.add_paragraph(resume.summary)

    # ---- Skills ----
    if resume.skills:
        add_section_heading("Skills")
        doc.add_paragraph(" • ".join(resume.skills))

    # ---- Education ----
    if resume.education:
        add_section_heading("Education")
        for e in resume.education:
            p = doc.add_paragraph()
            p.add_run(e.degree).bold = True
            p.add_run(f"  —  {e.institution}")
            meta = f"{e.start_year} – {e.end_year}"
            if e.grade:
                meta += f"   |   Grade: {e.grade}"
            if e.location:
                meta += f"   |   {e.location}"
            small_italic(meta)

    # ---- Experience ----
    if resume.experience:
        add_section_heading("Experience")
        for exp in resume.experience:
            p = doc.add_paragraph()
            p.add_run(exp.role).bold = True
            p.add_run(f"  —  {exp.company}")
            meta = f"{exp.start_date} – {exp.end_date}"
            if exp.location:
                meta += f"   |   {exp.location}"
            small_italic(meta)
            for r in exp.responsibilities:
                doc.add_paragraph(r, style="List Bullet")

    # ---- Projects ----
    if resume.projects:
        add_section_heading("Projects")
        for proj in resume.projects:
            p = doc.add_paragraph()
            p.add_run(proj.title).bold = True
            doc.add_paragraph(proj.description)
            small_italic("Tech: " + ", ".join(proj.tech_stack))
            if proj.link:
                link_p = doc.add_paragraph()
                link_run = link_p.add_run(proj.link)
                link_run.font.size = Pt(9.5)
                link_run.font.color.rgb = RGBColor(0x1A, 0x5A, 0xA6)

    # ---- Certifications ----
    if resume.certifications:
        add_section_heading("Certifications")
        for c in resume.certifications:
            line = c.name
            extras = [b for b in [c.issuer, c.date] if b]
            if extras:
                line += " — " + ", ".join(extras)
            doc.add_paragraph(line, style="List Bullet")

    # ---- Achievements ----
    if resume.achievements:
        add_section_heading("Achievements")
        for a in resume.achievements:
            doc.add_paragraph(a, style="List Bullet")

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


def _pdf_font_variants(font_name: Optional[str]):
    """Maps an arbitrary font family name (e.g. from a docx's detected body
    font) onto reportlab's built-in font families, since embedding
    arbitrary fonts isn't worth the added dependency for this app. Returns
    (regular, bold, italic) reportlab font names."""
    name = (font_name or "").strip().lower()
    if any(k in name for k in ("times", "georgia", "garamond", "cambria", "serif", "book")):
        return "Times-Roman", "Times-Bold", "Times-Italic"
    if any(k in name for k in ("courier", "consolas", "mono")):
        return "Courier", "Courier-Bold", "Courier-Oblique"
    return "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"


def _rgbcolor_to_reportlab(rgb: RGBColor) -> colors.Color:
    return colors.Color(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)


# ── Unicode sanitization for PDF (reportlab built-in fonts) ──────────────────
_PDF_CHAR_MAP = {
    "\u2010": "-",   # Unicode hyphen → ASCII hyphen
    "\u2011": "-",   # non-breaking hyphen → hyphen
    "\u2012": "-",   # figure dash → hyphen
    "\u2013": "-",   # en dash → hyphen
    "\u2014": "-",   # em dash → hyphen
    "\u2015": "-",   # horizontal bar → hyphen
    "\u2212": "-",   # minus sign → hyphen
    "\u2018": "'",   # left single quote → apostrophe
    "\u2019": "'",   # right single quote → apostrophe
    "\u201C": '"',   # left double quote → double quote
    "\u201D": '"',   # right double quote → double quote
    "\u2026": "...", # ellipsis → three dots
    "\u00A0": " ",   # non-breaking space → space
    "\u200B": "",    # zero-width space → nothing
    "\u00B7": "*",   # middle dot → asterisk
    "\u2022": "*",   # bullet → asterisk
    "\uFEFF": "",    # BOM → nothing
}


def _sanitize_for_pdf(obj):
    """Recursively replace Unicode characters unsupported by reportlab's
    built-in fonts (Helvetica/Times/Courier) with safe ASCII equivalents.

    Works on strings, lists, dicts, and Pydantic models. Does not remove
    meaningful content — only replaces characters that would render as
    black boxes (■) in the generated PDF.
    """
    if isinstance(obj, str):
        for u_char, replacement in _PDF_CHAR_MAP.items():
            obj = obj.replace(u_char, replacement)
        # Catch-all: anything still outside cp1252 gets transliterated to
        # its closest ASCII form instead of rendering as a black box.
        try:
            obj.encode("cp1252")
        except UnicodeEncodeError:
            obj = unicodedata.normalize("NFKD", obj).encode("ascii", "ignore").decode("ascii")
        return obj
    if isinstance(obj, list):
        return [_sanitize_for_pdf(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _sanitize_for_pdf(v) for k, v in obj.items()}
    if hasattr(obj, "__dict__"):
        for attr, value in vars(obj).items():
            if isinstance(value, (str, list, dict)):
                try:
                    setattr(obj, attr, _sanitize_for_pdf(value))
                except (AttributeError, TypeError):
                    pass
        return obj
    return obj


def resume_to_pdf(resume: Resume, style: Optional[dict] = None) -> io.BytesIO:
    """
    Renders a validated `Resume` into a clean, ATS-friendly PDF.
    Returns an in-memory BytesIO buffer ready for st.download_button.
    Built with reportlab's platypus layer only (pure Python — no
    LibreOffice / system dependencies required).

    `style`, if provided (see extract_resume_content()), carries over an
    accent color and an approximate font family detected from a
    candidate's originally-uploaded .docx — used by the Modifier's "keep
    my original design" option. Note PDF font matching is approximate
    (mapped to the closest of Helvetica/Times/Courier, since reportlab's
    built-in fonts don't include arbitrary embedded fonts); the .docx
    export matches the original typography more precisely.
    """
    style = style or {}
    accent = _rgbcolor_to_reportlab(style["accent_color"]) if style.get("accent_color") else _NAVY_HEX
    body_size_pt = style["body_size"].pt if style.get("body_size") else 10
    name_size_pt = style["name_size"].pt if style.get("name_size") else 22
    font_regular, font_bold, font_italic = _pdf_font_variants(style.get("body_font"))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        leftMargin=0.65 * inch,
        rightMargin=0.65 * inch,
        title=f"{resume.name} - Resume",
    )

    styles = getSampleStyleSheet()

    name_style = ParagraphStyle(
        "NameStyle", parent=styles["Title"], alignment=TA_CENTER,
        textColor=accent, fontSize=name_size_pt, leading=name_size_pt + 4, spaceAfter=2,
        fontName=font_bold,
    )
    contact_style = ParagraphStyle(
        "ContactStyle", parent=styles["Normal"], alignment=TA_CENTER,
        fontSize=9.5, textColor=_GRAY_HEX, spaceAfter=2, fontName=font_regular,
    )
    heading_style = ParagraphStyle(
        "SectionHeading", parent=styles["Heading2"], textColor=accent,
        fontSize=12, spaceBefore=10, spaceAfter=4, fontName=font_bold,
    )
    body_style = ParagraphStyle(
        "Body", parent=styles["Normal"], fontSize=body_size_pt,
        leading=body_size_pt + 3, fontName=font_regular,
    )
    italic_small = ParagraphStyle(
        "ItalicSmall", parent=styles["Normal"], fontSize=max(body_size_pt - 1, 8),
        textColor=_GRAY_HEX, fontName=font_italic, spaceAfter=4,
    )
    bold_line = ParagraphStyle(
        "BoldLine", parent=styles["Normal"], fontSize=body_size_pt + 0.5,
        fontName=font_bold, spaceBefore=6,
    )
    link_style = ParagraphStyle(
        "LinkLine", parent=styles["Normal"], fontSize=9.5,
        textColor=colors.HexColor("#1A5AA6"), spaceAfter=4, fontName=font_regular,
    )

    def esc(text: str) -> str:
        return _xml_escape(_sanitize_for_pdf(text or ""))

    def bullets(items: List[str]) -> ListFlowable:
        return ListFlowable(
            [ListItem(Paragraph(esc(i), body_style), leftIndent=12) for i in items],
            bulletType="bullet", start="•", leftIndent=14,
        )

    def section_heading(text: str):
        story.append(Paragraph(text.upper(), heading_style))
        story.append(HRFlowable(width="100%", thickness=0.75, color=accent, spaceAfter=6))

    story = [Paragraph(esc(resume.name), name_style)]

    contact_bits = [b for b in [resume.email, resume.phone, resume.location] if b]
    if contact_bits:
        story.append(Paragraph(esc(" | ".join(contact_bits)), contact_style))
    link_bits = [b for b in [resume.linkedin, resume.github, resume.portfolio] if b]
    if link_bits:
        story.append(Paragraph(esc(" | ".join(link_bits)), contact_style))
    story.append(Spacer(1, 6))

    if resume.summary:
        section_heading("Summary")
        story.append(Paragraph(esc(resume.summary), body_style))

    if resume.skills:
        section_heading("Skills")
        story.append(Paragraph(esc(" • ".join(resume.skills)), body_style))

    if resume.education:
        section_heading("Education")
        for e in resume.education:
            story.append(Paragraph(f"<b>{esc(e.degree)}</b> - {esc(e.institution)}", bold_line))
            meta = f"{esc(e.start_year)} - {esc(e.end_year)}"
            if e.grade:
                meta += f" | Grade: {esc(e.grade)}"
            if e.location:
                meta += f" | {esc(e.location)}"
            story.append(Paragraph(meta, italic_small))

    if resume.experience:
        section_heading("Experience")
        for exp in resume.experience:
            story.append(Paragraph(f"<b>{esc(exp.role)}</b> - {esc(exp.company)}", bold_line))
            meta = f"{esc(exp.start_date)} - {esc(exp.end_date)}"
            if exp.location:
                meta += f" | {esc(exp.location)}"
            story.append(Paragraph(meta, italic_small))
            story.append(bullets(exp.responsibilities))

    if resume.projects:
        section_heading("Projects")
        for proj in resume.projects:
            story.append(Paragraph(f"<b>{esc(proj.title)}</b>", bold_line))
            story.append(Paragraph(esc(proj.description), body_style))
            story.append(Paragraph("Tech: " + esc(", ".join(proj.tech_stack)), italic_small))
            if proj.link:
                story.append(Paragraph(esc(proj.link), link_style))

    if resume.certifications:
        section_heading("Certifications")
        lines = []
        for c in resume.certifications:
            line = c.name
            extras = [b for b in [c.issuer, c.date] if b]
            if extras:
                line += " - " + ", ".join(extras)
            lines.append(line)
        story.append(bullets(lines))

    if resume.achievements:
        section_heading("Achievements")
        story.append(bullets(resume.achievements))

    doc.build(story)
    buffer.seek(0)
    return buffer


# =================================================================
# Quick manual test: python backend.py
# =================================================================
if __name__ == "__main__":
    sample_raw_data = {
        "name": "Dil Jain",
        "email": "diljain121@gmail.com",
        "phone": "7621086000",
        "location": "Surat, India",
        "linkedin": "linkedin.com/in/dil-jain-b0980439b",
        "github": "github.com/diljain4444",
        "portfolio": "website-chi-pink-qqf6nszyza.vercel.app",
        "raw_summary": "3rd year AI/DS student, builds deployed AI systems end to end",
        "skills": "python, langchain, langgraph, fastapi, gemini, groq, streamlit",
        "education": [
            {
                "degree": "B.Tech in AI & Data Science",
                "institution": "Sarvajanik College of Engineering & Technology",
                "location": "Surat, India",
                "start_year": "2023",
                "end_year": "2027",
                "grade": "9.2 GPA",
            }
        ],
        "experience": [],
        "projects": [
            {
                "title": "FoodLens AI",
                "description": (
                    "multimodal app that detects ingredients from a photo "
                    "and suggests recipes, deployed"
                ),
                "tech_stack": "Python, LangChain, Gemini",
                "link": "",
            }
        ],
        "certifications": [],
        "achievements": "",
    }

    resume = generate_resume(sample_raw_data)
    print(resume.model_dump_json(indent=2))