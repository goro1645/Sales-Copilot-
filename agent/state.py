from typing import TypedDict


class JobAgentState(TypedDict, total=False):
    """Shared state that flows through the LangGraph job agent.

    We keep this as a TypedDict instead of a large class so every node can update only the
    fields it owns. That makes the graph easier to follow when you're learning.
    """

    company: str
    role: str
    job_posting: str
    resume_text: str
    job_summary: str
    required_skills: list[str]
    preferred_skills: list[str]
    matched_skills: list[str]
    missing_skills: list[str]
    preferred_hits: list[str]
    match_score: int
    rewritten_resume: str
    cover_letter: str
    apply_decision: str
