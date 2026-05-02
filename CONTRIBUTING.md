# Contributing to ASM

Thank you for your interest in contributing to Agent Service Manifest (ASM). This document covers how to add manifests, run tests, reproduce experiments, and submit changes.

## Code of Conduct

This project follows the [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/) v2.1. Participants are expected to uphold an open and respectful environment.

## Setup

Python 3.10+ is required. Install dependencies once:

```bash
pip install -r requirements.txt
```

For TypeScript tests in the registry:

```bash
cd registry && npm install
```

## Adding a Service Manifest

Manifests live in `manifests/`. Each file is a single JSON document validated against [`schema/asm-v0.3.schema.json`](schema/asm-v0.3.schema.json).

### Steps

1. Copy an existing manifest from the same taxonomy as a template.
2. Fill in all fields you can verify from public sources (pricing pages, documentation, benchmark leaderboards).
3. Set `asm_version` to `"0.3"`.
4. Name the file `{provider}-{service-name}.asm.json` (lowercase, hyphens).
5. Validate: `python -c "import json; jsonschema.validate(json.load(open('manifests/YOUR_FILE.asm.json')), json.load(open('schema/asm-v0.3.schema.json')))"`

### Required fields (3)

| Field | Format | Example |
|---|---|---|
| `asm_version` | string | `"0.3"` |
| `service_id` | `{provider}/{name}@{version}` | `"anthropic/claude-sonnet-4@4.0"` |
| `taxonomy` | dot-path | `"ai.llm.chat"` |

### Quality guidelines

- `quality.metrics[*].self_reported` must be `true` for vendor-claimed scores, `false` for third-party benchmarks.
- `sla.latency_p50` should be a string with unit suffix (e.g., `"800ms"`) or a number in seconds.
- `provenance.source_url` should point to the page where pricing/SLA data was retrieved.
- `updated_at` should be ISO 8601 (e.g., `"2026-03-15T00:00:00Z"`).

### What NOT to do

- Do not fabricate benchmark scores. If no third-party benchmark exists, use `self_reported: true` and note the source.
- Do not copy pricing from outdated pages. Check the provider's current pricing page.
- Do not add taxonomies without proposing them first (see below).

## Proposing a New Taxonomy

Taxonomies use hierarchical dot-notation (e.g., `ai.llm.chat`). To propose one:

1. Open an issue with the proposed name, parent category, and at least 2 services that would use it.
2. The maintainers will check for conflicts with existing categories and approve or suggest alternatives.

## Running Tests

```bash
# Python scorer tests
python -m pytest scorer/test_scorer.py -v

# TypeScript MCP server tests
cd registry && npx tsx src/test_scorer.ts
cd registry && npx tsx src/test_topsis.ts

# All tests via Make
make test
```

## Reproducing Experiments

All experiment scripts are in `experiments/`. Results write to `experiments/results/`.

### A/B evaluation (Section 6.5)

```bash
python experiments/ab_test.py
```

Generates 200 synthetic tasks over 70 manifests, compares ASM-TOPSIS vs Random vs Most-Expensive. Output: `experiments/results/ablation_*.csv|.json|.md`.

Also available as:
```bash
make eval
```

### Ablation studies (Section 6.3a)

```bash
python experiments/ablation_experiments.py --seed 2024
```

Three ablations: trust-delta removal, TOPSIS vs weighted average, io_ratio sensitivity. Output: `experiments/results/ablation_trust*`, `ablation_aggregator*`, `ablation_io_ratio*`.

Also available as:
```bash
make ablations
```

### Preference alignment (Section 6.6a)

```bash
python experiments/preference_alignment.py --seed 2024
```

Evaluates 20 natural-language user requests mapped to explicit hard constraints and preference weights. It compares ASM-TOPSIS against weighted average, cheapest-first, fastest-first, highest-quality-first, highest-reliability-first, and random selection. Output: `experiments/results/preference_alignment.*`.

Also available as:
```bash
make preference-alignment
```

### LLM-as-selector ranking experiment (Section 6.7)

This requires an LLM API key. The dry-run mode validates task setup without calling any API:

```bash
python experiments/expert_annotation/run_ranking_experiment.py \
  --tasks-file experiments/expert_annotation/tasks_objective.yaml \
  --dry-run
```

For live LLM evaluation, set one of these environment variables:

```bash
export DEEPSEEK_API_KEY="your-key"    # DeepSeek-V4-flash (default)
export QWEN_API_KEY="your-key"        # Qwen3-Max
export KIMI_API_KEY="your-key"         # Moonshot Kimi K2.5
```

Then run without `--dry-run`. Output goes to `experiments/expert_annotation/results_objective*/` (one directory per model).

Also available as:
```bash
make llm-eval          # dry-run only
make llm-eval-live     # requires API key env var
```

### Ecosystem audit (Section 2)

```bash
python experiments/mcp_ecosystem_audit.py
```

Audits MCP-related GitHub repositories for ASM-style metadata coverage. Output: console table + CSV.

Also available as:
```bash
make audit
```

## Project Structure

```
asm-spec/
├── schema/                    # JSON Schema definitions (v0.2 legacy, v0.3 current)
├── manifests/                 # 70 service manifests (.asm.json)
├── scorer/                    # Python scoring engine (TOPSIS + weighted avg)
│   ├── scorer.py              # Main module
│   └── test_scorer.py         # Unit tests
├── registry/                  # TypeScript MCP server
│   ├── src/index.ts           # Server entry point (5 tools)
│   ├── src/test_scorer.ts     # TS-side scorer tests
│   └── src/test_topsis.ts     # TS-side TOPSIS tests
├── experiments/               # Evaluation scripts & results
│   ├── ab_test.py             # A/B evaluation (Section 6.5)
│   ├── analyze.py             # Result analysis
│   ├── ablation_experiments.py # Ablation studies (Section 6.3a)
│   ├── mcp_ecosystem_audit.py # Repository audit (Section 2)
│   └── expert_annotation/    # LLM-as-selector experiment (Section 6.7)
│       ├── generate_objective_tasks.py
│       ├── run_ranking_experiment.py
│       └── tasks_objective.yaml
├── demo/                      # End-to-end demos
├── paper/                     # Academic paper draft
└── sep/                       # SEP proposal for MCP specification
```

## Submitting Changes

1. Fork the repository.
2. Create a branch: `git checkout -b feature/your-feature`.
3. Make your changes. Run `make test` and `make eval` to verify nothing breaks.
4. Commit with a clear message: `git commit -m "Add manifest for X service"`.
5. Push and open a pull request.

PRs that add manifests must include validation output (no JSON Schema errors). PRs that modify the scorer must include updated test results if metrics change.
