from dotenv import load_dotenv
load_dotenv()
from langchain_groq import ChatGroq
from pydantic import BaseModel
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from langchain_community.document_loaders import Docx2txtLoader, TextLoader, PyMuPDFLoader, UnstructuredImageLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END, START
from typing import TypedDict
from typing import List, Annotated, Any
import re
from langgraph.types import interrupt
from langgraph.checkpoint.memory import MemorySaver

# ── NEW IMPORTS ───────────────────────────────────────────────────────────────
import edge_tts
import asyncio
import io
import base64
import tempfile
import os

import os
model_text = ChatGroq(
    
    # model="meta-llama/llama-4-scout-17b-16e-instruct",
    model="openai/gpt-oss-120b",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.5,
)


# ═══════════════════════════════════════════════════════════════════════════════
# NEW: TEXT → AUDIO (edge-tts)
# ═══════════════════════════════════════════════════════════════════════════════

async def _synthesize_audio(text: str) -> bytes:
    """Core async TTS synthesis using edge-tts. Returns raw MP3 bytes."""
    communicate = edge_tts.Communicate(text, "en-US-GuyNeural", rate="-10%")
    buffer = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buffer.write(chunk["data"])
    buffer.seek(0)
    audio_bytes = buffer.read()
    print(f"[TTS] Synthesized {len(audio_bytes)} bytes of audio for text: {text[:60]}...")
    return audio_bytes


async def text_to_audio_b64_async(text: str) -> str:
    """Async version — call this from FastAPI async routes."""
    try:
        print(f"[TTS] text_to_audio_b64_async called, text length: {len(text)}")
        audio_bytes = await _synthesize_audio(text)
        if not audio_bytes:
            print("[TTS] WARNING: edge-tts returned empty audio bytes")
            return ""
        result = base64.b64encode(audio_bytes).decode("utf-8")
        print(f"[TTS] base64 result length: {len(result)}")
        return result
    except Exception as e:
        print(f"[TTS] FAILED: {repr(e)}")
        import traceback
        traceback.print_exc()
        return ""


