"""
api.py
──────────────────────────────────────────────────────────────────────
Single FastAPI backend for Smart Placement.

All routes live here. Interview session state is kept in a simple
Python dictionary (no database required).

Run with:
    uvicorn api:app --reload --port 8000
──────────────────────────────────────────────────────────────────────
"""

import os
import uuid
import tempfile
import traceback
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from langgraph.types import Command

# ── Import existing backends (UNCHANGED) ──────────────────────────────────────
from interview_backend import (
    preprocess,
    preprocess_jd,
    information_retrival,
    workflow,
    question_to_audio_b64,
    text_to_audio_b64,
    question_to_audio_b64_async,
    text_to_audio_b64_async,
    transcribe_audio,
)
from resume_backend import (
    generate_resume,
    generate_modified_resume,
    generate_modified_resume_from_text,
    rate_resume,
    resume_to_pdf,
    extract_resume_content,
)

# ══════════════════════════════════════════════════════════════════════════════
# APP SETUP
# ══════════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="Smart Placement API",
    description="AI-powered interview preparation and resume building platform",
    version="1.0.0",
)

# ── CORS — allow the React dev server ─────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://127.0.0.1:5173",
        "http://localhost:3000",   # fallback
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Serve video assets as static files ────────────────────────────────────────
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
if os.path.isdir(ASSETS_DIR):
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


# ══════════════════════════════════════════════════════════════════════════════
# INTERVIEW SESSION STORE
# ══════════════════════════════════════════════════════════════════════════════
# Simple in-memory dict. Each key is a session_id (UUID string),
# each value is a dict holding the interview's state.
#
# In production you'd swap this for Redis or a database, but for a
# college demo / single-machine setup this is perfectly fine.

interview_sessions: dict = {}


# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def _langgraph_config(thread_id: str) -> dict:
    """Build the LangGraph config dict from a thread ID."""
    return {"configurable": {"thread_id": thread_id}}


def _get_current_question(cfg: dict) -> Optional[str]:
    """Read the current interrupt value (= the question) from the workflow."""
    try:
        gs = workflow.get_state(cfg)
        for task in gs.tasks:
            if hasattr(task, "interrupts") and task.interrupts:
                return task.interrupts[0].value
    except Exception:
        pass
    return None


def _get_graph_values(cfg: dict) -> dict:
    """Safely read the current graph values dict."""
    try:
        return workflow.get_state(cfg).values
    except Exception:
        return {}


def _serialize_review(review_obj) -> Optional[dict]:
    """Convert the review Pydantic model to a plain JSON-safe dict.

    The review object has nested Pydantic models (Topic, Road_map),
    so we use model_dump() which handles everything recursively.
    """
    if review_obj is None:
        return None
    try:
        return review_obj.model_dump()
    except AttributeError:
        # Fallback if it's already a dict
        if isinstance(review_obj, dict):
            return review_obj
        return None


def _serialize_extracted_info(info_obj) -> dict:
    """Convert the user_info Pydantic model to a JSON-safe dict."""
    try:
        return info_obj.model_dump()
    except AttributeError:
        return {
            "education": getattr(info_obj, "education", ""),
            "skills": getattr(info_obj, "skills", []),
            "projects": getattr(info_obj, "projects", []),
        }


def _safe_temp_write(upload: UploadFile) -> str:
    """Write an uploaded file to a temp location and return the path.

    The caller is responsible for deleting the temp file.
    """
    suffix = "." + upload.filename.rsplit(".", 1)[-1].lower()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(upload.file.read())
    tmp.close()
    return tmp.name


# ══════════════════════════════════════════════════════════════════════════════
# REQUEST / RESPONSE MODELS
# ══════════════════════════════════════════════════════════════════════════════
# Kept simple and in this file per user request.

class InterviewStartRequest(BaseModel):
    """Data needed to begin an interview session."""
    education: str
    skills: list
    projects: list
    interview_mode: str = "resume_only"   # "resume_only" or "resume_jd"
    jd_context: str = ""
    voice_mode: bool = True


class TextAnswerRequest(BaseModel):
    """Submit a text answer during an interview."""
    session_id: str
    answer: str
    end_interview: bool = False  # True = user wants to end early


class EndInterviewRequest(BaseModel):
    """Force-end an interview."""
    session_id: str


