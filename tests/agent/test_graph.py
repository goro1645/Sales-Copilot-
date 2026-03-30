from agent.graph import build_job_agent_graph


def test_job_agent_graph_rejects_low_match_jobs():
    graph = build_job_agent_graph()

    result = graph.invoke(
        {
            "company": "MiniMind Labs",
            "role": "LLM Application Engineer",
            "job_posting": "Need LangGraph and SQLite experience.",
            "resume_text": "Experienced in Python model serving only.",
            "required_skills": ["langgraph", "sqlite"],
            "preferred_skills": [],
        }
    )

    assert result["match_score"] == 0
    assert result["apply_decision"] == "reject"
    assert result["cover_letter"] == ""


def test_job_agent_graph_rewrites_resume_for_medium_match_jobs():
    graph = build_job_agent_graph()

    result = graph.invoke(
        {
            "company": "MiniMind Labs",
            "role": "LLM Application Engineer",
            "job_posting": "Need Python, FastAPI and LangGraph.",
            "resume_text": "Built MiniMind services with Python and FastAPI.",
            "required_skills": ["python", "fastapi", "langgraph"],
            "preferred_skills": [],
        }
    )

    assert result["match_score"] == 66
    assert result["apply_decision"] == "rewrite_resume"
    assert "Tailored for LLM Application Engineer" in result["rewritten_resume"]
    assert result["cover_letter"] == ""


def test_job_agent_graph_generates_cover_letter_for_high_match_jobs():
    graph = build_job_agent_graph()

    result = graph.invoke(
        {
            "company": "MiniMind Labs",
            "role": "LLM Application Engineer",
            "job_posting": "Need Python and FastAPI.",
            "resume_text": "Delivered Python and FastAPI based MiniMind applications.",
            "required_skills": ["python", "fastapi"],
            "preferred_skills": ["streamlit"],
        }
    )

    assert result["match_score"] == 100
    assert result["apply_decision"] == "ready_to_apply"
    assert "MiniMind Labs" in result["cover_letter"]
    assert "LLM Application Engineer" in result["cover_letter"]
