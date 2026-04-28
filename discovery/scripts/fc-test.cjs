// Standalone Gemini Function Calling test — bypasses LangGraph embedding
const { GoogleGenerativeAI, HarmCategory, HarmBlockThreshold } = require("@google/generative-ai");

const API_KEY = process.env.GEMINI_API_KEY;
if (!API_KEY) { console.error("Set GEMINI_API_KEY"); process.exit(1); }

const TOOL = {
  name: "select_taxonomy_and_score",
  description: "Select the best matching taxonomy for an AI agent task and trigger scoring via the Circle x402 payment endpoint (/api/score). This function maps the agent's natural language task to a structured taxonomy identifier used for service discovery and per-API-call USDC settlement on Arc.",
  parameters: {
    type: "object",
    properties: {
      taxonomy: { type: "string", description: "The selected taxonomy identifier, e.g. ai.llm.chat, ai.image.generation, ai.audio.tts" },
      reasoning: { type: "string", description: "Brief explanation for why this taxonomy best matches the task" },
    },
    required: ["taxonomy"],
  },
};

const TASKS = [
  { task: "Generate a photorealistic product image of a smart water bottle", label: "Image Gen", expect: "ai.image" },
  { task: "Translate landing page copy into Japanese and German", label: "Translation", expect: "ai.llm" },
  { task: "Write a Python TOPSIS scoring function", label: "Code Gen", expect: "ai.code" },
  { task: "Convert blog article to natural speech audio", label: "TTS", expect: "ai.audio.tts" },
  { task: "Scrape top Hacker News posts about AI agents", label: "Scraping", expect: "tool.automation.browser" },
];

// All available taxonomies from our registry
const ALL_TAXONOMIES = [
  "ai.llm.chat", "ai.llm.completion", "ai.llm.embedding", "ai.llm.rerank",
  "ai.image.generation", "ai.image.edit", "ai.image.analysis",
  "ai.video.generation", "ai.video.edit", "ai.video.analysis",
  "ai.audio.tts", "ai.audio.stt", "ai.audio.music",
  "ai.code.completion", "ai.code.explanation", "ai.code.debug",
  "tool.data.search", "tool.data.scrape", "tool.data.pdf",
  "tool.automation.browser", "tool.automation.workflow",
  "tool.productivity.todo", "tool.productivity.calendar", "tool.productivity.document",
  "infra.compute.serverless", "infra.database.postgres", "infra.database.kv",
  "infra.storage.object", "infra.auth.identity", "infra.security.secrets",
];

async function runTest() {
  console.log("╔══════════════════════════════════════════════════════════╗");
  console.log("  Gemini 2.5 Flash — Function Calling Test");
  console.log("  Google Track: Agents securely interact with Circle APIs");
  console.log("╚══════════════════════════════════════════════════════════╝\n");

  const genAI = new GoogleGenerativeAI(API_KEY);
  const model = genAI.getGenerativeModel({
    model: "gemini-2.5-flash",
    tools: [{ functionDeclarations: [TOOL] }],
    safetySettings: [{ category: HarmCategory.HARM_CATEGORY_HARASSMENT, threshold: HarmBlockThreshold.BLOCK_NONE }],
    generationConfig: { temperature: 0, maxOutputTokens: 256 },
  });

  let success = 0;
  for (const { task, label, expect } of TASKS) {
    const prompt = `You are an AI service router. Given this task, pick the BEST taxonomy from our registry.
Task: "${task}"
Available taxonomies: ${ALL_TAXONOMIES.join(", ")}
Pick ONE and call select_taxonomy_and_score with it.`;

    try {
      const result = await model.generateContent(prompt);
      const response = result.response;
      const fc = response.functionCalls();
      
      if (fc && fc.length > 0) {
        const call = fc[0];
        success++;
        const icon = call.args.taxonomy?.includes(expect?.split(".")[0]) ? "✅" : "⚠️";
        console.log(`[${icon}] ${label}: FC → ${call.name}(${call.args.taxonomy})`);
        console.log(`    Reasoning: ${call.args.reasoning || "N/A"}`);
      } else {
        console.log(`[❌] ${label}: No FC — text: ${(response.text()||"(empty)").substring(0,80)}`);
      }
    } catch(e) {
      console.log(`[❌] ${label}: Error — ${e.message.substring(0,60)}`);
    }
  }

  console.log(`\n═══════════════════════════════════════`);
  console.log(`  Result: ${success}/${TASKS.length} Function Calls succeeded`);
  console.log(`═══════════════════════════════════════`);
}

runTest().catch(e => { console.error(e); process.exit(1); });
