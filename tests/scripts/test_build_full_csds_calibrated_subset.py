from __future__ import annotations

from pathlib import Path

from scripts import build_full_csds_calibrated_subset


def test_build_full_csds_calibrated_subset_cli_writes_working_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "build_full_csds_calibrated_subset.py",
            "--csds-data-dir",
            str(tmp_path / "csds"),
            "--split",
            "test",
            "--baseline-case-results",
            str(tmp_path / "case_results.jsonl"),
            "--output-dir",
            str(tmp_path / "outputs"),
        ],
    )
    monkeypatch.setattr(
        build_full_csds_calibrated_subset,
        "load_full_csds_cases",
        lambda dataset_dir, splits=None, limit=None: [
            {
                "case_id": "case_1",
                "source_uid": "1",
                "source_split": "test",
                "source_note": "sample",
                "customer_profile_text": "Source: CSDS",
                "meeting_note_text": "Agent says they will contact the customer tomorrow.",
                "expected_parse": {
                    "account_name": "JD Support",
                    "customer_roles": ["user", "agent"],
                    "confirmed_needs": ["handle order issue"],
                    "budget_signals": [],
                    "timeline_signals": [],
                    "next_steps": ["agent will follow up"],
                    "competitors": [],
                },
            }
        ],
    )
    monkeypatch.setattr(
        build_full_csds_calibrated_subset,
        "_load_raw_split_rows",
        lambda dataset_dir, split: {"1": {"UserSumm": [], "AgentSumm": [], "FinalSumm": []}},
    )
    monkeypatch.setattr(
        build_full_csds_calibrated_subset,
        "load_case_results_by_id",
        lambda path: {},
    )

    assert build_full_csds_calibrated_subset.main() == 0
    assert (tmp_path / "outputs" / "full_csds_calibration_working_100.jsonl").exists()


def test_build_full_csds_calibrated_subset_cli_exports_final_file(monkeypatch, tmp_path: Path) -> None:
    working_path = tmp_path / "working.jsonl"
    working_path.write_text(
        (
            '{"case_id":"case_1","source_uid":"1","source_split":"test","meeting_note_text":"m",'
            '"customer_profile_text":"c","auto_expected_parse":{"account_name":"JD Support","customer_roles":["user","agent"],'
            '"confirmed_needs":["need"],"budget_signals":[],"timeline_signals":[],"next_steps":["follow up"],"competitors":[]},'
            '"pre_annotation":{"corrected_expected_parse":{"confirmed_needs":["need"],"budget_signals":[],"timeline_signals":["tomorrow"],"next_steps":["contact customer"]}},'
            '"human_review":{"final_expected_parse":{"confirmed_needs":["need"],"budget_signals":[],"timeline_signals":["tomorrow"],"next_steps":["contact support"]}}}\n'
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "build_full_csds_calibrated_subset.py",
            "--export-final-from-working",
            str(working_path),
            "--output-dir",
            str(tmp_path / "outputs"),
        ],
    )

    assert build_full_csds_calibrated_subset.main() == 0
    assert (tmp_path / "outputs" / "full_csds_calibrated_100.jsonl").exists()


def test_build_full_csds_calibrated_subset_cli_fills_ai_review_and_exports(monkeypatch, tmp_path: Path) -> None:
    working_path = tmp_path / "working.jsonl"
    working_path.write_text(
        (
            '{"case_id":"case_1","source_uid":"1","source_split":"test","sampling_bucket":"ordinary_stable",'
            '"meeting_note_text":"m","customer_profile_text":"c","user_summ":[],"agent_summ":[],"final_summ":[],'
            '"auto_expected_parse":{"account_name":"JD Support","customer_roles":["user","agent"],'
            '"confirmed_needs":["need"],"budget_signals":[],"timeline_signals":[],"next_steps":["follow up"],"competitors":[]},'
            '"baseline_parse_result":{"account_name":"JD Support","customer_roles":["user","agent"],'
            '"confirmed_needs":["need"],"budget_signals":[],"timeline_signals":[],"next_steps":["follow up"],"competitors":[]},'
            '"pre_annotation":{"corrected_expected_parse":{"confirmed_needs":["need"],"budget_signals":[],"timeline_signals":[],"next_steps":["follow up"]},'
            '"review_reason":"auto_gold_vs_baseline_alignment"},'
            '"human_review":{}}\n'
        ),
        encoding="utf-8",
    )

    class _FakeClient:
        def complete_with_tool(self, messages, tools, tool_choice):
            return {
                "tool_name": "submit_ai_calibrated_parse",
                "arguments": {
                    "corrected_expected_parse": {
                        "confirmed_needs": ["need"],
                        "budget_signals": [],
                        "timeline_signals": [],
                        "next_steps": ["contact support"],
                    }
                },
            }

    monkeypatch.setattr(
        build_full_csds_calibrated_subset,
        "_build_deepseek_client",
        lambda api_key, base_url, model: _FakeClient(),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "build_full_csds_calibrated_subset.py",
            "--fill-ai-review-from-working",
            str(working_path),
            "--api-key",
            "test-key",
            "--output-dir",
            str(tmp_path / "outputs"),
        ],
    )

    assert build_full_csds_calibrated_subset.main() == 0
    assert (tmp_path / "outputs" / "full_csds_calibration_working_100.ai_reviewed.jsonl").exists()
    assert (tmp_path / "outputs" / "full_csds_ai_calibrated_100.jsonl").exists()
