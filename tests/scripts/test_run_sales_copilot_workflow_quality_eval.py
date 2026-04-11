from __future__ import annotations

from pathlib import Path

from scripts import run_sales_copilot_workflow_quality_eval


def test_main_threads_with_rag_flag(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_sales_copilot_workflow_quality_eval.py",
            "--cases",
            str(tmp_path / "cases.jsonl"),
            "--output-dir",
            str(tmp_path / "outputs"),
            "--with-rag",
        ],
    )
    monkeypatch.setattr(
        run_sales_copilot_workflow_quality_eval,
        "DeepSeekClient",
        lambda **kwargs: object(),
    )
    monkeypatch.setattr(
        run_sales_copilot_workflow_quality_eval,
        "run_workflow_quality_evaluation",
        lambda **kwargs: captured.update(kwargs) or {"summary": {"total_cases": 0}, "case_results": []},
    )
    monkeypatch.setattr(
        run_sales_copilot_workflow_quality_eval,
        "write_workflow_quality_report_bundle",
        lambda bundle, output_dir: str(tmp_path / "report"),
    )

    assert run_sales_copilot_workflow_quality_eval.main() == 0
    assert captured["with_rag"] is True
