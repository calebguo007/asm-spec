/**
 * ASM × Circle Nanopayments — Seller Server
 *
 * Wraps ASM Registry API as paid endpoints using x402 protocol + Circle Gateway Nanopayments.
 *
 * Paid endpoints (require USDC nanopayment):
 *   POST /api/score  → $0.005 USDC（TOPSIS scoring）
 *   POST /api/query  → $0.002 USDC（Conditional query）
 *
 * Free endpoints:
 *   GET  /api/services → Service discovery (free, lowering barriers)
 *   GET  /api/health   → Health check
 *   GET  /api/ledger   → Transaction ledger
 *   GET  /api/stats    → Transaction stats
 *   GET  /api/trust    → Trust scores
 *   GET  /api/dashboard → Dashboard
 *   GET  /api/events   → SSE real-time event stream
 *
 * Two operating modes:
 *   - live: Uses Circle Gateway + BatchFacilitatorClient + GatewayEvmScheme
 *   - mock: Simulates x402 payment flow for development and demos
 *
 * Important: all routes must be registered after x402 middleware, or Express will skip it.
 */

import express, { Request, Response, NextFunction } from "express";
import * as fs from "fs";
import * as path from "path";
import cors from "cors";
import helmet from "helmet";
import rateLimit from "express-rate-limit";
import { loadConfig } from "./config.js";
import { ledger } from "./ledger.js";
import { trustStore } from "./trust-delta.js";
import { PaymentRecord } from "./types.js";
import { parseAgentIntent } from "./gemini-agent.js";
import { fileURLToPath } from "url";
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const config = loadConfig();

// ── Express App ───────────────────────────────────────

const app = express();

// ── CORS: allow Vercel frontend + local dev + configurable origins ──────────
const CORS_ALLOW_ALL = process.env.CORS_ALLOW_ALL === "true";
const ALLOWED_ORIGINS = (
  process.env.CORS_ORIGINS ||
  "http://localhost:4173,http://localhost:3000,http://localhost:5173,https://*.vercel.app"
)
  .split(",")
  .map((s) => s.trim());
app.use(
  cors({
    origin: (origin, callback) => {
      // Allow all origins if CORS_ALLOW_ALL is set (useful for demos/public APIs)
      if (CORS_ALLOW_ALL) return callback(null, true);
      // Allow non-browser requests (mobile apps, curl, server-to-server)
      if (!origin) return callback(null, true);
      const allowed = ALLOWED_ORIGINS.some((o) =>
        o.startsWith("*.") ? origin.endsWith(o.slice(1)) : o === origin,
      );
      if (allowed) return callback(null, true);
      callback(new Error(`CORS blocked: ${origin}`));
    },
    credentials: true,
  }),
);
app.use(helmet({ contentSecurityPolicy: false }));
app.use(express.json());

// ── API Key guard for mutating endpoints ─────────────
const API_KEY = process.env.API_KEY || "";
function requireApiKey(req: Request, res: Response, next: NextFunction) {
  if (!API_KEY) return next(); // skip if not configured (local dev)
  const provided = req.headers["x-api-key"] || req.query.api_key;
  if (provided === API_KEY) return next();
  res.status(401).json({ error: "unauthorized", message: "Missing or invalid X-API-Key header" });
}

// Rate limiting: 100 requests per minute per IP for paid endpoints
const apiLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: 100,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: "rate_limited", message: "Too many requests, please try again later" },
});

// ── Global State ───────────────────────────────────────────

let x402Initialized = false;
let gatewayInstance: any = null;

// ── Real service deviation simulation (replacing uniform jitter) ────────────────
// Different dimensions have different deviation characteristics:
//   - cost: usually accurate (stable pricing), occasional promotions/increases
//   - quality: moderate variance (model updates, load effects)
//   - latency: highest variance (network jitter, queue delays)
//   - uptime: usually high, occasional failures (long-tail distribution)
const DIMENSION_PROFILES: Record<string, { mean: number; stddev: number; outlierProb: number; outlierScale: number }> = {
  cost:    { mean: 1.00, stddev: 0.02, outlierProb: 0.05, outlierScale: 1.15 },  // 5% chance of price increase 15%
  quality: { mean: 0.97, stddev: 0.06, outlierProb: 0.10, outlierScale: 0.80 },  // 10% chance of quality drop 20%
  latency: { mean: 1.15, stddev: 0.20, outlierProb: 0.15, outlierScale: 2.50 },  // 15% chance of latency spike 2.5x
  uptime:  { mean: 0.995, stddev: 0.005, outlierProb: 0.03, outlierScale: 0.85 }, // 3% chance of availability drop
};

// Box-Muller normal distribution
function normalRandom(mean: number, stddev: number): number {
  const u1 = Math.random();
  const u2 = Math.random();
  const z = Math.sqrt(-2.0 * Math.log(u1)) * Math.cos(2.0 * Math.PI * u2);
  return mean + z * stddev;
}

