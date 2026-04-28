import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";
import { OpenAIEmbedder, FakeHashEmbedder } from "../src/embedders.js";
import { discoverTaxonomyWithLangGraph, readIndex } from "../src/index.js";
import { generateBenchmarkTasks } from "../../payments/src/benchmark-tasks.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

interface EvalRecord {
  id: number;
  category: string;
  prompt: string;
  expected_taxonomy: string;
  matched_taxonomy: string | null;
  confidence: number;
  candidates: Array<{ taxonomy: string; score: number }>;
  reasoning: string;
  correct: boolean;
  timestamp: string;
}

async function main() {
  const repoRoot = path.resolve(__dirname, "..", "..");
  const indexPath = path.join(repoRoot, "discovery", "data", "taxonomy-index.json");
  const evalDir = path.join(repoRoot, "discovery", "eval");
  fs.mkdirSync(evalDir, { recursive: true });

  const index = readIndex(indexPath);
  const embedder = process.env.OPENAI_API_KEY
    ? new OpenAIEmbedder(process.env.OPENAI_API_KEY)
    : new FakeHashEmbedder(index.dimensions || 128);

  const tasks = generateBenchmarkTasks();
  const now = new Date().toISOString();
  const runSlug = now.replace(/[:.]/g, "-");
  const records: EvalRecord[] = [];

  for (const task of tasks) {
    const result = await discoverTaxonomyWithLangGraph(task.prompt, index, embedder, {
      topK: 5,
      minConfidence: 0.25,
    });
    records.push({
      id: task.id,
      category: task.category,
      prompt: task.prompt,
      expected_taxonomy: task.taxonomy,
      matched_taxonomy: result.taxonomy,
      confidence: result.confidence,
      candidates: result.candidates,
      reasoning: result.reasoning,
      correct: result.taxonomy === task.taxonomy,
      timestamp: now,
    });
  }

  const correct = records.filter((r) => r.correct).length;
  const summary = {
    timestamp: now,
    total: records.length,
    correct,
    accuracy: Number((correct / Math.max(records.length, 1)).toFixed(4)),
    embedding_model: process.env.OPENAI_API_KEY ? "openai-text-embedding-3-small" : "fake-hash-v1",
  };

  const runFile = path.join(evalDir, `eval-run-${runSlug}.json`);
  fs.writeFileSync(runFile, JSON.stringify({ summary, records }, null, 2), "utf-8");

  for (const record of records) {
    const fileName = `${String(record.id).padStart(2, "0")}-${record.category}.json`;
    const perPromptPath = path.join(evalDir, fileName);
    fs.writeFileSync(perPromptPath, JSON.stringify(record, null, 2), "utf-8");
  }

  console.log(`Eval completed. Files written to: ${evalDir}`);
  console.log(`Accuracy: ${(summary.accuracy * 100).toFixed(2)}% (${summary.correct}/${summary.total})`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

