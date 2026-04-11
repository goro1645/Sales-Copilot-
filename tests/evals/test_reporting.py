from evals.sales_copilot.reporting import _build_report_markdown


def test_build_report_markdown_includes_semantic_parse_metrics():
    bundle = {
        "summary": {
            "total_cases": 1,
            "parse": {
                "json_valid_rate": 1.0,
                "list_field_precision": 0.5,
                "list_field_recall": 0.5,
                "list_field_f1": 0.5,
                "average_list_field_f1": 0.5,
                "semantic_list_field_precision": 0.9,
                "semantic_list_field_recall": 0.8,
                "semantic_list_field_f1": 0.85,
                "average_semantic_list_field_f1": 0.86,
                "risk_flag_recall": 0.0,
                "field_exact_match_rate": {"account_name": 1.0},
            },
            "workflow": {},
        },
        "report_kind": "parse_only",
        "case_results": [],
    }

    markdown = _build_report_markdown(bundle)

    assert "semantic_list_field_precision" in markdown
    assert "average_semantic_list_field_f1" in markdown
