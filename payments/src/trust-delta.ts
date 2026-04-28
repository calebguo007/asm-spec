/**
 * ASM × Circle Nanopayments — Trust Delta Engine (TypeScript)
 *
 * Trust scoring logic ported from Python scorer.py:
 *   1. trust_delta = |declared - actual| / declared
 *   2. Exponential decay: recent receipts weighted higher
 *   3. Composite Trust Score: 1 - mean(Dimension deltas)
 *   4. Confidence level：asymptotic function of receipt count
 *
 * Used to auto-update service trust scores post-payment, affecting next TOPSIS ranking.
 */

import { ReceiptRecord, ServiceDeclared, TrustScore } from "./types.js";

// ── Core Formulas ───────────────────────────────────────────

/**
 * Compute trust delta
 * trust_delta = |declared - actual| / declared
 * Returns 0.0 = perfect match, >1.0 = severe deviation
 */
export function computeTrustDelta(declared: number, actual: number): number {
  if (declared === 0) return actual === 0 ? 0.0 : 1.0;
  return Math.abs(declared - actual) / Math.abs(declared);
}

/**
 * Exponential decay weight
 * w(t) = exp(-ln(2) × age / half_life)
 * Recent receipts weighted higher, default half-life 1 week
 */
export function exponentialDecayWeight(
  timestamp: number,
  now?: number,
  halfLifeSeconds: number = 7 * 24 * 3600
): number {
  const currentTime = now ?? Date.now() / 1000;
  const age = Math.max(currentTime - timestamp, 0);
  const decayConstant = Math.LN2 / halfLifeSeconds;
  return Math.exp(-decayConstant * age);
}

// ── Trust Score Computation ───────────────────────────────────────

/**
 * Compute trust score for a service
 *
 * For each dimension (cost, quality, latency, uptime):
 *   1. Compute trust_delta per receipt
 *   2. Apply exponential decay weighted average
 *   3. Score = 1 - mean(per-dimension deltas), clamped to [0, 1]
 *
 * Confidence asymptotically approaches 1.0 with receipt count:
 *   confidence = 1 - exp(-n / 5)
 */
export function computeTrustScore(
  service: ServiceDeclared,
  receipts: ReceiptRecord[],
  halfLifeSeconds: number = 7 * 24 * 3600,
  now?: number
): TrustScore {
  if (receipts.length === 0) {
    return {
      serviceId: service.serviceId,
      trustScore: 0.5,    // No data → neutral
      deltaBreakdown: {},
      numReceipts: 0,
      confidence: 0.0,
      reasoning: `${service.displayName} has no receipt history, neutral trust score (0.5).`,
    };
  }

  const currentTime = now ?? Date.now() / 1000;

  // Dimension config: [declared value attr, actual value attr]
  const dimensions: Record<string, [keyof ServiceDeclared, keyof ReceiptRecord]> = {
    cost:    ["costPerUnit",     "actualCostPerUnit"],
    quality: ["qualityScore",    "actualQualityScore"],
    latency: ["latencySeconds",  "actualLatencySeconds"],
    uptime:  ["uptime",          "actualUptime"],
  };

  const deltaBreakdown: Record<string, number> = {};

  for (const [dimName, [declaredKey, actualKey]] of Object.entries(dimensions)) {
    const declaredVal = service[declaredKey] as number;
    let weightedDeltaSum = 0;
    let weightSum = 0;

    for (const receipt of receipts) {
      const actualVal = receipt[actualKey] as number;
      const delta = computeTrustDelta(declaredVal, actualVal);
      const weight = exponentialDecayWeight(receipt.timestamp, currentTime, halfLifeSeconds);
      weightedDeltaSum += delta * weight;
      weightSum += weight;
    }

    deltaBreakdown[dimName] = weightSum > 0
      ? Math.round((weightedDeltaSum / weightSum) * 10000) / 10000
      : 0;
  }

  // Composite trust score
  const dims = Object.values(deltaBreakdown);
  const meanDelta = dims.length > 0
    ? dims.reduce((a, b) => a + b, 0) / dims.length
    : 0;
  const trustScore = Math.max(0, Math.min(1, 1 - meanDelta));

  // Confidence level
  const confidence = 1 - Math.exp(-receipts.length / 5);

  // Find best and worst dimensions
  const sortedDims = Object.entries(deltaBreakdown).sort((a, b) => a[1] - b[1]);
  const bestDim = sortedDims[0]?.[0] ?? "N/A";
  const worstDim = sortedDims[sortedDims.length - 1]?.[0] ?? "N/A";

  const reasoning =
    `${service.displayName} trust=${trustScore.toFixed(3)} ` +
    `(confidence=${confidence.toFixed(2)}, ${receipts.length} receipts). ` +
    `Most accurate: ${bestDim} (delta=${deltaBreakdown[bestDim]?.toFixed(3) ?? 0}). ` +
    `Least accurate: ${worstDim} (delta=${deltaBreakdown[worstDim]?.toFixed(3) ?? 0}).`;

  return {
    serviceId: service.serviceId,
    trustScore: Math.round(trustScore * 10000) / 10000,
    deltaBreakdown,
    numReceipts: receipts.length,
    confidence: Math.round(confidence * 10000) / 10000,
    reasoning,
  };
}

