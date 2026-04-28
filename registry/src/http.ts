#!/usr/bin/env node
/**
 * ASM Registry — HTTP API
 *
 * Maps MCP Server 4 core tools to REST endpoints,
 * imports from index.ts directly without duplicating logic.
 *
 * Endpoints:
 *   GET  /api/services          → asm_list
 *   GET  /api/services/:id      → asm_get
 *   POST /api/query             → asm_query
 *   POST /api/compare           → asm_compare
 *
 * Started：npx ts-node src/http.ts
 * Port: 3456 (override via PORT env var)
 */

import express, { Request, Response } from "express";
import cors from "cors";
import * as path from "path";
import * as fs from "fs";

import {
  ASMRegistry,
  ASMManifest,
  extractPrimaryCost,
  extractPrimaryQuality,
  parseLatency,
  scoreServices,
  scoreTopsis,
  pickWinner,
  formatManifestSummary,
} from "./index.js";

// ── Initialize Registry ────────────────────────────────────

const registry = new ASMRegistry();
const manifestDir = path.resolve(__dirname, "..", "..", "manifests");

if (!fs.existsSync(manifestDir)) {
  console.error(`❌ Manifest directory not found: ${manifestDir}`);
  process.exit(1);
}

const loadedCount = registry.loadFromDirectory(manifestDir);
console.log(`✅ ASM Registry: Loaded ${loadedCount}  manifests (${manifestDir})`);

// ── Create Express App ──────────────────────────────────

const app = express();
const PORT = parseInt(process.env.PORT || "3456", 10);

// Middleware
app.use(cors());
app.use(express.json());

// ── Health Check ───────────────────────────────────────────

app.get("/api/health", (_req: Request, res: Response) => {
  res.json({
    status: "ok",
    service: "asm-registry",
    version: "0.3.0",
    manifests_loaded: registry.count(),
    timestamp: new Date().toISOString(),
  });
});

// ── GET /api/services → asm_list ───────────────────────

app.get("/api/services", (_req: Request, res: Response) => {
  const all = registry.getAll();
  const services = all.map((m) => ({
    service_id: m.service_id,
    display_name: m.display_name || m.service_id,
    taxonomy: m.taxonomy,
    provider: m.provider?.name || "Unknown",
    has_receipts: !!m.receipt_endpoint,
    cost_per_unit: extractPrimaryCost(m),
    quality: extractPrimaryQuality(m),
    latency_p50: m.sla?.latency_p50 || null,
    uptime: m.sla?.uptime || null,
  }));

  res.json({
    count: services.length,
    services,
  });
});

// ── GET /api/services/:id → asm_get ────────────────────

app.get("/api/services/:id(*)", (req: Request, res: Response) => {
  // service_id may contain / and @, e.g. "anthropic/claude-sonnet-4@4.0"
  const rawId = req.params.id;
  const serviceId = Array.isArray(rawId) ? rawId.join("/") : rawId;
  const manifest = registry.getById(serviceId);

  if (!manifest) {
    res.status(404).json({
      error: "not_found",
      message: `Service not found: ${serviceId}`,
      available_services: registry.getAll().map((s) => s.service_id),
    });
    return;
  }

  res.json({
    service_id: manifest.service_id,
    manifest,
    summary: formatManifestSummary(manifest),
    computed: {
      cost_per_unit: extractPrimaryCost(manifest),
      quality_normalized: extractPrimaryQuality(manifest),
      latency_seconds: parseLatency(manifest.sla?.latency_p50),
    },
  });
});

// ── POST /api/query → asm_query ────────────────────────

