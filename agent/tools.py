import re

from agent.schemas import ApplicationRecord


JOB_POSTING_STOPWORDS = {
    "a",
    "ability",
    "an",
    "and",
    "around",
    "backend",
    "build",
    "building",
    "company",
    "data",
    "demos",
    "designing",
    "engineer",
    "engineering",
    "experience",
    "familiarity",
    "for",
    "frameworks",
    "in",
    "integrating",
    "is",
    "labs",
    "language",
    "lightweight",
    "looking",
    "models",
    "need",
    "needs",
    "of",
    "or",
    "other",
    "preferred",
    "practical",
    "products",
    "quality",
    "reliability",
    "required",
    "requirements",
    "role",
    "similar",
    "skills",
    "stores",
    "strong",
    "the",
    "to",
    "with",
    "workflows",
}


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


def parse_job_description(job_posting: str) -> dict:
    """Extract a lightweight summary and skill lists from a JD.

    Strategy:
    1. If the JD contains explicit `Requirements` / `Preferred` sections, trust those first.
    2. Otherwise fall back to a filtered full-text keyword scan.
    """

    def filtered_keywords(text: str) -> list[str]:
        return [keyword for keyword in extract_keywords(text) if keyword not in JOB_POSTING_STOPWORDS]

    current_section = None
    required_skills: list[str] = []
    preferred_skills: list[str] = []

    for raw_line in job_posting.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        lowered = line.lower().lstrip("#").strip()
        if "requirement" in lowered or lowered == "required":
            current_section = "required"
            continue
        if "preferred" in lowered or "nice to have" in lowered:
            current_section = "preferred"
            continue
        if line.startswith("#"):
            current_section = None
            continue
        if not line.startswith(("-", "*")) or current_section is None:
            continue

        keywords = filtered_keywords(line[1:].strip())
        target = required_skills if current_section == "required" else preferred_skills
        for keyword in keywords:
            if keyword not in target:
                target.append(keyword)

    if not required_skills and not preferred_skills:
        required_skills = filtered_keywords(job_posting)

    return {
        "job_summary": job_posting.strip(),
        "required_skills": required_skills,
        "preferred_skills": preferred_skills,
    }


def rewrite_resume_for_job(
    *,
    resume_text: str,
    role: str,
    required_skills: list[str],
    matched_skills: list[str],
) -> str:
    """Produce a readable fallback rewrite before we plug in the MiniMind generator."""

    highlighted = ", ".join(matched_skills or required_skills[:3])
    return (
        f"Tailored for {role}\n"
        f"{resume_text}\n\n"
        f"Relevant skills to highlight: {highlighted}"
    )


def generate_cover_letter(
    *,
    company: str,
    role: str,
    matched_skills: list[str],
) -> str:
    """Create a deterministic cover letter skeleton for high-match cases."""

    skills_summary = ", ".join(matched_skills) or "relevant LLM application skills"
    return (
        f"Dear {company},\n\n"
        f"I am excited to apply for the {role} role. My background aligns well with "
        f"the following skills: {skills_summary}.\n\n"
        "Best regards,"
    )


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
