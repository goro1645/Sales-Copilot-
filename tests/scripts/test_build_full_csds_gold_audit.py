from __future__ import annotations

import json
from pathlib import Path

from scripts import build_full_csds_gold_audit


def test_build_full_csds_gold_audit_cli_writes_sample_and_summary(monkeypatch, tmp_path: Path) -> None:
    dataset_dir = tmp_path / "csds"
    dataset_dir.mkdir()
    (dataset_dir / "test.json").write_text(
        json.dumps(
            [
                {
                    "DialogueID": 1,
                    "QRole": "用户",
                    "UserSumm": ["用户询问何时回电。"],
                    "AgentSumm": ["客服表示明天回电。"],
                    "FinalSumm": ["客服表示明天回电。"],
                },
                {
                    "DialogueID": 2,
                    "QRole": "用户",
                    "UserSumm": ["用户询问优惠券。"],
                    "AgentSumm": ["客服表示已下单商品不能再使用优惠券。"],
                    "FinalSumm": ["客服表示已下单商品不能再使用优惠券。"],
                },
                {
                    "DialogueID": 3,
                    "QRole": "用户",
                    "UserSumm": ["用户询问发货进度。"],
                    "AgentSumm": ["客服表示会尽快处理。"],
                    "FinalSumm": ["客服表示会尽快处理。"],
                },
                {
                    "DialogueID": 4,
                    "QRole": "用户",
                    "UserSumm": ["用户询问什么时候回复。"],
                    "AgentSumm": ["客服表示会在明天回电。"],
                    "FinalSumm": ["客服表示会在明天回电。"],
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "outputs"
    monkeypatch.setattr(
        "sys.argv",
        [
            "build_full_csds_gold_audit.py",
            "--csds-data-dir",
            str(dataset_dir),
            "--split",
            "test",
            "--output-dir",
            str(output_dir),
            "--ordinary-count",
            "1",
            "--timeline-count",
            "1",
            "--budget-count",
            "1",
            "--overlap-count",
            "1",
        ],
    )

    assert build_full_csds_gold_audit.main() == 0
    assert (output_dir / "full_csds_gold_audit_sample.jsonl").exists()
    assert (output_dir / "full_csds_gold_audit_summary.json").exists()