// Generate deterministic deviation seed for a service (consistent deviation pattern)
function serviceJitter(serviceId: string, dimension: string): number {
  const profile = DIMENSION_PROFILES[dimension] || { mean: 1.0, stddev: 0.05, outlierProb: 0.1, outlierScale: 1.5 };
  // Whether to trigger outlier (simulating real-world long-tail events)
  if (Math.random() < profile.outlierProb) {
    return profile.outlierScale;
  }
  // Normal distribution deviation
  const jitter = normalRandom(profile.mean, profile.stddev);
  return Math.max(0.5, Math.min(3.0, jitter)); // Clamp to reasonable range
}

// ── SSE Event Broadcast System ──────────────────────────────────

interface SSEClient {
  id: string;
  res: Response;
}

const sseClients: SSEClient[] = [];

function broadcastEvent(event: {
  type: 'connect' | 'browse' | 'decide' | 'pay' | 'disconnect';
  agentAddress: string;
  agentName?: string;
  data: any;
}) {
  const payload = `data: ${JSON.stringify({ ...event, timestamp: new Date().toISOString() })}\n\n`;
  for (let i = sseClients.length - 1; i >= 0; i--) {
    try {
      sseClients[i].res.write(payload);
    } catch (_e) {
      sseClients.splice(i, 1);
    }
  }
}

// ── Registry pick helper ─────────────────────────────────────
//
// Route every paid /api/score call to the WINNER's onchain_address.
// We ask the registry (which is already authoritative for scoring) and
// cache per-request (body.taxonomy) so the x402 DynamicPayTo resolver
// and the later handler don't hit the registry twice.

type RegistryPick = {
  taxonomy: string;
  winner: { service_id: string; display_name: string; onchain_address?: string };
  candidates: unknown[];
  reasoning: string;
};

// Short-TTL cache so DynamicPayTo + handler share one pick per request.
// Key = taxonomy; TTL 10s covers a benchmark burst without stale data.
const pickCache = new Map<string, { pick: RegistryPick; ts: number }>();
const PICK_TTL_MS = 10_000;

async function pickWinnerForTaxonomy(
  taxonomy: string | undefined,
): Promise<RegistryPick | null> {
  if (!taxonomy) return null;
  const now = Date.now();
  const cached = pickCache.get(taxonomy);
  if (cached && now - cached.ts < PICK_TTL_MS) return cached.pick;

  try {
    const data = await proxyToRegistry("/api/score", "POST", { taxonomy });
    const pick = data?.pick as RegistryPick | undefined;
    if (!pick?.winner?.onchain_address) return null;
    pickCache.set(taxonomy, { pick, ts: now });
    return pick;
  } catch (err: unknown) {
    console.warn(`⚠️  pickWinnerForTaxonomy(${taxonomy}) failed:`, err instanceof Error ? err.message : err);
    return null;
  }
}

// ── x402 Payment Middleware Init ──────────────────────────────

async function initX402(): Promise<boolean> {
  if (config.mode !== "live") {
    console.warn("⚠️  Mock mode — skipping x402 init");
    return false;
  }

  try {
    const { createGatewayMiddleware } = await import("@circle-fin/x402-batching/server");
    const rawGateway = createGatewayMiddleware({ sellerAddress: config.sellerAddress });

    // Wrap `.require(price)` to add diagnostic logging: when Circle Gateway
    // rejects verify/settle, the middleware responds with JSON body
    // `{ error, reason }`. We intercept res.end/write to log the reason so
    // we can see exactly why Circle rejected the payment.
    gatewayInstance = {
      ...rawGateway,
      require: (price: string) => {
        const inner = rawGateway.require(price);
        return async (req: any, res: any, next: any) => {
          const origEnd = res.end.bind(res);
          let captured = "";
          res.end = function (chunk?: any, ...rest: any[]) {
            if (chunk) {
              try {
                captured += typeof chunk === "string" ? chunk : Buffer.isBuffer(chunk) ? chunk.toString("utf-8") : String(chunk);
              } catch (_e) { /* ignore */ }
            }
            if (res.statusCode >= 400) {
              console.log(`\n🔴 [x402] ${req.method} ${req.url} → ${res.statusCode}`);
              console.log(`   Body: ${captured.slice(0, 800)}`);
              const incoming = (req.headers["payment-signature"] as string | undefined);
              if (incoming) {
                try {
                  const decoded = JSON.parse(Buffer.from(incoming, "base64").toString("utf-8"));
                  console.log(`   PayerAddr:  ${decoded?.payload?.authorization?.from || decoded?.payload?.from || "?"}`);
                  console.log(`   PayTo:      ${decoded?.accepted?.payTo || "?"}`);
                  console.log(`   Network:    ${decoded?.accepted?.network || "?"}`);
                  console.log(`   Amount:     ${decoded?.accepted?.amount || "?"}`);
                  console.log(`   VerifyingContract: ${decoded?.accepted?.extra?.verifyingContract || "?"}`);
                  console.log(`   validAfter: ${decoded?.payload?.authorization?.validAfter || "?"}`);
                  console.log(`   validBefore:${decoded?.payload?.authorization?.validBefore || "?"}`);
                } catch (_e) { /* ignore */ }
              }
            }
            return origEnd(chunk, ...rest);
          };
          return inner(req, res, next);
        };
      },
    };

    console.log("✅ x402 payment middleware initialized");
    console.log(`   Seller: ${config.sellerAddress}`);
    console.log(`   Network: ${config.network} (${config.chainName})`);
    console.log(`   Routes: POST /api/score, POST /api/query, POST /api/agent-decide`);
    x402Initialized = true;
    return true;
  } catch (err: unknown) {
    console.warn("⚠️  x402 init failed, falling back to mock mode");
    console.warn(`   Error: ${(err instanceof Error ? err.message : String(err))}`);
    return false;
  }
}

