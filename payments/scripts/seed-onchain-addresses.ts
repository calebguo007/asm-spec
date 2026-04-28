#!/usr/bin/env tsx
/**
 * ASM Manifest Onchain Address Seeder
 *
 * For each `manifests/*.asm.json` missing `payment.onchain_address`, deterministically
 * derive an Arc testnet EVM address from the service_id and write it in place.
 *
 * Why: for the hackathon demo, benchmark payments must route to distinct
 * per-service addresses so the "pick 1 from 2-5 → money flows to winner" story is
 * visible on Arc Explorer. Real service providers don't expose onchain
 * addresses yet, so we synthesize receiver-only addresses (no private keys
 * needed; we only need USDC to flow in, not out).
 *
 * Deterministic: same service_id always maps to the same 0x address, so
 * re-running the script is a no-op for already-seeded manifests.
 *
 * Idempotent: if a manifest already has `payment.onchain_address`, it is
 * left untouched.
 *
 * Usage:
 *   npx tsx scripts/seed-onchain-addresses.ts           # seed all missing
 *   npx tsx scripts/seed-onchain-addresses.ts --dry     # preview, no writes
 *   npx tsx scripts/seed-onchain-addresses.ts --force   # overwrite existing
 */

import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";
import { keccak256, toBytes, getAddress, type Address } from "viem";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const MANIFESTS_DIR = path.resolve(__dirname, "..", "..", "manifests");
const SEED_SALT = "asm-hackathon-arc-testnet-2026";

// ── Deterministic address derivation ─────────────────

/**
 * Derive an Arc-testnet EVM address from a service_id.
 * Uses keccak256(salt + serviceId), takes last 20 bytes.
 * This is a "receive-only" address — no one holds the private key.
 * That's fine for the demo: we only need USDC to land here on-chain.
 */
function deriveAddress(serviceId: string): Address {
  const hash = keccak256(toBytes(`${SEED_SALT}::${serviceId}`));
  // hash is 0x-prefixed 64 hex = 32 bytes. Take last 20 bytes as address.
  const addrHex = "0x" + hash.slice(-40);
  return getAddress(addrHex); // checksums it
}

// ── Manifest shape we care about (partial) ───────────

interface PartialManifest {
  service_id: string;
  display_name?: string;
  taxonomy?: string;
  payment?: {
    methods?: string[];
    auth_type?: string;
    signup_url?: string;
    onchain_address?: string;
    onchain_network?: string;
  } & Record<string, unknown>;
  [k: string]: unknown;
}

// ── Main ──────────────────────────────────────────────

function main() {
  const dry = process.argv.includes("--dry");
  const force = process.argv.includes("--force");

  if (!fs.existsSync(MANIFESTS_DIR)) {
    console.error(`❌ Manifests dir not found: ${MANIFESTS_DIR}`);
    process.exit(1);
  }

  const files = fs
    .readdirSync(MANIFESTS_DIR)
    .filter((f) => f.endsWith(".asm.json"))
    .sort();

  console.log(
    `🔐 ASM Onchain Address Seeder${dry ? " (dry run)" : ""}${force ? " [FORCE]" : ""}`,
  );
  console.log(`   Manifests dir: ${MANIFESTS_DIR}`);
  console.log(`   Found ${files.length} manifest files`);
  console.log(`   Salt: "${SEED_SALT}"\n`);

  let seeded = 0;
  let skipped = 0;
  let overwritten = 0;

  for (const file of files) {
    const fullPath = path.join(MANIFESTS_DIR, file);
    const raw = fs.readFileSync(fullPath, "utf-8");
    const manifest = JSON.parse(raw) as PartialManifest;

    const existing = manifest.payment?.onchain_address;
    if (existing && !force) {
      skipped++;
      continue;
    }

    const address = deriveAddress(manifest.service_id);

    // Ensure payment block exists
    if (!manifest.payment) manifest.payment = {};

    // Add/update onchain fields
    manifest.payment.onchain_address = address;
    manifest.payment.onchain_network = "eip155:5042002"; // Arc testnet
    // Ensure "onchain_usdc" is in methods list
    const methods = new Set(manifest.payment.methods ?? []);
    methods.add("onchain_usdc");
    manifest.payment.methods = Array.from(methods);

    const action = existing ? "overwrite" : "seed";
    console.log(
      `   ${action === "seed" ? "✅" : "♻️ "} ${manifest.service_id.padEnd(40)} → ${address}`,
    );

    if (!dry) {
      fs.writeFileSync(
        fullPath,
        JSON.stringify(manifest, null, 2) + "\n",
        "utf-8",
      );
    }

    if (existing) overwritten++;
    else seeded++;
  }

  console.log();
  console.log(`📊 Summary`);
  console.log(`   Seeded:      ${seeded}`);
  console.log(`   Overwritten: ${overwritten}`);
  console.log(`   Skipped:     ${skipped} (already had onchain_address)`);
  console.log(`   Total:       ${files.length}`);
  if (dry) console.log(`   ⚠️  Dry run — no files written.`);
}

main();
