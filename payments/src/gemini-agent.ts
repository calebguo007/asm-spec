/**
 * ASM × Gemini — Agent Semantic Decision Layer
 *
 * Uses Gemini to convert natural language needs into ASM multi-criteria decision parameters.
 * This is not "chat" — it's the Agent's "procurement brain":
 *
 *   1. Agent describes needs in natural language ("I need a cheap TTS service")
 *   2. Gemini extracts structured params (taxonomy, weights, constraints)
 *   3. ASM TOPSIS scoring + Trust Delta adjustment
 *   4. Returns optimal service recommendation + decision rationale
 *
 * Uses Gemini Free Tier (gemini-2.5-flash, no credit card needed)
 */

import { loadConfig } from "./config.js";

// ── Gemini Request/Response Types ──────────────────────────────

interface GeminiRequest {
  contents: Array<{
    parts: Array<{ text: string }>;
  }>;
  generationConfig?: {
    temperature?: number;
    maxOutputTokens?: number;
    responseMimeType?: string;
  };
}

interface ParsedIntent {
  taxonomy: string | null;
  weights: {
    w_cost: number;
    w_quality: number;
    w_speed: number;
    w_reliability: number;
  };
  constraints: {
    max_cost?: number;
    min_quality?: number;
    max_latency_s?: number;
    input_modality?: string;
    output_modality?: string;
  };
  io_ratio: number;
  reasoning: string;
}

interface AgentDecision {
  /** Original natural language request */
  request: string;
  /** Gemini-parsed intent */
  intent: ParsedIntent;
  /** ASM TOPSIS scoring result */
  ranking: Array<{
    rank: number;
    service_id: string;
    display_name: string;
    total_score: number;
    breakdown: Record<string, number>;
  }>;
  /** Final recommendation */
  recommendation: {
    service_id: string;
    display_name: string;
    score: number;
    reason: string;
  };
  /** Payment info */
  payment: {
    amount: string;
    chain: string;
    network: string;
  };
  /** Processing time */
  latencyMs: number;
}

// ── Gemini API Client ──────────────────────────────────

const GEMINI_MODEL = "gemini-2.5-flash";
const GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models";

const SYSTEM_PROMPT = `You are an AI service procurement engine. Your job is to parse a natural language request from an AI Agent and extract structured parameters for a multi-criteria service selection system called ASM (Agent Service Manifest).

You must output ONLY valid JSON with this exact schema:
{
  "taxonomy": string or null,  // Service category. Must be one of:
  // AI Models: "ai.llm.chat", "ai.vision.image_generation", "ai.video.generation", "ai.audio.tts", "ai.audio.stt", "ai.llm.embedding", "infra.compute.gpu"
  // Tools: "tool.productivity.todo", "tool.productivity.knowledge", "tool.productivity.project", "tool.automation.browser", "tool.devops.ci", "tool.communication.email", "tool.data.search"
  // Use null for cross-category search
  "weights": {
    "w_cost": number,      // 0-1, importance of low cost
    "w_quality": number,   // 0-1, importance of high quality
    "w_speed": number,     // 0-1, importance of low latency
    "w_reliability": number // 0-1, importance of high uptime
  },
  "constraints": {
    "max_cost": number or null,       // max USD per unit
    "min_quality": number or null,    // min quality score 0-1
    "max_latency_s": number or null,  // max latency in seconds
    "input_modality": string or null, // "text", "image", "audio"
    "output_modality": string or null // "text", "image", "audio", "video"
  },
  "io_ratio": number,  // 0-1, ratio of input to output tokens (for LLMs)
  "reasoning": string   // Brief explanation of how you interpreted the request
}

Rules:
- Weights MUST sum to 1.0
- If the user emphasizes "cheap" or "budget", increase w_cost
- If the user emphasizes "best" or "quality", increase w_quality
- If the user emphasizes "fast" or "real-time", increase w_speed
- If the user emphasizes "reliable" or "stable", increase w_reliability
- If no preference is clear, use balanced weights (0.25 each)
- Extract taxonomy from context clues (e.g., "translate" → "ai.nlp.translation", "generate image" → "ai.vision.image_generation")
- io_ratio: high for input-heavy tasks (RAG, summarization), low for output-heavy (generation)`;

/**
 * Call Gemini API to parse Agent intent
 */