// ── Mock Payment Middleware (dev mode) ─────────────────────────

function mockPaymentMiddleware(price: string) {
  return async (req: Request, _res: Response, next: NextFunction) => {
    const buyerAddress = req.headers["x-buyer-address"] as string
      || `0x${crypto.randomUUID().replace(/-/g, "").slice(0, 40)}`;
    const paymentId = crypto.randomUUID();

    // Pre-select winner so the ledger records who actually received the money,
    // making mock-mode funds-flow match what live mode will produce.
    const pick = await pickWinnerForTaxonomy(req.body?.taxonomy);
    const receiver = pick?.winner?.onchain_address ?? config.sellerAddress;

    const record: PaymentRecord = {
      paymentId,
      buyerAddress,
      sellerAddress: receiver,
      amount: price.replace("$", ""),
      endpoint: req.path,
      taxonomy: req.body?.taxonomy,
      chain: config.chainName,
      network: config.network,
      timestamp: new Date().toISOString(),
      status: "settled",
      txHash: `0xmock_${paymentId.slice(0, 16)}`,
    };
    ledger.record(record);

    (req as any).payment = {
      payerAddress: buyerAddress,
      amount: price,
      paymentId,
      txHash: record.txHash,
      recipientAddress: receiver,
    };
    // Attach pick for the handler to surface in the response body.
    (req as any).pick = pick;
    next();
  };
}

// ── Decode x402 PAYMENT-RESPONSE header ──────────────────

function decodePaymentResponse(res: Response): { transaction?: string; payer?: string; network?: string } | null {
  // x402 middleware sets PAYMENT-RESPONSE header after settlement
  // Value is base64-encoded JSON: { success, payer, transaction, network }
  // Try multiple header name variants (Express normalizes to lowercase)
  const headerNames = [
    "payment-response", "PAYMENT-RESPONSE", "Payment-Response",
    "x-payment-response", "X-Payment-Response",
    "x402-payment-response", "X402-Payment-Response",
  ];
  let raw: string | undefined;
  for (const name of headerNames) {
    const val = res.getHeader(name) as string | undefined;
    if (val) { raw = val; break; }
  }

  // Also scan all response headers for any payment-related header
  if (!raw) {
    const allHeaders = res.getHeaders();
    for (const [key, val] of Object.entries(allHeaders)) {
      if (key.toLowerCase().includes("payment") && typeof val === "string" && val.length > 10) {
        raw = val;
        break;
      }
    }
  }

  if (!raw) return null;

  // Try multiple decoding strategies
  const decoders: Array<() => any> = [
    // Strategy 1: base64 → JSON
    () => JSON.parse(Buffer.from(raw!, "base64").toString("utf-8")),
    // Strategy 2: plain JSON
    () => JSON.parse(raw!),
    // Strategy 3: URL-encoded base64
    () => JSON.parse(Buffer.from(decodeURIComponent(raw!), "base64").toString("utf-8")),
    // Strategy 4: double base64
    () => JSON.parse(Buffer.from(Buffer.from(raw!, "base64").toString("utf-8"), "base64").toString("utf-8")),
  ];

  for (const decoder of decoders) {
    try {
      const result = decoder();
      if (result && typeof result === "object") {
        return result;
      }
    } catch (_e) { /* try next strategy */ }
  }

  return null;
}

// ── Payment recording hook (records to ledger in live mode) ───────────
//
// Key timing issue: x402 middleware workflow is
//   intercept → validate → next() → handler executes res.json() → buffer response
//   → settlement → set PAYMENT-RESPONSE header → release response
//
// So inside res.json() hook, PAYMENT-RESPONSE header does not exist yet.
// Solution:
//   1. res.json hook: capture taxonomy etc. into temp vars
//   2. res.on("finish"): after response fully sent (x402 has set headers), decode and fill txHash

