/**
 * ASM × Circle Nanopayments — Transaction Ledger
 *
 * In-memory payment record storage for:
 * 1. Tracking all nanopayment transactions
 * 2. Generating statistics (meeting 50+ transaction requirements)
 * 3. Providing real-time data for the Dashboard
 * 4. Export as JSON for demo and submission evidence
 */

import { PaymentRecord, PaymentStats } from "./types.js";

export class PaymentLedger {
  private records: PaymentRecord[] = [];

  /** Record a payment */
  record(payment: PaymentRecord): void {
    this.records.push(payment);
    const txInfo = payment.txHash
      ? ` tx=${payment.txHash.slice(0, 14)}...`
      : "";
    console.log(
      `📒 Ledger: #${this.records.length} | ${payment.amount} USDC | ` +
      `${payment.endpoint} | ${payment.buyerAddress.slice(0, 10)}...→${payment.sellerAddress.slice(0, 10)}...` +
      txInfo
    );
  }

  /** Get all records */
  getAll(): PaymentRecord[] {
    return [...this.records];
  }

  /** Get record count */
  count(): number {
    return this.records.length;
  }

  /** Get last N records */
  getRecent(n: number = 10): PaymentRecord[] {
    return this.records.slice(-n);
  }

  /** Filter by buyer address */
  getByBuyer(address: string): PaymentRecord[] {
    return this.records.filter(
      (r) => r.buyerAddress.toLowerCase() === address.toLowerCase()
    );
  }

  /** Generate statistics */
  getStats(): PaymentStats {
    const buyers = new Set<string>();
    const sellers = new Set<string>();
    const byEndpoint: Record<string, { count: number; volume: number }> = {};
    const byTaxonomy: Record<string, { count: number; volume: number }> = {};
    let totalVolume = 0;

    for (const r of this.records) {
      const amount = parseFloat(r.amount);
      totalVolume += amount;
      buyers.add(r.buyerAddress.toLowerCase());
      sellers.add(r.sellerAddress.toLowerCase());

      // Stats by endpoint
      if (!byEndpoint[r.endpoint]) byEndpoint[r.endpoint] = { count: 0, volume: 0 };
      byEndpoint[r.endpoint].count++;
      byEndpoint[r.endpoint].volume += amount;

      // Stats by taxonomy
      if (r.taxonomy) {
        if (!byTaxonomy[r.taxonomy]) byTaxonomy[r.taxonomy] = { count: 0, volume: 0 };
        byTaxonomy[r.taxonomy].count++;
        byTaxonomy[r.taxonomy].volume += amount;
      }
    }

    const formatMap = (m: Record<string, { count: number; volume: number }>) =>
      Object.fromEntries(
        Object.entries(m).map(([k, v]) => [k, { count: v.count, volume: v.volume.toFixed(6) }])
      );

    return {
      totalTransactions: this.records.length,
      totalVolume: totalVolume.toFixed(6),
      uniqueBuyers: buyers.size,
      uniqueSellers: sellers.size,
      byEndpoint: formatMap(byEndpoint),
      byTaxonomy: formatMap(byTaxonomy),
    };
  }

  /** Export as JSON */
  exportJSON(): string {
    return JSON.stringify({
      exportedAt: new Date().toISOString(),
      stats: this.getStats(),
      records: this.records,
    }, null, 2);
  }
}

/** Global singleton */
export const ledger = new PaymentLedger();
