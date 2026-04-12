from sales_copilot.task_candidates import build_task_candidates, build_tasks_from_candidates


def test_build_task_candidates_prefers_meeting_actions_and_dedupes() -> None:
    meeting_summary = {
        "next_steps": [
            "schedule technical deep-dive next week",
            "send tailored proposal by Friday",
            "schedule technical deep-dive next week",
        ],
        "confirmed_needs": ["need security review package", "want integration details"],
    }

    candidates = build_task_candidates(
        meeting_summary=meeting_summary,
        risk_flags=["stakeholder_missing"],
        lead_priority="high",
        opportunity_stage="proposal",
    )

    assert [row["text"] for row in candidates] == [
        "schedule technical deep-dive next week",
        "send tailored proposal by Friday",
        "need security review package",
        "want integration details",
        "identify missing decision makers",
    ]
    assert candidates[0]["task_type"] == "customer_meeting"
    assert candidates[1]["task_type"] == "proposal_or_quote"
    assert candidates[2]["task_type"] == "internal_prep"
    assert candidates[3]["task_type"] == "internal_prep"
    assert candidates[4]["task_type"] == "risk_mitigation"


def test_build_tasks_from_candidates_materializes_specific_titles() -> None:
    tasks = build_tasks_from_candidates(
        [
            {
                "text": "send tailored proposal by Friday",
                "source": "meeting_next_steps",
                "task_type": "proposal_or_quote",
                "priority_hint": "high",
                "timing_hint": "this_week",
                "evidence": ["Customer asked for a tailored proposal by Friday."],
            },
            {
                "text": "schedule technical deep-dive next week",
                "source": "meeting_next_steps",
                "task_type": "customer_meeting",
                "priority_hint": "high",
                "timing_hint": "next_week",
                "evidence": ["Customer wants a technical deep-dive next week."],
            },
        ]
    )

    assert tasks[0]["title"] == "Send tailored proposal"
    assert "Customer asked for a tailored proposal" in tasks[0]["description"]
    assert tasks[0]["priority"] == "high"
    assert tasks[1]["title"] == "Schedule technical deep-dive"
    assert tasks[1]["owner"] == "Sales"
