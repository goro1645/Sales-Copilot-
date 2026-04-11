from evals.sales_copilot.workflow_quality_runner import (
    normalize_actual_crm_writeback,
    normalize_actual_generated_tasks,
)


def test_normalize_actual_generated_tasks_from_task_payload():
    workflow_result = {
        "task_payload": [
            {
                "title": "Send proposal",
                "description": "Email the proposal",
                "priority": "high",
                "owner": "Sales",
                "due_at": "2026-04-12",
            }
        ]
    }

    tasks = normalize_actual_generated_tasks(workflow_result)

    assert tasks == [
        {
            "title": "Send proposal",
            "description": "Email the proposal",
            "priority": "high",
            "owner": "Sales",
            "timing_or_due_hint": "2026-04-12",
        }
    ]


def test_normalize_actual_crm_writeback_extracts_core_fields():
    workflow_result = {
        "crm_writeback_performed": True,
        "crm_update_ids": [1],
        "lead_priority": "medium",
        "opportunity_stage": "qualification",
        "risk_flags": ["missing_required_facts"],
        "follow_up_plan": {"summary": "Clarify budget and timeline."},
    }

    crm = normalize_actual_crm_writeback(workflow_result)

    assert crm["crm_writeback_performed"] is True
    assert crm["crm_update_ids"] == [1]
    assert crm["lead_priority"] == "medium"
    assert crm["opportunity_stage"] == "qualification"
    assert crm["risk_flags"] == ["missing_required_facts"]
    assert crm["follow_up_summary"] == "Clarify budget and timeline."
