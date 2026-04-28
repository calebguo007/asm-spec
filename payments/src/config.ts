/**
 * ASM × Circle Nanopayments — Configuration
 *
 * Reads configuration from environment variables with type-safe config objects.
 * Supports two modes:
 *   - mock mode: no real wallet needed, for development and demos
 *   - live mode: uses real Circle Gateway + Arc Testnet
 */

import * as dotenv from "dotenv";
import * as path from "path";
import { fileURLToPath } from "url";
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Load .env
dotenv.config({ path: path.resolve(__dirname, "..", ".env") });

export interface PaymentConfig {
  // Circle Gateway
  circleApiKey: string;

  // Wallets
  sellerAddress: string;
  buyerPrivateKey: string;

  // Network — Arc Testnet (CAIP-2: eip155:5042002)
  chainName: string;   // "arcTestnet" — for GatewayClient
  network: string;     // "eip155:5042002" — for x402 route config

  // ASM Registry
  asmRegistryUrl: string;

  // Pricing (USDC strings, e.g. "$0.005")
  scorePrice: string;
  queryPrice: string;

  // Port
  port: number;

  // Mode
  mode: "mock" | "live";
}

function getEnv(key: string, fallback?: string): string {
  const val = process.env[key] || fallback;
  if (!val) {
    throw new Error(`Missing required env var: ${key}，please configure in .env file`);
  }
  return val;
}

function isValidAddress(addr: string): boolean {
  return /^0x[0-9a-fA-F]{40}$/.test(addr);
}

export function loadConfig(): PaymentConfig {
  const sellerAddress = getEnv("SELLER_ADDRESS", "0x0000000000000000000000000000000000000000");
  const buyerPrivateKey = getEnv("BUYER_PRIVATE_KEY", "0x0000000000000000000000000000000000000000000000000000000000000001");

  // Auto-detect mode: use mock if seller address is placeholder
  const explicitMode = process.env.PAYMENT_MODE;
  let mode: "mock" | "live";
  if (explicitMode === "live") {
    mode = "live";
  } else if (explicitMode === "mock") {
    mode = "mock";
  } else {
    // Auto-detect
    mode = isValidAddress(sellerAddress) && sellerAddress !== "0x0000000000000000000000000000000000000000"
      ? "live"
      : "mock";
  }

  return {
    circleApiKey: getEnv("CIRCLE_API_KEY", ""),
    sellerAddress,
    buyerPrivateKey: normalizePrivateKey(buyerPrivateKey),
    chainName: getEnv("CHAIN", "arcTestnet"),
    network: getEnv("NETWORK", "eip155:5042002"),
    asmRegistryUrl: getEnv("ASM_REGISTRY_URL", "http://localhost:3456"),
    scorePrice: getEnv("SCORE_PRICE", "$0.005"),
    queryPrice: getEnv("QUERY_PRICE", "$0.002"),
    port: parseInt(getEnv("PAYMENT_SERVER_PORT", process.env.PORT || "4402"), 10),
    mode,
  };
}

/**
 * Ensure private key starts with 0x
 */
function normalizePrivateKey(key: string): string {
  return key.startsWith("0x") ? key : `0x${key}`;
}
