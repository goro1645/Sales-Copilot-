def build_resume_rewrite_messages(
    *,
    role: str,
    resume_text: str,
    required_skills: list[str],
    matched_skills: list[str],
    missing_skills: list[str],
) -> list[dict]:
    """Build the prompt used to tailor resume bullets for one job.

    We keep prompts as plain message builders so they are easy to test, reuse, and tweak
    without digging through the orchestration code.
    """

    return [
        {
            "role": "system",
            "content": (
                "You are a resume optimization assistant. Rewrite the resume so it is concise, "
                "truthful, and tailored to the target role. Keep the tone professional and avoid "
                "inventing experience."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Target role: {role}\n"
                f"Required skills: {', '.join(required_skills) or 'None'}\n"
                f"Already matched skills: {', '.join(matched_skills) or 'None'}\n"
                f"Still missing skills: {', '.join(missing_skills) or 'None'}\n\n"
                f"Original resume:\n{resume_text}\n\n"
                "Please rewrite the most relevant project and experience bullets for this role."
            ),
        },
    ]


def build_cover_letter_messages(
    *,
    company: str,
    role: str,
    matched_skills: list[str],
    resume_text: str,
) -> list[dict]:
    """Build the prompt used to generate a short application cover letter."""

    return [
        {
            "role": "system",
            "content": (
                "You are a cover letter assistant. Write short, targeted cover letters that sound "
                "professional, specific, and grounded in the candidate's actual background."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Company: {company}\n"
                f"Role: {role}\n"
                f"Matched skills: {', '.join(matched_skills) or 'None'}\n\n"
                f"Candidate resume:\n{resume_text}\n\n"
                "Please write a concise cover letter for this application."
            ),
        },
    ]