function recordPayment(endpoint: string, price: string) {
  return (req: Request, res: Response, next: NextFunction) => {
    // Temp storage: populated in res.json, consumed in finish
    let capturedTaxonomy: string | undefined;
//     let capturedBody: any;  // unused

    const origJson = res.json.bind(res);
    (res as any).json = function(body: any) {
      if (x402Initialized) {
        // Capture taxonomy (available during handler execution)
        capturedTaxonomy = req.body?.taxonomy
          || body?.intent?.taxonomy
          || body?.scoring?.ranking?.[0]?.taxonomy
          || undefined;
        // capturedBody = body;  // unused
      }
      return origJson(body);
    };

    // Record after response fully sent (x402 has completed settlement and set headers)
    res.on("finish", async () => {
      if (!x402Initialized) return;

      // Decode settlement info from x402 PAYMENT-RESPONSE header
      const settlement = decodePaymentResponse(res);
      // Prefer X-Buyer-Address header (Agent identity address)
      const buyerAddr = req.headers["x-buyer-address"] as string
        || settlement?.payer
        || "unknown";

      // Ledger's sellerAddress should match where the x402 middleware
      // routed funds — i.e. the winner's onchain_address (dynamic payTo).
      // We resolve via the same pick cache used by dynamicScorePayTo.
      const pick = await pickWinnerForTaxonomy(capturedTaxonomy);
      const receiver = pick?.winner?.onchain_address ?? config.sellerAddress;

      const record: PaymentRecord = {
        paymentId: crypto.randomUUID(),
        buyerAddress: buyerAddr,
        sellerAddress: receiver,
        amount: price.replace("$", ""),
        endpoint,
        taxonomy: capturedTaxonomy,
        chain: config.chainName,
        network: config.network,
        timestamp: new Date().toISOString(),
        status: "settled",
        txHash: settlement?.transaction,
      };
      ledger.record(record);
    });

    next();
  };
}

// ── Proxy to ASM Registry ────────────────────────────────

async function proxyToRegistry(path: string, method: string = "GET", body?: any): Promise<any> {
  const url = `${config.asmRegistryUrl}${path}`;
  const options: RequestInit = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  if (body && method !== "GET") {
    options.body = JSON.stringify(body);
  }
  const resp = await fetch(url, options);
  if (!resp.ok) {
    throw new Error(`Registry API error: ${resp.status} ${resp.statusText}`);
  }
  return resp.json();
}

// ══════════════════════════════════════════════════════════
// Register all routes (called after x402 middleware)
// ══════════════════════════════════════════════════════════

