#!/usr/bin/env node
/**
 * ASM Registry — MCP Server
 *
 * Provides Agent Service Manifest data through MCP tools.
 * Agents can query, filter, compare, and score services.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import * as fs from "fs";
import * as path from "path";

// ── Types ──────────────────────────────────────────────

export interface BillingDimension {
  dimension: string;
  unit: string;
  cost_per_unit: number;
  currency: string;
  conditions?: { when: string; cost_per_unit: number };
  tiers?: { up_to: number | string; cost_per_unit: number }[];
}

export interface QualityMetric {
  name: string;
  score: number;
  scale?: string;
  benchmark?: string;
  benchmark_url?: string;
  evaluated_at?: string;
  self_reported?: boolean;
}

export interface ASMManifest {
  asm_version: string;
  service_id: string;
  taxonomy: string;
  display_name?: string;
  provider?: { name?: string; url?: string; verified_by?: string[] };
  capabilities?: {
    description?: string;
    input_modalities?: string[];
    output_modalities?: string[];
    supported_languages?: string[];
    context_window?: number;
    max_input_size?: string;
    max_output_size?: string;
  };
  pricing?: {
    billing_dimensions?: BillingDimension[];
    free_tier?: { dimension: string; limit: number; period: string } | null;
    batch_discount?: number;
    estimated?: boolean;
  };
  quality?: {
    metrics?: QualityMetric[];
    leaderboard_rank?: {
      name: string;
      rank: number;
      total: number;
      url?: string;
      snapshot_date?: string;
    };
  };
  sla?: {
    latency_p50?: string;
    latency_p99?: string;
    throughput?: string;
    uptime?: number;
    rate_limit?: string;
    max_concurrent?: number;
    cold_start?: string;
    regions?: string[];
  };
  payment?: {
    methods?: string[];
    auth_type?: string;
    ap2_endpoint?: string;
    signup_url?: string;
  };
  // v0.3 新增字段
  updated_at?: string;
  ttl?: number;
  receipt_endpoint?: string;
  receipt_types?: Record<string, unknown>;
  verification?: {
    protocol?: string;
    public_key?: string;
    public_key_url?: string;
    receipt_schema_version?: string;
  };
  extensions?: Record<string, unknown>;
}

// ── Registry Store ─────────────────────────────────────

export class ASMRegistry {
  private manifests: Map<string, ASMManifest> = new Map();

  loadFromDirectory(dir: string): number {
    const files = fs.readdirSync(dir).filter((f) => f.endsWith(".asm.json"));
    for (const file of files) {
      const content = fs.readFileSync(path.join(dir, file), "utf-8");
      const manifest: ASMManifest = JSON.parse(content);
      this.manifests.set(manifest.service_id, manifest);
    }
    return files.length;
  }

  getAll(): ASMManifest[] {
    return Array.from(this.manifests.values());
  }

  getById(id: string): ASMManifest | undefined {
    return this.manifests.get(id);
  }

  query(params: {
    taxonomy?: string;
    max_cost?: number;
    min_quality?: number;
    max_latency_s?: number;
    input_modality?: string;
    output_modality?: string;
  }): ASMManifest[] {
    let results = this.getAll();

    if (params.taxonomy) {
      results = results.filter((m) =>
        m.taxonomy.startsWith(params.taxonomy!)
      );
    }

    if (params.input_modality) {
      results = results.filter((m) =>
        m.capabilities?.input_modalities?.includes(params.input_modality!)
      );
    }

    if (params.output_modality) {
      results = results.filter((m) =>
        m.capabilities?.output_modalities?.includes(params.output_modality!)
      );
    }

    if (params.max_cost !== undefined) {
      results = results.filter((m) => {
        const cost = extractPrimaryCost(m);
        return cost <= params.max_cost!;
      });
    }

    if (params.min_quality !== undefined) {
      results = results.filter((m) => {
        const q = extractPrimaryQuality(m);
        return q >= params.min_quality!;
      });
    }

    if (params.max_latency_s !== undefined) {
      results = results.filter((m) => {
        const lat = parseLatency(m.sla?.latency_p50);
        return lat <= params.max_latency_s!;
      });
    }

    return results;
  }

  listTaxonomies(): string[] {
    const set = new Set<string>();
    for (const m of this.manifests.values()) {
      set.add(m.taxonomy);
    }
    return Array.from(set).sort();
  }

  count(): number {
    return this.manifests.size;
  }
}

// ── Scoring helpers (mirrors scorer.py) ────────────────

export function parseLatency(s?: string): number {
  if (!s) return Infinity;
  const cleaned = s.trim().replace(/^[~<>]/, "");
  if (cleaned.endsWith("ms")) return parseFloat(cleaned) / 1000;
  if (cleaned.endsWith("min")) return parseFloat(cleaned) * 60;
  if (cleaned.endsWith("s")) return parseFloat(cleaned);
  const n = parseFloat(cleaned);
  return isNaN(n) ? Infinity : n;
}

export function extractPrimaryCost(m: ASMManifest, ioRatio: number = 0.3): number {
  const dims = m.pricing?.billing_dimensions;
  if (!dims || dims.length === 0) return 0;

  let inputCost: number | null = null;
  let outputCost: number | null = null;

  for (const d of dims) {
    let cost = d.cost_per_unit;
    if (d.unit === "per_1M") cost /= 1_000_000;
    else if (d.unit === "per_1K") cost /= 1_000;

    if (d.dimension === "input_token") inputCost = cost;
    else if (d.dimension === "output_token") outputCost = cost;
  }

  if (inputCost !== null && outputCost !== null) {
    // 可配置的 IO 比例：ioRatio * input + (1 - ioRatio) * output
    return ioRatio * inputCost + (1 - ioRatio) * outputCost;
  }

  let cost = dims[0].cost_per_unit;
  if (dims[0].unit === "per_1M") cost /= 1_000_000;
  else if (dims[0].unit === "per_1K") cost /= 1_000;
  return cost;
}

export function extractPrimaryQuality(m: ASMManifest): number {
  const metrics = m.quality?.metrics;
  if (!metrics || metrics.length === 0) return 0.5;
  const met = metrics[0];
  const score = met.score;
  const scale = met.scale || "";

  if (scale === "Elo") return Math.min(Math.max((score - 800) / 600, 0), 1);
  if (scale === "0-100") return score / 100;
  if (scale === "0-1") return score;
  if (scale === "1-5") return (score - 1) / 4;
  if (scale === "lower_is_better") return Math.max(1 - score / 50, 0);
  if (score > 1) return Math.min(score / 100, 1);
  return score;
}

export function minMaxNormalize(vals: number[], invert: boolean): number[] {
  if (vals.length === 0) return [];
  const mn = Math.min(...vals);
  const mx = Math.max(...vals);
  if (mn === mx) return vals.map(() => 1);
  if (invert) return vals.map((v) => (mx - v) / (mx - mn));
  return vals.map((v) => (v - mn) / (mx - mn));
}

export interface ScoreResult {
  service_id: string;
  display_name: string;
  taxonomy: string;
  total_score: number;
  breakdown: { cost: number; quality: number; speed: number; reliability: number };
  reasoning: string;
  rank: number;
}

export function scoreServices(
  manifests: ASMManifest[],
  weights: { cost: number; quality: number; speed: number; reliability: number }
): ScoreResult[] {
  if (manifests.length === 0) return [];

  const costs = manifests.map(extractPrimaryCost);
  const qualities = manifests.map(extractPrimaryQuality);
  const latencies = manifests.map((m) => parseLatency(m.sla?.latency_p50));
  const uptimes = manifests.map((m) => m.sla?.uptime ?? 0.5);

  const nc = minMaxNormalize(costs, true);
  const nq = minMaxNormalize(qualities, false);
  const ns = minMaxNormalize(latencies, true);
  const nu = minMaxNormalize(uptimes, false);

  const results: ScoreResult[] = manifests.map((m, i) => {
    const bd = {
      cost: Math.round(nc[i] * 10000) / 10000,
      quality: Math.round(nq[i] * 10000) / 10000,
      speed: Math.round(ns[i] * 10000) / 10000,
      reliability: Math.round(nu[i] * 10000) / 10000,
    };
    const total =
      weights.cost * bd.cost +
      weights.quality * bd.quality +
      weights.speed * bd.speed +
      weights.reliability * bd.reliability;

    const dims = [
      { name: "cost", val: weights.cost * bd.cost },
      { name: "quality", val: weights.quality * bd.quality },
      { name: "speed", val: weights.speed * bd.speed },
      { name: "reliability", val: weights.reliability * bd.reliability },
    ];
    const topDim = dims.sort((a, b) => b.val - a.val)[0].name;

    return {
      service_id: m.service_id,
      display_name: m.display_name || m.service_id,
      taxonomy: m.taxonomy,
      total_score: Math.round(total * 10000) / 10000,
      breakdown: bd,
      reasoning: `${m.display_name || m.service_id} scored ${total.toFixed(3)} (cost=${bd.cost.toFixed(2)}, quality=${bd.quality.toFixed(2)}, speed=${bd.speed.toFixed(2)}, reliability=${bd.reliability.toFixed(2)}). Strongest weighted dimension: ${topDim}.`,
      rank: 0,
    };
  });

  results.sort((a, b) => b.total_score - a.total_score);
  results.forEach((r, i) => (r.rank = i + 1));
  return results;
}

/**
 * TOPSIS (Technique for Order Preference by Similarity to Ideal Solution)
 * 
 * 与 scorer.py 的 score_topsis 完全对齐的 TypeScript 实现。
 * 步骤：
 *   1. 构建决策矩阵 (n services × 4 criteria)
 *   2. 向量归一化
 *   3. 加权
 *   4. 找到正理想解 (A+) 和负理想解 (A-)
 *   5. 计算每个服务到 A+ 和 A- 的距离
 *   6. 计算贴近度: C = d- / (d+ + d-)
 *   7. 按 C 排序（越高越好）
 */
