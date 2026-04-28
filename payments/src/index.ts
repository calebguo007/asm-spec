/**
 * @asm-protocol/payments
 *
 * ASM (Agent Service Manifest) Payment Layer — x402 + Circle Nanopayments
 *
 * Provides AI Agents with service discovery, TOPSIS multi-criteria scoring, Trust Delta engine
 * and USDC micropayment capabilities.
 *
 * @example
 * ```typescript
 * import { ASMBuyerClient } from "@asm-protocol/payments/buyer";
 * import { computeTrustScore } from "@asm-protocol/payments/trust-delta";
 *
 * const buyer = new ASMBuyerClient();
 * await buyer.initialize();
 * const result = await buyer.agentDecide({ request: "I need a fast LLM" });
 * ```
 */

export { ASMBuyerClient } from "./buyer.js";
export {
  computeTrustDelta,
  computeTrustScore,
  exponentialDecayWeight,
  adjustScoresWithTrust,
  trustStore,
} from "./trust-delta.js";
export { PaymentLedger, ledger } from "./ledger.js";
export { loadConfig } from "./config.js";
export type {
  PaymentRecord,
  PaymentStats,
  WalletBalance,
  ReceiptRecord,
  ServiceDeclared,
  TrustScore,
  NanopaymentReceipt,
} from "./types.js";
