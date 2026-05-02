# Preference Alignment Evaluation

Generated at: 2026-05-02T12:43:25Z
Tasks: 20
Seed: 2024

Most suitable = best feasible service under the user's stated constraints and preference vector.

Regret is `utility(best feasible service) - utility(selected service)`, where utility is the TOPSIS score under the task-specific preference vector. Lower is better; zero means the selector found the most suitable service under the explicit user preference model.

## Aggregate Results

| Selector | Utility mean | Regret mean | Alignment mean | Zero-regret rate | Constraint violations | Cost mean | Quality mean | Latency mean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| asm_topsis | 0.9007 | 0.0000 | 1.0000 | 100.0% | 0.0% | 0.0161004092 | 0.6665 | 6.6945 |
| weighted_average | 0.8923 | 0.0084 | 0.9907 | 95.0% | 0.0% | 0.0161003905 | 0.6678 | 6.7395 |
| cheapest_first | 0.8000 | 0.1007 | 0.8749 | 75.0% | 0.0% | 0.0074421380 | 0.6586 | 7.5020 |
| fastest_first | 0.7503 | 0.1504 | 0.8330 | 75.0% | 0.0% | 0.0247586755 | 0.6728 | 5.8820 |
| highest_quality_first | 0.6345 | 0.2662 | 0.7221 | 60.0% | 0.0% | 0.0247588255 | 0.6775 | 5.9900 |
| highest_reliability_first | 0.4720 | 0.4287 | 0.5327 | 35.0% | 0.0% | 0.0246427230 | 0.6400 | 6.2500 |
| random | 0.4563 | 0.4445 | 0.5256 | 40.0% | 0.0% | 0.0076503905 | 0.6461 | 7.8975 |

## Per-Request ASM Choices

| Task | User request | ASM selected | Feasible candidates |
|---:|---|---|---:|
| 1 | I need a cheap but reliable TTS API for a 10-minute voiceover; latency should stay under one second. | OpenAI TTS (`openai/tts-1@1.0`) | 2 |
| 2 | I need premium voice quality for a polished product demo, and cost is secondary. | ElevenLabs TTS v2 (`elevenlabs/tts-v2@2.0`) | 2 |
| 3 | I need a low-cost general chat model, but it still needs strong quality and reasonable latency. | GPT-4o (`openai/gpt-4o@2024-11-20`) | 3 |
| 4 | I need the best chat model quality for a reasoning-heavy analysis task; cost is not important. | Gemini 2.5 Pro (`google/gemini-2.5-pro@2.5`) | 3 |
| 5 | I need a low-latency chat model for an interactive support agent. | GPT-4o (`openai/gpt-4o@2024-11-20`) | 2 |
| 6 | I need embeddings for a high-volume RAG pipeline and want to minimize cost without falling below acceptable benchmark quality. | text-embedding-3-large (`openai/text-embedding-3-large@3.0`) | 2 |
| 7 | I need embeddings for a quality-sensitive retrieval benchmark; benchmark quality dominates cost. | Voyage 3 Large (`voyageai/voyage-3-large@3.0`) | 2 |
| 8 | I need the highest-quality image generator for advertising assets; latency under 15 seconds is acceptable. | FLUX 1.1 Pro (`black-forest-labs/flux-1.1-pro@1.1`) | 3 |
| 9 | I need image generation for a batch workflow where speed matters more than small quality differences. | FLUX 1.1 Pro (`black-forest-labs/flux-1.1-pro@1.1`) | 3 |
| 10 | I need web search with the strongest answer quality for a research agent; cost is secondary. | Exa Search (`exa/search-api@v1`) | 2 |
| 11 | I need cheap web search for a high-volume enrichment job. | Tavily Search (`tavily/search-api@v1`) | 2 |
| 12 | I need a scraper for many simple pages, so cost dominates. | Jina Reader (`jina/reader@v1`) | 2 |
| 13 | I need a scraper for an interactive agent and prefer the faster option if costs are acceptable. | Jina Reader (`jina/reader@v1`) | 2 |
| 14 | I need cheap GPU serverless compute for a batch inference job. | RunPod Serverless GPU (`runpod/gpu-serverless@1.0`) | 2 |
| 15 | I need video generation for a benchmark-quality demo; rank by visual quality above all else. | Veo 3.1 (`google/veo-3.1@3.1`) | 2 |
| 16 | I need cheap video generation for social drafts and can tolerate lower benchmark quality. | Kling 3.0 (`kuaishou/kling-3.0@3.0`) | 2 |
| 17 | I need real-time speech-to-text for a meeting assistant. | Deepgram Nova-2 (`deepgram/nova@v2`) | 2 |
| 18 | I need low-cost speech transcription for a batch audio archive. | Deepgram Nova-2 (`deepgram/nova@v2`) | 2 |
| 19 | I need a todo API for a fast personal productivity agent. | Todoist (`todoist/api@v2`) | 3 |
| 20 | I need a todo API where app quality and reliability matter more than raw latency. | Todoist (`todoist/api@v2`) | 3 |