function registerRoutes() {
  // ── Marketplace Home ───────────────────────────────────

  app.get("/", (_req: Request, res: Response) => {
    const htmlPath = path.resolve(__dirname, "marketplace.html");
    if (fs.existsSync(htmlPath)) {
      res.setHeader("Content-Type", "text/html");
      res.send(fs.readFileSync(htmlPath, "utf-8"));
    } else {
      res.redirect("/api/dashboard");
    }
  });

  app.get("/benchmark", (_req: Request, res: Response) => {
    res.setHeader("Content-Type", "text/html");
    const htmlPath = path.resolve(__dirname, "benchmark.html");
    try {
      const html = fs.readFileSync(htmlPath, "utf-8");
      res.send(html);
    } catch (_e) {
      res.send("<h1>Benchmark HTML not found</h1><p>Expected at: " + htmlPath + "</p>");
    }
  });

  app.get("/assets/benchmark/:file", (req: Request, res: Response) => {
    const fileName = path.basename(req.params.file);
    const assetPath = path.resolve(__dirname, "assets", "benchmark", fileName);
    if (!assetPath.startsWith(path.resolve(__dirname, "assets", "benchmark"))) {
      res.status(400).send("Invalid asset path");
      return;
    }
    if (!fs.existsSync(assetPath)) {
      res.status(404).send("Benchmark asset not found");
      return;
    }
    res.sendFile(assetPath);
  });

  app.get("/benchmark-results/sample-for-frontend.json", (_req: Request, res: Response) => {
    const snapshotPath = path.resolve(__dirname, "..", "benchmark-results", "sample-for-frontend.json");
    if (!fs.existsSync(snapshotPath)) {
      res.status(404).json({ error: "benchmark_snapshot_not_found" });
      return;
    }
    res.setHeader("Content-Type", "application/json");
    res.send(fs.readFileSync(snapshotPath, "utf-8"));
  });

  app.get("/workbench", (_req: Request, res: Response) => {
    res.redirect("/api/dashboard");
  });

  // ── SSE Event Stream (free) ─────────────────────────────────
  app.get("/api/events", (req: Request, res: Response) => {
    res.setHeader("Content-Type", "text/event-stream");
    res.setHeader("Cache-Control", "no-cache");
    res.setHeader("Connection", "keep-alive");
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.flushHeaders();

    const clientId = crypto.randomUUID();
    const client: SSEClient = { id: clientId, res };
    sseClients.push(client);

    console.log(`📡 SSE client connected: ${clientId} (total: ${sseClients.length})`);

    // Send welcome event
    res.write(`data: ${JSON.stringify({ type: "welcome", clientId, connectedClients: sseClients.length, timestamp: new Date().toISOString() })}\n\n`);

    req.on("close", () => {
      const idx = sseClients.findIndex(c => c.id === clientId);
      if (idx !== -1) sseClients.splice(idx, 1);
      console.log(`📡 SSE client disconnected: ${clientId} (total: ${sseClients.length})`);
    });
  });

  // ── Health check（free） ───────────────────────────────────
  app.get("/api/health", (_req: Request, res: Response) => {
    res.json({
      status: "ok",
      service: "asm-payments",
      version: "0.2.0",
      mode: x402Initialized ? "live (x402 + Circle Gateway)" : "mock",
      chain: config.chainName,
      network: config.network,
      sellerAddress: config.sellerAddress,
      pricing: { score: config.scorePrice, query: config.queryPrice },
      ledger: { totalTransactions: ledger.count() },
      trust: { totalReceipts: trustStore.getTotalReceiptCount() },
      sseClients: sseClients.length,
      timestamp: new Date().toISOString(),
    });
  });

  // ── Service List (free) ──────────────────────────────────
  app.get("/api/services", async (req: Request, res: Response) => {
    try {
      const data = await proxyToRegistry("/api/services", "GET");

      // If Agent address present, broadcast browse event
      const agentAddr = req.headers["x-buyer-address"] as string;
      if (agentAddr) {
        broadcastEvent({
          type: "browse",
          agentAddress: agentAddr,
          agentName: req.headers["x-agent-name"] as string,
          data: { action: "list_services", count: data.count },
        });
      }

      res.json(data);
    } catch (err: unknown) {
      res.status(502).json({ error: "registry_unavailable", message: (err instanceof Error ? err.message : String(err)) });
    }
  });

  // ── Scoring & Ranking (paid) ──────────────────────────────────
  const scoreMiddleware = config.mode === "mock"
    ? mockPaymentMiddleware(config.scorePrice)
    : gatewayInstance.require(config.scorePrice);

  app.post("/api/score", apiLimiter, requireApiKey, scoreMiddleware, async (req: Request, res: Response) => {
    try {
      const data = await proxyToRegistry("/api/score", "POST", req.body);
      // live mode: settlement info decoded from PAYMENT-RESPONSE header by recordPayment hook
      // mock mode: payment attached by mockPaymentMiddleware
      const settlement = (req as any).settlement;
      const payment = (req as any).payment;

      // Pick is either attached by mockPaymentMiddleware (mock mode) or
      // freshly resolved here (live mode). Used both for the `recipient`
      // field in payment info and to be echoed back to the client.
      const pick = (req as any).pick
        ?? await pickWinnerForTaxonomy(req.body?.taxonomy);
      const recipient = pick?.winner?.onchain_address ?? config.sellerAddress;

      const paymentInfo = (settlement || payment) ? {
        paymentId: payment?.paymentId || crypto.randomUUID(),
        amount: config.scorePrice,
        payer: req.headers["x-buyer-address"] as string || settlement?.payer || payment?.payerAddress || "unknown",
        recipient,
        txHash: settlement?.transaction || payment?.txHash,
        chain: config.chainName,
        network: config.network,
      } : undefined;

      // Broadcast decision event
      const agentAddr = req.headers["x-buyer-address"] as string || settlement?.payer || payment?.payerAddress || "unknown";
      broadcastEvent({
        type: "decide",
        agentAddress: agentAddr,
        agentName: req.headers["x-agent-name"] as string,
        data: {
          action: "score",
          taxonomy: req.body?.taxonomy,
          weights: { w_cost: req.body?.w_cost, w_quality: req.body?.w_quality, w_speed: req.body?.w_speed, w_reliability: req.body?.w_reliability },
          ranking: data.ranking?.slice(0, 3)?.map((s: {display_name: string; total_score: number}) => ({ display_name: s.display_name, score: s.total_score })),
          winner: data.ranking?.[0]?.display_name,
          winnerAddress: recipient,
          amount: config.scorePrice,
          txHash: paymentInfo?.txHash,
        },
      });

      // Trust Delta: Generate receipts for top services (using real deviation model)
      const topSvc = data.ranking?.[0];
      if (topSvc) {
        const now = Date.now() / 1000;
        const sid = topSvc.service_id;
        trustStore.addReceipt(
          {
            serviceId: sid,
            timestamp: now,
            actualCostPerUnit: (topSvc.breakdown?.cost ?? 0.5) * serviceJitter(sid, "cost"),
            actualQualityScore: (topSvc.breakdown?.quality ?? 0.5) * serviceJitter(sid, "quality"),
            actualLatencySeconds: (topSvc.breakdown?.speed ?? 0.5) * serviceJitter(sid, "latency"),
            actualUptime: Math.min((topSvc.breakdown?.reliability ?? 0.5) * serviceJitter(sid, "uptime"), 1.0),
          },
          {
            serviceId: sid,
            displayName: topSvc.display_name,
            costPerUnit: topSvc.breakdown?.cost ?? 0.5,
            qualityScore: topSvc.breakdown?.quality ?? 0.5,
            latencySeconds: topSvc.breakdown?.speed ?? 0.5,
            uptime: topSvc.breakdown?.reliability ?? 0.5,
          }
        );
      }

      res.json({
        payment: paymentInfo,
        scoring: data,
        receipt: {
          id: crypto.randomUUID(),
          timestamp: new Date().toISOString(),
          amount: config.scorePrice,
          chain: config.chainName,
          network: config.network,
        },
      });
    } catch (err: unknown) {
      res.status(502).json({ error: "registry_unavailable", message: (err instanceof Error ? err.message : String(err)) });
    }
  });

  // ── Conditional query（paid） ──────────────────────────────────
  const queryMiddleware = config.mode === "mock"
    ? mockPaymentMiddleware(config.queryPrice)
    : gatewayInstance.require(config.queryPrice);

  app.post("/api/query", apiLimiter, requireApiKey, queryMiddleware, async (req: Request, res: Response) => {
    try {
      const data = await proxyToRegistry("/api/query", "POST", req.body);
      const settlement = (req as any).settlement;
      const payment = (req as any).payment;

      const paymentInfo = (settlement || payment) ? {
        paymentId: payment?.paymentId || crypto.randomUUID(),
        amount: config.queryPrice,
        payer: req.headers["x-buyer-address"] as string || settlement?.payer || payment?.payerAddress || "unknown",
        txHash: settlement?.transaction || payment?.txHash,
        chain: config.chainName,
        network: config.network,
      } : undefined;

      // Broadcast query event
      const agentAddr = req.headers["x-buyer-address"] as string || settlement?.payer || payment?.payerAddress || "unknown";
      broadcastEvent({
        type: "browse",
        agentAddress: agentAddr,
        agentName: req.headers["x-agent-name"] as string,
        data: { action: "query", filters: req.body, resultCount: data.count, amount: config.queryPrice },
      });

      res.json({
        payment: paymentInfo,
        query: data,
        receipt: {
          id: crypto.randomUUID(),
          timestamp: new Date().toISOString(),
          amount: config.queryPrice,
          chain: config.chainName,
          network: config.network,
        },
      });
    } catch (err: unknown) {
      res.status(502).json({ error: "registry_unavailable", message: (err instanceof Error ? err.message : String(err)) });
    }
  });

  // ── Transaction ledger（free） ──────────────────────────────────
  app.get("/api/ledger", (_req: Request, res: Response) => {
    res.json({ count: ledger.count(), recent: ledger.getRecent(50) });
  });

  // ── Transaction stats（free） ──────────────────────────────────
  app.get("/api/stats", (_req: Request, res: Response) => {
    res.json(ledger.getStats());
  });

  // ── Trust scores（free） ──────────────────────────────────
  app.get("/api/trust", (_req: Request, res: Response) => {
    res.json({
      totalReceipts: trustStore.getTotalReceiptCount(),
      scores: trustStore.getAllScores(),
    });
  });

  // ── Export Ledger (free) ──────────────────────────────────
  app.get("/api/ledger/export", (_req: Request, res: Response) => {
    res.setHeader("Content-Type", "application/json");
    res.setHeader("Content-Disposition",
      `attachment; filename=asm-payments-ledger-${new Date().toISOString().slice(0, 10)}.json`);
    res.send(ledger.exportJSON());
  });

  // ── Agent Semantic Decision (paid — Gemini + TOPSIS + Trust) ──
  const agentMiddleware = config.mode === "mock"
    ? mockPaymentMiddleware(config.scorePrice)
    : gatewayInstance.require(config.scorePrice);

  app.post("/api/agent-decide", apiLimiter, requireApiKey, agentMiddleware, async (req: Request, res: Response) => {
    const startTime = Date.now();
    try {
      const { request: agentRequest, gemini_api_key } = req.body;

      if (!agentRequest || typeof agentRequest !== "string") {
        res.status(400).json({
          error: "invalid_request",
          message: "Please provide a 'request' field describing your service needs (natural language)",
          example: { request: "I need a cheap and fast LLM for translation" },
        });
        return;
      }

      const settlement = (req as any).settlement;
      const payment = (req as any).payment;
      const agentAddr = req.headers["x-buyer-address"] as string || settlement?.payer || payment?.payerAddress || "unknown";
      const agentName = req.headers["x-agent-name"] as string;

      // Broadcast: Agent starting decision
      broadcastEvent({
        type: "browse",
        agentAddress: agentAddr,
        agentName,
        data: { action: "agent_decide_start", request: agentRequest },
      });

      // Step 1: Gemini parses intent
      const intent = await parseAgentIntent(agentRequest, gemini_api_key);

      // Step 2: Call ASM TOPSIS scoring
      const scoreParams = {
        taxonomy: intent.taxonomy,
        w_cost: intent.weights.w_cost,
        w_quality: intent.weights.w_quality,
        w_speed: intent.weights.w_speed,
        w_reliability: intent.weights.w_reliability,
        method: "topsis",
        io_ratio: intent.io_ratio,
      };
      const scoring = await proxyToRegistry("/api/score", "POST", scoreParams);

      // Step 3: Build recommendations
      const topService = scoring.ranking?.[0];

      // Step 3.5: Call selected service → get real latency (not random jitter)
      // Real scenario: Agent calls Top1 service API after getting recommendation
      // Using HTTP probe to measure real network latency as Trust Delta actual data source
      let serviceCallResult: { actualLatencyMs: number; success: boolean } | null = null;
      if (topService) {
        const callStart = Date.now();
        try {
          const svcEndpoint = topService.api_endpoint || topService.endpoint;
          if (svcEndpoint && typeof svcEndpoint === "string" && svcEndpoint.startsWith("http")) {
            // Has real endpoint → HEAD request probe latency
            const controller = new AbortController();
            const timeout = setTimeout(() => controller.abort(), 3000);
            try {
              await fetch(svcEndpoint, { method: "HEAD", signal: controller.signal });
            } catch (_e) { /* Timeout/unreachable also records latency */ }
            clearTimeout(timeout);
          } else {
            // No real endpoint → simulate based on declared latency + real network jitter
            const declaredMs = (topService.breakdown?.speed ?? 0.5) * 1000;
            const jitterMs = (Math.random() - 0.3) * declaredMs * 0.8;
            await new Promise(r => setTimeout(r, Math.max(20, declaredMs * 0.1 + jitterMs)));
          }
          serviceCallResult = { actualLatencyMs: Date.now() - callStart, success: true };
        } catch (_e) {
          serviceCallResult = { actualLatencyMs: Date.now() - callStart, success: false };
        }
      }

      const latencyMs = Date.now() - startTime;

      // Step 4: Trust Delta loop — generate receipts for recommended services and update trust scores
      let trustUpdate = undefined;
      if (topService) {
        const now = Date.now() / 1000;
        const declared = {
          serviceId: topService.service_id,
          displayName: topService.display_name,
          costPerUnit: topService.breakdown?.cost ?? 0.5,
          qualityScore: topService.breakdown?.quality ?? 0.5,
          latencySeconds: topService.breakdown?.speed ?? 0.5,
          uptime: topService.breakdown?.reliability ?? 0.5,
        };
        // Actual results: latency from real HTTP probe, other dimensions from deviation model
        const sid = topService.service_id;
        const actualLatency = serviceCallResult?.actualLatencyMs
          ? serviceCallResult.actualLatencyMs / 1000  // ms → seconds
          : declared.latencySeconds * serviceJitter(sid, "latency");
        const receipt = {
          serviceId: sid,
          timestamp: now,
          actualCostPerUnit: declared.costPerUnit * serviceJitter(sid, "cost"),
          actualQualityScore: declared.qualityScore * serviceJitter(sid, "quality"),
          actualLatencySeconds: actualLatency,
          actualUptime: serviceCallResult?.success === false
            ? Math.min(declared.uptime * 0.85, 1.0)  // Call failed → availability decrease
            : Math.min(declared.uptime * serviceJitter(sid, "uptime"), 1.0),
        };
        trustUpdate = trustStore.addReceipt(receipt, declared);
      }

      // Broadcast: decision complete (after trust is computed)
      broadcastEvent({
        type: "decide",
        agentAddress: agentAddr,
        agentName,
        data: {
          action: "agent_decide",
          request: agentRequest,
          intent: { taxonomy: intent.taxonomy, weights: intent.weights, reasoning: intent.reasoning },
          ranking: scoring.ranking?.slice(0, 5)?.map((s: {display_name: string; total_score: number; asm_score?: number; trust_score?: number; taxonomy?: string; breakdown?: Record<string, number>}) => ({
            display_name: s.display_name,
            score: s.total_score,
            taxonomy: s.taxonomy,
            breakdown: s.breakdown,
          })),
          winner: topService?.display_name,
          winnerTaxonomy: topService?.taxonomy,
          amount: config.scorePrice,
          txHash: settlement?.transaction || payment?.txHash,
          latencyMs,
          serviceCall: serviceCallResult ? {
            actualLatencyMs: serviceCallResult.actualLatencyMs,
            declaredLatencyMs: topService ? (topService.breakdown?.speed ?? 0.5) * 1000 : null,
            success: serviceCallResult.success,
          } : undefined,
          trust: trustUpdate ? {
            serviceId: trustUpdate.serviceId,
            trustScore: trustUpdate.trustScore,
            confidence: trustUpdate.confidence,
            numReceipts: trustUpdate.numReceipts,
          } : undefined,
        },
      });

      res.json({
        request: agentRequest,
        intent: {
          taxonomy: intent.taxonomy,
          weights: intent.weights,
          constraints: intent.constraints,
          io_ratio: intent.io_ratio,
          reasoning: intent.reasoning,
        },
        scoring: {
          method: scoring.method,
          count: scoring.count,
          ranking: scoring.ranking?.slice(0, 5),  // Top 5
        },
        recommendation: topService ? {
          service_id: topService.service_id,
          display_name: topService.display_name,
          score: topService.total_score,
          reason: `${topService.display_name} composite score ${topService.total_score?.toFixed(4)}，` +
            `in  ${scoring.count} candidates, ranked #1.` +
            `Decision basis: ${intent.reasoning}`,
        } : null,
        trust: trustUpdate ? {
          serviceId: trustUpdate.serviceId,
          trustScore: trustUpdate.trustScore,
          confidence: trustUpdate.confidence,
          numReceipts: trustUpdate.numReceipts,
        } : undefined,
        serviceCall: serviceCallResult ? {
          actualLatencyMs: serviceCallResult.actualLatencyMs,
          success: serviceCallResult.success,
          declaredLatencyMs: topService ? (topService.breakdown?.speed ?? 0.5) * 1000 : null,
          delta: topService && serviceCallResult.actualLatencyMs
            ? Math.abs((topService.breakdown?.speed ?? 0.5) * 1000 - serviceCallResult.actualLatencyMs) / ((topService.breakdown?.speed ?? 0.5) * 1000)
            : null,
        } : undefined,
        payment: (settlement || payment) ? {
          paymentId: payment?.paymentId || crypto.randomUUID(),
          amount: config.scorePrice,
          payer: req.headers["x-buyer-address"] as string || settlement?.payer || payment?.payerAddress || "unknown",
          txHash: settlement?.transaction || payment?.txHash,
          chain: config.chainName,
          network: config.network,
        } : undefined,
        latencyMs,
      });
    } catch (err: unknown) {
      res.status(500).json({ error: "agent_decide_failed", message: (err instanceof Error ? err.message : String(err)) });
    }
  });

  // ── Dashboard Page (free) ─────────────────────────────
  app.get("/api/dashboard", (_req: Request, res: Response) => {
    res.setHeader("Content-Type", "text/html");
    const htmlPath = path.resolve(__dirname, "dashboard.html");
    try {
      const html = fs.readFileSync(htmlPath, "utf-8");
      res.send(html);
    } catch (_e) {
      res.send("<h1>Dashboard HTML not found</h1><p>Expected at: " + htmlPath + "</p>");
    }
  });

  console.log("   Route registration complete");
}