export async function parseAgentIntent(
  naturalLanguageRequest: string,
  geminiApiKey?: string
): Promise<ParsedIntent> {
  const apiKey = geminiApiKey || process.env.GEMINI_API_KEY;

  if (!apiKey) {
    // No API Key → using rule engine fallback
    console.log("⚠️  No Gemini API Key, using rule engine to parse intent");
    return ruleBasedParse(naturalLanguageRequest);
  }

  try {
    const url = `${GEMINI_API_BASE}/${GEMINI_MODEL}:generateContent?key=${apiKey}`;

    const body: GeminiRequest = {
      contents: [
        {
          parts: [
            { text: `${SYSTEM_PROMPT}\n\nAgent request: "${naturalLanguageRequest}"\n\nOutput JSON only:` },
          ],
        },
      ],
      generationConfig: {
        temperature: 0.1,
        maxOutputTokens: 500,
        responseMimeType: "application/json",
      },
    };

    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!resp.ok) {
      const errText = await resp.text();
      console.warn(`⚠️  Gemini API error (${resp.status}): ${errText.slice(0, 200)}`);
      return ruleBasedParse(naturalLanguageRequest);
    }

    const data = await resp.json() as any;
    const text = data?.candidates?.[0]?.content?.parts?.[0]?.text;

    if (!text) {
      console.warn("⚠️  Gemini returned empty content, using rule engine");
      return ruleBasedParse(naturalLanguageRequest);
    }

    // Parse JSON
    const parsed = JSON.parse(text);
    return normalizeIntent(parsed);
  } catch (err: any) {
    console.warn(`⚠️  Gemini call failed: ${err.message}，using rule engine`);
    return ruleBasedParse(naturalLanguageRequest);
  }
}

/**
 * Rule engine fallback (no LLM needed)
 * Extracts intent via keyword matching
 */