export function scoreTopsis(
  manifests: ASMManifest[],
  weights: { cost: number; quality: number; speed: number; reliability: number },
  ioRatio: number = 0.3
): ScoreResult[] {
  if (manifests.length === 0) return [];

  const n = manifests.length;
  const numCriteria = 4;

  // Step 1: 决策矩阵 — [cost(minimize), quality(maximize), latency(minimize), uptime(maximize)]
  const isBenefit = [false, true, false, true];
  const w = [weights.cost, weights.quality, weights.speed, weights.reliability];

  const raw: number[][] = manifests.map((m) => [
    extractPrimaryCost(m, ioRatio),
    extractPrimaryQuality(m),
    parseLatency(m.sla?.latency_p50),
    m.sla?.uptime ?? 0.5,
  ]);

  // Step 2: 向量归一化
  const norm: number[][] = Array.from({ length: n }, () => Array(numCriteria).fill(0));
  for (let j = 0; j < numCriteria; j++) {
    const colSumSq = Math.sqrt(raw.reduce((sum, row) => sum + row[j] ** 2, 0));
    if (colSumSq === 0) continue;
    for (let i = 0; i < n; i++) {
      norm[i][j] = raw[i][j] / colSumSq;
    }
  }

  // Step 3: 加权归一化矩阵
  const weighted: number[][] = norm.map((row) =>
    row.map((val, j) => val * w[j])
  );

  // Step 4: 正理想解和负理想解
  const aPos: number[] = [];
  const aNeg: number[] = [];
  for (let j = 0; j < numCriteria; j++) {
    const col = weighted.map((row) => row[j]);
    if (isBenefit[j]) {
      aPos.push(Math.max(...col));
      aNeg.push(Math.min(...col));
    } else {
      aPos.push(Math.min(...col));
      aNeg.push(Math.max(...col));
    }
  }

  // Step 5: 到理想解的距离
  const dPos: number[] = [];
  const dNeg: number[] = [];
  for (let i = 0; i < n; i++) {
    const dp = Math.sqrt(weighted[i].reduce((sum, val, j) => sum + (val - aPos[j]) ** 2, 0));
    const dn = Math.sqrt(weighted[i].reduce((sum, val, j) => sum + (val - aNeg[j]) ** 2, 0));
    dPos.push(dp);
    dNeg.push(dn);
  }

  // Step 6: 贴近度系数
  const labels = ["cost", "quality", "speed", "reliability"] as const;
  const results: ScoreResult[] = manifests.map((m, i) => {
    const denom = dPos[i] + dNeg[i];
    const c = denom > 0 ? dNeg[i] / denom : 0.5;

    // 构建 breakdown（将加权归一化值转为 0-1 展示分数）
    const bd: Record<string, number> = {};
    for (let j = 0; j < numCriteria; j++) {
      const col = weighted.map((row) => row[j]);
      const vmin = Math.min(...col);
      const vmax = Math.max(...col);
      if (vmax === vmin) {
        bd[labels[j]] = 1.0;
      } else if (isBenefit[j]) {
        bd[labels[j]] = Math.round(((weighted[i][j] - vmin) / (vmax - vmin)) * 10000) / 10000;
      } else {
        bd[labels[j]] = Math.round(((vmax - weighted[i][j]) / (vmax - vmin)) * 10000) / 10000;
      }
    }

    const dims = labels.map((name, j) => ({
      name,
      val: w[j] * bd[name],
    }));
    const topDim = dims.sort((a, b) => b.val - a.val)[0].name;

    return {
      service_id: m.service_id,
      display_name: m.display_name || m.service_id,
      taxonomy: m.taxonomy,
      total_score: Math.round(c * 10000) / 10000,
      breakdown: {
        cost: bd.cost,
        quality: bd.quality,
        speed: bd.speed,
        reliability: bd.reliability,
      },
      reasoning: `${m.display_name || m.service_id} scored ${c.toFixed(3)} (cost=${bd.cost.toFixed(2)}, quality=${bd.quality.toFixed(2)}, speed=${bd.speed.toFixed(2)}, reliability=${bd.reliability.toFixed(2)}). Strongest weighted dimension: ${topDim}. [TOPSIS]`,
      rank: 0,
    };
  });

  results.sort((a, b) => b.total_score - a.total_score);
  results.forEach((r, i) => (r.rank = i + 1));
  return results;
}

