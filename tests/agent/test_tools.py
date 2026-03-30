from agent.tools import build_application_record, extract_keywords, score_resume_fit


def test_extract_keywords_returns_stable_unique_tokens():
    text = "Python, LangGraph, FastAPI, Python, SQL, MiniMind Agent"

    keywords = extract_keywords(text)

    assert keywords == ["python", "langgraph", "fastapi", "sql", "minimind", "agent"]


def test_score_resume_fit_reports_numeric_score_and_missing_skills():
    resume_text = "Experienced in Python, FastAPI and MiniMind service deployment."
    required_skills = ["python", "langgraph", "fastapi", "sqlite"]
    preferred_skills = ["streamlit"]

    result = score_resume_fit(
        resume_text=resume_text,
        required_skills=required_skills,
        preferred_skills=preferred_skills,
    )

    assert result["score"] == 50
    assert result["matched_skills"] == ["python", "fastapi"]
    assert result["missing_skills"] == ["langgraph", "sqlite"]
    assert result["preferred_hits"] == []


def test_build_application_record_serializes_expected_fields():
    record = build_application_record(
        company="MiniMind Labs",
        role="LLM Application Engineer",
        match_score=88,
        status="ready_to_apply",
        resume_version="resume_v2",
        cover_letter="Cover letter content",
    )

    assert record["company"] == "MiniMind Labs"
    assert record["role"] == "LLM Application Engineer"
    assert record["match_score"] == 88
    assert record["status"] == "ready_to_apply"
    assert record["resume_version"] == "resume_v2"
    assert record["cover_letter"] == "Cover letter content"
    assert record["created_at"]
