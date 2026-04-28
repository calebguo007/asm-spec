import crypto from "crypto";
import type { Embedder } from "./index.js";

export class FakeHashEmbedder implements Embedder {
  name = "fake-hash-v1";
  constructor(private readonly dimensions: number = 128) {}

  async embed(text: string): Promise<number[]> {
    const values = new Array<number>(this.dimensions).fill(0);
    const digest = crypto.createHash("sha256").update(text).digest();
    for (let i = 0; i < this.dimensions; i++) {
      const b = digest[i % digest.length];
      values[i] = (b / 255) * 2 - 1;
    }
    return values;
  }
}

export class OpenAIEmbedder implements Embedder {
  name = "openai-text-embedding-3-small";
  constructor(
    private readonly apiKey: string,
    private readonly model = process.env.OPENAI_EMBEDDING_MODEL ?? "text-embedding-3-small",
    private readonly baseUrl = process.env.OPENAI_BASE_URL ?? "https://api.openai.com",
  ) {}

  async embed(text: string): Promise<number[]> {
    const base = this.baseUrl.replace(/\/+$/, "");
    const url = base.endsWith("/v1") ? `${base}/embeddings` : `${base}/v1/embeddings`;
    const resp = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${this.apiKey}`,
      },
      body: JSON.stringify({
        model: this.model,
        input: text,
      }),
    });
    if (!resp.ok) {
      throw new Error(`OpenAI embeddings failed: ${resp.status} ${await resp.text()}`);
    }
    const json = (await resp.json()) as { data?: Array<{ embedding: number[] }> };
    const vector = json.data?.[0]?.embedding;
    if (!vector) throw new Error("OpenAI embeddings returned empty vector");
    return vector;
  }
}
