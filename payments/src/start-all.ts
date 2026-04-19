#!/usr/bin/env tsx
/**
 * ASM × Circle Nanopayments — Unified Launcher
 *
 * Starts ASM Registry HTTP API and Payment Server simultaneously.
 * Usage: npm run dev:all
 */

import { spawn, ChildProcess } from "child_process";
import * as path from "path";
import { fileURLToPath } from "url";
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const BOLD = "\x1b[1m";
const CYAN = "\x1b[96m";
const GREEN = "\x1b[92m";
const YELLOW = "\x1b[93m";
const RED = "\x1b[91m";
const RESET = "\x1b[0m";

const processes: ChildProcess[] = [];

function startProcess(name: string, command: string, args: string[], cwd: string, color: string): ChildProcess {
  console.log(`${color}[${name}]${RESET} starting...`);
  const proc = spawn(command, args, {
    cwd,
    stdio: ["ignore", "pipe", "pipe"],
    env: { ...process.env },
    shell: true,
  });

  proc.stdout?.on("data", (data: Buffer) => {
    const lines = data.toString().trim().split("\n");
    for (const line of lines) {
      console.log(`${color}[${name}]${RESET} ${line}`);
    }
  });

  proc.stderr?.on("data", (data: Buffer) => {
    const lines = data.toString().trim().split("\n");
    for (const line of lines) {
      console.log(`${color}[${name}]${RESET} ${RED}${line}${RESET}`);
    }
  });

  proc.on("exit", (code) => {
    console.log(`${color}[${name}]${RESET} process exited (code=${code})`);
  });

  processes.push(proc);
  return proc;
}

async function main() {
  console.log(`\n${BOLD}${CYAN}${"═".repeat(60)}${RESET}`);
  console.log(`${BOLD}${CYAN}  ASM × Circle Nanopayments — Unified Launcher${RESET}`);
  console.log(`${BOLD}${CYAN}${"═".repeat(60)}${RESET}\n`);

  const rootDir = path.resolve(__dirname, "..", "..");
//   const paymentsDir = path.resolve(__dirname, "..");  // unused

  // 1. Start ASM Registry
  startProcess("Registry", "npx", ["tsx", "registry/src/http.ts"], rootDir, GREEN);

  // Wait for Registry to start
  await new Promise((r) => setTimeout(r, 2000));

  // 2. Start Payment Server
  startProcess("Payment", "npx", ["tsx", "payments/src/seller.ts"], rootDir, YELLOW);

  console.log(`\n${BOLD}Both services started:${RESET}`);
  console.log(`  ${GREEN}Registry${RESET}  → http://localhost:3456`);
  console.log(`  ${YELLOW}Payment${RESET}   → http://localhost:4402`);
  console.log(`  ${CYAN}Dashboard${RESET} → http://localhost:4402/api/dashboard`);
  console.log(`\n  Press Ctrl+C to stop all services\n`);
}

// Graceful shutdown
process.on("SIGINT", () => {
  console.log(`\n${RED}Stopping all services...${RESET}`);
  for (const proc of processes) {
    proc.kill("SIGTERM");
  }
  setTimeout(() => process.exit(0), 1000);
});

process.on("SIGTERM", () => {
  for (const proc of processes) {
    proc.kill("SIGTERM");
  }
  process.exit(0);
});

main().catch((err) => {
  console.error("Startup failed:", err);
  process.exit(1);
});
