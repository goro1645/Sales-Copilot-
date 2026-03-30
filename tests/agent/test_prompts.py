from agent.prompts import build_cover_letter_messages, build_resume_rewrite_messages


def test_build_resume_rewrite_messages_includes_role_and_skill_context():
    messages = build_resume_rewrite_messages(
        role="LLM Application Engineer",
        resume_text="Built MiniMind APIs.",
        required_skills=["python", "langgraph"],
        matched_skills=["python"],
        missing_skills=["langgraph"],
    )

    assert messages[0]["role"] == "system"
    assert "resume optimization assistant" in messages[0]["content"].lower()
    assert "LLM Application Engineer" in messages[1]["content"]
    assert "python" in messages[1]["content"]
    assert "langgraph" in messages[1]["content"]


def test_build_cover_letter_messages_includes_company_role_and_skills():
    messages = build_cover_letter_messages(
        company="MiniMind Labs",
        role="LLM Application Engineer",
        matched_skills=["python", "fastapi"],
        resume_text="Built MiniMind APIs.",
    )

    assert messages[0]["role"] == "system"
    assert "cover letter assistant" in messages[0]["content"].lower()
    assert "MiniMind Labs" in messages[1]["content"]
    assert "LLM Application Engineer" in messages[1]["content"]
    assert "python, fastapi" in messages[1]["content"]
