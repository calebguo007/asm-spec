// Gemini FC Demo — gemini-2.5-flash-lite (has available quota)
// Raw HTTP via proxy, smart rate limit handling
const http = require("http");
const tls = require("tls");

const API_KEY = process.env.GEMINI_API_KEY;
if (!API_KEY) {
  console.error("GEMINI_API_KEY not set. export GEMINI_API_KEY=... before running.");
  process.exit(1);
}
const PROXY_PORT = 1082;
const HOST = "generativelanguage.googleapis.com";
const MODEL = "gemini-2.5-flash-lite";

const TOOL_DECL = {
  name: "select_taxonomy_and_score",
  description: "Select best taxonomy for ASM protocol and trigger Circle x402 /api/score.",
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

function geminiRequest(prompt) {
  return new Promise((resolve, reject) => {
    const req = http.request({ host: "127.0.0.1", port: PROXY_PORT, method: "CONNECT", path: `${HOST}:443` });
    req.on("connect", (res, socket) => {
      if (res.statusCode !== 200) { reject(new Error(`CONNECT ${res.statusCode}`)); return; }
      const tlsSock = tls.connect({ socket, servername: HOST }, () => {
        const body = JSON.stringify({
          contents: [{ parts: [{ text: prompt }] }],
          tools: [{ functionDeclarations: [TOOL_DECL] }],
          generationConfig: { temperature: 0, maxOutputTokens: 256 },
        });
        const path = `/v1beta/models/${MODEL}:generateContent?key=${API_KEY}`;
        tlsSock.write(`POST ${path} HTTP/1.1\r\nHost: ${HOST}\r\nContent-Type: application/json\r\nContent-Length: ${Buffer.byteLength(body)}\r\nConnection: close\r\n\r\n${body}`);
        let d = "";
        tlsSock.on("data", c => d += c);
        tlsSock.on("end", () => resolve(d));
        tlsSock.on("error", reject);
      });
      tlsSock.on("error", reject);
    });
    req.on("error", reject);
    req.end();
  });
}

function parseRetryAfter(resp) {
  const m = resp.match(/retry in ([\d.]+)s/);
  return m ? Math.ceil(parseFloat(m[1])) + 5 : 60;
}

function extractBody(resp) {
  const idx = resp.indexOf("\r\n\r\n");
  return idx >= 0 ? resp.substring(idx + 4) : resp;
}

async function sleep(sec) { return new Promise(r => setTimeout(r, sec * 1000)); }

async function main() {
  console.log("╔══════════════════════════════════════════════════════════════╗");
  console.log(`  Gemini FC Demo — Model: ${MODEL}`);
  console.log("  Google Track: Function Calling → Circle x402 /api/score");
  console.log("╚══════════════════════════════════════════════════════════════╝\n");

  let success = 0;
  for (let i = 0; i < TASKS.length; i++) {
    const { task, label, expectCat } = TASKS[i];
    const prompt = [
      "You are an AI service router for the Agent Service Manifest (ASM) protocol.",
      `Task: "${task}"`,
      `Available taxonomies: ${TAXONOMIES.join(", ")}`,
      "You MUST call select_taxonomy_and_score with your choice. Pick the closest match.",
    ].join("\n");

    // Smart 429 handling
    let resp = await geminiRequest(prompt);
    let status = resp.split("\r\n")[0];
    
    if (status.includes("429")) {
      const wait = parseRetryAfter(resp);
      console.log(`    [${label}] 429 — waiting ${wait}s...`);
      await sleep(wait);
      resp = await geminiRequest(prompt);
      status = resp.split("\r\n")[0];
      if (status.includes("429")) {
        console.log(`[❌] ${label}: still rate-limited\n`);
        continue;
      }
    }

    if (!status.includes("200")) {
      console.log(`[❌] ${label}: ${status}\n`);
      continue;
    }

    try {
      // Strip HTTP chunked encoding: "size\r\n...data...\r\n0\r\n\r\n"
      let bodyStr = extractBody(resp);
      // Remove chunk size prefixes like "360\r\n" or "555\r\n"
      bodyStr = bodyStr.replace(/^[0-9a-fA-F]+\r\n/, "");
      // Remove trailing chunk markers "0\r\n\r\n"
      bodyStr = bodyStr.replace(/\r\n0\r\n\r\n$/, "").replace(/\r\n0$/, "");
      
      const json = JSON.parse(bodyStr);
      const parts = json.candidates?.[0]?.content?.parts || [];
      const fcParts = parts.filter(p => p.functionCall);

      if (fcParts.length > 0) {
        success++;
        const fc = fcParts[0].functionCall;
        const ok = fc.args.taxonomy?.includes(expectCat.split(".")[0]);
        console.log(`[${ok ? "✅" : "⚠️"}] ${label} → ${fc.name}(${fc.args.taxonomy})`);
        console.log(`    ${(fc.args.reasoning || "").slice(0, 100)}`);
      } else {
        const text = parts[0]?.text || "(empty)";
        console.log(`[❌] ${label}: no FC — "${text.slice(0, 60)}"`);
      }
    } catch(e) {
      console.log(`[❌] ${label}: parse error`);
    }
    console.log("");

    if (i < TASKS.length - 1) {
      await sleep(6); // 6s between requests
    }
  }

  console.log("══════════════════════════════════════════════════════════════");
  console.log(`  ✅ ${success}/${TASKS.length} Function Calls | ${Math.round(success/TASKS.length*100)}%`);
  console.log("══════════════════════════════════════════════════════════════");
}
main().catch(console.error);
