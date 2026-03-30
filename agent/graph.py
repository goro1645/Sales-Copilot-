from langgraph.graph import END, StateGraph

from agent.state import JobAgentState
from agent.tools import (
    generate_cover_letter,
    parse_job_description,
    rewrite_resume_for_job,
    score_resume_fit,
)


def _generate_rewritten_resume(state: JobAgentState, content_generator=None) -> str:
    fallback = rewrite_resume_for_job(
        resume_text=state["resume_text"],
        role=state["role"],
        required_skills=state.get("required_skills", []),
        matched_skills=state.get("matched_skills", []),
    )
    if content_generator is None:
        return fallback

    try:
        generated = content_generator.rewrite_resume(
            role=state["role"],
            resume_text=state["resume_text"],
            required_skills=state.get("required_skills", []),
            matched_skills=state.get("matched_skills", []),
            missing_skills=state.get("missing_skills", []),
        )
        return generated.strip() or fallback
    except Exception:
        # The graph should still complete even if the LLM service is temporarily unavailable.
        return fallback


def _generate_cover_letter(state: JobAgentState, content_generator=None) -> str:
    fallback = generate_cover_letter(
        company=state["company"],
        role=state["role"],
        matched_skills=state.get("matched_skills", []),
    )
    if content_generator is None:
        return fallback

    try:
        generated = content_generator.generate_cover_letter(
            company=state["company"],
            role=state["role"],
            matched_skills=state.get("matched_skills", []),
            resume_text=state["resume_text"],
        )
        return generated.strip() or fallback
    except Exception:
        return fallback


def prepare_job_node(state: JobAgentState) -> dict:
    """Populate JD-derived fields only when the caller did not provide them already."""

    if state.get("required_skills"):
        return {
            "job_summary": state.get("job_summary", state["job_posting"]),
            "preferred_skills": state.get("preferred_skills", []),
        }
    return parse_job_description(state["job_posting"])


def score_fit_node(state: JobAgentState) -> dict:
    result = score_resume_fit(
        resume_text=state["resume_text"],
        required_skills=state.get("required_skills", []),
        preferred_skills=state.get("preferred_skills", []),
    )
    return {
        "match_score": result["score"],
        "matched_skills": result["matched_skills"],
        "missing_skills": result["missing_skills"],
        "preferred_hits": result["preferred_hits"],
    }


def route_after_scoring(state: JobAgentState) -> str:
    score = state["match_score"]
    if score < 60:
        return "reject"
    if score < 80:
        return "rewrite_resume"
    return "ready_to_apply"


def reject_node(state: JobAgentState) -> dict:
    return {
        "apply_decision": "reject",
        "rewritten_resume": state.get("resume_text", ""),
        "cover_letter": "",
    }


def rewrite_resume_node(state: JobAgentState, content_generator=None) -> dict:
    return {
        "apply_decision": "rewrite_resume",
        "rewritten_resume": _generate_rewritten_resume(state, content_generator),
        "cover_letter": "",
    }


def ready_to_apply_node(state: JobAgentState, content_generator=None) -> dict:
    return {
        "apply_decision": "ready_to_apply",
        "rewritten_resume": _generate_rewritten_resume(state, content_generator),
        "cover_letter": _generate_cover_letter(state, content_generator),
    }


def build_job_agent_graph(content_generator=None):
    """Compile the first job-agent graph.

    The graph intentionally stays small:
    1. prepare JD fields
    2. score fit
    3. route into reject / rewrite / ready-to-apply
    """

    builder = StateGraph(JobAgentState)
    builder.add_node("prepare_job", prepare_job_node)
    builder.add_node("score_fit", score_fit_node)
    builder.add_node("reject", reject_node)
    builder.add_node("rewrite_resume", lambda state: rewrite_resume_node(state, content_generator))
    builder.add_node("ready_to_apply", lambda state: ready_to_apply_node(state, content_generator))

    builder.set_entry_point("prepare_job")
    builder.add_edge("prepare_job", "score_fit")
    builder.add_conditional_edges(
        "score_fit",
        route_after_scoring,
        {
            "reject": "reject",
            "rewrite_resume": "rewrite_resume",
            "ready_to_apply": "ready_to_apply",
        },
    )
    builder.add_edge("reject", END)
    builder.add_edge("rewrite_resume", END)
    builder.add_edge("ready_to_apply", END)
    return builder.compile()
