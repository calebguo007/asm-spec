# ASM Demo Scenario — "Campaign"

> **Track**: Agent-to-Agent Payment Loop
> **Worked example**: Campaign, an AI marketing agent — 50 subtasks across 15 service categories
> **Updated**: 2026-04-21

---

## Important — this is one worked example, not the product

**ASM is a general-purpose protocol.** The Campaign persona below is a
narrative vehicle that makes the demo concrete and measurable — 50
purchases at sub-cent prices across 15 categories, exactly what the
hackathon brief asks for.

The exact same ten lines of code route **any agent's any sub-task to any
provider** in the ASM registry. Coding agents can pick IDEs. Research
agents can pick search APIs. Support agents can pick knowledge bases.
ASM does not care what domain the caller is in — it only reads
`taxonomy` and a preference vector.

---

## Meet Campaign (one-paragraph pitch)

**Campaign** is an AI marketing agent. A founder hands her a brief —
*"Launch FocusBear globally."* — and she decomposes it into 50 concrete
subtasks: images, copy, translations, voiceovers, video snippets,
sentiment checks, competitor scrapes, deploy scripts.

For each subtask, Campaign calls `asm_registry_lookup`. ASM returns
ranked candidates from its registry of 70 real services, the scorer
picks the best by price × quality × SLA, and Circle Nanopayments
settles the fee on Arc in USDC. Fifty on-chain transactions complete
in seconds. The dashboard shows the total cost versus what the same
50 transactions would cost on Ethereum mainnet at live gas — a ratio
of about 200×.

---

## 🎯 Why This Scenario (for judges)

| Hackathon requirement | How this scenario satisfies it |
|---|---|
| Track: Agent-to-Agent Payment Loop | Agent autonomously pays 50 different service agents in real time |
| Real per-action pricing ≤ $0.01 | Each subtask priced $0.001–$0.005 |
| 50+ on-chain tx in demo | Exactly 50, each with a distinct mission |
| Margin explanation | Live comparison with Ethereum gas (1,900×–3,800× overhead shown) |
| Use Arc + USDC + Nanopayments | All three on the critical path |
| Originality | ASM as value layer, paired with ERC-8004 trust layer — a new framing |
| Business value | Every agent vendor in the audience immediately thinks "I need this" |

---

## 🧩 The 50 Subtasks (distribution)

**Narrative**: User brief → "launch FocusBear (AI productivity app for ADHD users) on social media globally."

Agent decomposes into:

| Category | Count | Example subtask | Price/call |
|---|---|---|---|
| image generation | 4 | "Hero image, ADHD user, calm palette, 1024×1024" | $0.004 |
| copywriting | 6 | "Instagram caption, 150 chars, witty, target ADHD adults 25–40" | $0.002 |
| translation | 6 | "Translate caption to Japanese, keep tone" | $0.001 |
| text-to-speech | 3 | "Voiceover script A, female voice, 30s" | $0.003 |
| video generation | 3 | "6-sec product demo, screen recording style" | $0.005 |
| sentiment analysis | 5 | "Check if caption reads ADHD-friendly" | $0.001 |
| web scraping | 5 | "Scrape competitor X's latest post engagement" | $0.002 |
| OCR | 2 | "Extract text from competitor infographic" | $0.001 |
| code generation | 4 | "Generate Google Analytics snippet for campaign tracking" | $0.003 |
| data labeling | 3 | "Tag 100 sample reviews by sentiment" | $0.002 |
| summarization | 3 | "Summarize competitor landing page in 50 words" | $0.002 |
| search | 3 | "Find top 5 ADHD productivity blogs" | $0.002 |
| calendar | 1 | "Schedule post publish for local timezone peak hours" | $0.001 |
| storage | 1 | "Upload rendered image to R2 bucket" | $0.001 |
| deploy | 1 | "Trigger GitHub Action to push landing page" | $0.002 |
| **Total** | **50** | | **~$0.11** |

---

## 🔁 Per-Subtask Execution Flow

```
┌─────────────────────────────────────────────────────┐
│ Marketing Agent                                     │
│   │                                                 │
│   │ 1. "I need image-gen service, prompt: X"        │
│   ▼                                                 │
│ asm_registry_lookup({category: "image-gen"})        │
│   │                                                 │
│   │ 2. Returns 6 candidates with manifests          │
│   ▼                                                 │
│ ASM Scorer                                          │
│   │                                                 │
│   │ 3. Ranks by (price × quality × sla)             │
│   ▼                                                 │
│ Agent picks top-1 (e.g., bfl-flux-1.1-pro)          │
│   │                                                 │
│   │ 4. Circle Nanopayment via GatewayClient         │
│   ▼                                                 │
│ Arc settles USDC, sub-second, tx hash returned      │
│   │                                                 │
│   │ 5. Service called (or mocked)                   │
│   ▼                                                 │
│ Result logged, next subtask begins                  │
└─────────────────────────────────────────────────────┘
```

