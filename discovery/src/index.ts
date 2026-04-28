import * as fs from "fs";
import * as path from "path";

export interface Embedder {
  name: string;
  embed(text: string): Promise<number[]>;
}

export interface TaxonomyRecord {
  taxonomy: string;
  description: string;
  aliases: string[];
}

export interface IndexedTaxonomy extends TaxonomyRecord {
  embedding: number[];
}

export interface DiscoveryIndex {
  version: string;
  generatedAt: string;
  model: string;
  dimensions: number;
  taxonomies: IndexedTaxonomy[];
}

export interface DiscoveryResult {
  taxonomy: string | null;
  confidence: number;
  candidates: Array<{ taxonomy: string; score: number }>;
  reasoning: string;
}

function cosineSimilarity(a: number[], b: number[]): number {
  if (a.length === 0 || b.length === 0 || a.length !== b.length) return 0;
  let dot = 0;
  let normA = 0;
  let normB = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }
  const denom = Math.sqrt(normA) * Math.sqrt(normB);
  if (denom === 0) return 0;
  return dot / denom;
}

export async function buildIndex(
  records: TaxonomyRecord[],
  embedder: Embedder,
): Promise<DiscoveryIndex> {
  const taxonomies: IndexedTaxonomy[] = [];
  for (const record of records) {
    const prompt = [
      `taxonomy: ${record.taxonomy}`,
      `description: ${record.description}`,
      `aliases: ${record.aliases.join(", ")}`,
    ].join("\n");
    const embedding = await embedder.embed(prompt);
    taxonomies.push({ ...record, embedding });
  }
  const dimensions = taxonomies[0]?.embedding.length ?? 0;
  return {
    version: "0.1",
    generatedAt: new Date().toISOString(),
    model: embedder.name,
    dimensions,
    taxonomies,
  };
}

export function discoverTaxonomy(
  task: string,
  index: DiscoveryIndex,
  embedderVector: number[],
  opts: { topK?: number; minConfidence?: number } = {},
): DiscoveryResult {
  const topK = opts.topK ?? 5;
  const minConfidence = opts.minConfidence ?? 0.52;

  const scored = index.taxonomies.map((t) => ({
    taxonomy: t.taxonomy,
    score: cosineSimilarity(embedderVector, t.embedding),
  }));
  scored.sort((a, b) => b.score - a.score);
  const candidates = scored.slice(0, topK).map((s) => ({
    taxonomy: s.taxonomy,
    score: Number(s.score.toFixed(4)),
  }));

  const best = candidates[0];
  if (!best || best.score < minConfidence) {
    return {
      taxonomy: null,
      confidence: best?.score ?? 0,
      candidates,
      reasoning: `No confident taxonomy match for task "${task}"`,
    };
  }

  return {
    taxonomy: best.taxonomy,
    confidence: best.score,
    candidates,
    reasoning: `Matched "${task}" to ${best.taxonomy} with confidence ${best.score.toFixed(3)}`,
  };
}

export function readIndex(indexPath: string): DiscoveryIndex {
  const raw = fs.readFileSync(indexPath, "utf-8");
  return JSON.parse(raw) as DiscoveryIndex;
}

export function writeIndex(indexPath: string, index: DiscoveryIndex): void {
  const dir = path.dirname(indexPath);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(indexPath, JSON.stringify(index, null, 2), "utf-8");
}

export { discoverTaxonomyWithLangGraph } from "./langgraph-discovery.js";