// ── Format helpers ─────────────────────────────────────

export function formatManifestSummary(m: ASMManifest): string {
  const lines: string[] = [];
  lines.push(`**${m.display_name || m.service_id}**`);
  lines.push(`- Service ID: \`${m.service_id}\``);
  lines.push(`- Taxonomy: \`${m.taxonomy}\``);
  if (m.provider?.name) lines.push(`- Provider: ${m.provider.name}`);
  if (m.capabilities?.description)
    lines.push(`- Description: ${m.capabilities.description}`);

  // Pricing
  if (m.pricing?.billing_dimensions) {
    const parts = m.pricing.billing_dimensions.map(
      (d) => `${d.cost_per_unit} ${d.currency}/${d.unit} (${d.dimension})`
    );
    lines.push(`- Pricing: ${parts.join(" + ")}`);
    if (m.pricing.batch_discount)
      lines.push(
        `- Batch discount: ${(m.pricing.batch_discount * 100).toFixed(0)}% off`
      );
  }

  // Quality
  if (m.quality?.metrics && m.quality.metrics.length > 0) {
    const q = m.quality.metrics[0];
    lines.push(
      `- Quality: ${q.name}=${q.score} (${q.benchmark || "N/A"}, self_reported=${q.self_reported ?? true})`
    );
  }
  if (m.quality?.leaderboard_rank) {
    const lr = m.quality.leaderboard_rank;
    lines.push(
      `- Leaderboard: #${lr.rank}/${lr.total} on ${lr.name}`
    );
  }

  // SLA
  const sla: string[] = [];
  if (m.sla?.latency_p50) sla.push(`p50=${m.sla.latency_p50}`);
  if (m.sla?.latency_p99) sla.push(`p99=${m.sla.latency_p99}`);
  if (m.sla?.uptime) sla.push(`uptime=${(m.sla.uptime * 100).toFixed(1)}%`);
  if (m.sla?.rate_limit) sla.push(`rate=${m.sla.rate_limit}`);
  if (sla.length > 0) lines.push(`- SLA: ${sla.join(", ")}`);

  // Payment
  if (m.payment?.methods)
    lines.push(`- Payment: ${m.payment.methods.join(", ")}`);

  // v0.3 字段
  if (m.updated_at) lines.push(`- Updated at: ${m.updated_at}`);
  if (m.ttl !== undefined) lines.push(`- TTL: ${m.ttl}s`);
  if (m.receipt_endpoint) lines.push(`- Receipt endpoint: ${m.receipt_endpoint}`);
  if (m.verification) {
    const vParts: string[] = [];
    if (m.verification.protocol) vParts.push(`protocol=${m.verification.protocol}`);
    if (m.verification.public_key) vParts.push(`public_key=${m.verification.public_key.slice(0, 16)}...`);
    if (m.verification.public_key_url) vParts.push(`key_url=${m.verification.public_key_url}`);
    if (m.verification.receipt_schema_version) vParts.push(`receipt_schema=${m.verification.receipt_schema_version}`);
    if (vParts.length > 0) lines.push(`- Verification: ${vParts.join(", ")}`);
  }

  return lines.join("\n");
}