class ResetRequest(BaseModel):
    """Reset / delete an interview session."""
    session_id: str


# ══════════════════════════════════════════════════════════════════════════════
# ROUTES — HEALTH CHECK
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "Smart Placement API is running"}


# ══════════════════════════════════════════════════════════════════════════════
# ROUTES — INTERVIEW
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/interview/process-resume")
async def process_resume(
    file: UploadFile = File(...),
    interview_mode: str = Form("resume_only"),
    jd_text: str = Form(""),
):
    """Upload a resume file, extract education/skills/projects.

    Optionally process a Job Description if mode is 'resume_jd'.
    Returns the extracted profile information.
    """
    # Validate file type
    allowed = {"pdf", "docx"}
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in allowed:
        raise HTTPException(400, f"Unsupported file type '.{ext}'. Use PDF or DOCX.")

    tmp_path = None
    try:
        # Save to temp file for the existing backend
        tmp_path = _safe_temp_write(file)

        # Call existing backend functions (unchanged)
        context = preprocess(tmp_path)
        info = information_retrival(context)

        # Process JD if needed
        jd_context = ""
        if interview_mode == "resume_jd" and jd_text.strip():
            jd_context = preprocess_jd(jd_text)

        return {
            "extracted_info": _serialize_extracted_info(info),
            "jd_context": jd_context,
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Resume processing failed: {str(e)}")
    finally:
        # Always clean up the temp file
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.post("/api/interview/start")
async def start_interview(req: InterviewStartRequest):
    """Create a new interview session, initialize the LangGraph workflow,
    and return the first question (with optional TTS audio).
    """
    try:
        session_id = str(uuid.uuid4())
        thread_id = str(uuid.uuid4())
        cfg = _langgraph_config(thread_id)

        # Initialize the LangGraph workflow with the extracted resume info
        initial_state = {
            "education": req.education,
            "skills": req.skills,
            "projects": req.projects,
            "interview_mode": req.interview_mode,
            "jd_context": req.jd_context,
            "history": [],
            "current_depth": 0,
            "covered_topics": [],
            "follow_up_required": False,
            "over": False,
        }

        workflow.invoke(initial_state, config=cfg)

        # Read the first question from the interrupt
        question = _get_current_question(cfg)

        # Generate TTS audio if voice mode
        audio_b64 = ""
        if req.voice_mode and question:
            print(f"[API] Generating TTS for first question: {question[:60]}...")
            audio_b64 = await question_to_audio_b64_async(question)
            print(f"[API] TTS result: {'SUCCESS' if audio_b64 else 'EMPTY'}, length={len(audio_b64)}")

        # Store session info
        interview_sessions[session_id] = {
            "thread_id": thread_id,
            "interview_mode": req.interview_mode,
            "voice_mode": req.voice_mode,
            "current_question": question,
            "interview_complete": False,
        }

        return {
            "session_id": session_id,
            "question": question,
            "question_audio_b64": audio_b64,
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Failed to start interview: {str(e)}")


@app.post("/api/interview/answer")
async def submit_answer(req: TextAnswerRequest):
    """Submit a text answer, get feedback + next question (or final report).

    If end_interview=True, forces the interview to end after this answer.
    """
    session = interview_sessions.get(req.session_id)
    if not session:
        raise HTTPException(404, "Interview session not found.")

    try:
        cfg = _langgraph_config(session["thread_id"])

        # If user wants to end the interview, set the 'over' flag
        if req.end_interview:
            workflow.update_state(cfg, {"over": True})

        # Resume the workflow with the user's answer
        workflow.invoke(Command(resume=req.answer), config=cfg)

        # Read the updated state
        gs = workflow.get_state(cfg)
        gv = gs.values
        feedback = gv.get("feedback", "")
        topics_covered = list(set(gv.get("covered_topics", [])))

        # Check if interview is finished
        if not gs.next:
            # Workflow has reached END — report should be ready
            review = gv.get("review_final")
            session["interview_complete"] = True
            session["current_question"] = None

            return {
                "is_complete": True,
                "feedback": feedback,
                "topics_covered": topics_covered,
                "topic_count": len(topics_covered),
                "report": _serialize_review(review),
                "next_question": None,
                "question_audio_b64": "",
                "feedback_audio_b64": "",
            }

        # Interview continues — get the next question
        next_question = None
        for task in gs.tasks:
            if hasattr(task, "interrupts") and task.interrupts:
                next_question = task.interrupts[0].value
                break

        session["current_question"] = next_question

        # Generate TTS audio
        feedback_audio_b64 = ""
        question_audio_b64 = ""
        if session.get("voice_mode"):
            if feedback:
                feedback_audio_b64 = await text_to_audio_b64_async(feedback)
            if next_question:
                question_audio_b64 = await question_to_audio_b64_async(next_question)
            print(f"[API] Answer TTS: feedback={len(feedback_audio_b64)}, question={len(question_audio_b64)}")

        return {
            "is_complete": False,
            "feedback": feedback,
            "topics_covered": topics_covered,
            "topic_count": len(topics_covered),
            "report": None,
            "next_question": next_question,
            "question_audio_b64": question_audio_b64,
            "feedback_audio_b64": feedback_audio_b64,
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Failed to process answer: {str(e)}")


@app.post("/api/interview/voice-answer")
async def submit_voice_answer(
    session_id: str = Form(...),
    end_interview: bool = Form(False),
    audio: UploadFile = File(...),
):
    """Upload a voice recording, transcribe it, then process as a text answer.

    Returns the transcript along with feedback + next question.
    """
    session = interview_sessions.get(session_id)
    if not session:
        raise HTTPException(404, "Interview session not found.")

    try:
        # Read the audio bytes and transcribe
        audio_bytes = await audio.read()
        transcript = transcribe_audio(audio_bytes)

        if not transcript:
            raise HTTPException(400, "Could not transcribe audio. Please try again.")

        # Now process like a text answer
        cfg = _langgraph_config(session["thread_id"])

        if end_interview:
            workflow.update_state(cfg, {"over": True})

        workflow.invoke(Command(resume=transcript), config=cfg)

        gs = workflow.get_state(cfg)
        gv = gs.values
        feedback = gv.get("feedback", "")
        topics_covered = list(set(gv.get("covered_topics", [])))

        if not gs.next:
            review = gv.get("review_final")
            session["interview_complete"] = True
            session["current_question"] = None

            return {
                "transcript": transcript,
                "is_complete": True,
                "feedback": feedback,
                "topics_covered": topics_covered,
                "topic_count": len(topics_covered),
                "report": _serialize_review(review),
                "next_question": None,
                "question_audio_b64": "",
                "feedback_audio_b64": "",
            }

        next_question = None
        for task in gs.tasks:
            if hasattr(task, "interrupts") and task.interrupts:
                next_question = task.interrupts[0].value
                break

        session["current_question"] = next_question

        feedback_audio_b64 = ""
        question_audio_b64 = ""
        if session.get("voice_mode"):
            if feedback:
                feedback_audio_b64 = await text_to_audio_b64_async(feedback)
            if next_question:
                question_audio_b64 = await question_to_audio_b64_async(next_question)
            print(f"[API] Voice answer TTS: feedback={len(feedback_audio_b64)}, question={len(question_audio_b64)}")

        return {
            "transcript": transcript,
            "is_complete": False,
            "feedback": feedback,
            "topics_covered": topics_covered,
            "topic_count": len(topics_covered),
            "report": None,
            "next_question": next_question,
            "question_audio_b64": question_audio_b64,
            "feedback_audio_b64": feedback_audio_b64,
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Voice answer processing failed: {str(e)}")


@app.post("/api/interview/end")
async def end_interview(req: EndInterviewRequest):
    """Force-end an interview and generate the final report."""
    session = interview_sessions.get(req.session_id)
    if not session:
        raise HTTPException(404, "Interview session not found.")

    try:
        cfg = _langgraph_config(session["thread_id"])
        gv = _get_graph_values(cfg)

        # Set the 'over' flag and resume the workflow
        workflow.update_state(cfg, {"over": True})
        last_answer = gv.get("user_answer", "End interview")
        workflow.invoke(Command(resume=last_answer), config=cfg)

        # Read the final report
        gs = workflow.get_state(cfg)
        review = gs.values.get("review_final")

        session["interview_complete"] = True
        session["current_question"] = None

        if not review:
            raise HTTPException(500, "Report generation failed. Please try again.")

        return {
            "report": _serialize_review(review),
            "topics_covered": list(set(gs.values.get("covered_topics", []))),
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Failed to end interview: {str(e)}")


@app.post("/api/interview/reset")
async def reset_interview(req: ResetRequest):
    """Delete an interview session so the user can start fresh."""
    if req.session_id in interview_sessions:
        del interview_sessions[req.session_id]
    return {"status": "ok", "message": "Interview session cleared."}


# ══════════════════════════════════════════════════════════════════════════════
# ROUTES — RESUME
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/resume/build")
async def build_resume(
    raw_data: str = Form(...),  # JSON string of the form data
):
    """Generate a structured resume from form data and return it as a PDF.

    The raw_data field is a JSON string matching the dict format that
    generate_resume() expects (name, email, phone, skills, education, etc.)
    """
    import json

    try:
        data = json.loads(raw_data)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid form data. Expected JSON string.")

    try:
        # Call existing backend function (unchanged)
        resume = generate_resume(data)

        # Generate PDF
        pdf_buffer = resume_to_pdf(resume)
        pdf_bytes = pdf_buffer.getvalue()

        safe_name = data.get("name", "resume").replace(" ", "_")
        filename = f"{safe_name}_Resume.pdf"

        return StreamingResponse(
            iter([pdf_bytes]),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Resume generation failed: {str(e)}")


@app.post("/api/resume/modify")
async def modify_resume(
    input_mode: str = Form(...),           # "upload" or "form"
    job_description: str = Form(...),
    temperature: float = Form(0.5),
    raw_data: Optional[str] = Form(None),  # JSON string (form mode)
    resume_text: Optional[str] = Form(None),  # extracted text (upload mode)
    file: Optional[UploadFile] = File(None),   # uploaded file
):
    """Modify a resume to align with a job description.

    Supports two input modes:
    - 'upload': extract text from uploaded file, then modify
    - 'form': use structured form data
    """
    import json

    try:
        if input_mode == "form":
            if not raw_data:
                raise HTTPException(400, "Form data is required in form mode.")
            data = json.loads(raw_data)
            resume = generate_modified_resume(data, job_description, temperature=temperature)

        elif input_mode == "upload":
            # Use the text that was already extracted on the client side,
            # or extract from the uploaded file
            text = resume_text or ""

            if file and not text:
                file_bytes = await file.read()
                content = extract_resume_content(file_bytes, file.filename)
                text = content["text"]

            if not text.strip():
                raise HTTPException(400, "Resume text is required.")

            resume = generate_modified_resume_from_text(text, job_description, temperature=temperature)
        else:
            raise HTTPException(400, f"Unknown input mode: {input_mode}")

        # Generate PDF
        pdf_buffer = resume_to_pdf(resume)
        pdf_bytes = pdf_buffer.getvalue()

        safe_name = getattr(resume, "name", "resume").replace(" ", "_")
        filename = f"{safe_name}_Modified_Resume.pdf"

        return StreamingResponse(
            iter([pdf_bytes]),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Resume modification failed: {str(e)}")


@app.post("/api/resume/rate")
async def rate_resume_route(
    input_mode: str = Form(...),           # "text" or "upload"
    job_description: str = Form(...),
    resume_text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    """Rate a resume against a job description using hybrid scoring.

    Returns similarity scores, LLM rating, and aggregated hybrid score.
    """
    try:
        text = resume_text or ""

        if input_mode == "upload" and file:
            file_bytes = await file.read()
            content = extract_resume_content(file_bytes, file.filename)
            text = content["text"]

        if not text.strip():
            raise HTTPException(400, "Resume text is required.")
        if not job_description.strip():
            raise HTTPException(400, "Job description is required.")

        # Call existing backend function (unchanged)
        result = rate_resume(text, job_description)

        # Serialize the full rating result to JSON-safe dict
        return result.model_dump()

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Resume rating failed: {str(e)}")


@app.post("/api/resume/extract-text")
async def extract_text_route(
    file: UploadFile = File(...),
):
    """Extract text from an uploaded resume file (PDF, DOCX, or TXT).

    Used by the Resume Modifier and Rater before the user submits.
    """
    try:
        file_bytes = await file.read()
        content = extract_resume_content(file_bytes, file.filename)
        return {
            "text": content["text"],
            "file_type": content["file_type"],
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Text extraction failed: {str(e)}")
