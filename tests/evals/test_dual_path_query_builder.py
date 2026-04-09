from evals.sales_copilot.dual_path_query_builder import build_retrieval_query


def test_build_retrieval_query_prioritizes_confirmed_needs_then_risk_and_next_steps():
    query = build_retrieval_query(
        {
            "confirmed_needs": ["private deployment", "audit logging"],
            "timeline_signals": ["security review this week"],
            "next_steps": ["schedule technical demo"],
            "risk_flags": ["security_review"],
        }
    )

    assert query == "private deployment audit logging security_review schedule technical demo security review this week"


def test_build_retrieval_query_skips_empty_fields_and_deduplicates_terms():
    query = build_retrieval_query(
        {
            "confirmed_needs": ["crm sync", "crm sync"],
            "timeline_signals": [],
            "next_steps": ["assign one owner"],
            "risk_flags": [],
        }
    )

    assert query == "crm sync assign one owner"
