"""
roadmap_backend.py
LangGraph-based backend for the Placement Mentor "Roadmap" feature.
Model: Groq openai/gpt-oss-120b

Install:
    pip install langgraph langchain-groq pydantic

Env:
    export GROQ_API_KEY=your_key_here
"""

import os
import math
import json
from datetime import date
from typing import List, Optional, Literal, TypedDict

from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv

load_dotenv()  # reads GROQ_API_KEY from a .env file in the same folder, if present


# ---------------------------------------------------------------------------
# LLM setup
# ---------------------------------------------------------------------------

def get_llm(temperature: float = 0.5) -> ChatGroq:
    return ChatGroq(
        # model="meta-llama/llama-4-scout-17b-16e-instruct",
        model="openai/gpt-oss-120b",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=temperature,
    )


# ---------------------------------------------------------------------------
# Structured output schema for the phase-generation step
# ---------------------------------------------------------------------------

class RoadmapPhase(BaseModel):
    phase_name: str = Field(description="Short name of this phase, e.g. 'DSA Foundations'")
    duration_weeks: int = Field(description="How many weeks this phase should take")
    priority: Literal["high", "medium", "low"]
    topics: List[str] = Field(description="Specific topics/skills covered in this phase")
    milestone: str = Field(description="A concrete, measurable milestone for this phase")
    suggested_project: Optional[str] = Field(
        default=None, description="A project to build during this phase, if relevant"
    )
    why_this_order: str = Field(
        description="1-2 lines on why this phase comes at this point in the roadmap"
    )


class RoadmapPlanOutput(BaseModel):
    phases: List[RoadmapPhase]
    weekly_time_commitment: str = Field(
        description="Summary like '10-12 hrs/week' reflecting the user's stated availability"
    )


# ---------------------------------------------------------------------------
# Graph state
# ---------------------------------------------------------------------------

class RoadmapState(TypedDict, total=False):
    user_profile: dict
    gap_summary: str
    phases: List[dict]
    weekly_time_commitment: str
    available_weeks: Optional[int]
    final_output: dict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _profile_to_text(profile: dict) -> str:
    lines = [
        f"- {k.replace('_', ' ').title()}: {v}"
        for k, v in profile.items()
        if v not in (None, "", [])
    ]
    return "\n".join(lines)


def _weeks_until(deadline_str: Optional[str]) -> Optional[int]:
    if not deadline_str:
        return None
    try:
        deadline = date.fromisoformat(deadline_str)
    except ValueError:
        return None
    delta_days = (deadline - date.today()).days
    if delta_days <= 0:
        return None
    return max(1, round(delta_days / 7))


# ---------------------------------------------------------------------------
# Node 1 — Gap analysis (plain text generation)
# ---------------------------------------------------------------------------

def analyze_gap(state: RoadmapState) -> RoadmapState:
    llm = get_llm(temperature=0.3)
    profile_text = _profile_to_text(state["user_profile"])

    messages = [
        SystemMessage(content=(
            "You are a placement-prep mentor for engineering students in India. "
            "Given a student's current profile and target role, write a crisp 2-3 sentence "
            "gap summary: what they already have going for them, and the biggest gaps "
            "between their current level and their target. Be specific and honest, not generic."
        )),
        HumanMessage(content=f"Student profile:\n{profile_text}"),
    ]

    response = llm.invoke(messages)
    return {"gap_summary": response.content.strip()}


# ---------------------------------------------------------------------------
# Node 2 — Phase generation (structured output)
# ---------------------------------------------------------------------------

