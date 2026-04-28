#!/usr/bin/env tsx
/**
 * ASM × Circle Nanopayments — 50-tx Benchmark Runner
 *
 * Runs the 50-subtask Marketing Campaign scenario on Arc testnet.
 * Satisfies hackathon requirements:
 *   - ≥ 50 on-chain transactions in demo
 *   - Real per-action pricing ≤ $0.01
 *   - Data for the margin-vs-Ethereum comparison
 *
 * Usage:
 *   npm run benchmark:50tx              # live mode (Arc testnet)
 *   PAYMENT_MODE=mock npm run benchmark:50tx  # mock mode
 *
 * Output: benchmark-results/benchmark-<ISO-timestamp>.json
 *
 * Prerequisites (live mode):
 *   1. Seller server running:     npm run dev:seller
 *   2. Registry server running:   npm run dev:registry
 *   3. .env configured with real BUYER_PRIVATE_KEY + SELLER_ADDRESS
 *   4. Gateway balance funded:    npm run deposit -- 1
 *
 * In mock mode only prerequisite #1 is strictly needed (seller replies
 * to HTTP POST /api/score without requiring a real payment).
 */

import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";
import {
  generateBenchmarkTasks,
  summarizeTasks,
} from "../src/benchmark-tasks.js";
import { loadConfig } from "../src/config.js";
import { ASMBuyerClient } from "../src/buyer.js";
import { parseAgentIntent } from "../src/gemini-agent.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ── Result types ─────────────────────────────────────────────

interface CandidateLite {
  service_id: string;
  display_name: string;
  price_usd: number;
  quality: number;
  latency_p50_ms: number;
  score: number;
  onchain_address?: string;
  picked: boolean;
  rank: number;
}

interface TaskResult {
  id: number;
  category: string;
  taxonomy: string;
  expectedTaxonomy?: string;
  discoveryCorrect?: boolean;
  prompt: string;
  targetPriceUsd: number;
  /** Actual settled price in USDC (0 if stubbed / failed) */
  actualPriceUsd: number;
  /** On-chain tx hash if settled; undefined if stubbed or failed */
  txHash?: string;
  /** Service picked by ASM scorer */
  pickedService?: string;
  /** On-chain receiver address for the winning service (where USDC landed) */
  winnerOnchainAddress?: string;
  /** 2–5 candidates the scorer considered, in rank order */
  candidates?: CandidateLite[];
  /** One-sentence human-readable "why this one won" */
  reasoning?: string;
  /** Per-task wall-clock latency in ms */
  latencyMs: number;
  status: "settled" | "stubbed" | "failed";
  error?: string;
}

interface FundsFlowEntry {
  address: string;
  serviceId?: string;
  displayName?: string;
  txCount: number;
  totalValueUsd: number;
}

interface BenchmarkResult {
  runDate: string;
  mode: "live" | "mock";
  chain: string;
  network: string;
  distribution: ReturnType<typeof summarizeTasks>;
  arcResults: {
    totalTxs: number;
    settledCount: number;
    stubbedCount: number;
    failedCount: number;
    totalValueTransferredUsd: number;
    totalArcFeesUsd: number; // TODO: measure from tx receipts
    /** Distinct on-chain recipient addresses USDC flowed to */
    uniqueRecipientCount: number;
    /** Per-recipient breakdown — the "money fanned out" evidence */
    fundsFlow: FundsFlowEntry[];
    wallClockMs: number;
    avgLatencyMs: number;
    minLatencyMs: number;
    maxLatencyMs: number;
  };
  ethereumHypothetical: {
    note: string;
    // Filled in later (phase 2) by fetching Etherscan + CoinGecko
    gasPriceGwei?: number;
    ethPriceUsd?: number;
    totalGasCostUsd?: number;
    overheadRatio?: number;
  };
  discoveryAccuracy?: {
    enabled: boolean;
    evaluated: number;
    correct: number;
    accuracy: number;
    byCategory: Record<string, { evaluated: number; correct: number; accuracy: number }>;
  };
  tasks: TaskResult[];
}

// ── Main ─────────────────────────────────────────────────────

