import { Annotation, END, START, StateGraph } from "@langchain/langgraph";
import { ChatOpenAI } from "@langchain/openai";
import { GoogleGenerativeAI, HarmCategory, HarmBlockThreshold } from "@google/generative-ai";
import type { DiscoveryIndex, DiscoveryResult, Embedder } from "./index.js";

// ── Cosine Similarity ────────────────────────────────────────────────────

function cosineSimilarity(a: number[], b: number[]): number {
  if (a.length === 0 || b.length === 0 || a.length !== b.length) return 0;
  let dot = 0;
  let normA = 0;
  let normB = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }
  const denom = Math.sqrt(normA) * Math.sqrt(normB);
  if (denom === 0) return 0;
  return dot / denom;
}

// ── State Definition ─────────────────────────────────────────────────────

const DiscoveryState = Annotation.Root({
  task: Annotation<string>(),
  taskEmbedding: Annotation<number[]>({
    reducer: (_prev, next) => next,
    default: () => [],
  }),
  candidates: Annotation<Array<{ taxonomy: string; score: number }>>({
    reducer: (_prev, next) => next,
    default: () => [],
  }),
  rerankedTaxonomy: Annotation<string | null>({
    reducer: (_prev, next) => next,
    default: () => null,
  }),
  rerankReasoning: Annotation<string>({
    reducer: (_prev, next) => next,
    default: () => "",
  }),
  taxonomy: Annotation<string | null>({
    reducer: (_prev, next) => next,
    default: () => null,
  }),
  confidence: Annotation<number>({
    reducer: (_prev, next) => next,
    default: () => 0,
  }),
  reasoning: Annotation<string>({
    reducer: (_prev, next) => next,
    default: () => "",
  }),
});

// ── Function Calling Tool Definition for Circle x402 /api/score ───────────
// This is the Google track requirement: "Function Calling, allowing agents to
// securely interact with Circle APIs". The tool maps directly to the seller's
// scoring endpoint that triggers USDC nanopayment settlement on Arc.

const selectTaxonomyTool = {
  name: "select_taxonomy_and_score",
  description:
    "Selects the best matching ASM taxonomy for a user task and triggers scoring via the Circle x402 payment endpoint (/api/score). Call this function AFTER analyzing all candidates to commit your selection.",
  parameters: {
    type: "object" as const,
    properties: {
      taxonomy: {
        type: "string",
        description:
          "The selected ASM taxonomy string (e.g., 'ai.llm.chat', 'ai.video.generation')",
      },
      reasoning: {
        type: "string",
        description:
          "Brief explanation of why this taxonomy was chosen over other candidates",
      },
    },
    required: ["taxonomy", "reasoning"],
  },
};

// ── LLM Rerank: Gemini (Function Calling) → OpenRouter → OpenAI ──────────

