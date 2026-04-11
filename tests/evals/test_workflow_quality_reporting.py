from evals.sales_copilot.workflow_quality_reporting import summarize_workflow_quality_results


def test_summarize_workflow_quality_results_computes_averages_and_rates():
    summary = summarize_workflow_quality_results(
        [
            {
                "judge_result": {
                    "crm_writeback": {
                        "field_correctness_score": 4,
                        "business_usability_score": 5,
                    },
                    "task_generation": {
                        "structure_correctness_score": 3,
                        "execution_quality_score": 4,
                    },
                    "overall": {"overall_score": 4},
                    "benchmark_alignment": {"alignment_score": 3},
                }
            },
            {
                "judge_result": {
                    "crm_writeback": {
                        "field_correctness_score": 2,
                        "business_usability_score": 3,
                    },
                    "task_generation": {
                        "structure_correctness_score": 3,
                        "execution_quality_score": 2,
                    },
                    "overall": {"overall_score": 3},
                    "benchmark_alignment": {"alignment_score": 2},
                }
            },
        ]
    )

    assert summary["crm_field_correctness_avg"] == 3.0
    assert summary["crm_business_usability_avg"] == 4.0
    assert summary["task_structure_correctness_avg"] == 3.0
    assert summary["task_execution_quality_avg"] == 3.0
    assert summary["overall_score_avg"] == 3.5
    assert summary["alignment_score_avg"] == 2.5
    assert summary["overall_acceptable_rate"] == 1.0
    assert summary["overall_good_rate"] == 0.5
    assert summary["crm_acceptable_rate"] == 1.0
    assert summary["task_acceptable_rate"] == 0.5
