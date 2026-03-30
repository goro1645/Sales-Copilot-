import re

from agent.schemas import ApplicationRecord


def extract_keywords(text: str) -> list[str]:
    """Return lowercase keywords in first-seen order.

    We intentionally keep this helper deterministic so it is easy to test and reason about
    before any LLM-based extraction is introduced.
    """

    tokens = re.findall(r"[A-Za-z]+", text.lower())
    keywords: list[str] = []
    for token in tokens:
        if token not in keywords:
            keywords.append(token)
    return keywords


def score_resume_fit(
    *,
    resume_text: str,
    required_skills: list[str],
    preferred_skills: list[str] | None = None,
) -> dict:
    """Score resume fit using simple keyword overlap.

    This deterministic scorer gives us a stable baseline. Later, we can combine it with
    model-based reasoning without losing an easy-to-understand fallback path.
    """

    preferred_skills = preferred_skills or []
    resume_keywords = set(extract_keywords(resume_text))

    matched_skills = [skill for skill in required_skills if skill.lower() in resume_keywords]
    missing_skills = [skill for skill in required_skills if skill.lower() not in resume_keywords]
    preferred_hits = [skill for skill in preferred_skills if skill.lower() in resume_keywords]

    score = 0
    if required_skills:
        score = int(len(matched_skills) / len(required_skills) * 100)

    return {
        "score": score,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "preferred_hits": preferred_hits,
    }


def build_application_record(
    *,
    company: str,
    role: str,
    match_score: int,
    status: str,
    resume_version: str,
    cover_letter: str,
) -> dict:
    """Build a validated record for later JSON or SQLite persistence."""

    record = ApplicationRecord(
        company=company,
        role=role,
        match_score=match_score,
        status=status,
        resume_version=resume_version,
        cover_letter=cover_letter,
    )
    return record.model_dump()