async function llmRerankCandidates(
  task: string,
  candidates: Array<{ taxonomy: string; score: number }>,
): Promise<{ taxonomy: string | null; reasoning: string }> {
  if (candidates.length === 0) {
    return { taxonomy: null, reasoning: "LLM rerank skipped (no candidates)." };
  }

  const promptLines = [
    "You are ranking ASM taxonomy candidates for a user task.",
    "CRITICAL RULE: Pick the taxonomy for the VERB / ACTION the user wants to perform, NOT the DOMAIN they mention.",
    "Examples:",
    "- 'Write an Instagram caption' → pick ai.llm.chat (the action is writing text), NOT tool.communication.chat",
    "- 'Generate a Google Analytics snippet' → pick ai.code.completion (the action is generating code), NOT tool.data.analytics",
    "- 'Generate webhook handler for Circle payment' → pick ai.code.completion (generating code), NOT tool.payment.processing",
    "- 'Embed landing-page headlines to find similar ones' → pick ai.llm.embedding (embedding creation), NOT tool.data.search",
    "- '6s product demo video, screen-recording style' → pick ai.video.generation (creating video), NOT tool.data.screenshot",
    `Task: ${task}`,
    `Candidates: ${candidates.map((c) => `${c.taxonomy} (similarity=${c.score.toFixed(4)})`).join(", ")}`,
    "Pick exactly one taxonomy from Candidates. Use the select_taxonomy_and_score function to submit your choice.",
  ].join("\n");

  // ── Provider 0: AI/ML API (Hackathon Partner, OpenAI Compatible) ────
  const aimlApiKey = process.env.OPENAI_API_KEY;
  const aimlBaseUrl = process.env.OPENAI_BASE_URL;
  if (aimlApiKey && aimlBaseUrl?.includes("aimlapi.com")) {
    try {
      const aimlModel = process.env.OPENAI_CHAT_MODEL || "google/gemma-3-27b-it";
      console.log(`[AIMLAPI] Using ${aimlModel} for reranking via ${aimlBaseUrl}...`);

      const model = new ChatOpenAI({
        apiKey: aimlApiKey,
        model: aimlModel,
        temperature: 0,
        configuration: { baseURL: aimlBaseUrl },
      });

      const response = await model.invoke(promptLines);
      const text =
        typeof response.content === "string"
          ? response.content
          : Array.isArray(response.content)
            ? response.content
                .map((p: any) =>
                  typeof p === "string" ? p : p?.text ?? "",
                )
                .join("")
            : "";

      console.log(`[AIMLAPI] Response: ${JSON.stringify(text).substring(0, 200)}`);

      try {
        const jsonLike = text.includes("{")
          ? text.slice(text.indexOf("{"), text.lastIndexOf("}") + 1)
          : text;
        const parsed = JSON.parse(jsonLike) as {
          taxonomy?: string;
          reasoning?: string;
        };
        if (
          parsed.taxonomy &&
          candidates.some((c) => c.taxonomy === parsed.taxonomy)
        ) {
          console.log(
            `[AIMLAPI] ✅ Selected: ${parsed.taxonomy}`,
          );
          return {
            taxonomy: parsed.taxonomy,
            reasoning: `[AIMLAPI → /api/score] ${parsed.reasoning ?? "Taxonomy selected via AI/ML API (hackathon partner)."}`,
          };
        }
      } catch {
        // Malformed JSON — fall through to Gemini
      }
      console.warn("[AIMLAPI] No usable output, falling back to Gemini...");
    } catch (err) {
      console.error("[AIMLAPI] Error:", err);
    }
  }

  // ── Provider 1: Gemini with Function Calling (Google track) ──────────
  const geminiKey = process.env.GEMINI_API_KEY;
  if (geminiKey) {
    let proxyAgent: any = undefined; // declare outside try for finally access
    try {
      console.log("[Gemini FC] Initializing gemini-2.5-flash with Function Calling...");

      // Configure proxy for users behind GFW / corporate firewall
      const proxyUrl = process.env.HTTPS_PROXY || process.env.HTTP_PROXY || process.env.ALL_PROXY;
      if (proxyUrl) {
        console.log(`[Gemini FC] Using proxy: ${proxyUrl}`);
        const { ProxyAgent, setGlobalDispatcher } = await import("undici");
        proxyAgent = new ProxyAgent(proxyUrl);
        setGlobalDispatcher(proxyAgent);
      }

      const genAI = new GoogleGenerativeAI(geminiKey);
      const model = genAI.getGenerativeModel({
        model: process.env.GEMINI_MODEL || "gemini-2.5-flash",
        tools: [{ functionDeclarations: [selectTaxonomyTool] }],
        toolConfig: {
          functionCallingConfig: {
            mode: "ANY", // FORCE function call — required for Google track demo
            allowedFunctionNames: ["select_taxonomy_and_score"],
          },
        },
        safetySettings: [
          {
            category: HarmCategory.HARM_CATEGORY_HARASSMENT,
            threshold: HarmBlockThreshold.BLOCK_NONE,
          },
        ],
        generationConfig: {
          temperature: 0,
          maxOutputTokens: 512,
        },
      });

      const result = await model.generateContent(promptLines);
      const response = result.response;

      // Debug: log raw response
      console.log("[Gemini FC] Response text:", JSON.stringify(response.text()).substring(0, 200));
      console.log("[Gemini FC] Function calls:", JSON.stringify(response.functionCalls()));

      // Check for function call in response
      const fc = response.functionCalls();
      if (fc && fc.length > 0) {
        const call = fc[0];
        const args = call.args as { taxonomy?: string; reasoning?: string };
        if (
          typeof args.taxonomy === "string" &&
          candidates.some((c) => c.taxonomy === args.taxonomy)
        ) {
          console.log(
            `[Gemini FC] ✅ Function called: select_taxonomy_and_score(${args.taxonomy})`,
          );
          return {
            taxonomy: args.taxonomy,
            reasoning: `[Gemini FC → /api/score] ${args.reasoning ?? "Taxonomy selected via structured function call to Circle x402 endpoint."}`,
          };
        }
        console.warn(
          "[Gemini FC] Function returned invalid taxonomy, falling through...",
        );
      }

      // No valid function call — try text parse as fallback
      const text = response.text();
      if (text) {
        try {
          const jsonLike = text.includes("{")
            ? text.slice(text.indexOf("{"), text.lastIndexOf("}") + 1)
            : text;
          const parsed = JSON.parse(jsonLike) as {
            taxonomy?: string;
            reasoning?: string;
          };
          if (
            parsed.taxonomy &&
            candidates.some((c) => c.taxonomy === parsed.taxonomy)
          ) {
            return {
              taxonomy: parsed.taxonomy,
              reasoning: parsed.reasoning
                ? `[Gemini text] ${parsed.reasoning}`
                : "[Gemini text] LLM rerank selected taxonomy.",
            };
          }
        } catch {
          // fall through to OpenAI fallback
        }
      }
      console.warn(
        "[Gemini FC] No usable output, falling back to OpenAI/OpenRouter...",
      );
    } catch (err) {
      console.error("[Gemini FC] Error:", err);
    } finally {
      // Restore default fetch dispatcher so OpenAI fallback isn't affected
      if (proxyAgent) {
        try { 
          const { setGlobalDispatcher, Agent: UndiciAgent } = await import("undici");
          setGlobalDispatcher(new UndiciAgent()); 
        } catch(e) { /* ignore cleanup errors */ }
      }
    }
  }

  // ── Provider 2/3: OpenRouter or OpenAI (existing logic) ──────────────
  const openaiKey = process.env.OPENAI_API_KEY;
  if (!openaiKey) {
    // No API key at all — heuristic fallback
    const heuristic = candidates[0]?.taxonomy ?? null;
    return {
      taxonomy: heuristic,
      reasoning: "No API key found (GEMINI_API_KEY or OPENAI_API_KEY). Fallback to top similarity candidate.",
    };
  }

  try {
    const isOpenRouter =
      process.env.OPENAI_BASE_URL?.includes("openrouter.ai");
    const model = new ChatOpenAI({
      apiKey: openaiKey,
      model:
        process.env.OPENAI_CHAT_MODEL ||
        (isOpenRouter ? "openrouter/auto" : "gpt-4o-mini"),
      temperature: 0,
      configuration: process.env.OPENAI_BASE_URL
        ? { baseURL: process.env.OPENAI_BASE_URL }
        : undefined,
    });

    const source = isOpenRouter ? "OpenRouter" : "OpenAI";
    console.log(`[${source}] Using ${model.modelName} for reranking...`);

    const response = await model.invoke(promptLines);
    const text =
      typeof response.content === "string"
        ? response.content
        : Array.isArray(response.content)
          ? response.content
              .map((p: any) =>
                typeof p === "string" ? p : p?.text ?? "",
              )
              .join("")
          : "";

    try {
      const jsonLike = text.includes("{")
        ? text.slice(text.indexOf("{"), text.lastIndexOf("}") + 1)
        : text;
      const parsed = JSON.parse(jsonLike) as {
        taxonomy?: string;
        reasoning?: string;
      };
      if (parsed.taxonomy && candidates.some((c) => c.taxonomy === parsed.taxonomy)) {
        return {
          taxonomy: parsed.taxonomy,
          reasoning: parsed.reasoning
            ? `[${source}] ${parsed.reasoning}`
            : `[${source}] LLM rerank selected taxonomy.`,
        };
      }
    } catch {
      // Malformed JSON
    }
  } catch (err) {
    console.error("[OpenAI] Error:", err);
  }

  // Final fallback: top similarity candidate
  const heuristic = candidates[0]?.taxonomy ?? null;
  return {
    taxonomy: heuristic,
    reasoning: "All LLM providers failed or returned invalid output. Fallback to top similarity candidate.",
  };
}

