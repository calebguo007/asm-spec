#!/usr/bin/env tsx
/**
 * Deposit USDC to Circle Gateway
 *
 * Usage: npm run deposit -- <amount>
 * Example: npm run deposit -- 10
 */

import { GatewayClient } from "@circle-fin/x402-batching/client";
import * as dotenv from "dotenv";
import * as path from "path";
import { fileURLToPath } from "url";
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

dotenv.config({ path: path.resolve(__dirname, "..", ".env") });

async function main() {
  const amount = process.argv[2] || "10";

  const chain = (process.env.CHAIN || "arcTestnet") as any;
  const privateKey = process.env.BUYER_PRIVATE_KEY as `0x${string}`;

  if (!privateKey || privateKey === "0x0000000000000000000000000000000000000000000000000000000000000001") {
    console.error("❌ Please set a real BUYER_PRIVATE_KEY in .env");
    process.exit(1);
  }

  console.log(`\n🏦 Depositing ${amount} USDC to Circle Gateway...`);
  console.log(`   Chain: ${chain}`);

  const client = new GatewayClient({ chain, privateKey });
  console.log(`   Address: ${client.address}`);

  // Check current balance
  const before = await client.getBalances();
  console.log(`\n   Current balance:`);
  console.log(`     Wallet USDC: ${before.wallet.formatted}`);
  console.log(`     Gateway:   ${before.gateway.formattedAvailable} (available) / ${before.gateway.formattedTotal} (total)`);

  // Deposit
  console.log(`\n   Depositing ${amount} USDC...`);
  const result = await client.deposit(amount);
  console.log(`   ✅ Deposit successful!`);
  console.log(`     Amount: ${result.formattedAmount} USDC`);
  console.log(`     Deposit TX: ${result.depositTxHash}`);
  if (result.approvalTxHash) {
    console.log(`     Approval TX: ${result.approvalTxHash}`);
  }

  // Check new balance
  const after = await client.getBalances();
  console.log(`\n   New balance:`);
  console.log(`     Wallet USDC: ${after.wallet.formatted}`);
  console.log(`     Gateway:   ${after.gateway.formattedAvailable} (available) / ${after.gateway.formattedTotal} (total)`);

  console.log(`\n   View transaction: https://testnet.arcscan.app/tx/${result.depositTxHash}\n`);
}

main().catch((err) => {
  console.error("❌ Deposit failed:", err.message);
  process.exit(1);
});
