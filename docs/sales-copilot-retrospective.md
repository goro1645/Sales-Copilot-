# Sales Copilot Retrospective

## Scope

This note summarizes the main design, implementation, evaluation, and benchmarking lessons from the Sales Copilot project work completed in this branch.

It is intended as a practical reference for future iteration, not as a polished external report.

## What We Built

Sales Copilot evolved from a parse-focused workflow demo into a more complete LLM application prototype with:

- LangGraph-based stateful workflow orchestration
- sales and customer-service oriented structured parsing
- local CRM/Tasks MCP-style tool layer and stdio MCP server support
- OpenAI-compatible local inference interface for MiniMind
- retrieval-enhanced context lookup with hybrid retrieval and reranker experiments
- offline benchmark pipelines for parse, retrieval, and workflow evaluation

## Parse Line: What Held Up Best

The strongest production-like baseline remains the direct parse path without second-stage rewriting.

On the calibrated 100-case subset, the current baseline remains stronger than the second-stage refinement variants. This means the primary parse prompt and schema design are still the most reliable path for now.

Main reason:

- baseline output is already strong enough on `confirmed_needs`
- second-stage processing adds semantic ambiguity around `budget_signals`, `timeline_signals`, and `next_steps`
- the additional refinement logic has not yet demonstrated consistent net benefit

## RAG Line: What We Added

The retrieval stack was upgraded in stages:

1. keyword-based retrieval
2. embedding plus keyword hybrid retrieval
3. cross-encoder reranker experiments
4. retrieval benchmark, hard benchmark, and dual-path benchmark

What we learned:

- hybrid retrieval is meaningfully better than pure keyword lookup when query wording becomes more realistic
- reranker integration is technically complete, but current reranker choices and fusion strategies do not yet reliably beat the best hybrid baseline
- retrieval infrastructure is now strong enough for future iteration, even though it is not yet the main source of score gains

In short:

- RAG infrastructure improved a lot
- RAG evaluation quality improved a lot
- RAG is now a real engineering subsystem in the project
- but it is not yet the strongest user-facing differentiator compared with parse quality

## Benchmarking Lessons

The original `full-CSDS 800` parse benchmark turned out to be useful but limited.

Important lesson:

- the large 800-case benchmark is generated from CSDS summaries plus adaptation rules
- this makes it a weak benchmark, not a fully independent human gold benchmark

Main issues we found:

- `budget_signals`, `timeline_signals`, and `next_steps` often overlap in the adapted gold
- some rules absorb full service-response sentences instead of clean field-specific signals
- improving model behavior does not always improve the benchmark score if the benchmark itself rewards a different wording style

Because of that, the 800-case benchmark should be used mainly for:

- trend tracking
- regression checks
- schema stability checks

It should not be treated as the only final judge of model quality.

## AI-Calibrated 100

To get a more trustworthy benchmark layer, we built an `AI-calibrated 100` subset:

- source: sampled from the full CSDS test split
- purpose: provide a more reviewable and less weakly adapted benchmark draft
- role: serve as the main comparison set for model iteration

This is still not the same as a fully human-reviewed benchmark, but it is much more useful than relying only on the weak 800-case auto-gold.

Recommended positioning:

- `full-CSDS 800`: weak benchmark for large-scale trend tracking
- `AI-calibrated 100`: better benchmark draft for model comparison

## Second-Stage Refinement: What We Learned

We explored multiple second-stage refinement strategies:

- freeform JSON reclassification
- tool-call reclassification
- confidence-gated merging
- candidate span generation plus local filtering

Key conclusion:

- second-stage refinement is now engineering-stable
- but it does not currently outperform the direct baseline on the calibrated benchmark

That is a useful result, not a failure. It tells us the current best practical strategy is:

- keep baseline parse as the mainline
- keep second-stage refinement as an experiment line

## Semantic Metrics

We also added semantic list-field metrics so evaluation is not forced to depend only on literal string overlap.

These metrics now run in parallel with the old ones:

- legacy metrics: conservative, stable, regression-friendly
- semantic metrics: closer to "semantic correctness is enough"

We also learned that semantic scoring is highly sensitive to:

- field guards
- threshold selection
- which fields are allowed to bypass guard checks

This means semantic metrics are useful, but they must be treated as tuned evaluation instruments rather than automatic truth.

## Current Practical Conclusion

At the current project state:

- the direct baseline parse path is still the strongest primary solution
- RAG and retrieval infrastructure are now much more mature than before
- benchmark quality and evaluation rigor improved substantially
- second-stage refinement remains valuable for research, but not yet as the default production path

## Recommended Next Steps

The most practical next steps are:

1. Keep baseline parse as the default mainline
2. Use `AI-calibrated 100` as the primary comparison benchmark
3. Use `full-CSDS 800` only as a weak large-scale trend benchmark
4. Continue semantic-metric tuning carefully, field by field
5. If second-stage refinement work continues, focus only on the worst fields rather than redesigning the whole chain again

## Bottom Line

The biggest outcome of this phase is not that every experimental path improved scores.

The biggest outcome is that the project now has:

- a stronger parse baseline
- a real retrieval subsystem
- a more honest benchmark structure
- clearer separation between mainline solutions and research experiments

That gives future work a much more reliable foundation.

## Artificial Sales Workflow Benchmark

We also added an AI-authored 50-case sales workflow benchmark draft to cover ecommerce merchant and platform sales scenarios that are not represented well in CSDS-derived datasets. This benchmark is intended for workflow-level evaluation first, especially route selection, CRM writeback quality, task generation quality, and future with-RAG versus without-RAG comparisons on true sales-style cases.
