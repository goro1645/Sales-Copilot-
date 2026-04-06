# CSDS Eval Adapter Design

## Goal

Add a `CSDS`-backed offline evaluation path to the existing `Sales Copilot` evaluation framework so the project can report results on a public Chinese customer-service corpus without pretending that the data is native sales CRM data.

## Scope

This design only covers:

- loading a small local subset derived from the official `CSDS` dataset
- adapting that subset into the existing evaluation schema
- running `parse-only` evaluation on the adapted samples
- documenting the correct reporting language for these results

This design does not cover:

- full-dataset ingestion for all of CSDS
- model fine-tuning on CSDS
- forcing `CSDS` cases through the current end-to-end sales workflow metrics

## Rationale

`CSDS` is closer than `MeetingBank` to the current project because it is a Chinese customer-service dialogue summarization dataset. It is still not identical to sales follow-up workflow data, so the right design is to use it for `parse`/summary-style evaluation and keep business workflow metrics on the self-built gold set.

This keeps the reporting honest:

- `CSDS`: public real customer-service dialogue corpus for structured extraction / summary adaptation
- `golden_cases`: self-built workflow benchmark for route / CRM / task metrics

## Approaches Considered

### 1. Direct full-schema adaptation into current `GoldenCase` format

Map every `CSDS` sample into the current `GoldenCase` structure, including workflow labels.

Pros:

- reuses the existing runner with minimal branching

Cons:

- requires inventing workflow labels that `CSDS` does not naturally provide
- encourages overstating what the public corpus actually measures

Decision: rejected for V1.

### 2. Separate `CSDS` parse-eval adapter on top of current metrics

Add a small adapter that converts `CSDS` records into the fields required by `evaluate_parse_case`, and expose a `parse-only` evaluation runner for that subset.

Pros:

- preserves metric honesty
- small implementation surface
- leverages existing parse metrics and report generation patterns

Cons:

- produces two evaluation paths instead of one unified path

Decision: recommended.

### 3. Build a generic multi-corpus evaluation framework first

Introduce a dataset registry abstraction, corpus-specific adapters, and mode-specific runners up front.

Pros:

- cleaner long-term architecture if many corpora are added later

Cons:

- too much abstraction for the immediate need
- slows delivery

Decision: deferred.

## Proposed Design

### Data Flow

1. Store a small local `CSDS` subset under `evals/sales_copilot/`.
2. Add an adapter that reads the subset and emits parse-eval records compatible with the current parse metrics.
3. Add a dedicated runner that:
   - loads the adapted `CSDS` records
   - calls the existing parse node / LLM client
   - computes parse metrics only
   - writes a report bundle
4. Keep `run_sales_copilot_eval.py` and `golden_cases.jsonl` for workflow evaluation unchanged.

### Files

- Create: `evals/sales_copilot/csds_cases.jsonl`
  - small local subset derived from official `CSDS`
- Create: `evals/sales_copilot/csds_adapter.py`
  - converts `CSDS` rows into parse-eval records
- Create: `evals/sales_copilot/csds_runner.py`
  - runs parse-only evaluation on adapted `CSDS` rows
- Modify: `scripts/run_sales_copilot_eval.py`
  - add a dataset selector or dedicated `--cases-kind` path for `csds`
- Create: `tests/evals/test_csds_adapter.py`
  - validates conversion rules
- Create: `tests/evals/test_csds_runner.py`
  - validates parse-only execution and summary output
- Modify: `README.md`
  - document `CSDS` as a public real customer-service corpus used for parse evaluation only

### Local Subset Format

To avoid coupling the repo to the full upstream release in V1, the local file will contain a normalized subset with source metadata, for example:

```json
{
  "case_id": "csds_001",
  "source_dataset": "CSDS",
  "source_split": "train",
  "source_note": "Derived from the official CSDS customer-service dialogue summarization dataset.",
  "dialogue_text": "...",
  "expected_parse": {
    "account_name": "...",
    "customer_roles": ["..."],
    "confirmed_needs": ["..."],
    "budget_signals": [],
    "timeline_signals": ["..."],
    "next_steps": ["..."],
    "competitors": []
  }
}
```

### Metric Contract

`CSDS` results should report only:

- `json_valid_rate`
- `field_exact_match_rate.account_name`
- list-field precision / recall / F1
- `average_list_field_f1`

No `workflow` metrics should be reported from `CSDS` in V1.

### Reporting Language

Allowed:

- `based on the public CSDS customer-service dialogue corpus`
- `public real customer-service dialogue data`
- `parse-only offline evaluation on CSDS`

Not allowed:

- `real sales CRM data`
- `real sales visit records`
- `production workflow accuracy from CSDS`

## Testing

- adapter unit tests for field mapping
- runner tests for parse-only execution and report summary shape
- regression check that existing `golden_cases` workflow evaluation remains unchanged

## Risks

### Risk: CSDS source schema differs from our assumptions

Mitigation:

- keep the local subset normalized in-repo
- isolate source-specific assumptions inside `csds_adapter.py`

### Risk: users over-interpret CSDS numbers as workflow metrics

Mitigation:

- hard-separate `CSDS` runner from workflow runner
- document the reporting boundary in `README.md`

## Success Criteria

- repo can run a local `CSDS` parse-only evaluation command
- parse metrics are produced on a public Chinese customer-service corpus
- existing workflow evaluation on `golden_cases` still passes unchanged
- README clearly explains the difference between `CSDS` and workflow benchmarks
