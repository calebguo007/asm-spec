# Discovery Eval Artifacts

This directory holds **evaluation artifacts** for the deck/demo: prompt → discovery output → matched taxonomy.

## Prompt set (selected)

We evaluate against the **50-subtask benchmark prompts** (the canonical demo workload) from:

- `payments/src/benchmark-tasks.ts`

Rationale: this is the most realistic, judge-facing workload and makes results directly comparable to the live benchmark run.

## Files expected here

Generated JSON files (one per prompt or one per run), containing at minimum:

- `prompt`
- `expected_taxonomy` (from benchmark)
- `matched_taxonomy` (from discovery)
- `confidence`
- `candidates` (top-k)
- `reasoning`
- `timestamp`

