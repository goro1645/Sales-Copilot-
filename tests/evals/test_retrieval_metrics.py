from evals.sales_copilot.retrieval_metrics import (
    recall_at_k,
    reciprocal_rank,
    summarize_retrieval_metrics_by_bucket,
    summarize_retrieval_metrics,
)


def test_recall_at_k_returns_one_when_expected_id_is_in_top_k():
    assert recall_at_k(expected_ids=[5], ranked_ids=[7, 5, 9], k=3) == 1.0
    assert recall_at_k(expected_ids=[5], ranked_ids=[7, 5, 9], k=1) == 0.0


def test_reciprocal_rank_uses_first_matching_rank():
    assert reciprocal_rank(expected_ids=[5], ranked_ids=[7, 5, 9]) == 0.5
    assert reciprocal_rank(expected_ids=[5], ranked_ids=[7, 9]) == 0.0


def test_summarize_retrieval_metrics_averages_scores():
    summary = summarize_retrieval_metrics(
        {
            "keyword_only": [
                {"recall_at_1": 1.0, "recall_at_3": 1.0, "recall_at_5": 1.0, "mrr": 1.0},
                {"recall_at_1": 0.0, "recall_at_3": 1.0, "recall_at_5": 1.0, "mrr": 0.5},
            ]
        }
    )

    assert summary["keyword_only"]["recall_at_1"] == 0.5
    assert summary["keyword_only"]["recall_at_3"] == 1.0
    assert summary["keyword_only"]["mrr"] == 0.75


def test_summarize_retrieval_metrics_handles_multiple_modes_independently():
    summary = summarize_retrieval_metrics(
        {
            "keyword_only": [
                {"recall_at_1": 1.0, "recall_at_3": 1.0, "recall_at_5": 1.0, "mrr": 1.0},
            ],
            "hybrid": [
                {"recall_at_1": 0.0, "recall_at_3": 0.0, "recall_at_5": 1.0, "mrr": 0.25},
                {"recall_at_1": 1.0, "recall_at_3": 1.0, "recall_at_5": 1.0, "mrr": 1.0},
            ],
        }
    )

    assert summary["keyword_only"] == {
        "recall_at_1": 1.0,
        "recall_at_3": 1.0,
        "recall_at_5": 1.0,
        "mrr": 1.0,
    }
    assert summary["hybrid"]["recall_at_1"] == 0.5
    assert summary["hybrid"]["recall_at_5"] == 1.0
    assert summary["hybrid"]["mrr"] == 0.625


def test_summarize_retrieval_metrics_by_bucket_separates_case_types():
    summary = summarize_retrieval_metrics_by_bucket(
        {
            "hybrid": [
                {
                    "case_type": "product_hard",
                    "recall_at_1": 1.0,
                    "recall_at_3": 1.0,
                    "recall_at_5": 1.0,
                    "mrr": 1.0,
                },
                {
                    "case_type": "cross_source_confusing",
                    "recall_at_1": 0.0,
                    "recall_at_3": 1.0,
                    "recall_at_5": 1.0,
                    "mrr": 0.5,
                },
            ]
        }
    )

    assert summary["hybrid"]["product_hard"]["recall_at_1"] == 1.0
    assert summary["hybrid"]["product_hard"]["mrr"] == 1.0
    assert summary["hybrid"]["cross_source_confusing"]["recall_at_1"] == 0.0
    assert summary["hybrid"]["cross_source_confusing"]["mrr"] == 0.5