app.post("/api/query", (req: Request, res: Response) => {
  const {
    taxonomy,
    max_cost,
    min_quality,
    max_latency_s,
    input_modality,
    output_modality,
    has_receipts,
    sort_by,
    limit,
  } = req.body;

  // Basic filtering (reuse registry.query)
  let results = registry.query({
    taxonomy,
    max_cost,
    min_quality,
    max_latency_s,
    input_modality,
    output_modality,
  });

  // v0.3: Receipt filtering
  if (has_receipts !== undefined) {
    results = results.filter((m) =>
      has_receipts ? !!m.receipt_endpoint : !m.receipt_endpoint
    );
  }

  // Sort
  if (sort_by) {
    const sortFns: Record<string, (a: ASMManifest, b: ASMManifest) => number> = {
      cost: (a, b) => extractPrimaryCost(a) - extractPrimaryCost(b),
      quality: (a, b) => extractPrimaryQuality(b) - extractPrimaryQuality(a),
      latency: (a, b) =>
        parseLatency(a.sla?.latency_p50) - parseLatency(b.sla?.latency_p50),
      uptime: (a, b) => (b.sla?.uptime || 0) - (a.sla?.uptime || 0),
    };
    if (sortFns[sort_by]) {
      results.sort(sortFns[sort_by]);
    }
  }

  // Limit count
  const maxResults = typeof limit === "number" && limit > 0 ? limit : results.length;
  results = results.slice(0, maxResults);

  // Build response
  const services = results.map((m) => ({
    service_id: m.service_id,
    display_name: m.display_name || m.service_id,
    taxonomy: m.taxonomy,
    provider: m.provider?.name || "Unknown",
    cost_per_unit: extractPrimaryCost(m),
    quality: extractPrimaryQuality(m),
    latency_p50: m.sla?.latency_p50 || null,
    uptime: m.sla?.uptime || null,
    has_receipts: !!m.receipt_endpoint,
  }));

  res.json({
    query: { taxonomy, max_cost, min_quality, max_latency_s, input_modality, output_modality, has_receipts },
    count: services.length,
    services,
  });
});

// ── POST /api/compare → asm_compare ────────────────────

app.post("/api/compare", (req: Request, res: Response) => {
  const { service_ids } = req.body;

  if (!Array.isArray(service_ids) || service_ids.length < 2) {
    res.status(400).json({
      error: "invalid_request",
      message: "Provide an array of at least 2 service_ids in the request body.",
    });
    return;
  }

  if (service_ids.length > 5) {
    res.status(400).json({
      error: "invalid_request",
      message: "Maximum 5 services can be compared at once.",
    });
    return;
  }

  const manifests: ASMManifest[] = [];
  const notFound: string[] = [];

  for (const id of service_ids) {
    const m = registry.getById(id);
    if (m) manifests.push(m);
    else notFound.push(id);
  }

  if (manifests.length < 2) {
    res.status(404).json({
      error: "insufficient_services",
      message: `Need at least 2 valid services to compare. Not found: ${notFound.join(", ")}`,
      available_services: registry.getAll().map((s) => s.service_id),
    });
    return;
  }

  // Build comparison data
  const comparison = manifests.map((m) => ({
    service_id: m.service_id,
    display_name: m.display_name || m.service_id,
    taxonomy: m.taxonomy,
    provider: m.provider?.name || "Unknown",
    pricing: {
      cost_per_unit: extractPrimaryCost(m),
      billing_dimensions: m.pricing?.billing_dimensions || [],
      free_tier: m.pricing?.free_tier || null,
      batch_discount: m.pricing?.batch_discount || null,
    },
    quality: {
      normalized_score: extractPrimaryQuality(m),
      metrics: m.quality?.metrics || [],
      leaderboard_rank: m.quality?.leaderboard_rank || null,
    },
    sla: {
      latency_p50: m.sla?.latency_p50 || null,
      latency_p50_seconds: parseLatency(m.sla?.latency_p50),
      latency_p99: m.sla?.latency_p99 || null,
      uptime: m.sla?.uptime || null,
      rate_limit: m.sla?.rate_limit || null,
      regions: m.sla?.regions || [],
    },
    capabilities: {
      input_modalities: m.capabilities?.input_modalities || [],
      output_modalities: m.capabilities?.output_modalities || [],
      context_window: m.capabilities?.context_window || null,
      supported_languages: m.capabilities?.supported_languages || [],
    },
    payment: {
      methods: m.payment?.methods || [],
      auth_type: m.payment?.auth_type || null,
    },
    receipts: {
      has_receipts: !!m.receipt_endpoint,
      receipt_endpoint: m.receipt_endpoint || null,
      verification_protocol: m.verification?.protocol || null,
    },
  }));

  // Use TOPSIS for composite scoring (aligned with Python scorer)
  const ioRatio = req.body.io_ratio ?? 0.3;
  const method = req.body.method ?? "topsis";
  const weights = {
    cost: 0.25,
    quality: 0.25,
    speed: 0.25,
    reliability: 0.25,
  };
  const scores = method === "topsis"
    ? scoreTopsis(manifests, weights, ioRatio)
    : scoreServices(manifests, weights);

  res.json({
    compared: manifests.length,
    not_found: notFound.length > 0 ? notFound : undefined,
    comparison,
    ranking: scores.map((s) => ({
      service_id: s.service_id,
      display_name: s.display_name,
      rank: s.rank,
      total_score: s.total_score,
      breakdown: s.breakdown,
    })),
  });
});

