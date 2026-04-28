import * as path from "path";
import { fileURLToPath } from "url";
import { FakeHashEmbedder } from "../src/embedders.js";
import { discoverTaxonomyWithLangGraph, readIndex } from "../src/index.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function main() {
  const repoRoot = path.resolve(__dirname, "..", "..");
  const indexPath = path.join(repoRoot, "discovery", "data", "taxonomy-index.json");
  const index = readIndex(indexPath);
  const embedder = new FakeHashEmbedder(index.dimensions || 128);

  // 5 diverse tasks covering image gen / translate / code gen / TTS / scrape
  const tasks = [
    { task: "Generate a photorealistic product image of a smart water bottle on a minimalist desk.", label: "Image Generation" },
    { task: "Translate my landing page headline into Japanese for the Tokyo market launch.", label: "Translation" },
    { task: "Write a Python function that calculates TOPSIS multi-criteria scoring for service ranking.", label: "Code Generation" },
    { task: "Convert this blog article into natural American English speech audio narration.", label: "TTS" },
    { task: "Scrape the top 10 Hacker News posts about AI agent frameworks today.", label: "Web Scraping" },
  ];

  console.log("═════════════════════════════════════════════════════");
  console.log("  Gemini 2.5 Flash — Function Calling Demo");
  console.log("  Track: Google — Circle x402 Integration");
  console.log("═════════════════════════════════════════════════════\n");

  let fcSuccess = 0;
  let total = tasks.length;

  for (const { task, label } of tasks) {
    console.log(`─── [${label}] ───`);
    console.log(`  Task: ${task}`);
    const result = await discoverTaxonomyWithLangGraph(task, index, embedder, { 
      topK: 5, 
      minConfidence: 0.01 // very low threshold — we care about FC, not embedding quality
    });
    
    const hasFC = result.reasoning?.includes("[Gemini FC") ?? false;
    if (hasFC) fcSuccess++;
    
    console.log(`  Taxonomy: ${result.taxonomy ?? "null"}`);
    console.log(`  Reasoning: ${result.reasoning?.substring(0, 120)}...`);
    console.log(`  FC Triggered: ${hasFC ? "YES ✅" : "no"}`);
    console.log();
  }

  console.log("═════════════════════════════════════════════════════");
  console.log(`  Result: ${fcSuccess}/${total} tasks used Gemini Function Calling`);
  console.log(`  Rate: ${Math.round(fcSuccess/total*100)}%`);
  console.log("═════════════════════════════════════════════════════");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
