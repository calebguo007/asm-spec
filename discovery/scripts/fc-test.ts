import { GoogleGenerativeAI, HarmCategory, HarmBlockThreshold } from "@google/generative-ai";

const API_KEY = process.env.GEMINI_API_KEY;
if (!API_KEY) { console.error("Set GEMINI_API_KEY"); process.exit(1); }

// Setup proxy
const proxyUrl = process.env.HTTPS_PROXY || process.env.HTTP_PROXY || process.env.ALL_PROXY;
if (proxyUrl) {
  console.log(`[Proxy] ${proxyUrl}`);
  const { ProxyAgent, setGlobalDispatcher } = await import("undici");
  setGlobalDispatcher(new ProxyAgent(proxyUrl));
}

const TOOL = {
  name: "select_taxonomy_and_score",
  description: "Select best taxonomy and trigger scoring via Circle x402 /api/score endpoint.",
  parameters: {
    type: "object",
    properties: {
      taxonomy: { type: "string", description: "e.g. ai.llm.chat, ai.image.generation" },
      reasoning: { type: "string", description: "Why this matches" },
    },
    required: ["taxonomy"],
  },
};

const TASKS = [
  { task: "Generate a photorealistic product image of a smart water bottle", label: "Image Gen", expectCat: "ai.image" },
  { task: "Translate landing page copy into Japanese and German", label: "Translation", expectCat: "ai.llm" },
  { task: "Write a Python TOPSIS multi-criteria scoring function", label: "Code Gen", expectCat: "ai.code" },
  { task: "Convert blog article to natural American English speech audio", label: "TTS", expectCat: "ai.audio" },
  { task: "Scrape top Hacker News posts about AI agent frameworks today", label: "Web Scraping", expectCat: "tool.automation" },
];

const TAXONOMIES = [
  "ai.llm.chat","ai.llm.completion","ai.llm.embedding","ai.llm.rerank",
  "ai.image.generation","ai.image.edit","ai.image.analysis",
  "ai.video.generation","ai.video.edit","ai.video.analysis",
  "ai.audio.tts","ai.audio.stt","ai.audio.music",
  "ai.code.completion","ai.code.explanation","ai.code.debug",
  "tool.data.search","tool.data.scrape","tool.data.pdf",
  "tool.automation.browser","tool.automation.workflow",
  "tool.productivity.todo","tool.productivity.calendar","tool.productivity.document",
  "infra.compute.serverless","infra.database.postgres","infra.database.kv",
  "infra.storage.object","infra.auth.identity","infra.security.secrets",
];

// Use gemini-2.5-flash-lite (has generous free tier quota)
const MODEL = process.env.GEMINI_MODEL || "gemini-2.5-flash-lite";

async function runTest() {
  console.log("╔══════════════════════════════════════════════════════════════╗");
  console.log(`  Gemini Function Calling Demo — Model: ${MODEL}`);
  console.log("  Google Track: FC → Circle x402 /api/score");
  console.log("╚══════════════════════════════════════════════════════════════╝\n");

  // Initial cooldown: wait for rate limit to fully reset
  console.log("[Cooldown] Waiting 90s for API rate limit quota to reset...");
  await new Promise(r => setTimeout(r, 90000));
  console.log("[Cooldown] Done. Starting tests.\n");

  const genAI = new GoogleGenerativeAI(API_KEY);
  const model = genAI.getGenerativeModel({
    model: MODEL,
    tools: [{ functionDeclarations: [TOOL] }],
    safetySettings: [{ category: HarmCategory.HARM_CATEGORY_HARASSMENT, threshold: HarmBlockThreshold.BLOCK_NONE }],
    generationConfig: { temperature: 0, maxOutputTokens: 256 },
  });

  let success = 0;
  for (let i = 0; i < TASKS.length; i++) {
    const { task, label, expectCat } = TASKS[i];
    const prompt = [
      "You are an AI service router for ASM protocol.",
      `Task: "${task}"`,
      `Taxonomies: ${TAXONOMIES.join(", ")}`,
      "MUST call select_taxonomy_and_score with the best match.",
    ].join("\n");

    // Retry with aggressive backoff on 429
    let result: any = null;
    for (let attempt = 1; attempt <= 3; attempt++) {
      try {
        result = await model.generateContent(prompt);
        break;
      } catch (err: any) {
        const msg = (err.message || err).toString();
        const isRateLimit = msg.includes("429") || msg.includes("quota") || msg.includes("RESOURCE_EXHAUSTED");
        if (attempt < 3) {
          const waitSec = isRateLimit ? 60 : 5;
          console.log(`    [${label}] retry ${attempt}/3${isRateLimit ? " (429, wait " + waitSec + "s)" : ""}`);
          await new Promise(r => setTimeout(r, waitSec * 1000));
        } else {
          console.log(`[❌] ${label}: ${msg.slice(0, 80)}`);
          console.log("");
        }
      }
    }
    if (!result) continue;

    const fc = result.response.functionCalls();
    if (fc && fc.length > 0) {
      success++;
      const call = fc[0];
      const ok = call.args.taxonomy?.includes(expectCat.split(".")[0]);
      console.log(`[${ok ? "✅" : "⚠️"}] ${label} → ${call.name}(${call.args.taxonomy})`);
      console.log(`    ${(call.args.reasoning || "").slice(0, 100)}`);
    } else {
      console.log(`[❌] ${label}: no FC — "${(result.response.text() || "").slice(0, 60)}"`);
    }
    console.log("");

    // Rate limit guard: 15s between requests = max 4/min
    if (i < TASKS.length - 1) {
      await new Promise(r => setTimeout(r, 15000));
    }
  }

  console.log("══════════════════════════════════════════════════════════════");
  console.log(`  ✅ ${success}/${TASKS.length} Function Calls | ${Math.round(success / TASKS.length * 100)}%`);
  console.log("══════════════════════════════════════════════════════════════");
}
runTest().catch(e => { console.error(e); process.exit(1); });
