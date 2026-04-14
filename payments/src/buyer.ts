/**
 * ASM × Circle Nanopayments — Buyer Client
 *
 * Payment client for the Agent side, implemented with Circle GatewayClient:
 *   1. Automatically handles x402 402 → sign → settle → response flow
 *   2. Wraps ASM scoring + payment into a single operation
 *   3. Tracks spending and balance
 *
 * Two modes:
 *   - live: Uses GatewayClient.pay() to auto-handle 402 flow
 *   - mock: Direct POST with X-Buyer-Address header
 */

import { loadConfig, PaymentConfig } from "./config.js";
import { WalletBalance, NanopaymentReceipt } from "./types.js";
import { privateKeyToAccount } from "viem/accounts";

export class ASMBuyerClient {
  private config: PaymentConfig;
  private gatewayClient: any = null;
  private isRealMode: boolean = false;
  private transactionCount: number = 0;
  private buyerAddress: string;

  constructor(config?: PaymentConfig) {
    this.config = config || loadConfig();
    // Derive address from private key (generates real format even in mock mode)
    try {
      const account = privateKeyToAccount(this.config.buyerPrivateKey as `0x${string}`);
      this.buyerAddress = account.address;
    } catch (_e) {
      this.buyerAddress = `0xAgent${crypto.randomUUID().replace(/-/g, "").slice(0, 36)}`;
    }
  }

  /** Initialize Gateway client */
  async initialize(): Promise<boolean> {
    if (this.config.mode !== "live") {
      console.log("⚠️  Buyer: Mock mode (skipping GatewayClient init)");
      this.isRealMode = false;
      return false;
    }

    try {
      const { GatewayClient } = await import("@circle-fin/x402-batching/client");
      this.gatewayClient = new GatewayClient({
        chain: this.config.chainName as any,
        privateKey: this.config.buyerPrivateKey as `0x${string}`,
      });
      this.isRealMode = true;
      this.buyerAddress = this.gatewayClient.address;
      console.log(`✅ Buyer: GatewayClient initialized`);
      console.log(`   Address: ${this.buyerAddress}`);
      console.log(`   Chain: ${this.config.chainName}`);
      return true;
    } catch (err: any) {
      console.warn("⚠️  Buyer: GatewayClient init failed, falling back to mock mode");
      console.warn(`   Error: ${err.message}`);
      this.isRealMode = false;
      return false;
    }
  }

  /** Query balance */
  async getBalance(): Promise<WalletBalance> {
    if (this.isRealMode && this.gatewayClient) {
      try {
        const balances = await this.gatewayClient.getBalances();
        return {
          gatewayAvailable: balances.gateway.formattedAvailable,
          gatewayTotal: balances.gateway.formattedTotal,
          walletBalance: balances.wallet?.formatted || "0",
          chain: this.config.chainName,
          timestamp: new Date().toISOString(),
        };
      } catch (err: any) {
        console.warn(`⚠️  Balance query failed: ${err.message}`);
      }
    }

    // Mock balance
    return {
      gatewayAvailable: "10.000000",
      gatewayTotal: "10.000000",
      walletBalance: "100.000000",
      chain: this.config.chainName,
      timestamp: new Date().toISOString(),
    };
  }

  /** Deposit USDC to Gateway (live mode only) */
  async deposit(amount: string): Promise<any> {
    if (!this.isRealMode || !this.gatewayClient) {
      console.log(`🟡 Mock: Mock deposit ${amount} USDC`);
      return { mock: true, amount };
    }
    const result = await this.gatewayClient.deposit(amount);
    console.log(`✅ Deposited ${result.formattedAmount} USDC`);
    console.log(`   Deposit TX: ${result.depositTxHash}`);
    return result;
  }

  /**
   * Paid call to ASM scoring endpoint
   *
   * Live mode: GatewayClient.pay() auto-handles 402 → sign → settle
   * Mock mode: Direct POST with X-Buyer-Address header
   */
  async score(params: {
    taxonomy?: string;
    w_cost?: number;
    w_quality?: number;
    w_speed?: number;
    w_reliability?: number;
    method?: string;
    io_ratio?: number;
  }): Promise<any> {
    const endpoint = `http://localhost:${this.config.port}/api/score`;

    if (this.isRealMode && this.gatewayClient) {
      const result = await this.gatewayClient.pay(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: params,
      });
      this.transactionCount++;
      const data = result.data as any;
      if (result.transaction) {
        data._txHash = result.transaction;
        data._formattedAmount = result.formattedAmount;
      }
      return data;
    }

    // Mock mode
    const response = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Buyer-Address": this.buyerAddress,
      },
      body: JSON.stringify(params),
    });

    this.transactionCount++;

    if (!response.ok) {
      throw new Error(`Score API error: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  /** Paid query to ASM Registry */
  async query(params: {
    taxonomy?: string;
    max_cost?: number;
    min_quality?: number;
    max_latency_s?: number;
    input_modality?: string;
    output_modality?: string;
  }): Promise<any> {
    const endpoint = `http://localhost:${this.config.port}/api/query`;

    if (this.isRealMode && this.gatewayClient) {
      const result = await this.gatewayClient.pay(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: params,
      });
      this.transactionCount++;
      const data = result.data as any;
      if (result.transaction) {
        data._txHash = result.transaction;
        data._formattedAmount = result.formattedAmount;
      }
      return data;
    }

    const response = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Buyer-Address": this.buyerAddress,
      },
      body: JSON.stringify(params),
    });

    this.transactionCount++;

    if (!response.ok) {
      throw new Error(`Query API error: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Paid call to Agent semantic decision endpoint
   *
   * Natural language → Gemini parsing → TOPSIS scoring → recommendations
   */
  async agentDecide(params: {
    request: string;
    gemini_api_key?: string;
  }, agentName?: string, overrideAddress?: string): Promise<any> {
    const endpoint = `http://localhost:${this.config.port}/api/agent-decide`;
    const buyerAddr = overrideAddress || this.buyerAddress;

    if (this.isRealMode && this.gatewayClient) {
      const result = await this.gatewayClient.pay(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Buyer-Address": buyerAddr,
          "X-Agent-Name": agentName || "default-agent",
        },
        body: params,
      });
      this.transactionCount++;
      // PayResult contains { data, transaction, formattedAmount, status }
      // Inject on-chain txHash into response for demo display and Block Explorer links
      const data = result.data as any;
      if (result.transaction) {
        data._txHash = result.transaction;
        data._formattedAmount = result.formattedAmount;
      }
      return data;
    }

    // Mock mode
    const response = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Buyer-Address": buyerAddr,
        "X-Agent-Name": agentName || "default-agent",
      },
      body: JSON.stringify(params),
    });

    this.transactionCount++;

    if (!response.ok) {
      throw new Error(`Agent-Decide API error: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  /** List available services (free) */
  async listServices(): Promise<any> {
    const resp = await fetch(`http://localhost:${this.config.port}/api/services`);
    return resp.json();
  }

  /** Get transaction count */
  getTransactionCount(): number {
    return this.transactionCount;
  }

  /** Get buyer address */
  getAddress(): string {
    return this.buyerAddress;
  }

  /** Whether using real payment mode */
  isLive(): boolean {
    return this.isRealMode;
  }
}
