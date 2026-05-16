from __future__ import annotations

from pathlib import Path

from scripts import run_sales_copilot_eval


def test_main_threads_signal_reclassification_flag(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_sales_copilot_eval.py",
            "--dataset-kind",
            "full-csds",
            "--csds-data-dir",
            str(tmp_path / "csds"),
            "--csds-splits",
            "test",
            "--output-dir",
            str(tmp_path / "outputs"),
            "--use-signal-reclassification",
        ],
    )
    monkeypatch.setattr(
        run_sales_copilot_eval,
        "DeepSeekClient",
        lambda **kwargs: object(),
    )
    monkeypatch.setattr(
        run_sales_copilot_eval,
        "run_full_csds_parse_evaluation",
        lambda **kwargs: captured.update(kwargs) or {
            "summary": {"total_cases": 0, "parse": {}},
            "case_results": [],
        },
    )
    monkeypatch.setattr(run_sales_copilot_eval, "write_report_bundle", lambda bundle, output_dir: str(tmp_path / "report"))

    assert run_sales_copilot_eval.main() == 0
    assert captured["use_signal_reclassification"] is True


def test_main_threads_candidate_generation_refinement_flag(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_sales_copilot_eval.py",
            "--dataset-kind",
            "full-csds",
            "--csds-data-dir",
            str(tmp_path / "csds"),
            "--csds-splits",
            "test",
            "--output-dir",
            str(tmp_path / "outputs"),
            "--use-candidate-generation-refinement",
        ],
    )
    monkeypatch.setattr(
        run_sales_copilot_eval,
        "DeepSeekClient",
        lambda **kwargs: object(),
    )
    monkeypatch.setattr(
        run_sales_copilot_eval,
        "run_full_csds_parse_evaluation",
        lambda **kwargs: captured.update(kwargs) or {
            "summary": {"total_cases": 0, "parse": {}},
            "case_results": [],
        },
    )
    monkeypatch.setattr(run_sales_copilot_eval, "write_report_bundle", lambda bundle, output_dir: str(tmp_path / "report"))

    assert run_sales_copilot_eval.main() == 0
    assert captured["use_candidate_generation_refinement"] is True
