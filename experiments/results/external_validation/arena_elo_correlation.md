# ASM declared quality vs LM Arena Elo

Generated: 2026-05-04T05:17:25Z
Source:    pickle:arena_elo.pkl
Paired:    8 / 8 manifests matched

## Headline correlation (all metrics pooled)

- Spearman rho = **-0.2143**  (95% bootstrap CI [-0.8571, 0.7619])
- Kendall tau  = **-0.2143**   (95% bootstrap CI [-0.75, 0.4286])

Pooled across heterogeneous declared metrics (LMSYS_Elo, Artificial_Analysis_Intelligence,
MMLU). The pooled correlation is uninformative because the three scales are not commensurable
— see per-metric breakdown below.

## Per-metric breakdown

| Declared metric | n | Spearman rho (95% CI) | Kendall tau |
|---|---:|---|---:|
| `Artificial_Analysis_Intelligence` | 4 | -0.2 [-0.6, 1.0] | 0.0 |
| `LMSYS_Elo` | 3 | 1.0 [1.0, 1.0] | 1.0 |
| `MMLU` | 1 | n/a n/a | n/a |

## Per-pair detail

| ASM service_id | ASM metric | ASM score | Arena model | Arena Elo | Arena rank | Battles | Gap note |
|---|---|---:|---|---:|---:|---:|---|
| `openai/gpt-4o@2024-11-20` | LMSYS_Elo | 1285.0 | `gpt-4o-2024-08-06` | 1286 | 86 | 47,973 | Closest dated GPT-4o variant; manifest is 2024-11-20, Arena snapshot has Aug 2024 release. |
| `anthropic/claude-sonnet-4@4.0` | LMSYS_Elo | 1290.0 | `claude-sonnet-4-20250514` | 1334 | 50 | 28,536 | Same family generation (Sonnet 4); Arena entry is May 2025 release. |
| `google/gemini-2.5-pro@2.5` | LMSYS_Elo | 1300.0 | `gemini-2.5-pro` | 1466 | 1 | 35,586 | Direct match. |
| `deepseek/deepseek-v4-flash@4.0` | Artificial_Analysis_Intelligence | 53.0 | `deepseek-v3.1` | 1418 | 2 | 4,979 | V4-flash not yet on Arena (Aug 2025 snapshot); using V3.1 as nearest predecessor. |
| `qwen/qwen3-max@3.0` | Artificial_Analysis_Intelligence | 56.0 | `qwen-max-2025-08-15` | 1429 | 2 | 5,547 | Closest Qwen-Max release in Arena snapshot; manifest is Qwen3 line. |
| `moonshot/kimi-k2.5@2.5` | Artificial_Analysis_Intelligence | 60.0 | `kimi-k2-0711-preview` | 1379 | 24 | 18,734 | Only Kimi entry in Arena Aug 2025 snapshot; manifest is K2.5, Arena has K2 preview. |
| `zhipu/glm-5@5.0` | Artificial_Analysis_Intelligence | 58.0 | `glm-4.5` | 1429 | 2 | 11,222 | GLM-5 not yet on Arena snapshot; GLM-4.5 is the most recent dated entry. |
| `minimax/m2.7@2.7` | MMLU | 78.0 | `minimax-m1` | 1350 | 42 | 22,994 | Only MiniMax entry in Arena snapshot; manifest is M2.7, Arena has M1. |

## Caveats

- N = 8 paired observations; the bootstrap CI is wide and the point estimate is sensitive to any single mismatch.
- Arena entries are best-effort matches to ASM service_ids; the exact-dated variant in our manifest is rarely on Arena yet, so we use the closest dated predecessor and document the gap in the per-pair table above.
- Arena Elo measures pairwise chat preference; ASM-declared quality (mostly Artificial Analysis Intelligence index) measures benchmark suite performance. These are correlated but not identical; a positive rho means ASM's quality axis tracks user preference at the rank level, not that the two scales are interchangeable.