// ══════════════════════════════════════════════════════════
// Start
// ══════════════════════════════════════════════════════════

async function main() {
  // 1. Initialize x402 first (mount payment middleware)
  await initX402();

  // 2. Then register all routes (ensure x402 middleware comes first)
  registerRoutes();

  // 3. Start server
  app.listen(config.port, () => {
    console.log(`\n🚀 ASM Payment Server started`);
    console.log(`   Address: http://localhost:${config.port}`);
    console.log(`   Mode: ${x402Initialized ? "🟢 LIVE (x402 + Circle Gateway)" : "🟡 MOCK (simulated payments)"}`);
    console.log(`   Chain:   ${config.chainName} (${config.network})`);
    console.log(`\n   Paid endpoints:`);
    console.log(`     POST /api/score   — ${config.scorePrice} USDC`);
    console.log(`     POST /api/query   — ${config.queryPrice} USDC`);
    console.log(`     POST /api/agent-decide — ${config.scorePrice} USDC (Gemini + TOPSIS + Trust Delta)`);
    console.log(`\n   Free endpoints:`);
    console.log(`     GET  /api/health    — Health check`);
    console.log(`     GET  /api/services  — Service list`);
    console.log(`     GET  /api/ledger    — Transaction ledger`);
    console.log(`     GET  /api/stats     — Transaction stats`);
    console.log(`     GET  /api/trust     — Trust scores`);
    console.log(`     GET  /api/events    — SSE real-time event stream`);
    console.log(`     GET  /api/dashboard — Dashboard`);
    console.log(`     GET  /benchmark     — Benchmark showcase`);
    console.log(`     GET  /workbench     — Workbench shortcut`);
    console.log(`\n   Depends on: ASM Registry → ${config.asmRegistryUrl}`);
    console.log("");
  });
}

main().catch((err) => {
  console.error("❌ Startup failed:", err);
  process.exit(1);
});

export { app };
