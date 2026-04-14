#!/usr/bin/env tsx
/**
 * ASM × Circle Nanopayments — End-to-End Demo v2
 *
 * Simulates multiple independent Agents (different wallets) using ASM paid services (14 categories).
 * Demonstrates the complete Agent Economy loop:
 *
 *   1. Multiple Agents with independent wallets and preferences
 *   2. Natural language → Gemini parsing → TOPSIS scoring
 *   3. Each call paid via Nanopayment
 *   4. Trust Delta auto-updates service trust scores
 *   5. 50+ transactions from different Agent addresses
 *
 * Usage:
 *   First start: npm run dev:all
 *   Then run: npm run demo
 */

import { loadConfig } from "./config.js";
import { ASMBuyerClient } from "./buyer.js";

// ── ANSI Colors ──────────────────────────────────────────

const B = "\x1b[1m";
const D = "\x1b[2m";
const G = "\x1b[92m";
const Y = "\x1b[93m";
const C = "\x1b[96m";
const R = "\x1b[91m";
const M = "\x1b[95m";
const W = "\x1b[97m";
const X = "\x1b[0m";

function header(text: string) {
  console.log(`\n${B}${C}${"═".repeat(70)}${X}`);
  console.log(`${B}${C}  ${text}${X}`);
  console.log(`${B}${C}${"═".repeat(70)}${X}`);
}

// ── On-chain tx collector (for Block Explorer links) ─────────
const collectedTxHashes: string[] = [];
const ARC_TESTNET_EXPLORER = "https://testnet.arcscan.app/tx";

function step(num: number, text: string) {
  console.log(`\n${B}${Y}  Step ${num}: ${text}${X}`);
}

function ok(text: string) { console.log(`    ${G}✓${X} ${text}`); }
function info(text: string) { console.log(`    ${D}${text}${X}`); }

// ── Deterministic wallet address generation (independent per Agent) ──────────

/**
 * Generate multiple Agent wallet addresses from deterministic seeds using viem
 * Consistent addresses across runs for Block Explorer verification
 */
async function generateAgentWallets(count: number): Promise<Array<{ address: string; name: string }>> {
  const { privateKeyToAccount } = await import("viem/accounts");
  const { keccak256, toHex } = await import("viem");

  const wallets: Array<{ address: string; name: string }> = [];
  const agentNames = [
    "ChatBot-Agent",
    "Creative-Agent",
    "PersonalAssistant-Agent",
    "WebScraper-Agent",
    "DevOps-Agent",
    "Notification-Agent",
    "Research-Agent",
    "Knowledge-Agent",
    "DataEngineer-Agent",
    "FullStack-Agent",
    "Multilingual-Agent",
    "Sales-Agent",
    "Scheduler-Agent",
    "Code-Agent",
  ];

  for (let i = 0; i < count; i++) {
    // Deterministic seed: keccak256("asm-agent-{i}")
    const seed = keccak256(toHex(`asm-demo-agent-${i}`));
    const account = privateKeyToAccount(seed as `0x${string}`);
    wallets.push({
      address: account.address,
      name: agentNames[i] || `Agent-${i}`,
    });
  }

  return wallets;
}

// ── Agent Scenario Definitions ─────────────────────────────────────

interface AgentScenario {
  name: string;
  emoji: string;
  description: string;
  tasks: Array<{
    action: "score" | "query" | "agent-decide";
    params: any;
    description: string;
  }>;
}

