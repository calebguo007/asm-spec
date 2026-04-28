#!/usr/bin/env npx tsx
/**
 * ASM Registry TypeScript unit tests — 3 key test cases.
 *
 * 1. Golden test: TOPSIS output on known synthetic input
 * 2. io_ratio test: effect of io_ratio param on ranking
 * 3. Cross-language parity: compare with Python scorer output
 *
 * Usage: npx tsx src/test_scorer.ts
 */

import * as path from "path";
import {
  ASMRegistry,
  ASMManifest,
  scoreTopsis,
  scoreServices,
  extractPrimaryCost,
  extractPrimaryQuality,
  parseLatency,
  minMaxNormalize,
} from "./index.js";

// ── TestTool ────────────────────────────────────

let passed = 0;
let failed = 0;

function assert(condition: boolean, msg: string): void {
  if (!condition) {
    throw new Error(`Assertion failed: ${msg}`);
  }
}

function assertClose(a: number, b: number, tol: number, msg: string): void {
  const diff = Math.abs(a - b);
  if (diff > tol) {
    throw new Error(`${msg}: ${a} vs ${b}, diff=${diff.toFixed(8)} > tol=${tol}`);
  }
}

function runTest(name: string, fn: () => void): void {
  try {
    fn();
    console.log(`✅ ${name}: PASSED`);
    passed++;
  } catch (e: any) {
    console.log(`❌ ${name}: FAILED — ${e.message}`);
    failed++;
  }
}

// ── Synthetic Test Data ────────────────────────────────

const SYNTHETIC_MANIFESTS: ASMManifest[] = [
  {
    asm_version: "0.3",
    service_id: "test/cheap-fast@1.0",
    taxonomy: "ai.llm.chat",
    display_name: "Cheap Fast",
    pricing: {
      billing_dimensions: [
        { dimension: "input_token", unit: "per_1M", cost_per_unit: 1.0, currency: "USD" },
        { dimension: "output_token", unit: "per_1M", cost_per_unit: 2.0, currency: "USD" },
      ],
    },
    quality: { metrics: [{ name: "Elo", score: 1100, scale: "Elo" }] },
    sla: { latency_p50: "300ms", uptime: 0.99 },
  },
  {
    asm_version: "0.3",
    service_id: "test/expensive-good@1.0",
    taxonomy: "ai.llm.chat",
    display_name: "Expensive Good",
    pricing: {
      billing_dimensions: [
        { dimension: "input_token", unit: "per_1M", cost_per_unit: 10.0, currency: "USD" },
        { dimension: "output_token", unit: "per_1M", cost_per_unit: 30.0, currency: "USD" },
      ],
    },
    quality: { metrics: [{ name: "Elo", score: 1350, scale: "Elo" }] },
    sla: { latency_p50: "1.5s", uptime: 0.999 },
  },
  {
    asm_version: "0.3",
    service_id: "test/balanced-mid@1.0",
    taxonomy: "ai.llm.chat",
    display_name: "Balanced Mid",
    pricing: {
      billing_dimensions: [
        { dimension: "input_token", unit: "per_1M", cost_per_unit: 3.0, currency: "USD" },
        { dimension: "output_token", unit: "per_1M", cost_per_unit: 8.0, currency: "USD" },
      ],
    },
    quality: { metrics: [{ name: "Elo", score: 1250, scale: "Elo" }] },
    sla: { latency_p50: "800ms", uptime: 0.995 },
  },
];

// ── Test 1: TOPSIS Golden Test ──────────────────

runTest("Test 1: TOPSIS Golden Test", () => {
  const weights = { cost: 0.25, quality: 0.25, speed: 0.25, reliability: 0.25 };
  const results = scoreTopsis(SYNTHETIC_MANIFESTS, weights, 0.3);

  // Basic structure
  assert(results.length === 3, `Expected 3 results, got ${results.length}`);
  assert(results[0].rank === 1, `Rank 1 should be 1`);
  assert(results[1].rank === 2, `Rank 2 should be 2`);
  assert(results[2].rank === 3, `Rank 3 should be 3`);

  // Score range [0, 1]
  for (const r of results) {
    assert(r.total_score >= 0 && r.total_score <= 1,
      `${r.display_name} score ${r.total_score} out of range [0,1]`);
  }

  // Ranking monotonicity
  for (let i = 0; i < results.length - 1; i++) {
    assert(results[i].total_score >= results[i + 1].total_score,
      `Rank #${i+1} score ${results[i].total_score} < #${i+2} score ${results[i+1].total_score}`);
  }

  // Breakdown completeness
  for (const r of results) {
    assert("cost" in r.breakdown, `${r.display_name} missing cost`);
    assert("quality" in r.breakdown, `${r.display_name} missing quality`);
    assert("speed" in r.breakdown, `${r.display_name} missing speed`);
    assert("reliability" in r.breakdown, `${r.display_name} missing reliability`);
  }

  // Cost-priority: Cheap Fast should rank first
  const costWeights = { cost: 0.7, quality: 0.1, speed: 0.1, reliability: 0.1 };
  const costResults = scoreTopsis(SYNTHETIC_MANIFESTS, costWeights, 0.3);
  assert(costResults[0].service_id === "test/cheap-fast@1.0",
    `Cost-priority rank 1 should be Cheap Fast, got ${costResults[0].display_name}`);

  // Quality-priority: Expensive Good should rank first
  const qualityWeights = { cost: 0.1, quality: 0.7, speed: 0.1, reliability: 0.1 };
  const qualityResults = scoreTopsis(SYNTHETIC_MANIFESTS, qualityWeights, 0.3);
  assert(qualityResults[0].service_id === "test/expensive-good@1.0",
    `Quality-priority rank 1 should be Expensive Good, got ${qualityResults[0].display_name}`);
});

