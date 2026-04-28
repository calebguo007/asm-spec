import * as path from "path";
import { fileURLToPath } from "url";
import { FakeHashEmbedder, OpenAIEmbedder } from "../src/embedders.js";
import { discoverTaxonomyWithLangGraph, readIndex } from "../src/index.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function main() {
  const repoRoot = path.resolve(__dirname, "..", "..");
  const indexPath = path.join(repoRoot, "discovery", "data", "taxonomy-index.json");
  const index = readIndex(indexPath);
  const embedder = process.env.OPENAI_API_KEY
    ? new OpenAIEmbedder(
        process.env.OPENAI_API_KEY,
        process.env.OPENAI_EMBEDDING_MODEL || "text-embedding-3-small",
      )
    : new FakeHashEmbedder(index.dimensions || 128);

  const tasks = [
    "I need to translate launch copy to Japanese and German.",
    "Generate a short product demo video with subtitle overlays.",
    "Scrape latest reddit posts about ADHD productivity tools.",
    "Find me a cheap postgres database for campaign metrics.",
  ];

  for (const task of tasks) {
    const result = await discoverTaxonomyWithLangGraph(task, index, embedder, { minConfidence: 0.25 });
    console.log(`Task: ${task}`);
    console.log(`  taxonomy=${result.taxonomy} confidence=${result.confidence.toFixed(3)}`);
    console.log(`  candidates=${result.candidates.map((c) => `${c.taxonomy}:${c.score.toFixed(3)}`).join(", ")}`);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
