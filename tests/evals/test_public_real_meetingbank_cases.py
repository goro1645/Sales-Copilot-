import json
from pathlib import Path

from evals.sales_copilot.cases import load_golden_cases


def test_public_real_meetingbank_cases_load_and_keep_source_metadata():
    repo_root = Path(__file__).resolve().parents[2]
    cases_path = repo_root / "evals" / "sales_copilot" / "public_real_meetingbank_cases.jsonl"

    cases = load_golden_cases(cases_path)
    raw_rows = [json.loads(line) for line in cases_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert len(cases) == 5
    assert len(raw_rows) == 5
    assert {row["source_dataset"] for row in raw_rows} == {"MeetingBank"}
    assert all(row["source_uid"] for row in raw_rows)
    assert all("manually adapted" in row["source_note"] for row in raw_rows)
    assert any(case["segment"] == "high_intent_complete" for case in cases)
    assert any(case["segment"] == "medium_intent_nurture" for case in cases)
    assert any(case["segment"] == "low_intent_or_noise" for case in cases)
