#!/usr/bin/env tsx
/**
 * Query Circle Gateway balance
 *
 * Usage: npm run balance
 */

import { GatewayClient } from "@circle-fin/x402-batching/client";
import * as dotenv from "dotenv";
import * as path from "path";
import { fileURLToPath } from "url";
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

dotenv.config({ path: path.resolve(__dirname, "..", ".env") });

async function main() {
  const chain = (process.env.CHAIN || "arcTestnet") as any;
  const privateKey = process.env.BUYER_PRIVATE_KEY as `0x${string}`;

  if (!privateKey || privateKey === "0x0000000000000000000000000000000000000000000000000000000000000001") {
    console.error("❌ Please set a real BUYER_PRIVATE_KEY in .env");
    console.log("\n💡 Mock mode balance:");
    console.log("   Gateway:   10.000000 USDC (simulated)");
    console.log("   Wallet:      100.000000 USDC (simulated)");
    process.exit(0);
  }

  console.log(`\n💰 Querying balance...`);
  console.log(`   Chain: ${chain}`);

  const client = new GatewayClient({ chain, privateKey });
  console.log(`   Address: ${client.address}`);

  const balances = await client.getBalances();

  console.log(`\n   Wallet USDC:     ${balances.wallet.formatted}`);
  console.log(`   Gateway available:  ${balances.gateway.formattedAvailable}`);
  console.log(`   Gateway total:  ${balances.gateway.formattedTotal}`);
  console.log(`   Withdrawing:        ${balances.gateway.formattedWithdrawing}`);
  console.log(`   Withdrawable:        ${balances.gateway.formattedWithdrawable}`);

  console.log(`\n   View on-chain: https://testnet.arcscan.app/address/${client.address}\n`);
}

main().catch((err) => {
  console.error("❌ Query failed:", err.message);
  process.exit(1);
});
