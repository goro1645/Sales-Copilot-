def build_resume_rewrite_messages(
    *,
    role: str,
    resume_text: str,
    required_skills: list[str],
    matched_skills: list[str],
    missing_skills: list[str],
) -> list[dict]:
    """构建“简历改写”用的 messages。

    这里不直接调用模型，只负责“组织提示词”。
    这样拆出来之后：
    - prompt 更容易单独调试
    - 想改 wording 时，不用翻整个 graph
    - 以后换模型也不影响主流程
    """

    return [
        {
            "role": "system",
            # system 负责设定模型的角色和边界：
            # 要专业、要真实、不要虚构经历。
            "content": (
                "You are a resume optimization assistant. Rewrite the resume so it is concise, "
                "truthful, and tailored to the target role. Keep the tone professional and avoid "
                "inventing experience."
            ),
        },
        {
            "role": "user",
            # user 里塞的是本次任务的具体上下文：
            # 岗位、技能要求、已命中的技能、还缺的技能、原始简历。
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
    """构建“求职信生成”用的 messages。"""

    return [
        {
            "role": "system",
            # 求职信和简历改写虽然都是文本生成，
            # 但它们的语气和目标不同，所以单独用一套 prompt。
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