def text_to_audio_b64(text: str) -> str:
    """
    Sync wrapper for TTS. Detects if an asyncio event loop is already
    running (e.g. inside FastAPI) and handles it correctly.
    Returns base64-encoded MP3 string, or "" on failure.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # We're inside an async context (FastAPI) — cannot use asyncio.run().
        # Use a new thread to avoid blocking the event loop.
        import concurrent.futures
        print("[TTS] Detected running event loop, using thread executor")
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, _synthesize_audio(text))
            try:
                audio_bytes = future.result(timeout=30)
                if not audio_bytes:
                    print("[TTS] WARNING: edge-tts returned empty audio bytes")
                    return ""
                result = base64.b64encode(audio_bytes).decode("utf-8")
                print(f"[TTS] Sync wrapper success, base64 length: {len(result)}")
                return result
            except Exception as e:
                print(f"[TTS] Thread executor FAILED: {repr(e)}")
                import traceback
                traceback.print_exc()
                return ""
    else:
        # No event loop running — safe to use asyncio.run()
        try:
            print("[TTS] No running event loop, using asyncio.run()")
            audio_bytes = asyncio.run(_synthesize_audio(text))
            if not audio_bytes:
                return ""
            return base64.b64encode(audio_bytes).decode("utf-8")
        except Exception as e:
            print(f"[TTS] asyncio.run FAILED: {repr(e)}")
            import traceback
            traceback.print_exc()
            return ""

# alias kept for backward compat
question_to_audio_b64 = text_to_audio_b64
question_to_audio_b64_async = text_to_audio_b64_async


# ═══════════════════════════════════════════════════════════════════════════════
# AUDIO → TEXT (Groq Whisper API — no local model needed)
# ═══════════════════════════════════════════════════════════════════════════════

_groq_client = None  # lazy-loaded singleton


def _get_groq_client():
    global _groq_client
    if _groq_client is None:
        from groq import Groq
        _groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    return _groq_client


def transcribe_audio(audio_bytes: bytes) -> str:
    """
    Convert raw audio bytes (wav from st.audio_input) to text using
    Groq's hosted Whisper API.  No local model download required.
    Returns transcribed string or empty string on failure.
    """
    try:
        client = _get_groq_client()

        # st.audio_input returns WAV; save to temp file so Groq can read it
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        with open(tmp_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                file=("answer.wav", audio_file, "audio/wav"),
                model="whisper-large-v3-turbo",
                language="en",
                response_format="text",
            )

        os.unlink(tmp_path)

        # response is a plain string when response_format="text"
        transcript = response.strip() if isinstance(response, str) else response.text.strip()
        return transcript

    except Exception as e:
        print(f"Groq transcription error: {e}")
        return ""


# ═══════════════════════════════════════════════════════════════════════════════
# ORIGINAL CODE (unchanged below)
# ═══════════════════════════════════════════════════════════════════════════════

def ingestion(path):
    file_type = path.split(".")[-1].lower()
    if file_type == "pdf":
        loader = PyMuPDFLoader(path)
        documents = loader.load()
    elif file_type == "docx":
        loader = Docx2txtLoader(path)
        documents = loader.load()
    elif file_type in ["png", "jpg", "jpeg"]:
        loader = UnstructuredImageLoader(path)
        documents = loader.load()
    else:
        raise ValueError("Unsupported file format")
    return documents


def cleaning(documents):
    cleaned_docs = []
    for doc in documents:
        text = doc.page_content
        text = re.sub(r'Page\s+\d+', ' ', text)
        text = re.sub(r'^\s*\d+\s*$', ' ', text, flags=re.MULTILINE)
        text = re.sub(r'[^\x00-\x7F]+', ' ', text)
        text = re.sub(r'\n+', '\n', text)
        text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        cleaned_docs.append(Document(page_content=text, metadata=doc.metadata))
    return cleaned_docs


def preprocess(path):
    docs = ingestion(path=path)
    clean_text = cleaning(docs)
    splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=50)
    splitted_doc = splitter.split_documents(clean_text)
    context = " "
    for item in splitted_doc:
        context += item.page_content
    return context


# ═══════════════════════════════════════════════════════════════════════════════
# NEW: JOB DESCRIPTION PREPROCESSING (Resume + JD mode)
# ═══════════════════════════════════════════════════════════════════════════════

def preprocess_jd(jd_text: str) -> str:
    """
    Clean raw Job Description text (pasted by the user in a text area).
    Mirrors the normalization done in `cleaning()` for resumes, but operates
    directly on plain text since a JD isn't loaded from a file.
    Returns an empty string for empty/whitespace-only input.
    """
    if not jd_text or not jd_text.strip():
        return ""
    text = jd_text
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    return text


import operator


class state(TypedDict):
    education: str
    skills: List[str]
    projects: List[str]
    interview_mode: str            # NEW: "resume_only" | "resume_jd"
    jd_context: str                # NEW: cleaned Job Description text ("" for resume_only)
    user_question: str
    user_answer: str
    history: Annotated[list[Any], operator.add]
    current_depth: int
    feedback: str
    covered_topics: Annotated[list[str], operator.add]
    follow_up_required: bool
    current_topic: str
    score: int
    review_final: Any
    over: bool


class user_info(BaseModel):
    education: str
    skills: List[str]
    projects: List[str]


user_info_pydantic = PydanticOutputParser(pydantic_object=user_info)


def information_retrival(context):
    prompt = PromptTemplate(
        template="""
You are an expert information extractor. Your task is to carefully read the given context 
and extract the following details accurately.

Extract the information and return it in the required format:

1. **Education** - Extract the highest or most relevant educational qualification 
   (degree, institution, year if mentioned). If multiple, combine into a single string.

2. **Skills** - Extract all technical and non-technical skills mentioned 
   (programming languages, tools, frameworks, soft skills, etc.).

3. **Projects** - Extract all projects mentioned along with a brief description 
   if available. Each project should be a separate item in the list.

Context:
{context}

{format_instructions}

Rules:
- Only extract information that is explicitly mentioned in the context.
- Do not make up or infer information that is not present.
- If a field has no information, use an empty string or empty list accordingly.
""",
        input_variables=["context"],
        partial_variables={"format_instructions": user_info_pydantic.get_format_instructions()}
    )
    chain = prompt | model_text | user_info_pydantic
    result = chain.invoke({"context": context})
    return result


class question_verify(BaseModel):
    topic_covered: str
    question: str


question_parser = PydanticOutputParser(pydantic_object=question_verify)


def question_generator(state):
    education = state.get("education", "")
    skills = state.get("skills", "")
    projects = state.get("projects", "")
    history = state.get("history", "")
    covered_topics = state.get("covered_topics", "")
    current_topic = state.get("current_topic", "")
    current_depth = state.get("current_depth", 0)
    follow_up_required = state.get("follow_up_required", False)
    user_question = state.get("user_question", "")
    user_answer = state.get("user_answer", "")
    feedback = state.get("feedback", "")
    interview_mode = state.get("interview_mode", "resume_only")   # NEW
    jd_context = state.get("jd_context", "")                       # NEW

    if (follow_up_required == False) or (current_depth > 2):

        # ── NEW: Resume + JD mode uses an extended, role-aware prompt ─────────
        # The original resume-only prompt/chain below is left completely
        # untouched so existing behaviour is preserved exactly.
        if interview_mode == "resume_jd" and jd_context:
            prompt = PromptTemplate(
                template="""