// ── Test 2: io_ratio Regression ─────────────────

runTest("Test 2: io_ratio Regression", () => {
  // extractPrimaryCost io_ratio behavior
  const expensiveManifest = SYNTHETIC_MANIFESTS[1]; // input=10, output=30

  const costChat = extractPrimaryCost(expensiveManifest, 0.3);
  const costRag = extractPrimaryCost(expensiveManifest, 0.8);

  assert(costChat > costRag,
    `Chat cost (${costChat}) should be greater than RAG cost (${costRag})`);

  // Exact value
  const expectedChat = 0.3 * 10 / 1_000_000 + 0.7 * 30 / 1_000_000;
  const expectedRag = 0.8 * 10 / 1_000_000 + 0.2 * 30 / 1_000_000;
  assertClose(costChat, expectedChat, 1e-12, "Chat cost Exact value");
  assertClose(costRag, expectedRag, 1e-12, "RAG cost Exact value");

  // Edge cases
  const cost0 = extractPrimaryCost(expensiveManifest, 0.0);
  const cost1 = extractPrimaryCost(expensiveManifest, 1.0);
  assertClose(cost0, 30 / 1_000_000, 1e-12, "io_ratio=0 should be pure output cost");
  assertClose(cost1, 10 / 1_000_000, 1e-12, "io_ratio=1 should be pure input cost");

  // TOPSIS ranking affected by io_ratio
  const weights = { cost: 0.5, quality: 0.2, speed: 0.2, reliability: 0.1 };
  const chatResults = scoreTopsis(SYNTHETIC_MANIFESTS, weights, 0.3);
  const ragResults = scoreTopsis(SYNTHETIC_MANIFESTS, weights, 0.8);

  // Scores should differ
  let anyDiff = false;
  for (const cr of chatResults) {
    for (const rr of ragResults) {
      if (cr.service_id === rr.service_id) {
        if (Math.abs(cr.total_score - rr.total_score) > 1e-6) {
          anyDiff = true;
        }
      }
    }
  }
  assert(anyDiff, "Scores should differ after io_ratio change");
});

// ── Test 3: Cross-language Parity ───────────────

runTest("Test 3: Cross-language Parity (with real manifests)", () => {
  // Load real manifests
  const registry = new ASMRegistry();
  const manifestDir = path.resolve(__dirname, "..", "..", "manifests");
  const count = registry.loadFromDirectory(manifestDir);

  if (count < 2) {
    console.log("  ⚠️ SKIPPED — Less than 2 manifests");
    return;
  }

  const all = registry.getAll();
  const weights = { cost: 0.3, quality: 0.3, speed: 0.2, reliability: 0.2 };

  // TOPSIS
  const topsisResults = scoreTopsis(all, weights, 0.3);

  // Output Python-parseable format (for test_scorer.py Test 3)
  console.log(`  Loaded ${count} manifests, TOPSIS ranking:`);
  for (const r of topsisResults) {
    console.log(`    #${r.rank} ${r.service_id}: score=${r.total_score.toFixed(4)}`);
  }

  // Self-verify: consecutive ranks and decreasing scores
  for (let i = 0; i < topsisResults.length; i++) {
    assert(topsisResults[i].rank === i + 1,
      `Non-consecutive rank at position ${i} rank=${topsisResults[i].rank}`);
  }
  for (let i = 0; i < topsisResults.length - 1; i++) {
    assert(topsisResults[i].total_score >= topsisResults[i + 1].total_score,
      `Non-decreasing scores: #${i+1}=${topsisResults[i].total_score} < #${i+2}=${topsisResults[i+1].total_score}`);
  }

  // Verify Weighted Average too
  const waResults = scoreServices(all, weights);
  assert(waResults.length === count,
    `Weighted Average result count ${waResults.length} != manifest count ${count}`);

  // Two methods may differ on #1, but scores should be reasonable
  for (const r of waResults) {
    assert(r.total_score >= 0 && r.total_score <= 1,
      `WA ${r.display_name} score ${r.total_score} out of range [0,1]`);
  }

  // Extra: verify parseLatency various formats
  assertClose(parseLatency("800ms"), 0.8, 1e-6, "800ms");
  assertClose(parseLatency("3s"), 3.0, 1e-6, "3s");
  assertClose(parseLatency("~15s"), 15.0, 1e-6, "~15s");
  assertClose(parseLatency("1.5s"), 1.5, 1e-6, "1.5s");
  assertClose(parseLatency("2min"), 120.0, 1e-6, "2min");
  assert(parseLatency(undefined) === Infinity, "undefined → Infinity");

  // Verify extractPrimaryQuality various scales
  const eloManifest: ASMManifest = {
    asm_version: "0.3", service_id: "t", taxonomy: "t",
    quality: { metrics: [{ name: "x", score: 1300, scale: "Elo" }] },
  };
  const q = extractPrimaryQuality(eloManifest);
  assertClose(q, (1300 - 800) / 600, 1e-6, "Elo 1300 Normalize");
});

// ── Results Summary ────────────────────────────────────

console.log(`\n${"=".repeat(60)}`);
console.log(`  Results: ${passed} passed, ${failed} failed`);
console.log(`${"=".repeat(60)}`);

process.exit(failed > 0 ? 1 : 0);
