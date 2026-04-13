#!/usr/bin/env npx tsx
/**
 * ASM Registry TypeScript 单元测试 — 3 个关键测试用例。
 *
 * 1. Golden Test:  TOPSIS 在已知合成输入下的输出
 * 2. io_ratio Test: io_ratio 参数对排名的影响
 * 3. Cross-language Parity: 与 Python scorer 输出对比
 *
 * 用法: npx tsx src/test_scorer.ts
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

// ── 测试工具 ────────────────────────────────────

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

// ── 合成测试数据 ────────────────────────────────

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

  // 基本结构
  assert(results.length === 3, `应有 3 个结果，得到 ${results.length}`);
  assert(results[0].rank === 1, `第一名 rank 应为 1`);
  assert(results[1].rank === 2, `第二名 rank 应为 2`);
  assert(results[2].rank === 3, `第三名 rank 应为 3`);

  // 分数范围 [0, 1]
  for (const r of results) {
    assert(r.total_score >= 0 && r.total_score <= 1,
      `${r.display_name} 分数 ${r.total_score} 超出 [0,1]`);
  }

  // 排名单调性
  for (let i = 0; i < results.length - 1; i++) {
    assert(results[i].total_score >= results[i + 1].total_score,
      `排名 #${i+1} 分数 ${results[i].total_score} < #${i+2} 分数 ${results[i+1].total_score}`);
  }

  // Breakdown 完整性
  for (const r of results) {
    assert("cost" in r.breakdown, `${r.display_name} 缺少 cost`);
    assert("quality" in r.breakdown, `${r.display_name} 缺少 quality`);
    assert("speed" in r.breakdown, `${r.display_name} 缺少 speed`);
    assert("reliability" in r.breakdown, `${r.display_name} 缺少 reliability`);
  }

  // 成本优先时，Cheap Fast 排第一
  const costWeights = { cost: 0.7, quality: 0.1, speed: 0.1, reliability: 0.1 };
  const costResults = scoreTopsis(SYNTHETIC_MANIFESTS, costWeights, 0.3);
  assert(costResults[0].service_id === "test/cheap-fast@1.0",
    `成本优先排名第一应是 Cheap Fast，实际是 ${costResults[0].display_name}`);

  // 质量优先时，Expensive Good 排第一
  const qualityWeights = { cost: 0.1, quality: 0.7, speed: 0.1, reliability: 0.1 };
  const qualityResults = scoreTopsis(SYNTHETIC_MANIFESTS, qualityWeights, 0.3);
  assert(qualityResults[0].service_id === "test/expensive-good@1.0",
    `质量优先排名第一应是 Expensive Good，实际是 ${qualityResults[0].display_name}`);
});

// ── Test 2: io_ratio Regression ─────────────────

runTest("Test 2: io_ratio Regression", () => {
  // extractPrimaryCost 的 io_ratio 行为
  const expensiveManifest = SYNTHETIC_MANIFESTS[1]; // input=10, output=30

  const costChat = extractPrimaryCost(expensiveManifest, 0.3);
  const costRag = extractPrimaryCost(expensiveManifest, 0.8);

  assert(costChat > costRag,
    `Chat cost (${costChat}) 应大于 RAG cost (${costRag})`);

  // 精确值
  const expectedChat = 0.3 * 10 / 1_000_000 + 0.7 * 30 / 1_000_000;
  const expectedRag = 0.8 * 10 / 1_000_000 + 0.2 * 30 / 1_000_000;
  assertClose(costChat, expectedChat, 1e-12, "Chat cost 精确值");
  assertClose(costRag, expectedRag, 1e-12, "RAG cost 精确值");

  // 边界值
  const cost0 = extractPrimaryCost(expensiveManifest, 0.0);
  const cost1 = extractPrimaryCost(expensiveManifest, 1.0);
  assertClose(cost0, 30 / 1_000_000, 1e-12, "io_ratio=0 应为纯 output cost");
  assertClose(cost1, 10 / 1_000_000, 1e-12, "io_ratio=1 应为纯 input cost");

  // TOPSIS 排名受 io_ratio 影响
  const weights = { cost: 0.5, quality: 0.2, speed: 0.2, reliability: 0.1 };
  const chatResults = scoreTopsis(SYNTHETIC_MANIFESTS, weights, 0.3);
  const ragResults = scoreTopsis(SYNTHETIC_MANIFESTS, weights, 0.8);

  // 分数应有差异
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
  assert(anyDiff, "io_ratio 变化后分数应有差异");
});

// ── Test 3: Cross-language Parity ───────────────

runTest("Test 3: Cross-language Parity (with real manifests)", () => {
  // 加载真实 manifests
  const registry = new ASMRegistry();
  const manifestDir = path.resolve(__dirname, "..", "..", "manifests");
  const count = registry.loadFromDirectory(manifestDir);

  if (count < 2) {
    console.log("  ⚠️ SKIPPED — 不足 2 个 manifest");
    return;
  }

  const all = registry.getAll();
  const weights = { cost: 0.3, quality: 0.3, speed: 0.2, reliability: 0.2 };

  // TOPSIS
  const topsisResults = scoreTopsis(all, weights, 0.3);

  // 输出 Python 可解析的格式（供 test_scorer.py 的 Test 3 使用）
  console.log(`  Loaded ${count} manifests, TOPSIS ranking:`);
  for (const r of topsisResults) {
    console.log(`    #${r.rank} ${r.service_id}: score=${r.total_score.toFixed(4)}`);
  }

  // 自验证：排名连续且分数递减
  for (let i = 0; i < topsisResults.length; i++) {
    assert(topsisResults[i].rank === i + 1,
      `排名不连续: 位置 ${i} rank=${topsisResults[i].rank}`);
  }
  for (let i = 0; i < topsisResults.length - 1; i++) {
    assert(topsisResults[i].total_score >= topsisResults[i + 1].total_score,
      `分数不递减: #${i+1}=${topsisResults[i].total_score} < #${i+2}=${topsisResults[i+1].total_score}`);
  }

  // Weighted Average 也验证一下
  const waResults = scoreServices(all, weights);
  assert(waResults.length === count,
    `Weighted Average 结果数 ${waResults.length} != manifest 数 ${count}`);

  // 两种方法的 #1 可以不同，但都应该有合理的分数
  for (const r of waResults) {
    assert(r.total_score >= 0 && r.total_score <= 1,
      `WA ${r.display_name} 分数 ${r.total_score} 超出 [0,1]`);
  }

  // 额外：验证 parseLatency 的各种格式
  assertClose(parseLatency("800ms"), 0.8, 1e-6, "800ms");
  assertClose(parseLatency("3s"), 3.0, 1e-6, "3s");
  assertClose(parseLatency("~15s"), 15.0, 1e-6, "~15s");
  assertClose(parseLatency("1.5s"), 1.5, 1e-6, "1.5s");
  assertClose(parseLatency("2min"), 120.0, 1e-6, "2min");
  assert(parseLatency(undefined) === Infinity, "undefined → Infinity");

  // 验证 extractPrimaryQuality 的各种 scale
  const eloManifest: ASMManifest = {
    asm_version: "0.3", service_id: "t", taxonomy: "t",
    quality: { metrics: [{ name: "x", score: 1300, scale: "Elo" }] },
  };
  const q = extractPrimaryQuality(eloManifest);
  assertClose(q, (1300 - 800) / 600, 1e-6, "Elo 1300 归一化");
});

// ── 结果汇总 ────────────────────────────────────

console.log(`\n${"=".repeat(60)}`);
console.log(`  结果: ${passed} passed, ${failed} failed`);
console.log(`${"=".repeat(60)}`);

process.exit(failed > 0 ? 1 : 0);