Repeated 50×, total wall-clock target: **< 30 seconds end-to-end**.

---

## 📊 Live Dashboard (frontend — what viewers see)

Top bar:
- Progress: **37 / 50 subtasks complete**
- Elapsed: **11.3s**
- Total value moved on Arc: **$0.0841**
- Arc fees: **$0.0000** *(actual, measured)*

Middle pane (task log, scrolling):
```
✓ image-gen  → bfl-flux-1.1-pro       | $0.004 | 0.31s | tx: 0x8f…
✓ copywrite  → anthropic-claude…      | $0.002 | 0.18s | tx: 0x71…
✓ translate  → deepl-translate        | $0.001 | 0.12s | tx: 0x42…
...
```

Bottom comparison panel (the killer chart):
```
                  ASM-Pay on Arc    Same 50 tx on Ethereum
                  ───────────────   ────────────────────────
Total cost        $0.08             $94.75  (at 15 gwei)
                                    $0.44   (at today's low)
                                    $189    (at 30 gwei)
Overhead ratio    1.0×              1,184× – 2,363×
```

Tag: *"Methodology: Live Etherscan + CoinGecko at runtime. Source: this benchmark run."*

---

## 🛠 Implementation Plan

### Phase 1 · Today 4/20 (14:00–17:00)
- [ ] `payments/scripts/benchmark-50tx.ts` skeleton
- [ ] Task generator: emits 50 subtasks matching distribution above
- [ ] Integrate with existing `buyer.ts` (Circle GatewayClient already works)
- [ ] Run once end-to-end (mock service responses OK for now)
- [ ] **Measure & log actual Arc fees** (critical — don't trust marketing copy)
- [ ] Output JSON result file: `benchmark-results/[timestamp].json`

### Phase 2 · 4/21
- [ ] Live Etherscan gas API fetch + CoinGecko ETH price fetch
- [ ] Compute hypothetical Ethereum cost, append to JSON
- [ ] Polish ASM registry lookup — ensure scorer picks make sense
- [ ] Real (not mocked) service calls for at least 10 of 50 categories

### Phase 3 · 4/22
- [ ] Dashboard frontend polish
- [ ] Real-time streaming of tx log during run
- [ ] Comparison chart uses live data

### Phase 4 · 4/23–4/24
- [ ] Deck + video script + video recording referencing this scenario

---

## 🧯 Risk & Fallback

| Risk | Mitigation |
|---|---|
| Real service calls fail / paywall | Demo uses **mocked service responses** — the *payment* is real, the *service result* is stubbed. Note this explicitly in video: "we're demonstrating the payment + selection flow; service execution is stubbed to avoid vendor keys for 15 providers." Judges accept this. |
| 50 tx on Arc testnet slower than expected | Use Promise.all for batches of 5–10 parallel calls |
| Arc testnet has unexpected fees | Still a win — log actual fees, update punchline to "Arc fees: $X, still 100× better than Ethereum" |
| Etherscan API rate limit | Cache gas price once at start of benchmark run; note timestamp in output |
| Narrative confusion: "why a marketing agent?" | Reframe in video: "The marketing workflow is just the example. ASM routes *any* agent's *any* subtask to *any* registry." |

---

## 📹 Video Demo Segment (for 4/24 planning)

A 60-second video segment based on this scenario:

- **0:00–0:10** — User types brief into UI: "Launch FocusBear globally"
- **0:10–0:15** — Agent decomposes into 50 subtasks (animated list)
- **0:15–0:40** — Dashboard streams 50 task completions live, tx hashes rolling
- **0:40–0:50** — Final comparison panel appears: Arc $0.08 vs Ethereum $95
- **0:50–0:55** — Click into Arc Block Explorer, show one tx verified *(hackathon requirement)*
- **0:55–1:00** — Circle Developer Console showing completed tx *(hackathon requirement)*

---

## Success Criteria

- [ ] 50 real on-chain tx on Arc testnet
- [ ] Arc fees measured and logged (value TBD — **do not assume zero until measured**)
- [ ] Hypothetical Ethereum cost computed from live data at runtime
- [ ] End-to-end wall clock < 30 seconds
- [ ] Dashboard renders all 50 tx with hashes
- [ ] Video segment built from this scenario is ≤ 60s and self-explanatory
