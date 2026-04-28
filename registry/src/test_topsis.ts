import * as path from "path";
import { ASMRegistry, scoreTopsis, scoreServices } from "./index.js";

const registry = new ASMRegistry();
const manifestDir = path.resolve(__dirname, "..", "..", "manifests");
const count = registry.loadFromDirectory(manifestDir);
console.log(`Loaded ${count} manifests`);

const all = registry.getAll();
const weights = { cost: 0.3, quality: 0.3, speed: 0.2, reliability: 0.2 };

console.log("\n--- TypeScript TOPSIS (io_ratio=0.3) ---");
const topsisResults = scoreTopsis(all, weights, 0.3);
for (const r of topsisResults) {
  console.log(`  #${r.rank} ${r.service_id}: score=${r.total_score.toFixed(4)} cost=${r.breakdown.cost.toFixed(4)} quality=${r.breakdown.quality.toFixed(4)} speed=${r.breakdown.speed.toFixed(4)} reliability=${r.breakdown.reliability.toFixed(4)}`);
}

console.log("\n--- TypeScript Weighted Average ---");
const waResults = scoreServices(all, weights);
for (const r of waResults.slice(0, 5)) {
  console.log(`  #${r.rank} ${r.service_id}: score=${r.total_score.toFixed(4)}`);
}