async function main() {
  console.log("🧪 ASM-Pay 50-tx Benchmark\n");

  const config = loadConfig();
  console.log(`   Mode:    ${config.mode}`);
  console.log(`   Chain:   ${config.chainName}`);
  console.log(`   Network: ${config.network}`);
  console.log(`   Seller:  http://localhost:${config.port}\n`);

  // 0. Initialize buyer client (once, reused for all 50 tasks)
  const buyer = new ASMBuyerClient(config);
  const liveReady = await buyer.initialize();
  if (config.mode === "live" && !liveReady) {
    console.warn("⚠️  Live mode requested but GatewayClient init failed.");
    console.warn("    Benchmark will still run, but tx will be HTTP mock calls.\n");
  }

  // Quick seller health check — fail fast if not running
  try {
    const resp = await fetch(`http://localhost:${config.port}/api/services`, {
      signal: AbortSignal.timeout(3000),
    });
    if (!resp.ok) throw new Error(`status ${resp.status}`);
  } catch (err: unknown) {
    console.error(`❌ Seller not reachable at http://localhost:${config.port}`);
    console.error(`   Start it first with:  npm run dev:seller`);
    console.error(`   Error: ${err instanceof Error ? err.message : String(err)}`);
    process.exit(1);
  }

  // 1. Generate tasks
  const allTasks = generateBenchmarkTasks();

  // Optional `--limit N` flag for smoke tests (runs first N tasks only).
  // Example: `npm run benchmark:50tx -- --limit 1`
  const limitArgIdx = process.argv.findIndex((a) => a === "--limit");
  const limit =
    limitArgIdx >= 0 && process.argv[limitArgIdx + 1]
      ? Math.max(1, Number.parseInt(process.argv[limitArgIdx + 1], 10))
      : allTasks.length;
  const tasks = allTasks.slice(0, limit);
  if (limit < allTasks.length) {
    console.log(
      `⚠️  --limit ${limit} — running ${tasks.length}/${allTasks.length} tasks (smoke-test mode)\n`,
    );
  }

  const summary = summarizeTasks(tasks);
  const discoveryEnabled = process.env.ASM_DISCOVERY_ENABLED === "1";
  console.log(`📋 Generated ${summary.total} subtasks across ${Object.keys(summary.byCategory).length} categories`);
  console.log(`   Taxonomy source: ${discoveryEnabled ? "nl-discovery (prompt -> taxonomy)" : "static benchmark mapping"}`);
  console.log(`   Target total cost: $${summary.totalTargetCostUsd.toFixed(4)}`);
  console.log(`   By category:`);
  for (const [cat, n] of Object.entries(summary.byCategory)) {
    console.log(`     ${cat.padEnd(14)} × ${n}`);
  }
  console.log();

  // 2. Run loop
  const results: TaskResult[] = [];
  const runStart = Date.now();

  for (const task of tasks) {
    const taskStart = Date.now();
    let result: TaskResult;

    try {
      const resolvedTaxonomy = discoveryEnabled
        ? (await parseAgentIntent(task.prompt)).taxonomy || task.taxonomy
        : task.taxonomy;

      // PAYMENT CALL — real buyer.score() via Circle Gateway (live) or
      // direct POST (mock). Each call = one on-chain tx in live mode.
      const scoreResult = await buyer.score({ taxonomy: resolvedTaxonomy });

      // Extract tx hash injected by buyer.score() in live mode
      const txHash: string | undefined = scoreResult?._txHash;
      // _formattedAmount is the amount GatewayClient reports paid
      const actualPriceUsd = parsePriceSafe(
        scoreResult?._formattedAmount,
        config.scorePrice,
      );

      // New contract: seller returns { payment, scoring: {pick, ranking, ...} }
      // pick = { winner, candidates, reasoning, taxonomy }
      const pick = scoreResult?.scoring?.pick;
      const winner = pick?.winner;
      const pickedService: string | undefined =
        winner?.service_id ??
        scoreResult?.topService ??
        scoreResult?.top_service;
      const winnerOnchainAddress: string | undefined =
        winner?.onchain_address ??
        scoreResult?.payment?.recipient;
      const candidates: CandidateLite[] | undefined = pick?.candidates?.map(
        (c: any): CandidateLite => ({
          service_id: c.service_id,
          display_name: c.display_name,
          price_usd: c.price_usd,
          quality: c.quality,
          latency_p50_ms: c.latency_p50_ms,
          score: c.score,
          onchain_address: c.onchain_address,
          picked: c.picked,
          rank: c.rank,
        }),
      );
      const reasoning: string | undefined = pick?.reasoning;

      result = {
        id: task.id,
        category: task.category,
        taxonomy: resolvedTaxonomy,
        expectedTaxonomy: discoveryEnabled ? task.taxonomy : undefined,
        discoveryCorrect: discoveryEnabled ? resolvedTaxonomy === task.taxonomy : undefined,
        prompt: task.prompt,
        targetPriceUsd: task.targetPriceUsd,
        actualPriceUsd,
        txHash,
        pickedService,
        winnerOnchainAddress,
        candidates,
        reasoning,
        latencyMs: Date.now() - taskStart,
        status: txHash ? "settled" : "stubbed",
      };
    } catch (err: unknown) {
      result = {
        id: task.id,
        category: task.category,
        taxonomy: discoveryEnabled ? "discovery_failed" : task.taxonomy,
        expectedTaxonomy: discoveryEnabled ? task.taxonomy : undefined,
        discoveryCorrect: discoveryEnabled ? false : undefined,
        prompt: task.prompt,
        targetPriceUsd: task.targetPriceUsd,
        actualPriceUsd: 0,
        latencyMs: Date.now() - taskStart,
        status: "failed",
        error: err instanceof Error ? err.message : String(err),
      };
    }

    results.push(result);
    logTaskRow(result);
  }

  const wallClockMs = Date.now() - runStart;

  // 3. Aggregate
  const latencies = results.map((r) => r.latencyMs);

  // Funds-flow: "USDC fanned out to how many winners, how much each".
  // This is the on-chain evidence that the scorer actually chose.
  const flowMap = new Map<string, FundsFlowEntry>();
  for (const r of results) {
    if (!r.winnerOnchainAddress) continue;
    const key = r.winnerOnchainAddress;
    const e = flowMap.get(key) ?? {
      address: key,
      serviceId: r.pickedService,
      displayName: r.candidates?.find((c) => c.picked)?.display_name,
      txCount: 0,
      totalValueUsd: 0,
    };
    e.txCount += 1;
    e.totalValueUsd = Number((e.totalValueUsd + r.actualPriceUsd).toFixed(6));
    flowMap.set(key, e);
  }
  const fundsFlow = Array.from(flowMap.values()).sort(
    (a, b) => b.totalValueUsd - a.totalValueUsd,
  );
  const benchmark: BenchmarkResult = {
    runDate: new Date().toISOString(),
    mode: config.mode,
    chain: config.chainName,
    network: config.network,
    distribution: summary,
    arcResults: {
      totalTxs: results.length,
      settledCount: results.filter((r) => r.status === "settled").length,
      stubbedCount: results.filter((r) => r.status === "stubbed").length,
      failedCount: results.filter((r) => r.status === "failed").length,
      totalValueTransferredUsd: Number(
        results.reduce((s, r) => s + r.actualPriceUsd, 0).toFixed(6),
      ),
      totalArcFeesUsd: 0, // TODO: measure from tx receipts once live
      uniqueRecipientCount: fundsFlow.length,
      fundsFlow,
      wallClockMs,
      avgLatencyMs: Math.round(avg(latencies)),
      minLatencyMs: Math.min(...latencies),
      maxLatencyMs: Math.max(...latencies),
    },
    ethereumHypothetical: {
      note: "Filled in Phase 2 via Etherscan gas + CoinGecko ETH price fetch at runtime.",
    },
    discoveryAccuracy: discoveryEnabled
      ? computeDiscoveryAccuracy(results)
      : undefined,
    tasks: results,
  };

  // 4. Write output
  const outDir = path.resolve(__dirname, "..", "benchmark-results");
  if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
  const outFile = path.join(
    outDir,
    `benchmark-${benchmark.runDate.replace(/[:.]/g, "-")}.json`,
  );
  fs.writeFileSync(outFile, JSON.stringify(benchmark, null, 2));

  // 5. Summary
  console.log();
  console.log("📊 Benchmark complete");
  console.log(`   Total tx:         ${benchmark.arcResults.totalTxs}`);
  console.log(`   Settled:          ${benchmark.arcResults.settledCount}`);
  console.log(`   Stubbed:          ${benchmark.arcResults.stubbedCount}`);
  console.log(`   Failed:           ${benchmark.arcResults.failedCount}`);
  console.log(`   Total value:      $${benchmark.arcResults.totalValueTransferredUsd}`);
  console.log(`   Unique recipients: ${benchmark.arcResults.uniqueRecipientCount}`);
  if (fundsFlow.length > 0) {
    console.log(`   Top recipients:`);
    for (const e of fundsFlow.slice(0, 5)) {
      console.log(
        `     ${(e.displayName || e.serviceId || "—").padEnd(28)} ${e.address.slice(0, 10)}…  ${e.txCount}×  $${e.totalValueUsd.toFixed(4)}`,
      );
    }
  }
  console.log(`   Wall clock:       ${(wallClockMs / 1000).toFixed(2)}s`);
  console.log(`   Avg latency:      ${benchmark.arcResults.avgLatencyMs}ms`);
  if (benchmark.discoveryAccuracy?.enabled) {
    console.log(
      `   Discovery acc:    ${(benchmark.discoveryAccuracy.accuracy * 100).toFixed(1)}% (${benchmark.discoveryAccuracy.correct}/${benchmark.discoveryAccuracy.evaluated})`,
    );
  }
  console.log(`   Output:           ${path.relative(process.cwd(), outFile)}`);
  console.log();
}