// ── POST /api/score → Scoring & Ranking ──────────────────────

app.post("/api/score", (req: Request, res: Response) => {
  const {
    taxonomy,
    w_cost = 0.3,
    w_quality = 0.3,
    w_speed = 0.2,
    w_reliability = 0.2,
    method = "topsis",
    io_ratio = 0.3,
  } = req.body;

  // NormalizeWeight
  const total = w_cost + w_quality + w_speed + w_reliability;
  const weights = {
    cost: w_cost / total,
    quality: w_quality / total,
    speed: w_speed / total,
    reliability: w_reliability / total,
  };

  let candidates = registry.getAll();
  if (taxonomy) {
    candidates = candidates.filter((m: ASMManifest) =>
      m.taxonomy.startsWith(taxonomy)
    );
  }

  if (candidates.length === 0) {
    res.json({
      method,
      io_ratio,
      weights,
      count: 0,
      ranking: [],
      available_taxonomies: registry.listTaxonomies(),
    });
    return;
  }

  const results = method === "topsis"
    ? scoreTopsis(candidates, weights, io_ratio)
    : scoreServices(candidates, weights);

  // v2 contract: emit a `pick` block the benchmark/frontend consume directly.
  // Only meaningful when scoring a single taxonomy's pool (≥ 1 candidate).
  // Always included when candidates exist — harmless for legacy callers
  // because the old `ranking` field is preserved below.
  let pick;
  try {
    pick = pickWinner(candidates, weights, io_ratio);
  } catch {
    pick = undefined;
  }

  res.json({
    method: method === "topsis" ? "TOPSIS" : "Weighted Average",
    io_ratio,
    weights,
    taxonomy: taxonomy || null,
    count: results.length,
    // New v2 fields — UI/benchmark contract
    pick: pick
      ? {
          taxonomy: pick.taxonomy,
          candidates: pick.candidates,
          winner: pick.winner,
          reasoning: pick.reasoning,
        }
      : null,
    // Legacy ranking (kept for back-compat with existing dashboard)
    ranking: results.map((r) => ({
      rank: r.rank,
      service_id: r.service_id,
      display_name: r.display_name,
      taxonomy: r.taxonomy,
      total_score: r.total_score,
      breakdown: r.breakdown,
      reasoning: r.reasoning,
    })),
  });
});

// ── Start Server ─────────────────────────────────────────

app.listen(PORT, () => {
  console.log(`\n🚀 ASM Registry HTTP API started`);
  console.log(`   Address: http://localhost:${PORT}`);
  console.log(`   Endpoints:`);
  console.log(`     GET  /api/health           — Health Check`);
  console.log(`     GET  /api/services          — List all services`);
  console.log(`     GET  /api/services/:id      — Get service details`);
  console.log(`     POST /api/query             — Query services by criteria`);
  console.log(`     POST /api/compare           — Compare multiple services`);
  console.log(`     POST /api/score             — Scoring & Ranking（TOPSIS/weighted average）`);
  console.log(`\n   Loaded ${loadedCount}  ASM manifests\n`);
});