// ── Trust-Adjusted Scoring ───────────────────────────────────────

/**
 * Adjust TOPSIS ranking with trust scores
 *
 * final_score = (1 - trust_weight) × original_score + trust_weight × trust_score × confidence
 */
export function adjustScoresWithTrust(
  scoredServices: Array<{ serviceId: string; totalScore: number; breakdown: Record<string, number> }>,
  trustScores: Record<string, TrustScore>,
  trustWeight: number = 0.2
): Array<{ serviceId: string; totalScore: number; breakdown: Record<string, number>; rank: number }> {
  const adjusted = scoredServices.map((scored) => {
    const ts = trustScores[scored.serviceId];
    if (ts && ts.confidence > 0) {
      const trustAdjustment = ts.trustScore * ts.confidence;
      const newScore = (1 - trustWeight) * scored.totalScore + trustWeight * trustAdjustment;
      return {
        serviceId: scored.serviceId,
        totalScore: Math.round(newScore * 10000) / 10000,
        breakdown: { ...scored.breakdown, trust: Math.round(trustAdjustment * 10000) / 10000 },
        rank: 0,
      };
    }
    return { ...scored, rank: 0 };
  });

  // Re-rank
  adjusted.sort((a, b) => b.totalScore - a.totalScore);
  adjusted.forEach((item, i) => { item.rank = i + 1; });

  return adjusted;
}

// ── In-Memory Trust Store ────────────────────────────────

/** Global trust store (in-memory) */
class TrustStore {
  private receipts: Map<string, ReceiptRecord[]> = new Map();
  private scores: Map<string, TrustScore> = new Map();

  /** Add receipt and recompute trust score */
  addReceipt(receipt: ReceiptRecord, declared: ServiceDeclared): TrustScore {
    if (!this.receipts.has(receipt.serviceId)) {
      this.receipts.set(receipt.serviceId, []);
    }
    this.receipts.get(receipt.serviceId)!.push(receipt);

    // Recompute
    const score = computeTrustScore(declared, this.receipts.get(receipt.serviceId)!);
    this.scores.set(receipt.serviceId, score);
    return score;
  }

  /** Get trust score */
  getScore(serviceId: string): TrustScore | undefined {
    return this.scores.get(serviceId);
  }

  /** Get all trust scores */
  getAllScores(): Record<string, TrustScore> {
    const result: Record<string, TrustScore> = {};
    for (const [k, v] of this.scores) result[k] = v;
    return result;
  }

  /** Get receipt count */
  getReceiptCount(serviceId: string): number {
    return this.receipts.get(serviceId)?.length ?? 0;
  }

  /** Get total receipt count */
  getTotalReceiptCount(): number {
    let total = 0;
    for (const receipts of this.receipts.values()) total += receipts.length;
    return total;
  }
}

export const trustStore = new TrustStore();