// ── Helpers ──────────────────────────────────────────────────

/**
 * Parse a price string like "$0.005" or "0.005" into a number.
 * Falls back to configScorePrice if primary is missing/unparseable.
 */
function parsePriceSafe(primary: unknown, configScorePrice: string): number {
  const fromConfig = Number.parseFloat(configScorePrice.replace(/[^0-9.]/g, ""));
  if (primary == null) return fromConfig || 0;
  const s = String(primary).replace(/[^0-9.]/g, "");
  const n = Number.parseFloat(s);
  return Number.isFinite(n) ? n : fromConfig || 0;
}

function logTaskRow(r: TaskResult): void {
  const icon = r.status === "settled" ? "✅" : r.status === "stubbed" ? "🔵" : "❌";
  const tx = r.txHash ? r.txHash.slice(0, 10) + "…" : "—";
  console.log(
    `   ${icon} #${String(r.id).padStart(2, "0")} ${r.category.padEnd(12)} $${r.actualPriceUsd.toFixed(4)}  ${String(r.latencyMs).padStart(4)}ms  ${tx}`,
  );
}

function avg(nums: number[]): number {
  return nums.length === 0 ? 0 : nums.reduce((a, b) => a + b, 0) / nums.length;
}

function computeDiscoveryAccuracy(results: TaskResult[]): {
  enabled: boolean;
  evaluated: number;
  correct: number;
  accuracy: number;
  byCategory: Record<string, { evaluated: number; correct: number; accuracy: number }>;
} {
  const evaluated = results.filter((r) => r.expectedTaxonomy).length;
  const correct = results.filter((r) => r.discoveryCorrect).length;
  const byCategoryAccumulator: Record<string, { evaluated: number; correct: number }> = {};
  for (const r of results) {
    if (!r.expectedTaxonomy) continue;
    const item = byCategoryAccumulator[r.category] ?? { evaluated: 0, correct: 0 };
    item.evaluated += 1;
    if (r.discoveryCorrect) item.correct += 1;
    byCategoryAccumulator[r.category] = item;
  }
  const byCategory: Record<string, { evaluated: number; correct: number; accuracy: number }> = {};
  for (const [category, stats] of Object.entries(byCategoryAccumulator)) {
    byCategory[category] = {
      ...stats,
      accuracy: stats.evaluated === 0 ? 0 : Number((stats.correct / stats.evaluated).toFixed(4)),
    };
  }
  return {
    enabled: true,
    evaluated,
    correct,
    accuracy: evaluated === 0 ? 0 : Number((correct / evaluated).toFixed(4)),
    byCategory,
  };
}

main().catch((err) => {
  console.error("❌ Benchmark failed:", err);
  process.exit(1);
});
