# ASM Discovery

`discovery/` turns natural-language tasks into valid ASM taxonomies.

## What it does

- Loads the live taxonomy universe from `manifests/*.asm.json`.
- Builds an embedding index (`discovery/data/taxonomy-index.json`).
- Resolves task text to the closest taxonomy with confidence and top-k candidates.
- Supports deterministic CI runs with `FakeHashEmbedder` (no API keys).
- Uses a LangGraph workflow (`embedTask -> retrieveCandidates -> selectWinner`) for production-style orchestration.

## Commands

```bash
cd discovery
npm install
npm run precompute
npm run demo
npm run test:smoke
```

## Embedding modes

- default: requires `OPENAI_API_KEY` and uses OpenAI `text-embedding-3-small`.
- fallback mode: set `ASM_ALLOW_FAKE_EMBEDDER=1` to use deterministic `FakeHashEmbedder` (CI/local without keys).

## LLM provider (reranking)

**Powered by Gemini 2.5 Flash via Function Calling to Circle x402 endpoints**

The LangGraph rerank node supports a 3-tier fallback chain:

| Priority | Env Var | Model | Notes |
|----------|---------|-------|-------|
| 1 (Google track) | `GEMINI_API_KEY` | `gemini-2.5-flash` | **Function Calling** to `/api/score` — agents securely interact with Circle APIs |
| 2 | `OPENAI_API_KEY` + `OPENAI_BASE_URL=openrouter.ai/...` | `openrouter/auto` | OpenRouter fallback |
| 3 | `OPENAI_API_KEY` | `gpt-4o-mini` | Default OpenAI fallback |

When Gemini is active, the model uses native **Function Calling** (`select_taxonomy_and_score`) to structure its taxonomy selection as a tool invocation that maps directly to the seller's `/api/score` endpoint — satisfying the Google track requirement for "Function Calling, allowing agents to securely interact with Circle APIs."

## Output contract

`discoverTaxonomy(...)` returns:

- `taxonomy`: selected taxonomy or `null` (low confidence)
- `confidence`: 0..1 similarity score
- `candidates`: top-k taxonomy shortlist
- `reasoning`: concise matching explanation

## Integration target

The index is intended to be consumed by payment-side agent routing (`/api/agent-decide`) so winner selection uses real task understanding instead of static mappings.
