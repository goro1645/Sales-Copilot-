import json


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
        "You are a sales copilot. The customer profile is background only for disambiguation, "
        "not a source of facts. Extract facts from the meeting note first. "
        "Return valid JSON only. Do not invent missing details."
    )
    user_prompt = (
        "Parse the meeting notes into structured JSON with fields:\n"
        "- account_name\n"
        "- customer_roles\n"
        "- confirmed_needs\n"
        "- objections\n"
        "- next_steps\n"
        "- budget_signals\n"
        "- timeline_signals\n"
        "- competitors\n\n"
        "Field guidance:\n"
        "- account_name: use the clearest company or account named in the note; when the meeting note does not identify a clearer company or account, use the service account named in the customer profile.\n"
        "- confirmed_needs: the customer questions, requests, or needs raised in the dialogue.\n"
        "- objections: blockers, constraints, or reasons a request cannot proceed as asked.\n"
        "- budget_signals: explicit pricing, coupon, refund, price-protection, difference-amount, freight, invoice, or payment-rule statements in the dialogue.\n"
        "- timeline_signals: time commitments, waiting windows, urgency, or status-gated timing statements such as today callback, 3 business days, after receipt confirmation, after return shipment, or flash sale ending soon.\n"
        "- next_steps: actionable resolutions, instructions, commitments, or handling steps stated in the dialogue.\n"
        "- In customer-service dialogues, keep handling steps in next_steps even if the same sentence also contains a restriction or status condition.\n"
        "- In customer-service dialogues, the same fact may appear in multiple fields when it carries action plus timing or cost semantics.\n"
        "- Copy timing or status facts into timeline_signals even when the sentence is also used in next_steps or objections.\n"
        "- Copy pricing or refund facts into budget_signals even when the sentence is also used in next_steps or objections.\n"
        "- If the agent already provided a concrete solution or promised handling action, include it in next_steps.\n"
        "- Do not leave next_steps empty when the note already contains solutions already provided, explicit instructions, or follow-up handling steps.\n\n"
        f"Customer profile:\n{customer_profile_text}\n\n"
        f"Meeting notes:\n{meeting_note_text}"
    )
    return _build_messages(system_prompt, user_prompt)


def build_lead_scoring_messages(
    *,
    customer_profile_text: str,
    meeting_summary: dict,
    retrieved_docs: list[dict],
    account_memory: dict,
) -> list[dict[str, str]]:
    system_prompt = (
        "You are a sales copilot. Score leads from the provided evidence only. "
        "Return valid JSON only. Do not invent missing details. "
        "Return exactly one JSON object with these top-level fields: "
        "lead_score, lead_priority, opportunity_stage, risk_flags, reasons, evidence. "
        "Do not use alternate field names such as score, priority, stage, or risks."
    )
    user_prompt = (
        "Evaluate the lead and produce JSON using this schema:\n"
        "{\n"
        '  "lead_score": <integer 0-100>,\n'
        '  "lead_priority": "low|medium|high",\n'
        '  "opportunity_stage": "discovery|qualification|proposal|negotiation|closed_won|closed_lost",\n'
        '  "risk_flags": ["..."],\n'
        '  "reasons": ["..."],\n'
        '  "evidence": ["..."]\n'
        "}\n"
        "If key information is missing, add missing_required_facts to risk_flags.\n\n"
        f"Customer profile:\n{customer_profile_text}\n\n"
        "Meeting summary:\n"
        f"{json.dumps(meeting_summary, ensure_ascii=False)}\n\n"
        "Retrieved context:\n"
        f"{json.dumps(retrieved_docs, ensure_ascii=False)}\n\n"
        "Account memory:\n"
        f"{json.dumps(account_memory, ensure_ascii=False)}"
    )
    return _build_messages(system_prompt, user_prompt)


def build_followup_plan_messages(
    *,
    meeting_summary: dict,
    opportunity_stage: str,
    risk_flags: list[str],
    task_candidates: list[dict],
) -> list[dict[str, str]]:
    system_prompt = (
        "You are a sales copilot. Create a follow-up plan from the evidence only. "
        "Return valid JSON only. Do not hallucinate."
    )
    user_prompt = (
        "Write a concise follow-up plan in JSON with next actions, owners, timing, "
        "and stage-aware guidance.\n"
        "Prioritize the task candidates below. Do not ignore the task candidates when they already contain concrete follow-up actions. "
        "Only add generic qualification tasks when the task candidates are insufficient.\n\n"
        "Meeting summary:\n"
        f"{json.dumps(meeting_summary, ensure_ascii=False)}\n\n"
        f"Opportunity stage:\n{opportunity_stage}\n\n"
        f"Risk flags:\n{', '.join(risk_flags) if risk_flags else 'None'}\n\n"
        "Task candidates:\n"
        f"{json.dumps(task_candidates, ensure_ascii=False)}"
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


def build_signal_reclassification_messages(
    *,
    conversation_context: str,
    signal_candidates: list[dict],
) -> list[dict[str, str]]:
    system_prompt = (
        "You are a customer-service signal classifier. "
        "Classify each candidate into one fixed label only by calling the classify_signal_candidates function. "
        "Allowed labels are budget_signals, timeline_signals, next_steps, and other. "
        "Do not reply with plain text."
    )
    user_prompt = json.dumps(
        {
            "task": "classify_signal_candidates",
            "conversation_context": conversation_context,
            "signal_candidates": signal_candidates,
        },
        ensure_ascii=False,
    )
    return _build_messages(system_prompt, user_prompt)


def build_signal_candidate_generation_messages(
    *,
    meeting_note_text: str,
    baseline_parse: dict,
) -> list[dict[str, str]]:
    system_prompt = (
        "You are a customer-service span proposal assistant. "
        "Propose multiple candidate spans by calling the propose_signal_candidates function only. "
        "Each candidate text must be copied verbatim from the meeting note text as one contiguous span. "
        "Prefer shorter spans over long paraphrases. "
        "You may return multiple candidates from the same sentence. "
        "Allowed coarse labels are budget_signals, timeline_signals, next_steps, and other. "
        "Do not reply with plain text."
    )
    user_prompt = json.dumps(
        {
            "task": "propose_signal_candidates",
            "meeting_note_text": meeting_note_text,
            "baseline_parse": {
                "budget_signals": baseline_parse.get("budget_signals", []),
                "timeline_signals": baseline_parse.get("timeline_signals", []),
                "next_steps": baseline_parse.get("next_steps", []),
                "objections": baseline_parse.get("objections", []),
            },
            "constraints": {
                "return_multiple_candidates": True,
                "copy_verbatim_from_meeting_note": True,
                "max_candidates": 8,
            },
        },
        ensure_ascii=False,
    )
    return _build_messages(system_prompt, user_prompt)