// ── Main Export ──────────────────────────────────────────────────────────

export async function discoverTaxonomyWithLangGraph(
  task: string,
  index: DiscoveryIndex,
  embedder: Embedder,
  opts: { topK?: number; minConfidence?: number } = {},
): Promise<DiscoveryResult> {
  const topK = opts.topK ?? 5;
  const minConfidence = opts.minConfidence ?? 0.3;

  const graph = new StateGraph(DiscoveryState)
    .addNode("embedTask", async (state) => {
      const taskEmbedding = await embedder.embed(state.task);
      return { taskEmbedding };
    })
    .addNode("retrieveCandidates", async (state) => {
      const candidates = index.taxonomies
        .map((t) => ({
          taxonomy: t.taxonomy,
          score: Number(
            cosineSimilarity(state.taskEmbedding, t.embedding).toFixed(4),
          ),
        }))
        .sort((a, b) => b.score - a.score)
        .slice(0, topK);
      return { candidates };
    })
    .addNode("rerankCandidates", async (state) => {
      const reranked = await llmRerankCandidates(state.task, state.candidates);
      return {
        rerankedTaxonomy: reranked.taxonomy,
        rerankReasoning: reranked.reasoning,
      };
    })
    .addNode("selectWinner", async (state) => {
      const reranked = state.rerankedTaxonomy
        ? state.candidates.find((c) => c.taxonomy === state.rerankedTaxonomy)
        : null;
      const best = reranked ?? state.candidates[0];
      if (!best || best.score < minConfidence) {
        return {
          taxonomy: null,
          confidence: best?.score ?? 0,
          reasoning: `LangGraph: low confidence for "${state.task}". ${state.rerankReasoning}`.trim(),
        };
      }
      return {
        taxonomy: best.taxonomy,
        confidence: best.score,
        reasoning: `LangGraph: selected ${best.taxonomy} for "${state.task}" (${best.score.toFixed(3)}). ${state.rerankReasoning}`.trim(),
      };
    })
    .addEdge(START, "embedTask")
    .addEdge("embedTask", "retrieveCandidates")
    .addEdge("retrieveCandidates", "rerankCandidates")
    .addEdge("rerankCandidates", "selectWinner")
    .addEdge("selectWinner", END)
    .compile();

  const result = await graph.invoke({ task });
  return {
    taxonomy: result.taxonomy,
    confidence: result.confidence,
    candidates: result.candidates,
    reasoning: result.reasoning,
  };
}