You are an elite, highly experienced technical interviewer conducting a professional, adaptive interview with the user for a SPECIFIC job role.

Your primary objective is to simulate a real-world, role-focused interviewer by asking intelligent, relevant, non-repetitive questions based on BOTH the candidate's profile AND the target Job Description (JD). You must assess how well the candidate fits the role, not just their general background.

## Available Candidate Data

You are provided with:
* Personal Information (name, education, background, experience, career goals) -> {education}
* Skills (technical and non-technical) -> {skills}
* Projects completed -> {projects}
* Interview history -> {history}
* Topic-covered list (questions/topics already asked) -> {covered_topics}

## Target Job Description

* Job Description (required skills, responsibilities, experience expectations) -> {jd_context}

## Core Interview Rules

### 1. Conversation History Validation (MANDATORY)

Before asking any new question:
* Carefully analyze the full interview history.
* Check whether the candidate's introduction/personal background has already been asked.
* If NOT asked: Start with introduction-focused questions such as:
  * "Tell me about yourself."
  * "Walk me through your educational background."
* If ALREADY asked: NEVER repeat introduction or personal background questions. Progress directly to skills, projects, JD-alignment, or behavioral questions.

### 2. Strict Non-Repetition Rule

* Review the topic-covered list before generating each question.
* NEVER ask previously asked questions, reworded duplicates, or conceptually repetitive questions from the same subtopic.
* Every new question must add fresh evaluative value.

### 3. Intelligent Progression Strategy (Role-Aware)

Questions must follow a logical, role-focused interviewer flow:
* Stage A: Personal Introduction (only if not already covered)
* Stage B: Skills Assessment, prioritizing skills explicitly required in the JD (fundamental → intermediate → advanced)
* Stage C: Project Deep Dive, favoring projects most relevant to the JD's responsibilities
* Stage D: Role & Responsibility Alignment — probe how the candidate's experience maps to the specific responsibilities and expectations listed in the JD
* Stage E: Gap Assessment — if the JD requires skills or experience not evident in the candidate's profile, ask a question that surfaces whether the candidate actually has that knowledge
* Stage F: Behavioral + Scenario-Based — realistic, role-specific scenarios drawn from the JD's responsibilities (teamwork, conflict resolution, ownership, prioritization)

### 4. Question Structure Rules (STRICT)

* Ask ONLY 1 clean, focused question at a time
* If a sub-part is needed, include a MAXIMUM of 1 sub-question only
* NEVER combine more than 2 parts into a single question
* The question should feel natural, like a real interviewer speaking

BAD EXAMPLE (too many parts):
"Can you explain your project, what tech stack you used, why you chose it, what challenges you faced, and how you'd improve it?"

GOOD EXAMPLE (focused + max 1 sub-part):
"The role calls for strong experience with X — where have you used that in your projects?"

### 5. Professional Interview Tone

* Be realistic, conversational, and engaging.
* One question at a time, always.
* Do not read the JD back verbatim — use it only to steer what you ask.

### 6. Output Format

Return the topic covered and the question.
Strictly follow the schema -> {format_instructions}
""",
                input_variables=["education", "skills", "projects", "history", "covered_topics", "jd_context"],
                partial_variables={"format_instructions": question_parser.get_format_instructions()}
            )
            chain = prompt | model_text | question_parser
            result = chain.invoke({
                "education": education,
                "skills": skills,
                "projects": projects,
                "history": history,
                "covered_topics": covered_topics,
                "jd_context": jd_context,
            })
            user_answer = interrupt(result.question)
            return {
                "covered_topics": [result.topic_covered],
                "user_question": result.question,
                "current_topic": result.topic_covered,
                "history": [f"Q: {result.question}\nA: {user_answer}"],
                "user_answer": user_answer
            }

        # ── ORIGINAL resume-only prompt/chain (unchanged) ─────────────────────
        prompt = PromptTemplate(
            template="""
You are an elite, highly experienced technical interviewer conducting a professional, adaptive interview with the user.

