import { parseAgentIntent } from "./src/gemini-agent.js";

// Regression tests: using actual requests from e2e-demo
const tests: [string, string][] = [
  // Demo scenarios
  ["I need a cheap and fast LLM for customer service chatbot, budget is important", "ai.llm.chat"],
  ["Find the highest quality LLM for complex reasoning tasks, cost doesn't matter", "ai.llm.chat"],
  ["I need the best image generation service for professional marketing materials", "ai.vision.image_generation"],
  ["Looking for a video generation tool to create short product demos", "ai.video.generation"],
  ["Help me find a free todo list app with reminders", "tool.productivity.todo"],
  ["I need a powerful task manager with Pomodoro timer", "tool.productivity.todo"],
  ["I need a browser automation service to scrape product prices from e-commerce sites reliably", "tool.data.scraping"],
  ["Looking for the cheapest headless browser API for automated testing", "tool.automation.browser"],
  ["Need a CI/CD pipeline service that's reliable", "tool.devops.ci"],
  ["I need an email API to send transactional emails, delivery rate is critical", "tool.communication.email"],
  ["I need a search API optimized for AI agents", "tool.data.search"],
  ["I need a knowledge base tool for my team", "tool.productivity.knowledge"],
  ["Looking for a fast issue tracker with keyboard shortcuts", "tool.productivity.project"],
  ["I need a serverless Postgres database", "infra.database.postgres"],
  ["Looking for a vector database for my RAG pipeline", "infra.database.vector"],
  ["I need a deployment platform with preview environments and edge functions", "tool.devops.deployment"],
  ["Looking for error tracking and performance monitoring", "tool.devops.monitoring"],
  ["I need a high-quality translation API for Japanese to English", "ai.nlp.translation"],
  ["Looking for OCR service to extract text from scanned documents", "ai.vision.ocr"],
  ["I need a CRM to track leads and automate follow-up emails", "tool.business.crm"],
  ["Looking for SMS API to send appointment reminders", "tool.communication.sms"],
  ["I need a calendar API to check availability", "tool.productivity.calendar"],
  ["I need a sandboxed environment to safely execute AI-generated Python code", "infra.compute.sandbox"],
  // Fill requests
  ["Find the cheapest LLM for simple Q&A tasks", "ai.llm.chat"],
  ["I need a high quality image generator for marketing", "ai.vision.image_generation"],
  ["Looking for a fast TTS service for real-time applications", "ai.audio.tts"],
  ["Need reliable video generation, don't want downtime", "ai.video.generation"],
  ["Best embedding model for semantic search on a budget", "ai.llm.embedding"],
  ["GPU compute for fine-tuning, need good price-performance ratio", "infra.compute.gpu"],
];

async function main() {
  let pass = 0;
  for (const [t, expected] of tests) {
    const r = await parseAgentIntent(t);
    const ok = r.taxonomy === expected;
    if (ok) pass++;
    else {
      const short = t.length > 55 ? t.slice(0, 52) + "..." : t;
      console.log(`❌ ${short.padEnd(55)} → ${(r.taxonomy || "null").padEnd(28)} (expected: ${expected})`);
    }
  }
  console.log(`\nRegression: ${pass}/${tests.length} passed`);
  if (pass === tests.length) console.log("✅ All regression tests passed!");
}
main();
