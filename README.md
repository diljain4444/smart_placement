# 🎯 Smart Placement — AI Career Platform

An AI-powered career preparation platform with two main features:
- **Mock Interview** — Practice with an AI interviewer avatar (voice + text), get real-time feedback, and receive a comprehensive performance report
- **Resume Suite** — Build, modify, and rate resumes using AI, with ATS-optimized PDF downloads

## Architecture

```
smart_placement/
├── frontend/              ← React + Vite (port 5173)
│   ├── src/
│   │   ├── pages/         ← Home, MockInterview, ResumeSuite
│   │   ├── components/    ← Navbar, AvatarPanel, InterviewReport, ResumeForm, Loading
│   │   └── styles/        ← main.css
│   └── public/videos/     ← Interview avatar video clips
│
├── api.py                 ← FastAPI backend (single file, all routes)
├── interview_backend.py   ← AI interview logic (LangGraph + Groq LLM)
├── resume_backend.py      ← AI resume generation + rating logic
├── resume_validators.py   ← Form validation helpers
├── assets/                ← Video files (served by FastAPI)
├── requirements.txt       ← Python dependencies
└── .env                   ← GROQ_API_KEY
```

## Quick Start

### 1. Clone & Set Environment

```bash
# Copy .env.example to .env and add your Groq API key
cp .env.example .env
# Edit .env and set GROQ_API_KEY=your_key_here
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Start FastAPI Backend

```bash
uvicorn api:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.

### 4. Install & Start React Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend will open at `http://localhost:5173`.

## API Routes

| Route | Method | Description |
|---|---|---|
| `/api/health` | GET | Health check |
| `/api/interview/process-resume` | POST | Upload resume → extract profile info |
| `/api/interview/start` | POST | Create session → generate first question |
| `/api/interview/answer` | POST | Submit text answer → get feedback + next question |
| `/api/interview/voice-answer` | POST | Upload audio → transcribe → evaluate |
| `/api/interview/end` | POST | Force end → generate final report |
| `/api/interview/reset` | POST | Delete interview session |
| `/api/resume/build` | POST | Generate resume from form data → return PDF |
| `/api/resume/modify` | POST | Modify resume for JD → return PDF |
| `/api/resume/rate` | POST | Rate resume against JD → return scores |
| `/api/resume/extract-text` | POST | Extract text from uploaded file |

## How It Works

### React ↔ FastAPI Communication
- React makes HTTP requests to `/api/*` routes via Axios
- Vite dev server proxies `/api` requests to `http://localhost:8000`
- No direct state sharing — all interview state lives in FastAPI's memory

### Interview Session Management
- Each interview gets a UUID session ID stored in a Python dictionary (`interview_sessions`)
- The session tracks: thread ID, interview mode, voice mode, completion status
- LangGraph workflow runs server-side with `MemorySaver` checkpointer
- Questions are generated via LangGraph `interrupt()` mechanism
- Answers are submitted via `Command(resume=answer)` to resume the workflow

### Resume PDF Generation
- React sends form data as JSON string via FormData
- FastAPI calls `generate_resume()` → `resume_to_pdf()` → streams PDF back
- React creates a Blob URL and triggers browser download

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, Vite, React Router, Axios |
| Backend API | FastAPI, Uvicorn |
| AI/LLM | LangChain, LangGraph, Groq (openai/gpt-oss-120b) |
| Speech | Edge-TTS (text-to-speech), Groq Whisper (speech-to-text) |
| Documents | python-docx, ReportLab (PDF), PyMuPDF |
| Validation | Pydantic v2, resume_validators.py |

## Environment Variables

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | Groq API key for LLM inference and Whisper STT |

## Features

### Mock Interview
- Upload resume (PDF/DOCX) with optional job description
- Voice mode (browser microphone → Groq Whisper transcription) or text mode
- AI avatar with 3 video states (speaking, waiting, listening)
- Real-time TTS audio playback for questions and feedback
- Topic-by-topic progress tracking (minimum 3 topics before ending)
- Comprehensive final report with scores, analysis, and learning roadmap

### Resume Suite
- **Builder**: 7-section form with inline validation → AI-generated professional resume PDF
- **Modifier**: Upload or fill form → rewrite for target JD with configurable creativity
- **Rater**: Hybrid scoring (35% keyword similarity + 65% AI analysis) with detailed metrics
