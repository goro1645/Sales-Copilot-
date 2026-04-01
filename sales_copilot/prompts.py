def _build_messages(system_prompt: str, user_prompt: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_meeting_parse_messages(
    *,
    customer_profile_text: str,
    meeting_note_text: str,
) -> list[dict[str, str]]:
    system_prompt = (
        "You are a sales copilot. Extract only facts that appear in the notes. "
        "Return valid JSON only. Do not invent missing details."
    )
    user_prompt = (
        "Parse the meeting notes into structured JSON with fields like attendees, "
        "company, pains, objections, next_steps, and crm_fields.\n\n"
        f"Customer profile:\n{customer_profile_text}\n\n"
        f"Meeting notes:\n{meeting_note_text}"
    )
    return _build_messages(system_prompt, user_prompt)


def build_lead_scoring_messages(
    *,
    customer_profile_text: str,
    meeting_summary: str,
    retrieved_docs: str,
    account_memory: str,
) -> list[dict[str, str]]:
    system_prompt = (
        "You are a sales copilot. Score leads from the provided evidence only. "
        "Return valid JSON only. Do not invent missing details."
    )
    user_prompt = (
        "Evaluate the lead and produce JSON with a numeric score, short reasons, "
        "and the evidence used.\n\n"
        f"Customer profile:\n{customer_profile_text}\n\n"
        f"Meeting summary:\n{meeting_summary}\n\n"
        "Retrieved context:\n"
        f"{retrieved_docs}\n\n"
        "Account memory:\n"
        f"{account_memory}"
    )
    return _build_messages(system_prompt, user_prompt)


def build_followup_plan_messages(
    *,
    meeting_summary: str,
    opportunity_stage: str,
    risk_flags: list[str],
) -> list[dict[str, str]]:
    system_prompt = (
        "You are a sales copilot. Create a follow-up plan from the evidence only. "
        "Return valid JSON only. Do not hallucinate."
    )
    user_prompt = (
        "Write a concise follow-up plan in JSON with next actions, owners, timing, "
        "and stage-aware guidance.\n\n"
        f"Meeting summary:\n{meeting_summary}\n\n"
        f"Opportunity stage:\n{opportunity_stage}\n\n"
        f"Risk flags:\n{', '.join(risk_flags) if risk_flags else 'None'}"
    )
    return _build_messages(system_prompt, user_prompt)


def build_crm_update_messages(
    *,
    lead_context: str,
    meeting_parse_json: str,
    current_crm_state_json: str | None = None,
) -> list[dict[str, str]]:
    system_prompt = (
        "You are a sales copilot. Produce CRM update instructions from the evidence only. "
        "Return valid JSON only. Do not invent missing details."
    )
    user_prompt = (
        "Generate CRM update JSON with fields to update and the supporting evidence.\n\n"
        f"Lead context:\n{lead_context}\n\n"
        f"Meeting parse JSON:\n{meeting_parse_json}"
    )
    if current_crm_state_json:
        user_prompt += f"\n\nCurrent CRM state JSON:\n{current_crm_state_json}"
    return _build_messages(system_prompt, user_prompt)


def build_dashboard_summary_messages(
    *,
    meeting_parse_json: str,
    lead_scoring_json: str,
    followup_plan_json: str,
    crm_update_json: str | None = None,
) -> list[dict[str, str]]:
    system_prompt = (
        "You are a sales copilot. Summarize pipeline signals for a dashboard. "
        "Return valid JSON only. Do not invent missing details."
    )
    user_prompt = (
        "Generate a dashboard summary JSON with status, score, risks, and next actions.\n\n"
        f"Meeting parse JSON:\n{meeting_parse_json}\n\n"
        f"Lead scoring JSON:\n{lead_scoring_json}\n\n"
        f"Follow-up plan JSON:\n{followup_plan_json}"
    )
    if crm_update_json:
        user_prompt += f"\n\nCRM update JSON:\n{crm_update_json}"
    return _build_messages(system_prompt, user_prompt)