def generate_phases(state: RoadmapState) -> RoadmapState:
    llm = get_llm(temperature=0.4).with_structured_output(RoadmapPlanOutput)
    profile_text = _profile_to_text(state["user_profile"])

    messages = [
        SystemMessage(content=(
            "You are a placement-prep roadmap generator. Based on the student's profile and "
            "gap summary below, produce a phased preparation roadmap (3-6 phases). "
            "Order phases logically (foundations before advanced topics, DSA alongside "
            "core CS, projects timed to reinforce recently learned skills, interview prep "
            "near the end). Keep phase durations realistic given their stated weekly time "
            "availability. Prioritize phases as high/medium/low based on how critical they "
            "are for the target role and company tier."
        )),
        HumanMessage(content=(
            f"Student profile:\n{profile_text}\n\n"
            f"Gap summary:\n{state['gap_summary']}"
        )),
    ]

    result: RoadmapPlanOutput = llm.invoke(messages)
    return {
        "phases": [phase.model_dump() for phase in result.phases],
        "weekly_time_commitment": result.weekly_time_commitment,
    }


# ---------------------------------------------------------------------------
# Node 3 — Deadline adjustment (pure logic, no LLM call)
# ---------------------------------------------------------------------------

def adjust_for_deadline(state: RoadmapState) -> RoadmapState:
    available_weeks = state.get("available_weeks")
    phases = state["phases"]

    if not available_weeks:
        return {"phases": phases}

    total_weeks = sum(p["duration_weeks"] for p in phases)
    if total_weeks <= available_weeks:
        return {"phases": phases}

    scale = available_weeks / total_weeks
    adjusted = []
    for p in phases:
        scaled = max(1, math.floor(p["duration_weeks"] * scale))
        adjusted.append({**p, "duration_weeks": scaled})

    return {"phases": adjusted}


# ---------------------------------------------------------------------------
# Node 4 — Finalize output
# ---------------------------------------------------------------------------

def finalize(state: RoadmapState) -> RoadmapState:
    return {
        "final_output": {
            "gap_summary": state["gap_summary"],
            "phases": state["phases"],
            "weekly_time_commitment": state["weekly_time_commitment"],
        }
    }


# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------

def build_graph():
    graph = StateGraph(RoadmapState)
    graph.add_node("analyze_gap", analyze_gap)
    graph.add_node("generate_phases", generate_phases)
    graph.add_node("adjust_for_deadline", adjust_for_deadline)
    graph.add_node("finalize", finalize)

    graph.set_entry_point("analyze_gap")
    graph.add_edge("analyze_gap", "generate_phases")
    graph.add_edge("generate_phases", "adjust_for_deadline")
    graph.add_edge("adjust_for_deadline", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()


_compiled_graph = None


def get_compiled_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


# ---------------------------------------------------------------------------
# Public entrypoint — this is what frontend.py calls
# ---------------------------------------------------------------------------

def generate_roadmap(user_input: dict) -> dict:
    """
    user_input keys expected (all optional except where noted):
      year, branch, dsa_problems_solved, known_skills (list),
      os_confidence, dbms_confidence, cn_confidence, oops_confidence,
      projects_count, certifications, target_role, company_tier,
      placement_mode, dream_companies, hours_per_week, deadline (YYYY-MM-DD),
      learning_style
    """
    graph = get_compiled_graph()
    available_weeks = _weeks_until(user_input.get("deadline"))

    initial_state: RoadmapState = {
        "user_profile": user_input,
        "available_weeks": available_weeks,
    }

    result = graph.invoke(initial_state)
    return result["final_output"]


if __name__ == "__main__":
    sample_input = {
        "year": "3rd year",
        "branch": "AI & Data Science",
        "dsa_problems_solved": "50-150",
        "known_skills": ["Python", "FastAPI", "LangChain"],
        "os_confidence": "familiar",
        "dbms_confidence": "strong",
        "cn_confidence": "not started",
        "oops_confidence": "strong",
        "projects_count": 3,
        "certifications": "None",
        "target_role": "AI/ML Engineer",
        "company_tier": "Product-based (mid-tier)",
        "placement_mode": "Off-campus",
        "dream_companies": "Razorpay, Groww",
        "hours_per_week": 15,
        "deadline": "2027-01-15",
        "learning_style": "Practice-first",
    }
    output = generate_roadmap(sample_input)
    print(json.dumps(output, indent=2))