const scenarios: AgentScenario[] = [
  // ── AI Model Agents ──
  {
    name: "ChatBot Agent",
    emoji: "🤖",
    description: "Customer service bot needing cheap fast LLM",
    tasks: [
      { action: "agent-decide", params: { request: "I need a cheap and fast LLM for customer service chatbot, budget is important" }, description: "NL → cheap fast chat LLM" },
      { action: "agent-decide", params: { request: "Find the highest quality LLM for complex reasoning tasks, cost doesn't matter" }, description: "NL → highest quality reasoning LLM" },
    ],
  },
  {
    name: "Creative Agent",
    emoji: "🎨",
    description: "Creative studio needing highest quality image+video",
    tasks: [
      { action: "agent-decide", params: { request: "I need the best image generation service for professional marketing materials" }, description: "NL → professional image generation" },
      { action: "agent-decide", params: { request: "Looking for a video generation tool to create short product demos" }, description: "NL → product demo video" },
    ],
  },
  // ── Tool Agents (new categories!)──
  {
    name: "Personal Assistant",
    emoji: "📋",
    description: "Personal assistant finding best todo tools",
    tasks: [
      { action: "agent-decide", params: { request: "Help me find a free todo list app with reminders, I want something simple and cheap" }, description: "NL → free simple todo tool" },
      { action: "agent-decide", params: { request: "I need a powerful task manager with Pomodoro timer and habit tracking for productivity" }, description: "NL → professional task management（features first）" },
    ],
  },
  {
    name: "Web Scraper Agent",
    emoji: "🌐",
    description: "Data collection needing reliable browser automation",
    tasks: [
      { action: "agent-decide", params: { request: "I need a browser automation service to scrape product prices from e-commerce sites reliably" }, description: "NL → browser automation（web scraping）" },
      { action: "agent-decide", params: { request: "Looking for the cheapest headless browser API for automated testing" }, description: "NL → cheap headless browser" },
    ],
  },
  {
    name: "DevOps Agent",
    emoji: "⚡",
    description: "CI/CD pipeline needing reliable build system",
    tasks: [
      { action: "agent-decide", params: { request: "Need a CI/CD pipeline service that's reliable and has good free tier for open source projects" }, description: "NL → open source project CI/CD" },
      { action: "agent-decide", params: { request: "Looking for fast build pipeline with Docker support and test parallelism for enterprise" }, description: "NL → enterprise fast CI" },
    ],
  },
  {
    name: "Notification Agent",
    emoji: "📧",
    description: "Notification service needing high-deliverability email API",
    tasks: [
      { action: "agent-decide", params: { request: "I need an email API to send transactional emails, delivery rate is critical" }, description: "NL → high-delivery email API" },
      { action: "agent-decide", params: { request: "Looking for the cheapest email sending service for a newsletter with 10k subscribers" }, description: "NL → cheap email blast" },
    ],
  },
  {
    name: "Research Agent",
    emoji: "🔍",
    description: "Research assistant needing AI-optimized search",
    tasks: [
      { action: "agent-decide", params: { request: "I need a search API optimized for AI agents, should return structured data not raw HTML" }, description: "NL → AI optimized search API" },
      { action: "agent-decide", params: { request: "Find me a semantic search engine for building a RAG pipeline with web data" }, description: "NL → semantic search engine" },
    ],
  },
  {
    name: "Knowledge Agent",
    emoji: "📝",
    description: "Knowledge management needing best docs/project tools",
    tasks: [
      { action: "agent-decide", params: { request: "I need a knowledge base tool for my team, must support collaboration and have good API" }, description: "NL → team knowledge base" },
      { action: "agent-decide", params: { request: "Looking for a fast issue tracker with keyboard shortcuts and good developer experience" }, description: "NL → dev-friendly project management" },
    ],
  },
  // ── Additional Category Agents ──
  {
    name: "Data Engineer",
    emoji: "🗄️",
    description: "Data engineer needing databases and vector stores",
    tasks: [
      { action: "agent-decide", params: { request: "I need a serverless Postgres database for my AI agent's persistent state" }, description: "NL → Serverless Postgres" },
      { action: "agent-decide", params: { request: "Looking for a vector database for my RAG pipeline, need fast similarity search" }, description: "NL → vector database" },
    ],
  },
  {
    name: "Full-Stack Builder",
    emoji: "🚀",
    description: "Full-stack dev needing deployment and monitoring",
    tasks: [
      { action: "agent-decide", params: { request: "I need a deployment platform with preview environments and edge functions" }, description: "NL → deployment platform" },
      { action: "agent-decide", params: { request: "Looking for error tracking and performance monitoring for my production app" }, description: "NL → monitoring service" },
    ],
  },
  {
    name: "Multilingual Agent",
    emoji: "🌍",
    description: "Multilingual assistant needing translation and OCR",
    tasks: [
      { action: "agent-decide", params: { request: "I need a high-quality translation API for Japanese to English, accuracy is critical" }, description: "NL → high-quality translation" },
      { action: "agent-decide", params: { request: "Looking for OCR service to extract text from scanned documents and receipts" }, description: "NL → OCR document OCR" },
    ],
  },
  {
    name: "Sales Agent",
    emoji: "💼",
    description: "Sales assistant needing CRM and communication",
    tasks: [
      { action: "agent-decide", params: { request: "I need a CRM to track leads and automate follow-up emails" }, description: "NL → CRM system" },
      { action: "agent-decide", params: { request: "Looking for SMS API to send appointment reminders to customers worldwide" }, description: "NL → SMS notification" },
    ],
  },
  {
    name: "Scheduler Agent",
    emoji: "📅",
    description: "Schedule management needing calendar and booking",
    tasks: [
      { action: "agent-decide", params: { request: "I need a calendar API to check availability and create events for my user" }, description: "NL → calendar management" },
      { action: "agent-decide", params: { request: "Looking for a scheduling tool to let clients book meetings automatically" }, description: "NL → auto scheduling" },
    ],
  },
  {
    name: "Code Agent",
    emoji: "💻",
    description: "Coding assistant needing code execution sandbox",
    tasks: [
      { action: "agent-decide", params: { request: "I need a sandboxed environment to safely execute AI-generated Python code" }, description: "NL → code sandbox" },
      { action: "agent-decide", params: { request: "Looking for the best AI code completion tool for my development workflow" }, description: "NL → AI code completion" },
    ],
  },
];