function ruleBasedParse(request: string): ParsedIntent {
  const lower = request.toLowerCase();

  // Detect taxonomy (covering 14 categories)
  let taxonomy: string | null = null;

  // AI Models
  // Specific categories first (more precise matching takes priority)
  // AI — Translation (must be before llm.chat since "translate" could match both)
  if (/\b(translat(e|ion|or|ing)?|deepl|locali[sz](e|ation)?|interpret(er|ing)?|multilingual|japanese.*english|english.*chinese)\b/.test(lower) && !/\b(llm|gpt|claude)\b/.test(lower)) {
    taxonomy = "ai.nlp.translation";
  } else if (/\b(ocr|recognize text|scan.*document|extract.*text.*image|receipt.*scan)\b/.test(lower)) {
    taxonomy = "ai.vision.ocr";
  } else if (/\b(sandbox|sandboxed|safe.*execut|e2b|code.*run|isolated.*env|execut.*code|run.*code.*safe)\b/.test(lower)) {
    taxonomy = "infra.compute.sandbox";
  } else if (/\b(code.*complet|copilot|cursor|ai.*code|code.*assist|codewhisperer)\b/.test(lower)) {
    taxonomy = "ai.code.completion";

  // Scraping vs Browser automation (scraping is more specific)
  } else if (/\b(scrape|crawl|firecrawl|jina|extract.*web|web.*data)\b/.test(lower) && !/\b(automat|test|selenium)\b/.test(lower)) {
    taxonomy = "tool.data.scraping";

  // Deployment vs CI/CD (deployment is more specific)
  } else if (/\b(deploy(ment)?|hosting|go.*live|publish|vercel|fly\.io|netlify|railway|render|platform)\b/.test(lower) && !/\b(ci|cd|pipeline|build)\b/.test(lower)) {
    taxonomy = "tool.devops.deployment";

  // Now general AI models
  } else if (/\b(llm|chat|gpt|claude|gemini|summariz|writ|write|convers|reason|answer)\b/.test(lower)) {
    taxonomy = "ai.llm.chat";
  } else if (/\b(image|imag|draw|picture|photo|dall|midjourney|flux|imagen)\b/.test(lower)) {
    taxonomy = "ai.vision.image_generation";
  } else if (/\b(video|video|film|clip|sora|veo|kling)\b/.test(lower)) {
    taxonomy = "ai.video.generation";
  } else if (/\b(tts|speech|voice|voice|read aloud|speak|elevenlabs)\b/.test(lower)) {
    taxonomy = "ai.audio.tts";
  } else if (/\b(stt|transcri|dictation|dictation|whisper)\b/.test(lower)) {
    taxonomy = "ai.audio.stt";
  } else if (/\b(embed(?!ding)|embedding.*model|rag.*embed)\b/.test(lower) && !/\b(database|db|store|pinecone|qdrant)\b/.test(lower)) {
    taxonomy = "ai.llm.embedding";
  } else if (/\b(gpu|compute|compute|train|train|inference)\b/.test(lower)) {
    taxonomy = "infra.compute.gpu";

  // Tools — Productivity
  } else if (/\b(todo|task|todo|remind|remind|checklist|task management)\b/.test(lower)) {
    taxonomy = "tool.productivity.todo";
  } else if (/\b(note|wiki|knowledge base|docs|notion|obsidian|knowledge)\b/.test(lower)) {
    taxonomy = "tool.productivity.knowledge";
  } else if (/\b(project|issue|jira|linear|kanban|kanban|sprint|backlog)\b/.test(lower)) {
    taxonomy = "tool.productivity.project";

  // Tools — Browser Automation
  } else if (/\b(browser|browser|scrape|crawler|crawl|automat|selenium|playwright|puppeteer|webpage)\b/.test(lower)) {
    taxonomy = "tool.automation.browser";

  // Tools — DevOps / CI
  } else if (/\b(ci[\s/]?cd|build.*pipeline|ci.*pipeline|github.?action|circleci|jenkins|travis|gitlab.*ci|continuous.*integr)\b/.test(lower)) {
    taxonomy = "tool.devops.ci";

  // Tools — Communication
  } else if (/\b(email|email|mail|send.*mail|notify|notify|newsletter)\b/.test(lower)) {
    taxonomy = "tool.communication.email";

  // Tools — Data/Search
  } else if (/\b(search|web.*search|tavily|exa|retriev|lookup|find.*info|find.*data)\b/.test(lower)) {
    taxonomy = "tool.data.search";

  // Tools — Communication/chat
  } else if (/\b(slack|discord|chat|chat|message|im|workspace)\b/.test(lower)) {
    taxonomy = "tool.communication.chat";
  } else if (/\b(sms|sms|text.*message|twilio|whatsapp)\b/.test(lower)) {
    taxonomy = "tool.communication.sms";

  // Infrastructure — Database
  // Vector DB must be checked before postgres (both match "database")
  } else if (/\b(vector.*(?:db|database|store)|pinecone|qdrant|weaviate|milvus|chroma|similarity.*search)\b/.test(lower)) {
    taxonomy = "infra.database.vector";
  } else if (/\b(postgres|sql|database|supabase|neon|relational|mysql|sqlite)\b/.test(lower)) {
    taxonomy = "infra.database.postgres";
  } else if (/\b(redis|cache|kv|key.?value|session|memcache)\b/.test(lower)) {
    taxonomy = "infra.database.kv";

  // Infrastructure — Storage/Network
  } else if (/\b(storage|storage|s3|r2|blob|object.*store|bucket)\b/.test(lower)) {
    taxonomy = "infra.storage.object";
  } else if (/\b(dns|cdn|cloudflare|domain|domain)\b/.test(lower)) {
    taxonomy = "infra.network.dns";
  } else if (/\b(auth|auth|login|oauth|clerk|identity|mfa)\b/.test(lower)) {
    taxonomy = "infra.auth.identity";
  } else if (/\b(secret|secret|env|environment.*var|vault)\b/.test(lower)) {
    taxonomy = "infra.security.secrets";
  } else if (/\b(queue|message queue|message.*queue|qstash|pubsub)\b/.test(lower)) {
    taxonomy = "infra.messaging.queue";

  // Tools — Deploy/Monitor

  } else if (/\b(monitor(?:ing)?|sentry|error.*track|alert|observ|apm|performance.*monitor)\b/.test(lower)) {
    taxonomy = "tool.devops.monitoring";
  } else if (/\b(log|log|logging|betterstack)\b/.test(lower)) {
    taxonomy = "tool.devops.logging";

  // Tools — Productivity Extended
  } else if (/\b(calendar|calendar|event|schedule|schedule|scheduling|booking|booking)\b/.test(lower)) {
    taxonomy = "tool.productivity.calendar";
  } else if (/\b(spreadsheet|spreadsheet|sheet|airtable|excel)\b/.test(lower)) {
    taxonomy = "tool.productivity.spreadsheet";
  } else if (/\b(doc|document|docs|google.*doc|word)\b/.test(lower)) {
    taxonomy = "tool.productivity.document";
  } else if (/\b(form|form|survey|survey|typeform|feedback)\b/.test(lower)) {
    taxonomy = "tool.productivity.forms";

  // Tools — Business
  } else if (/\b(crm|customer|customer|lead|sales|hubspot|pipeline)\b/.test(lower)) {
    taxonomy = "tool.business.crm";
  } else if (/\b(pay|payment|stripe|checkout|invoice|billing)\b/.test(lower)) {
    taxonomy = "tool.payment.processing";

  // Tools — Data Processing

  } else if (/\b(map|map|geocod|location|direction|places)\b/.test(lower)) {
    taxonomy = "tool.data.geolocation";
  } else if (/\b(weather|weather|forecast|temperature)\b/.test(lower)) {
    taxonomy = "tool.data.weather";
  } else if (/\b(analytic|analytics|posthog|mixpanel|track.*event)\b/.test(lower)) {
    taxonomy = "tool.data.analytics";
  } else if (/\b(convert|convert|pdf|format|cloudconvert)\b/.test(lower)) {
    taxonomy = "tool.data.conversion";
  } else if (/\b(screenshot|screenshot|capture.*page|og.*image)\b/.test(lower)) {
    taxonomy = "tool.data.screenshot";
  } else if (/\b(chart|chart|visualiz|graph|plot)\b/.test(lower)) {
    taxonomy = "tool.data.visualization";

  // AI — translat/OCR/code

  // Infrastructure — Compute

  } else if (/\b(serverless|serverless|modal|lambda|function)\b/.test(lower)) {
    taxonomy = "infra.compute.serverless";
  }

  // Detect weight preferences
  let w_cost = 0.25, w_quality = 0.25, w_speed = 0.25, w_reliability = 0.25;

  if (/\b(cheap|budget|cheap|save money|cost|economical|affordable|low.?cost)\b/.test(lower)) {
    w_cost = 0.55; w_quality = 0.2; w_speed = 0.15; w_reliability = 0.1;
  } else if (/\b(best|quality|high quality|best|premium|excellent|premium)\b/.test(lower)) {
    w_cost = 0.1; w_quality = 0.6; w_speed = 0.15; w_reliability = 0.15;
  } else if (/\b(fast|quick|speed|real.?time|low latency|instant|rapid)\b/.test(lower)) {
    w_cost = 0.15; w_quality = 0.2; w_speed = 0.5; w_reliability = 0.15;
  } else if (/\b(reliable|stable|stable|reliable|uptime|never.?down)\b/.test(lower)) {
    w_cost = 0.15; w_quality = 0.2; w_speed = 0.15; w_reliability = 0.5;
  }

  // io_ratio
  let io_ratio = 0.3;
  if (/\b(summar|summary|extract|extract|rag|retriev)\b/.test(lower)) io_ratio = 0.8;
  if (/\b(generat|create|write|writing|create)\b/.test(lower)) io_ratio = 0.15;

  return {
    taxonomy,
    weights: { w_cost, w_quality, w_speed, w_reliability },
    constraints: {},
    io_ratio,
    reasoning: `Rule engine: taxonomy=${taxonomy || "all"}, preference=${w_cost > 0.4 ? "cost" : w_quality > 0.4 ? "quality" : w_speed > 0.4 ? "speed" : w_reliability > 0.4 ? "reliability" : "balanced"}`,
  };
}

/**
 * Normalize intent parameters
 */
function normalizeIntent(raw: any): ParsedIntent {
  const weights = raw.weights || {};
  let w_cost = parseFloat(weights.w_cost) || 0.25;
  let w_quality = parseFloat(weights.w_quality) || 0.25;
  let w_speed = parseFloat(weights.w_speed) || 0.25;
  let w_reliability = parseFloat(weights.w_reliability) || 0.25;

  // Normalize weights
  const total = w_cost + w_quality + w_speed + w_reliability;
  if (total > 0) {
    w_cost /= total;
    w_quality /= total;
    w_speed /= total;
    w_reliability /= total;
  }

  return {
    taxonomy: raw.taxonomy || null,
    weights: { w_cost, w_quality, w_speed, w_reliability },
    constraints: raw.constraints || {},
    io_ratio: parseFloat(raw.io_ratio) || 0.3,
    reasoning: raw.reasoning || "Gemini parsed intent",
  };
}

export type { ParsedIntent, AgentDecision };
