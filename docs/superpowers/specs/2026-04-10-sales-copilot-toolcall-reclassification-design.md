# Sales Copilot Tool-Call Signal Reclassification Design

## Goal

Replace the current freeform JSON second-pass signal reclassification with a DeepSeek tool-call based constrained classifier so that:

- reclassification output no longer depends on fragile freeform JSON field names
- `CSDS` parse-only evaluation can safely experiment with second-pass repair logic
- the first-pass parse remains the source of truth and is never damaged by reclassification failures

The first implementation will validate the new output path on a `20`-case smoke run before any larger re-run.

## Problem Statement

The current second-pass reclassification logic does not fail because DeepSeek cannot classify the signals. It fails because the provider returns valid JSON that does not match the hard-coded schema expected by the client code.

Observed behavior:

- DeepSeek often returns a structure like:

```json
{
  "classifications": [
    {
      "candidate_id": "sig_001",
      "classification": "timeline_signals"
    }
  ]
}
```

- The current code expects:

```json
{
  "classified_signals": [
    {
      "candidate_id": "sig_001",
      "predicted_label": "timeline_signals",
      "confidence": 0.62,
      "alternative_labels": [],
      "notes": ""
    }
  ]
}
```

This mismatch causes retries and fallback despite the model having produced a usable classification.

## Recommended Approach

Use DeepSeek tool calls for second-pass classification instead of freeform JSON generation.

The classifier will:

1. Extract target candidates from the first-pass parse result
2. Batch candidates into small groups
3. Force DeepSeek to call a single classification function
4. Read structured arguments from the returned tool call
5. Merge the classifications into the existing parse result using an additive strategy

This removes the need to parse model-authored JSON text for the classification result.

## Approaches Considered

### 1. Expand freeform JSON compatibility

Continue adding support for more returned JSON shapes, such as:

- `classified_signals`
- `classifications`
- `predicted_label`
- `classification`

Pros:
- small code change

Cons:
- fragile
- format drift will continue
- still depends on freeform assistant content

### 2. Stronger freeform prompt plus JSON mode

Keep the current strategy but harden the prompt further.

Pros:
- minimal conceptual change

Cons:
- JSON mode only guarantees valid JSON, not the desired schema
- still vulnerable to naming drift

### 3. Tool-call based constrained classification (recommended)

Force the model to emit a single function call with schema-constrained arguments.

Pros:
- schema is explicit
- no freeform JSON parsing for classification payloads
- labels can be restricted via enum
- easier to debug and reason about

Cons:
- requires client support for non-streaming tool calls
- requires small prompt and adapter rewrite

## Scope

The first version affects only:

- `budget_signals`
- `timeline_signals`
- `next_steps`

It does not alter:

- first-pass meeting parsing prompt
- lead scoring
- follow-up planning
- main Streamlit demo behavior

The new classifier is only enabled through the `CSDS parse-only eval` path by explicit flag.

## Data Flow

Current experimental path:

`dialogue -> first-pass parse -> freeform JSON reclassification -> rebuild fields -> evaluation`

New path:

`dialogue -> first-pass parse -> candidate extraction -> tool-call classification -> additive merge -> evaluation`

## Tool Schema

The classifier uses a single tool:

- name: `classify_signal_candidates`

The tool schema must remain minimal.

```json
{
  "type": "function",
  "function": {
    "name": "classify_signal_candidates",
    "description": "Classify each signal candidate into one fixed label.",
    "strict": true,
    "parameters": {
      "type": "object",
      "properties": {
        "classifications": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "candidate_id": {
                "type": "string"
              },
              "label": {
                "type": "string",
                "enum": [
                  "budget_signals",
                  "timeline_signals",
                  "next_steps",
                  "other"
                ]
              }
            },
            "required": ["candidate_id", "label"],
            "additionalProperties": false
          }
        }
      },
      "required": ["classifications"],
      "additionalProperties": false
    }
  }
}
```

### Why this schema is intentionally narrow

The first version omits:

- `confidence`
- `notes`
- `alternative_labels`

These fields add flexibility but also increase output drift and parsing complexity. The goal of v1 is to make the output path stable first.

## Prompt Strategy

The model prompt should do only one job:

- classify candidate phrases into the fixed label set

The prompt should:

- define the four labels clearly
- emphasize that only the tool call is required
- avoid asking for explanation text

The prompt should not:

- ask for confidence scores
- ask for freeform reasoning
- ask for rewritten summaries

## Client Responsibilities

`DeepSeekClient` should gain a helper for non-streaming tool-call consumption.

The helper should:

1. Send messages with `tools`
2. Force the tool via `tool_choice`
3. Read `choices[0].message.tool_calls`
4. Validate:
   - tool exists
   - tool name matches expectation
   - arguments parse as JSON object
5. Return the parsed arguments payload

This helper should be independent from the current streaming tool-call logic.

## Reclassifier Responsibilities

The reclassifier should:

1. Extract candidates from:
   - `budget_signals`
   - `timeline_signals`
   - `next_steps`
   - optional `objections`
2. Batch candidates into small groups such as `8` to `10`
3. Call DeepSeek tool classification for each batch
4. Validate each returned `candidate_id`
5. Merge labels back into the parse result

## Merge Strategy

The merge strategy must be additive and safe.

### Rules

- never delete existing first-pass values
- only add labels inferred from successful tool-call classification
- if a batch fails, keep the original parse values unchanged
- if a candidate is labeled `other`, do nothing

This is critical because the earlier freeform version regressed `next_steps` by rebuilding target fields from scratch.

## Error Handling

Errors should be split cleanly:

- `parse_errors`: first-pass parse failed
- `reclassification_errors`: tool-call reclassification failed for one or more batches

Reclassification failure must not be recorded as a top-level parse failure when baseline parse remains usable.

For each failed batch:

- record the batch-level reclassification failure
- keep the original parse result
- continue processing remaining batches if appropriate

## Validation Rules

Returned tool-call payloads must be validated before merge:

- `classifications` must be a list
- each `candidate_id` must belong to the current batch
- each `label` must be one of:
  - `budget_signals`
  - `timeline_signals`
  - `next_steps`
  - `other`

Unknown labels or unknown candidate ids invalidate that batch.

## Testing Strategy

### Unit tests

- `DeepSeekClient` extracts tool-call arguments correctly
- invalid or missing tool calls raise clear errors
- reclassifier merges labels additively
- reclassification failure preserves original parse output

### Integration tests

- `CSDS` runner records `reclassification_errors` separately from `parse_errors`
- CLI flag still enables the reclassification path

### Smoke run

After implementation, run:

- `full-csds`
- `test`
- `limit=20`
- `--use-signal-reclassification`

Inspect:

- output format in `case_results.jsonl`
- `parse_error_count`
- `reclassification_error_count`
- whether `next_steps` is preserved

## Success Criteria

The first version is successful if:

- the `20`-case smoke run shows stable tool-call argument structure
- reclassification no longer depends on freeform JSON field names
- `parse_error_count` stays at `0`
- `reclassification_error_count` drops significantly relative to the current freeform version
- original `next_steps` values are preserved when reclassification fails

Improving the full `800`-case F1 is desirable but not the v1 acceptance gate. Stability and safe integration come first.
