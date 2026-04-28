# Benchmark Results

Generated output from `payments/scripts/benchmark-50tx.ts`.

## `sample-for-frontend.json`

**Pinned sample** — do not overwrite. This is the canonical mock-mode run that
the frontend dashboard and demo animations are built against. 50 tasks, 15
unique recipient addresses, $0.25 total value moved.

Everyone else's runs are written as `benchmark-<ISO-timestamp>.json` and are
gitignored.

## Top-level schema

```jsonc
{
  "runDate": "2026-04-20T14:49:02.987Z",
  "mode": "mock" | "live",
  "chain": "arc-testnet",
  "network": "eip155:5042002",
  "distribution": { /* category -> count */ },

  "arcResults": {
    "totalTxs": 50,
    "settledCount": 50,
    "stubbedCount": 0,
    "failedCount": 0,
    "totalValueTransferredUsd": 0.25,
    "totalArcFeesUsd": 0,
    "uniqueRecipientCount": 15,
    "fundsFlow": [
      {
        "address": "0x...",
        "serviceId": "openai/gpt-4o@2024-08-06",
        "displayName": "GPT-4o",
        "txCount": 6,
        "totalValueUsd": 0.03
      }
      /* ...one entry per unique recipient, sorted by txCount desc */
    ],
    "wallClockMs": 12300,
    "avgLatencyMs": 246,
    "minLatencyMs": 80,
    "maxLatencyMs": 620
  },

  "ethereumHypothetical": { /* gas comparison, live-fetched at runtime */ },

  "tasks": [
    {
      "id": 1,
      "category": "image-gen",
      "taxonomy": "ai.vision.image_generation",
      "prompt": "Hero image, ADHD user working peacefully, ...",
      "targetPriceUsd": 0.004,
      "actualPriceUsd": 0.004,
      "pickedService": "black-forest-labs/flux-1.1-pro@1.1",
      "winnerOnchainAddress": "0x746b0F52b979b18225CC31FC7EB1dd89a67100a9",
      "candidates": [
        {
          "service_id": "black-forest-labs/flux-1.1-pro@1.1",
          "display_name": "FLUX 1.1 Pro",
          "price_usd": 0.04,
          "quality": 0.9,
          "latency_p50_ms": 3500,
          "score": 0.832,
          "onchain_address": "0x746b0F...",
          "picked": true,
          "rank": 1
        }
        /* ...all 2-5 candidates for this taxonomy, ranked */
      ],
      "reasoning": "FLUX 1.1 Pro wins on price ($0.040/call, trust 0.90) among 3 candidates; +0.643 ahead of Imagen 3.",
      "latencyMs": 246,
      "status": "settled"
    }
    /* ...50 tasks */
  ]
}
```

## Keys the frontend must surface

**Per task (the hero shot):**
- `prompt` — what Campaign asked for
- `candidates[]` — fan out these cards, animate score bars, highlight `picked: true`
- `reasoning` — caption under the winner
- `winnerOnchainAddress` — the address money flies to
- `actualPriceUsd` — the amount that flew

**Roll-up (the scale panel):**
- `arcResults.totalTxs` (50)
- `arcResults.uniqueRecipientCount` (15)
- `arcResults.totalValueTransferredUsd` ($0.25)
- `arcResults.wallClockMs` (~12s)
- `arcResults.fundsFlow[]` — the sankey / bar chart source

**Comparison panel (the punchline):**
- `arcResults.totalValueTransferredUsd` (our cost: $0.25)
- `ethereumHypothetical.totalCostUsd` (their cost: ~$50)
- Ratio = ~200×
