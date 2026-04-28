import { parseAgentIntent } from "./src/gemini-agent.js";

const tests: [string, string][] = [
  ["I need a high-quality translation API for Japanese to English", "ai.nlp.translation"],
  ["I need a deployment platform with preview environments", "tool.devops.deployment"],
  ["I need a browser automation service to scrape product prices", "tool.data.scraping"],
  ["Looking for a cheap and fast LLM for customer service", "ai.llm.chat"],
  ["I need a CI/CD pipeline service for open source projects", "tool.devops.ci"],
  ["Looking for OCR service to extract text from scanned documents", "ai.vision.ocr"],
  ["I need a sandboxed environment to safely execute Python code", "infra.compute.sandbox"],
  ["I need the best AI code completion tool", "ai.code.completion"],
  ["Looking for the cheapest headless browser API for automated testing", "tool.automation.browser"],
  ["I need a search API optimized for AI agents", "tool.data.search"],
  ["Find me an email API with high delivery rate", "tool.communication.email"],
  ["I need a vector database for my RAG pipeline", "infra.database.vector"],
];

async function main() {
  let pass = 0;
  for (const [t, expected] of tests) {
    const r = await parseAgentIntent(t);
    const ok = r.taxonomy === expected;
    if (ok) pass++;
    const mark = ok ? "✅" : "❌";
    const short = t.length > 50 ? t.slice(0, 47) + "..." : t;
    console.log(`${mark} ${short.padEnd(52)} → ${(r.taxonomy || "null").padEnd(28)}${ok ? "" : " (expected: " + expected + ")"}`);
  }
  console.log(`\nResult: ${pass}/${tests.length} passed`);
}
main();