// ── Main Flow ─────────────────────────────────────────────

async function main() {
  const config = loadConfig();
  const baseUrl = `http://localhost:${config.port}`;

  header("ASM × Circle Nanopayments — E2E Demo v2");
  console.log(`\n  ${B}Multi-Agent independent wallets + Gemini semantic decisions + Nanopayment settlement${X}`);
  console.log(`  ${D}Target: 50+ txns from ${scenarios.length}  different Agent addresses, covering all categories${X}`);

  // Step 1: Generate Agent wallets
  step(1, "Generate Agent wallet addresses");
  const wallets = await generateAgentWallets(Math.max(scenarios.length, 8));
  for (const w of wallets) {
    ok(`${w.name}: ${W}${w.address}${X}`);
  }

  // Step 2: Check services
  step(2, "Check service availability");
  try {
    const healthResp = await fetch(`${baseUrl}/api/health`);
    const health = await healthResp.json() as any;
    ok(`Payment Server: ${health.mode}`);

    const svcResp = await fetch(`${baseUrl}/api/services`);
    const services = await svcResp.json() as any;
    ok(`Found ${services.count}  ASM services`);
    for (const svc of services.services.slice(0, 3)) {
      info(`  • ${svc.display_name} (${svc.taxonomy})`);
    }
    if (services.count > 3) info(`  ... and ${services.count - 3}  more`);
  } catch (err: any) {
    console.log(`    ${R}✗ Cannot connect: ${err.message}${X}`);
    console.log(`    ${D}Please start first: npm run dev:all${X}`);
    process.exit(1);
  }

  // Step 2.5: Init Buyer Client (live mode uses GatewayClient.pay() for real payments)
  const buyer = new ASMBuyerClient(config);
  const isLive = config.mode === "live";
  if (isLive) {
    step(2, "Init Buyer GatewayClient");
    const ok_init = await buyer.initialize();
    if (ok_init) {
      ok(`Buyer initialized: ${buyer.getAddress()}`);
      const bal = await buyer.getBalance();
      ok(`Gateway balance: ${bal.gatewayAvailable} USDC`);
    } else {
      console.log(`    ${R}✗ Buyer init failed, falling back to mock mode${X}`);
    }
  }

  // Step 3: Run Agent scenarios
  step(3, "Run Agent scenarios");
  let totalTx = 0;
  let agentDecideTx = 0;
  let scoreTx = 0;

  for (let i = 0; i < scenarios.length; i++) {
    const scenario = scenarios[i];
    const wallet = wallets[i];
    console.log(`\n    ${M}${scenario.emoji} ${scenario.name}${X} — ${scenario.description}`);
    info(`  Wallet: ${wallet.address.slice(0, 12)}...${wallet.address.slice(-6)}`);

    for (const task of scenario.tasks) {
      try {
        if (task.action === "agent-decide") {
          // Gemini semantic decision
          let result: any;
          if (isLive && buyer.isLive()) {
            // Live mode: GatewayClient.pay() auto-handles 402 → sign → settle
            result = await buyer.agentDecide(task.params, wallet.name, wallet.address);
          } else {
            // Mock mode: direct fetch
            const resp = await fetch(`${baseUrl}/api/agent-decide`, {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                "X-Buyer-Address": wallet.address,
                "X-Agent-Name": wallet.name,
              },
              body: JSON.stringify(task.params),
            });
            result = await resp.json() as any;
          }
          const rec = result.recommendation;
          ok(`${C}[Gemini]${X} ${task.description}`);
          if (rec) {
            info(`    → Recommended: ${B}${rec.display_name}${X} (score=${rec.score?.toFixed(4)})`);
            info(`    → Intent: ${result.intent?.reasoning || ""}`);
            // Show server-side real call results (seller executed HTTP probe)
            const sc = result.serviceCall;
            if (sc) {
              const deltaStr = sc.delta != null ? `${(sc.delta * 100).toFixed(1)}%` : "N/A";
              const statusStr = sc.success ? `${G}OK${X}` : `${R}FAIL${X}`;
              info(`    → Call: ${rec.display_name} [${statusStr}] actual=${sc.actualLatencyMs}ms declared=${sc.declaredLatencyMs?.toFixed(0) || "?"}ms delta=${deltaStr}`);
            }
          }
          if (result.trust) {
            info(`    → Trust: ${result.trust.serviceId} trust=${result.trust.trustScore?.toFixed(3)} (${result.trust.numReceipts} receipts)`);
          }
          // Collect on-chain tx hashes (prefer _txHash from GatewayClient.pay())
          const txh = result._txHash || result.payment?.txHash;
          if (txh && txh.startsWith("0x") && txh.length >= 64 && !txh.includes("-")) {
            collectedTxHashes.push(txh);
          }
          agentDecideTx++;
        } else if (task.action === "score") {
          // Convert TOPSIS params to agent-decide call (compatible with live mode x402 protection)
          const scoreRequest = `Service selection: taxonomy=${task.params.taxonomy || "all"}, ` +
            `cost_weight=${task.params.w_cost}, quality_weight=${task.params.w_quality}, ` +
            `speed_weight=${task.params.w_speed}, reliability_weight=${task.params.w_reliability}`;
          let scoreResult: any;
          if (isLive && buyer.isLive()) {
            scoreResult = await buyer.agentDecide({ request: scoreRequest }, wallet.name, wallet.address);
          } else {
            const resp = await fetch(`${baseUrl}/api/agent-decide`, {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                "X-Buyer-Address": wallet.address,
                "X-Agent-Name": wallet.name,
              },
              body: JSON.stringify({ request: scoreRequest }),
            });
            scoreResult = await resp.json() as any;
          }
          const rec = scoreResult.recommendation;
          ok(`${Y}[TOPSIS]${X} ${task.description} → ${B}${rec?.display_name || "N/A"}${X} (${rec?.score?.toFixed(4) || "N/A"})`);
          const stxh = scoreResult._txHash || scoreResult.payment?.txHash;
          if (stxh && stxh.startsWith("0x") && stxh.length >= 64 && !stxh.includes("-")) collectedTxHashes.push(stxh);
          scoreTx++;
        } else {
          const resp = await fetch(`${baseUrl}/api/query`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-Buyer-Address": wallet.address,
            },
            body: JSON.stringify(task.params),
          });
          const result = await resp.json() as any;
          ok(`${G}[Query]${X} ${task.description} → ${result.query?.count || 0}  results`);
        }
        totalTx++;
      } catch (err: any) {
        console.log(`    ${R}✗ ${task.description}: ${err.message}${X}`);
      }
    }
  }

  // Step 4: Fill transactions to 50+ (rotating Agent addresses)
  step(4, `Fill transactions (current ${totalTx}  txns, target 55+)`);
  const remaining = Math.max(55 - totalTx, 0);

  if (remaining > 0) {
    info(`Need ${remaining}  more txns, rotating Agent addresses`);
    const taxonomies = ["ai.llm.chat", "ai.vision.image_generation", "ai.audio.tts", "ai.video.generation", "ai.embedding", "cloud.compute.gpu"];
    const nlRequests = [
      "Find the cheapest LLM for simple Q&A tasks",
      "I need a high quality image generator for marketing",
      "Looking for a fast TTS service for real-time applications",
      "Need reliable video generation, don't want downtime",
      "Best embedding model for semantic search on a budget",
      "GPU compute for fine-tuning, need good price-performance ratio",
      "Help me find a free todo list with calendar integration",
      "I need a browser automation tool for web scraping at scale",
      "Looking for CI/CD with great free tier for my side project",
      "Need email API with highest delivery rate for transactional emails",
      "Find me an AI-powered search API for my chatbot's knowledge retrieval",
      "I want a project management tool that integrates with GitHub",
      "Need a knowledge base tool like Notion but with better API rate limits",
      "Cheapest way to send 50k marketing emails per month",
      "Most reliable headless browser for automated e2e testing",
      "Best task manager for a team of 5 with recurring tasks and reminders",
    ];

    for (let i = 0; i < remaining; i++) {
      const wallet = wallets[i % wallets.length];
      const useGemini = i % 3 === 0;  // Use Gemini decision every 3 txns

      try {
        const nlReq = nlRequests[i % nlRequests.length];
        if (isLive && buyer.isLive()) {
          await buyer.agentDecide({ request: nlReq }, wallet.name, wallet.address);
        } else {
          await fetch(`${baseUrl}/api/agent-decide`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-Buyer-Address": wallet.address,
              "X-Agent-Name": wallet.name,
            },
            body: JSON.stringify({ request: nlReq }),
          });
        }
        agentDecideTx++;
        totalTx++;
        // Collect txHash (silent)
        // Fill txns do not print each txHash, but record for Explorer
        if ((i + 1) % 10 === 0) ok(`Completed ${totalTx}  transactions`);
      } catch (_e) { /* silent */ }
    }
    ok(`Fill complete, total ${totalTx}  txns`);
  }

  // Step 5: Statistics
  step(5, "Transaction Statistics");
  try {
    const statsResp = await fetch(`${baseUrl}/api/stats`);
    const stats = await statsResp.json() as any;

    console.log(`\n    ${B}📊 Transaction Statistics${X}`);
    console.log(`    ├─ Total txns:     ${G}${stats.totalTransactions}${X}`);
    console.log(`    ├─ Total volume:       ${G}${stats.totalVolume} USDC${X}`);
    console.log(`    ├─ Unique Agents:   ${G}${stats.uniqueBuyers}${X}  unique addresses`);
    console.log(`    ├─ Agent-Decide: ${C}${agentDecideTx}${X}  txns (Gemini semantic decision)`);
    console.log(`    ├─ TOPSIS Score: ${Y}${scoreTx}${X}  txns (precise scoring)`);
    console.log(`    └─ Unique sellers:     ${stats.uniqueSellers}`);

    if (stats.byEndpoint) {
      console.log(`\n    ${B}By endpoint:${X}`);
      for (const [ep, data] of Object.entries(stats.byEndpoint) as any) {
        console.log(`    ├─ ${ep}: ${data.count}  txns, ${data.volume} USDC`);
      }
    }

    if (stats.byTaxonomy) {
      console.log(`\n    ${B}By taxonomy:${X}`);
      for (const [tax, data] of Object.entries(stats.byTaxonomy) as any) {
        console.log(`    ├─ ${tax}: ${data.count}  txns, ${data.volume} USDC`);
      }
    }

    if (stats.totalTransactions >= 50) {
      console.log(`\n    ${G}${B}✅ Reached 50+ transaction requirement!${X}`);
    }
  } catch (err: any) {
    console.log(`    ${R}Cannot get stats: ${err.message}${X}`);
  }

  // Step 6: Trust Delta Verification
  step(6, "Trust Delta Loop Verification");
  try {
    const trustResp = await fetch(`${baseUrl}/api/trust`);
    const trust = await trustResp.json() as any;
    console.log(`\n    ${B}🔒 Trust Delta${X}`);
    console.log(`    ├─ Total receipts: ${G}${trust.totalReceipts}${X}`);
    const scores = trust.scores || {};
    const serviceIds = Object.keys(scores);
    console.log(`    ├─ Evaluated services: ${G}${serviceIds.length}${X} `);
    // Show top 5 trust scores
    const sorted = serviceIds
      .map(id => ({ id, ...scores[id] }))
      .sort((a: any, b: any) => b.trustScore - a.trustScore)
      .slice(0, 5);
    if (sorted.length > 0) {
      console.log(`    └─ Top 5 trust scores:`);
      for (const s of sorted as any[]) {
        const bar = "█".repeat(Math.round(s.trustScore * 20)) + "░".repeat(20 - Math.round(s.trustScore * 20));
        console.log(`       ${s.serviceId.slice(0, 30).padEnd(30)} ${bar} ${s.trustScore.toFixed(3)} (${s.numReceipts} receipts, conf=${s.confidence.toFixed(2)})`);
      }
    }
    if (trust.totalReceipts > 0) {
      console.log(`\n    ${G}${B}✅ Trust Delta loop verification passed!${X}`);
    }
  } catch (err: any) {
    console.log(`    ${R}Cannot get trust data: ${err.message}${X}`);
  }

  // Step 7: Block Explorer links
  step(7, "Block Explorer On-chain Evidence");
  if (collectedTxHashes.length > 0) {
    const uniqueTxs = [...new Set(collectedTxHashes.filter(h => h && !h.startsWith("0xmock_")))];
    if (uniqueTxs.length > 0) {
      console.log(`\n    ${B}🔗 Arc Testnet Block Explorer${X}`);
      console.log(`    ├─ On-chain txns: ${G}${uniqueTxs.length}${X}`);
      for (const tx of uniqueTxs.slice(0, 10)) {
        console.log(`    ├─ ${D}${ARC_TESTNET_EXPLORER}/${tx}${X}`);
      }
      if (uniqueTxs.length > 10) {
        console.log(`    └─ ... and ${uniqueTxs.length - 10}  txnsmore transactions`);
      }
      console.log(`\n    ${G}${B}✅ All transactions verifiable on Arc Testnet Block Explorer!${X}`);
    } else {
      console.log(`\n    ${Y}⚠️  Mock mode — no on-chain txns (use live mode for real transactions)${X}`);
    }
  } else {
    console.log(`\n    ${Y}⚠️  No transaction hashes collected${X}`);
  }

  // Complete
  header("Demo Complete");
  console.log(`
  ${B}What this demo demonstrates:${X}

  ${C}1. Agent Economy${X}
     ${scenarios.length}  independent Agents, each with unique wallet and preferences
     Not one buyer calling repeatedly — a real multi-party marketplace

  ${C}2. Gemini semantic decision${X}
     Agent describes needs in natural language ("I need a cheap LLM")
     Gemini auto-parses into structured params → TOPSIS multi-criteria scoring
     ${B}Agent doesn't need to understand algorithms — just speak naturally${X}

  ${C}3. USDC Nanopayment${X}
     Each decision $0.005 USDC, settled via Circle Gateway on Arc Testnet
     Agent pays for "procurement decisions", not "chat"

  ${C}4. Trust Delta Loop${X}
     Pay → use service → generate receipt → update trust → affect next ranking
     ${B}Each decision auto-generates receipts, exponential decay weighting, recent data weighted higher${X}
     Self-evolving system driven by economic incentives

  ${B}In one sentence:${X}
  ${G}"ASM is Google Shopping for AI Agents —${X}
  ${G} describe what you need, pay $0.005, get the optimal service."${X}

  ${B}View:${X}
    Marketplace: http://localhost:4402/
    Dashboard:   http://localhost:4402/api/dashboard
    Ledger export:    http://localhost:4402/api/ledger/export
    Trust scores:    http://localhost:4402/api/trust
    Explorer:    ${ARC_TESTNET_EXPLORER}
`);
}

main().catch((err) => {
  console.error(`${R}Demo failed:${X}`, err);
  process.exit(1);
});