// ── Main ───────────────────────────────────────────────

async function main() {
  // Load manifests
  const registry = new ASMRegistry();
  const manifestDir = path.resolve(__dirname, "..", "..", "manifests");

  if (!fs.existsSync(manifestDir)) {
    console.error(`Manifest directory not found: ${manifestDir}`);
    process.exit(1);
  }

  const count = registry.loadFromDirectory(manifestDir);
  console.error(`ASM Registry: loaded ${count} manifests from ${manifestDir}`);

  // Create MCP Server
  const server = new McpServer({
    name: "asm-registry",
    version: "0.3.0",
  });

  // ── Tool: asm_list ──
  server.tool(
    "asm_list",
    "List all services in the ASM registry with summary info. Use this for an overview of available services. Shows receipt support status.",
    {},
    async () => {
      const all = registry.getAll();
      const lines = all.map(
        (m) => {
          const receiptsTag = m.receipt_endpoint ? " 🧾 receipts" : "";
          return `• **${m.display_name || m.service_id}** — \`${m.taxonomy}\` — ${m.provider?.name || "Unknown"}${receiptsTag}`;
        }
      );
      return {
        content: [
          {
            type: "text" as const,
            text: `# ASM Registry — ${all.length} services\n\n${lines.join("\n")}`,
          },
        ],
      };
    }
  );

  // ── Tool: asm_get ──
  server.tool(
    "asm_get",
    "Get the full ASM manifest for a specific service by its service_id. Returns complete pricing, quality, SLA, and payment information.",
    {
      service_id: z.string().describe("Service ID (e.g., 'anthropic/claude-sonnet-4@4.0')"),
    },
    async ({ service_id }) => {
      const m = registry.getById(service_id);
      if (!m) {
        return {
          content: [
            {
              type: "text" as const,
              text: `Service not found: \`${service_id}\`\n\nAvailable services:\n${registry
                .getAll()
                .map((s) => `• \`${s.service_id}\``)
                .join("\n")}`,
            },
          ],
        };
      }
      // 构建包含 v0.3 字段的详情输出
      let detail = formatManifestSummary(m);

      // v0.3 额外字段独立展示
      const v03Lines: string[] = [];
      if (m.updated_at) v03Lines.push(`- **Updated at**: ${m.updated_at}`);
      if (m.ttl !== undefined) v03Lines.push(`- **TTL**: ${m.ttl}s`);
      if (m.receipt_endpoint) v03Lines.push(`- **Receipt endpoint**: ${m.receipt_endpoint}`);
      if (m.verification) {
        v03Lines.push(`- **Verification**:`);
        if (m.verification.protocol) v03Lines.push(`  - Protocol: ${m.verification.protocol}`);
        if (m.verification.public_key) v03Lines.push(`  - Public key: \`${m.verification.public_key}\``);
        if (m.verification.public_key_url) v03Lines.push(`  - Public key URL: ${m.verification.public_key_url}`);
        if (m.verification.receipt_schema_version) v03Lines.push(`  - Receipt schema version: ${m.verification.receipt_schema_version}`);
      }
      if (v03Lines.length > 0) {
        detail += "\n\n### Signed Receipts (v0.3)\n" + v03Lines.join("\n");
      }

      detail += "\n\n<details><summary>Raw JSON</summary>\n\n```json\n" + JSON.stringify(m, null, 2) + "\n```\n</details>";

      return {
        content: [
          {
            type: "text" as const,
            text: detail,
          },
        ],
      };
    }
  );

  // ── Tool: asm_query ──
  server.tool(
    "asm_query",
    "Query the ASM registry with filters. Find services by taxonomy (category), cost, quality, latency, or modality. All filters are optional — combine them to narrow results.",
    {
      taxonomy: z
        .string()
        .optional()
        .describe("Taxonomy prefix filter (e.g., 'ai.llm', 'ai.vision.image_generation', 'ai.audio.tts')"),
      max_cost: z
        .number()
        .optional()
        .describe("Maximum cost per unit (normalized to per-1 basis)"),
      min_quality: z
        .number()
        .optional()
        .describe("Minimum quality score (0-1 normalized)"),
      max_latency_s: z
        .number()
        .optional()
        .describe("Maximum p50 latency in seconds"),
      input_modality: z
        .string()
        .optional()
        .describe("Required input modality (text, image, audio, video)"),
      output_modality: z
        .string()
        .optional()
        .describe("Required output modality (text, image, audio, video)"),
      has_receipts: z
        .boolean()
        .optional()
        .describe("If true, only return services that have a receipt_endpoint (support Signed Receipts)"),
    },
    async (params) => {
      let results = registry.query(params);
      // v0.3: 按 receipt_endpoint 过滤
      if (params.has_receipts !== undefined) {
        if (params.has_receipts) {
          results = results.filter((m) => !!m.receipt_endpoint);
        } else {
          results = results.filter((m) => !m.receipt_endpoint);
        }
      }
      if (results.length === 0) {
        return {
          content: [
            {
              type: "text" as const,
              text: "No services match the given filters.\n\nAvailable taxonomies:\n" +
                registry.listTaxonomies().map((t) => `• \`${t}\``).join("\n"),
            },
          ],
        };
      }
      const text = results.map(formatManifestSummary).join("\n\n---\n\n");
      return {
        content: [
          {
            type: "text" as const,
            text: `# Query Results — ${results.length} services found\n\n${text}`,
          },
        ],
      };
    }
  );

  // ── Tool: asm_compare ──
  server.tool(
    "asm_compare",
    "Compare 2-5 services side by side on pricing, quality, SLA, and payment. Provide service IDs to compare.",
    {
      service_ids: z
        .array(z.string())
        .min(2)
        .max(5)
        .describe("Array of service_ids to compare"),
    },
    async ({ service_ids }) => {
      const manifests: ASMManifest[] = [];
      const notFound: string[] = [];

      for (const id of service_ids) {
        const m = registry.getById(id);
        if (m) manifests.push(m);
        else notFound.push(id);
      }

      if (manifests.length < 2) {
        return {
          content: [
            {
              type: "text" as const,
              text: `Need at least 2 valid services. Not found: ${notFound.join(", ")}`,
            },
          ],
        };
      }

      // Build comparison table
      const header = ["Dimension", ...manifests.map((m) => m.display_name || m.service_id)];
      const rows: string[][] = [];

      // Taxonomy
      rows.push(["Taxonomy", ...manifests.map((m) => m.taxonomy)]);

      // Provider
      rows.push(["Provider", ...manifests.map((m) => m.provider?.name || "—")]);

      // Pricing
      rows.push([
        "Cost/unit",
        ...manifests.map((m) => {
          const c = extractPrimaryCost(m);
          return `$${c.toFixed(6)}`;
        }),
      ]);

      // Quality
      rows.push([
        "Quality (normalized)",
        ...manifests.map((m) => extractPrimaryQuality(m).toFixed(3)),
      ]);

      // Latency
      rows.push([
        "Latency p50",
        ...manifests.map((m) => m.sla?.latency_p50 || "—"),
      ]);

      // Uptime
      rows.push([
        "Uptime",
        ...manifests.map((m) =>
          m.sla?.uptime ? `${(m.sla.uptime * 100).toFixed(1)}%` : "—"
        ),
      ]);

      // Payment
      rows.push([
        "Payment",
        ...manifests.map((m) => m.payment?.methods?.join(", ") || "—"),
      ]);

      // v0.3: Receipt endpoint
      rows.push([
        "Receipt endpoint",
        ...manifests.map((m) => m.receipt_endpoint ? "✅ Yes" : "—"),
      ]);

      // v0.3: Verification protocol
      rows.push([
        "Verification",
        ...manifests.map((m) => m.verification?.protocol || "—"),
      ]);

      // Format as markdown table
      const colWidths = header.map((h, i) =>
        Math.max(h.length, ...rows.map((r) => (r[i] || "").length))
      );
      const pad = (s: string, w: number) => s.padEnd(w);
      const hLine = header.map((h, i) => pad(h, colWidths[i])).join(" | ");
      const sep = colWidths.map((w) => "-".repeat(w)).join(" | ");
      const body = rows
        .map((r) => r.map((c, i) => pad(c, colWidths[i])).join(" | "))
        .join("\n");

      let text = `# Service Comparison\n\n| ${hLine} |\n| ${sep} |\n`;
      text += body
        .split("\n")
        .map((l) => `| ${l} |`)
        .join("\n");

      if (notFound.length > 0) {
        text += `\n\n⚠️ Not found: ${notFound.join(", ")}`;
      }

      return { content: [{ type: "text" as const, text }] };
    }
  );

  // ── Tool: asm_score ──
  server.tool(
    "asm_score",
    "Score and rank services based on user preferences. Supports two methods: 'topsis' (default, multi-criteria decision analysis aligned with Python scorer) and 'weighted_average'. Also supports io_ratio for configurable input/output token cost blending.",
    {
      taxonomy: z
        .string()
        .optional()
        .describe("Taxonomy prefix to filter before scoring (e.g., 'ai.llm.chat')"),
      w_cost: z.number().min(0).max(1).default(0.3).describe("Weight for cost (lower is better). Default 0.3"),
      w_quality: z.number().min(0).max(1).default(0.3).describe("Weight for quality (higher is better). Default 0.3"),
      w_speed: z.number().min(0).max(1).default(0.2).describe("Weight for speed/latency (lower is better). Default 0.2"),
      w_reliability: z.number().min(0).max(1).default(0.2).describe("Weight for reliability/uptime (higher is better). Default 0.2"),
      method: z
        .enum(["topsis", "weighted_average"])
        .default("topsis")
        .describe("Scoring method. 'topsis' = TOPSIS multi-criteria analysis (default, aligned with Python scorer). 'weighted_average' = simple weighted average."),
      io_ratio: z
        .number()
        .min(0)
        .max(1)
        .default(0.3)
        .describe("Input/output token cost blend ratio. 0.3 = chat (default), 0.8 = RAG, 0.1 = creative writing, 0.5 = balanced."),
    },
    async ({ taxonomy, w_cost, w_quality, w_speed, w_reliability, method, io_ratio }) => {
      // Normalize weights
      const total = w_cost + w_quality + w_speed + w_reliability;
      const weights = {
        cost: w_cost / total,
        quality: w_quality / total,
        speed: w_speed / total,
        reliability: w_reliability / total,
      };

      let candidates = registry.getAll();
      if (taxonomy) {
        candidates = candidates.filter((m) => m.taxonomy.startsWith(taxonomy));
      }

      if (candidates.length === 0) {
        return {
          content: [
            {
              type: "text" as const,
              text: `No services found${taxonomy ? ` for taxonomy '${taxonomy}'` : ""}.\n\nAvailable taxonomies:\n${registry.listTaxonomies().map((t) => `• \`${t}\``).join("\n")}`,
            },
          ],
        };
      }

      const results = method === "topsis"
        ? scoreTopsis(candidates, weights, io_ratio)
        : scoreServices(candidates, weights);

      const methodLabel = method === "topsis" ? "TOPSIS" : "Weighted Average";
      let text = `# ASM Service Ranking (${methodLabel})\n\n`;
      text += `**Method**: ${methodLabel}\n`;
      text += `**Weights**: cost=${weights.cost.toFixed(2)}, quality=${weights.quality.toFixed(2)}, speed=${weights.speed.toFixed(2)}, reliability=${weights.reliability.toFixed(2)}\n`;
      text += `**IO Ratio**: ${io_ratio} (input token cost weight)\n`;
      text += `**Candidates**: ${candidates.length} services`;
      if (taxonomy) text += ` (taxonomy: \`${taxonomy}\`)`;
      text += "\n\n";

      for (const r of results) {
        const marker = r.rank === 1 ? " ⭐ RECOMMENDED" : "";
        text += `### #${r.rank} ${r.display_name}${marker}\n`;
        text += `- **Score**: ${r.total_score.toFixed(4)}\n`;
        text += `- **Breakdown**: cost=${r.breakdown.cost.toFixed(2)}, quality=${r.breakdown.quality.toFixed(2)}, speed=${r.breakdown.speed.toFixed(2)}, reliability=${r.breakdown.reliability.toFixed(2)}\n`;
        text += `- ${r.reasoning}\n`;
        text += `- Taxonomy: \`${r.taxonomy}\` | Service: \`${r.service_id}\`\n\n`;
      }

      return { content: [{ type: "text" as const, text }] };
    }
  );

  // ── Tool: asm_taxonomies ──
  server.tool(
    "asm_taxonomies",
    "List all available service taxonomies (categories) in the registry.",
    {},
    async () => {
      const taxonomies = registry.listTaxonomies();
      const grouped: Record<string, string[]> = {};
      for (const t of taxonomies) {
        const domain = t.split(".").slice(0, 2).join(".");
        if (!grouped[domain]) grouped[domain] = [];
        grouped[domain].push(t);
      }

      let text = `# ASM Taxonomies — ${taxonomies.length} categories\n\n`;
      for (const [domain, cats] of Object.entries(grouped)) {
        text += `## ${domain}\n`;
        for (const cat of cats) {
          const count = registry
            .getAll()
            .filter((m) => m.taxonomy === cat).length;
          text += `• \`${cat}\` — ${count} service(s)\n`;
        }
        text += "\n";
      }

      return { content: [{ type: "text" as const, text }] };
    }
  );

  // ── Resource: schema ──
  server.resource(
    "asm-schema",
    "asm://schema/v0.3",
    { description: "ASM v0.3 JSON Schema specification", mimeType: "application/json" },
    async () => {
      const schemaPath = path.resolve(__dirname, "..", "..", "schema", "asm-v0.3.schema.json");
      const content = fs.readFileSync(schemaPath, "utf-8");
      return { contents: [{ uri: "asm://schema/v0.3", text: content, mimeType: "application/json" }] };
    }
  );

  // ── Start server ─────────────────────────────────────

  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("ASM Registry MCP Server running on stdio");
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});