Your primary objective is to simulate a real-world interviewer by asking intelligent, relevant, non-repetitive questions based on the candidate's profile and prior conversation history.

## Available Candidate Data

You are provided with:
* Personal Information (name, education, background, experience, career goals) -> {education}
* Skills (technical and non-technical) -> {skills}
* Projects completed -> {projects}
* Interview history -> {history}
* Topic-covered list (questions/topics already asked) -> {covered_topics}


## Core Interview Rules

### 1. Conversation History Validation (MANDATORY)

Before asking any new question:
* Carefully analyze the full interview history.
* Check whether the candidate's introduction/personal background has already been asked.
* If NOT asked: Start with introduction-focused questions such as:
  * "Tell me about yourself."
  * "Walk me through your educational background."
* If ALREADY asked: NEVER repeat introduction or personal background questions. Progress directly to skills, projects, or behavioral questions.

### 2. Strict Non-Repetition Rule

* Review the topic-covered list before generating each question.
* NEVER ask previously asked questions, reworded duplicates, or conceptually repetitive questions from the same subtopic.
* Every new question must add fresh evaluative value.

### 3. Intelligent Progression Strategy

Questions must follow a logical interviewer flow:
* Stage A: Personal Introduction (only if not already covered)
* Stage B: Skills Assessment (fundamental → intermediate → advanced)
* Stage C: Project Deep Dive (prioritize after core skills)
* Stage D: Behavioral + Problem Solving (communication, teamwork, conflict resolution)

### 4. Question Structure Rules (STRICT)

* Ask ONLY 1 clean, focused question at a time
* If a sub-part is needed, include a MAXIMUM of 1 sub-question only
* NEVER combine more than 2 parts into a single question
* The question should feel natural, like a real interviewer speaking

BAD EXAMPLE (too many parts):
"Can you explain your project, what tech stack you used, why you chose it, what challenges you faced, and how you'd improve it?"

GOOD EXAMPLE (focused + max 1 sub-part):
"Tell me about your most recent project — what problem were you solving with it?"

### 5. Professional Interview Tone

* Be realistic, conversational, and engaging.
* One question at a time, always.

### 6. Output Format

Return the topic covered and the question.
Strictly follow the schema -> {format_instructions}
""",
            input_variables=["education", "skills", "projects", "history", "covered_topics"],
            partial_variables={"format_instructions": question_parser.get_format_instructions()}
        )
        chain = prompt | model_text | question_parser
        result = chain.invoke({
            "education": education,
            "skills": skills,
            "projects": projects,
            "history": history,
            "covered_topics": covered_topics,
        })
        user_answer = interrupt(result.question)
        return {
            "covered_topics": [result.topic_covered],
            "user_question": result.question,
            "current_topic": result.topic_covered,
            "history": [f"Q: {result.question}\nA: {user_answer}"],
            "user_answer": user_answer
        }

    else:
        parser = StrOutputParser()
        prompt = PromptTemplate(
            template="""
You are an expert interview follow-up question generator.

Previous question -> {user_question}
Candidate's answer -> {user_answer}
Evaluator's feedback -> {feedback}
Current topic -> {current_topic}

Generate ONLY ONE follow-up question on the SAME topic.

QUESTION RULES:
- Ask only 1 clean, focused question
- If you need to add a sub-part, maximum 1 sub-question only (e.g., "...and why do you think that is?")
- Never combine more than 2 parts into a single question
- Keep it conversational and natural, like a real interviewer would ask
- The question should directly stem from the gap or point mentioned in the feedback

BAD EXAMPLE (too many sub-questions):
"Can you explain what a closure is, how it differs from a lambda, when you'd use it, and what are its memory implications?"

GOOD EXAMPLE (focused + max 1 sub-part):
"You mentioned closures briefly — can you give me a quick real-world example of where you'd actually use one?"

Return ONLY the question text, nothing else.
""",
            input_variables=["user_answer", "user_question", "feedback", "current_topic"]
        )
        chain = prompt | model_text | parser
        result = chain.invoke({
            "user_question": user_question,
            "user_answer": user_answer,
            "current_topic": current_topic,
            "feedback": feedback
        })
        user_answer = interrupt(result)
        return {
            "user_question": result,
            "current_topic": current_topic,
            "current_depth": current_depth + 1,
            "history": [f"Q: {result}\nA: {user_answer}"],
            "user_answer": user_answer
        }


class ans_eval(BaseModel):
    score: int
    follow_up_required: bool
    feedback: str


ans_parser = PydanticOutputParser(pydantic_object=ans_eval)


def answer_evaluator(state):
    question = state.get("user_question")
    answer = state.get("user_answer")

    prompt = PromptTemplate(
        template="""
