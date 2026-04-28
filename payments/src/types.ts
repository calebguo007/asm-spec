/**
 * ASM × Circle Nanopayments — Type Definitions
 *
 * Core data structures for the payment layer + Trust Delta.
 */

// ── Payment Record ───────────────────────────────────────────

export interface PaymentRecord {
  /** Unique payment ID */
  paymentId: string;
  /** Buyer wallet address */
  buyerAddress: string;
  /** Seller wallet address */
  sellerAddress: string;
  /** Payment amount（USDC） */
  amount: string;
  /** Paid API endpoint */
  endpoint: string;
  /** Requested taxonomy (e.g. "ai.llm.chat") */
  taxonomy?: string;
  /** Chain identifier */
  chain: string;
  /** Network identifier (CAIP-2) */
  network: string;
  /** Timestamp（ISO 8601） */
  timestamp: string;
  /** Payment status */
  status: "pending" | "settled" | "failed";
  /** On-chain transaction hash (populated in live mode) */
  txHash?: string;
  /** Associated ASM scoring result */
  scoreResult?: {
    topService: string;
    totalScore: number;
    method: string;
  };
}

// ── Payment Statistics ───────────────────────────────────────────

export interface PaymentStats {
  /** Total transaction count */
  totalTransactions: number;
  /** Total amount (USDC) */
  totalVolume: string;
  /** Unique buyer count */
  uniqueBuyers: number;
  /** Unique seller count */
  uniqueSellers: number;
  /** Stats by endpoint */
  byEndpoint: Record<string, { count: number; volume: string }>;
  /** Stats by taxonomy */
  byTaxonomy: Record<string, { count: number; volume: string }>;
}

// ── Agent Wallet Status ─────────────────────────────────────

export interface WalletBalance {
  /** Gateway available balance (USDC) */
  gatewayAvailable: string;
  /** Gateway total balance (USDC) */
  gatewayTotal: string;
  /** On-chain wallet balance (USDC) */
  walletBalance: string;
  /** Chain identifier */
  chain: string;
  /** Query timestamp */
  timestamp: string;
}

// ── Trust Delta Types (ported from Python scorer) ──────────

/** Single execution receipt */
export interface ReceiptRecord {
  serviceId: string;
  timestamp: number;               // Unix Timestamp
  actualLatencySeconds: number;
  actualQualityScore: number;
  actualUptime: number;
  actualCostPerUnit: number;
}

/** Service declared values (extracted from ASM manifest) */
export interface ServiceDeclared {
  serviceId: string;
  displayName: string;
  costPerUnit: number;
  qualityScore: number;
  latencySeconds: number;
  uptime: number;
}

/** Trust Score */
export interface TrustScore {
  serviceId: string;
  trustScore: number;               // 0-1，higher = more trustworthy
  deltaBreakdown: Record<string, number>;  // Per-dimension deltas
  numReceipts: number;
  confidence: number;               // 0-1，Based on sample size
  reasoning: string;
}

// ── Payment Receipt (aligned with ASM v0.3 Signed Receipts) ──────

export interface NanopaymentReceipt {
  /** Receipt ID */
  receiptId: string;
  /** Payment Record */
  payment: PaymentRecord;
  /** ASM scoring request params (if applicable) */
  request?: {
    taxonomy?: string;
    weights?: { cost: number; quality: number; speed: number; reliability: number };
    method?: string;
  };
  /** ASM scoring response (if applicable) */
  response?: {
    ranking: Array<{
      rank: number;
      serviceId: string;
      displayName: string;
      totalScore: number;
    }>;
  };
  /** Trust Delta update (auto-computed post-payment) */
  trustUpdate?: TrustScore;
}
