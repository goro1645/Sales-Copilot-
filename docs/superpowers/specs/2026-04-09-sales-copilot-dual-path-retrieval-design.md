# Dual-Path Retrieval Benchmark Design

## Goal
Build a more realistic retrieval benchmark that measures Sales Copilot knowledge retrieval under two paths:
- `gold-parse -> retrieval`
- `model-parse -> retrieval`

The benchmark should explain whether retrieval quality is limited by retrieval itself, by parse quality, or by both.

## Why This Benchmark Exists
The existing retrieval benchmarks answer two different but incomplete questions:
- the baseline retrieval benchmark is too easy and cannot distinguish `hybrid_rerank`
- the CSDS-derived hard retrieval benchmark is more useful, but its queries are still manually authored and therefore may over-favor keyword retrieval

A dual-path benchmark will better simulate real usage while still preserving a clean upper-bound retrieval measurement.

## Benchmark Structure
The benchmark uses the same case set, the same local knowledge base, and the same retrieval modes, but evaluates two query-generation paths.

### Path A: gold-parse -> retrieval
- Input: manually labeled structured fields
- Purpose: measure retrieval quality when upstream parse is correct
- Interpretation: retrieval upper bound

### Path B: model-parse -> retrieval
- Input: model-generated structured fields from the real parse pipeline
- Purpose: measure retrieval quality in a realistic end-to-end system path
- Interpretation: practical retrieval quality after parse noise

## Shared Retrieval Corpus
The retrieval corpus remains unchanged:
- local `product knowledge` chunks
- local `sales playbook` chunks

This benchmark does not expand the knowledge base into a larger external corpus.

## Case Source
The benchmark reuses the CSDS-derived hard case set and extends each case with enough information to support both paths.

Cases should preserve:
- `case_id`
- `source_uid`
- `source_type`
- `case_type`
- `expected_chunk_ids`
- `acceptable_chunk_ids`

The benchmark should additionally include a minimal structured gold payload that is sufficient to build a retrieval query.

## Query Builder
Both paths must use the same deterministic query-building logic.

A single helper should construct retrieval queries from a structured parse payload. The helper should only depend on structured fields, not on whether they came from gold labels or model output.

### Input fields for query construction
Use only the following fields:
- `confirmed_needs`
- `next_steps`
- `timeline_signals`
- `risk_flags`

These fields are sufficient to express user intent while keeping the query concise enough to resemble realistic retrieval usage.

### Query-building principles
- prioritize `confirmed_needs`
- add `risk_flags` when available to disambiguate retrieval intent
- append `next_steps` when they materially change whether the query is product-oriented or playbook-oriented
- avoid generating very long bag-of-words prompts
- do not use another LLM to rewrite queries

The query builder should remain rule-based so retrieval quality can be measured without adding another model-dependent stage.

## Gold Path
For each case:
1. read gold structured fields
2. construct a retrieval query through the shared query builder
3. run retrieval benchmark modes:
   - `keyword_only`
   - `hybrid`
   - `hybrid_rerank`

This path answers:
- how strong retrieval is when parse is correct
- whether reranking adds value independent of parse noise

## Model Path
For each case:
1. obtain model parse output from the real parse pipeline
2. construct a retrieval query through the same shared query builder
3. run the same retrieval benchmark modes:
   - `keyword_only`
   - `hybrid`
   - `hybrid_rerank`

This path answers:
- how strong retrieval is in the realistic system path
- how much parse noise degrades retrieval quality

## Metrics
Use the same core metrics for both paths:
- `Recall@1`
- `Recall@3`
- `Recall@5`
- `MRR`

Metrics should be reported for:
- overall results
- `product_hard`
- `playbook_hard`
- `cross_source_confusing`

## Gap Analysis
Reports should include a gap section comparing `gold` and `model` paths.

This gap is the main diagnostic signal:
- if `gold` is strong and `model` is weak, parse is the main bottleneck
- if both are weak, retrieval is the main bottleneck
- if both are strong, the full chain is working well

## Output Format
The report should include three major sections:
1. `Gold Retrieval`
2. `Model Retrieval`
3. `Gap Analysis`

Each section should show:
- overall metrics per retrieval mode
- per-bucket metrics per retrieval mode

## Non-Goals
This benchmark will not:
- replace the existing CSDS parse-only extraction benchmark
- replace the existing small retrieval benchmark
- claim access to private enterprise retrieval logs
- evaluate CRM write-back or workflow routing quality

## Success Criteria
The benchmark is useful if it makes these questions answerable:
- is keyword retrieval outperforming hybrid because of query construction?
- does reranking help when retrieval queries come from realistic structured outputs?
- how large is the retrieval quality gap between gold parse and model parse?
- which case bucket is most sensitive to parse noise?