You are a friendly technical interviewer giving feedback after hearing a candidate's answer.

QUESTION -> {question}
ANSWER -> {answer}

Evaluate the answer and return:
1. Score (0-10)
2. follow_up_required (boolean)
3. Feedback that sounds like a real human interviewer — casual, warm, and short (1-2 lines max)

SCORING: 0-2=no understanding, 3-4=weak, 5-6=basic, 7-8=strong, 9-10=excellent

FOLLOW-UP RULE:
- true → answer is incomplete, vague, or missing key points
- false → topic is well covered, ready to move on

FEEDBACK RULES:
- Sound like a real person talking, NOT a formal report
- If answer is correct/good: give a quick positive nod, briefly mention what was strong
- If answer has mistakes or gaps: gently point out what's missing or incorrect in one line
- Keep it to 1-2 sentences max
- DO NOT ask any follow-up questions
- DO NOT transition to or hint at any next question
- DO NOT use phrases like "tell me", "curious to know", "what about", or any question-like endings
- End naturally as if wrapping up your thoughts on this answer only

ENDING STYLE EXAMPLES (pick tone based on context, don't copy verbatim):
- "Yeah, that covers the key points nicely."
- "Good foundation — just the core idea of X was a bit fuzzy."
- "Solid answer overall, you clearly get the concept."
- "That's mostly right, though Y is worth brushing up on."
- "Makes sense, and you touched on the important parts."

strictly follow schema -> {format_instructions}
""",
        input_variables=["question", "answer"],
        partial_variables={"format_instructions": ans_parser.get_format_instructions()}
    )

    chain = prompt | model_text | ans_parser
    result = chain.invoke({"question": question, "answer": answer})
    return {
        "score": result.score,
        "follow_up_required": result.follow_up_required,
        "feedback": result.feedback
    }


from typing import Optional
from pydantic import Field


class Topic(BaseModel):
    topic_name: str = Field(description="name of the topic")
    rating: float = Field(description="rating of the answer for the particular topic")
    weakness: str = Field(description="weak point that for the topic")


class Road_map(BaseModel):
    topic_name: str
    concepts_to_learn: List[str]
    duration_it_takes: str
    best_resource: List[str]


class review(BaseModel):
    overall_rating: float
    topic: List[Topic]
    overall_strength: List[str]
    overall_weakness: List[str]
    top_recommendation: List[str]
    road_map: List[Road_map]
    communication_score: float
    confidence_score: float


review_parser = PydanticOutputParser(pydantic_object=review)


def report_ready(state):
    history = state["history"]
    covered_topics = state["covered_topics"]

    prompt = PromptTemplate(
        template="""
You are an expert AI technical interviewer and career evaluator.

Analyze the complete interview conversation and generate a detailed performance report.

INTERVIEW HISTORY:
{history}

TOPICS COVERED:
{covered_topics}

INSTRUCTIONS:
1. Evaluate performance across all covered topics with rating/10 and weakness for each.
2. Overall rating (0-10) considering technical knowledge, problem-solving, communication, confidence.
3. Overall strengths and weaknesses.
4. Top recommendations for improvement.
5. Personalized roadmap for weak topics with concepts, duration, and resources.
6. Communication score (0-10) and Confidence score (0-10).

Be honest: 9-10=excellent, 7-8=strong, 5-6=average, below 5=weak.

STRICTLY FOLLOW SCHEMA->{format_instructions}""",
        input_variables=["history", "covered_topics"],
        partial_variables={"format_instructions": review_parser.get_format_instructions()}
    )

    chain = prompt | model_text | review_parser
    result = chain.invoke({"history": history, "covered_topics": covered_topics})
    return {"review_final": result}


def route_after_eval(state):
    covered = state.get("covered_topics", [])
    over = state.get("over")
    if over == True:
        return "end"
    if len(set(covered)) >= 5:
        return "end"
    return "continue"


graph = StateGraph(state)
graph.add_node("question_generator", question_generator)
graph.add_node("answer_evaluator", answer_evaluator)
graph.add_node("report_ready", report_ready)

graph.add_edge(START, "question_generator")
graph.add_edge("question_generator", "answer_evaluator")
graph.add_edge("report_ready", END)

graph.add_conditional_edges(
    "answer_evaluator",
    route_after_eval,
    {"continue": "question_generator", "end": "report_ready"}
)

checkpointer = MemorySaver()
workflow = graph.compile(checkpointer=checkpointer)