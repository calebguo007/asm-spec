/**
 * ASM × Circle Nanopayments — Benchmark Task Generator
 *
 * Generates the 50-subtask Marketing Campaign scenario used in the
 * hackathon benchmark demo. See docs/demo-scenario.md for full spec.
 *
 * Output: 50 realistic subtasks spanning 15 categories, each with a
 * target price ≤ $0.005 (hackathon requirement: per-action ≤ $0.01).
 *
 * **Taxonomy contract** — every `taxonomy` string below MUST match a
 * taxonomy that has ≥ 2 providers in the ASM registry (`manifests/*`).
 * That's what makes the "pick 1 from 2-5 providers" story real: for every task, the
 * scorer has ≥ 2 candidates to rank.
 *
 * Usage:
 *   import { generateBenchmarkTasks } from "./benchmark-tasks.js";
 *   const tasks = generateBenchmarkTasks();
 *   // tasks.length === 50
 */

// ── Types ────────────────────────────────────────────────────

/** A category of agent-callable service. Matches (semantically) a
 *  registry taxonomy that has ≥ 2 providers. */
export type TaskCategory =
  | "image-gen"       // ai.vision.image_generation
  | "copywrite"       // ai.llm.chat
  | "translate"       // ai.nlp.translation
  | "tts"             // ai.audio.tts
  | "video-gen"       // ai.video.generation
  | "embed"           // ai.llm.embedding     (was: sentiment)
  | "scrape"          // tool.data.scraping
  | "browse"          // tool.automation.browser  (was: ocr)
  | "code-gen"        // ai.code.completion
  | "spreadsheet"     // tool.productivity.spreadsheet  (was: data-label)
  | "transcribe"      // ai.audio.stt         (was: summarize)
  | "search"          // tool.data.search
  | "todo"            // tool.productivity.todo  (was: calendar)
  | "database"        // infra.database.postgres  (was: storage)
  | "deploy";         // tool.devops.deployment

/** One subtask the marketing agent needs to execute. */
export interface BenchmarkSubtask {
  /** 1-indexed ordinal in the 50-task run */
  id: number;
  /** Service category this subtask belongs to */
  category: TaskCategory;
  /** ASM taxonomy string (used by scorer to find candidates). Must match a registry taxonomy with ≥ 2 providers. */
  taxonomy: string;
  /** Natural-language prompt the agent would send */
  prompt: string;
  /** Target per-call price in USDC (display/narrative only) */
  targetPriceUsd: number;
}

// ── Category distribution (must sum to 50) ───────────────────

interface CategorySpec {
  category: TaskCategory;
  taxonomy: string;
  count: number;
  targetPriceUsd: number;
  /** Prompt templates; generator rotates through these */
  prompts: string[];
}

const CATEGORY_SPECS: CategorySpec[] = [
  {
    category: "image-gen",
    taxonomy: "ai.vision.image_generation",
    count: 4,
    targetPriceUsd: 0.004,
    prompts: [
      "Hero image, ADHD user working peacefully, calm palette, 1024x1024",
      "App icon, focus bear mascot, flat design, 512x512",
      "Social ad banner, product UI screenshot + tagline, 1200x628",
      "Thumbnail for short video, bold text overlay, 720x1280",
    ],
  },
  {
    category: "copywrite",
    taxonomy: "ai.llm.chat",
    count: 6,
    targetPriceUsd: 0.002,
    prompts: [
      "Instagram caption, 150 chars, witty, target ADHD adults 25-40",
      "Twitter/X post, 240 chars, product launch announcement",
      "LinkedIn post, 500 chars, founder-voice, tell the ADHD pain point",
      "TikTok hook line, 8 words, stop-the-scroll energy",
      "Email subject line, under 50 chars, curiosity-driven",
      "Product Hunt tagline, under 60 chars, benefit-led",
    ],
  },
  {
    category: "translate",
    taxonomy: "ai.nlp.translation",
    count: 6,
    targetPriceUsd: 0.001,
    prompts: [
      "Translate launch caption to Japanese, keep witty tone",
      "Translate to Simplified Chinese, localize idioms",
      "Translate to Spanish (LATAM), casual register",
      "Translate to German, professional tone",
      "Translate to Brazilian Portuguese, friendly tone",
      "Translate to Korean, preserve product name in katakana-style",
    ],
  },
  {
    category: "tts",
    taxonomy: "ai.audio.tts",
    count: 3,
    targetPriceUsd: 0.003,
    prompts: [
      "Voiceover script A, female voice, 30s, warm conversational",
      "Voiceover script B, male voice, 15s, energetic",
      "Short tag jingle voice, neutral, 8s",
    ],
  },
  {
    category: "video-gen",
    taxonomy: "ai.video.generation",
    count: 3,
    targetPriceUsd: 0.005,
    prompts: [
      "6s product demo, screen recording style, highlight timer feature",
      "6s lifestyle clip, ADHD user feeling focused at desk",
      "3s logo sting, bear mascot animates, brand palette",
    ],
  },
  {
    category: "embed",
    taxonomy: "ai.llm.embedding",
    count: 5,
    targetPriceUsd: 0.001,
    prompts: [
      "Embed 10 caption variants to find most semantically distinct 3",
      "Embed competitor taglines to cluster their positioning angles",
      "Embed landing-page headline candidates, find closest to 'relief'",
      "Embed 20 Reddit pain-point quotes, cluster into top 5 themes",
      "Embed founder-voice LinkedIn drafts, pick the most on-brand one",
    ],
  },
  {
    category: "scrape",
    taxonomy: "tool.data.scraping",
    count: 5,
    targetPriceUsd: 0.002,
    prompts: [
      "Scrape competitor Focusmate latest 10 posts + engagement",
      "Scrape Reddit r/ADHD top posts of past week mentioning productivity apps",
      "Scrape Product Hunt ADHD-related launches past 30 days",
      "Scrape App Store reviews for top 3 ADHD apps, latest 20 each",
      "Scrape YouTube titles of ADHD productivity videos past 7 days",
    ],
  },
  {
    category: "browse",
    taxonomy: "tool.automation.browser",
    count: 2,
    targetPriceUsd: 0.003,
    prompts: [
      "Open competitor pricing page in headless browser, capture full-page screenshot",
      "Automate Product Hunt submission flow draft, screenshot each step",
    ],
  },
  {
    category: "code-gen",
    taxonomy: "ai.code.completion",
    count: 4,
    targetPriceUsd: 0.003,
    prompts: [
      "Generate Google Analytics 4 snippet for campaign tracking",
      "Generate TikTok Pixel install snippet for the landing page",
      "Generate UTM-tagged link builder helper in TS",
      "Generate webhook handler for Circle payment confirmation",
    ],
  },
  {
    category: "spreadsheet",
    taxonomy: "tool.productivity.spreadsheet",
    count: 3,
    targetPriceUsd: 0.002,
    prompts: [
      "Tag 100 App Store review snippets by sentiment (pos/neg/neutral) in a sheet",
      "Log 50 Reddit comments + pain-point category into tracking sheet",
      "Build competitor feature-overlap matrix, FocusBear vs 5 rivals",
    ],
  },
  {
    category: "transcribe",
    taxonomy: "ai.audio.stt",
    count: 3,
    targetPriceUsd: 0.002,
    prompts: [
      "Transcribe 3-min competitor Focusmate demo video for theme extraction",
      "Transcribe ADHD-creator TikTok voiceover (30s) to match their tone",
      "Transcribe ADHD productivity podcast clip (90s) for quotable lines",
    ],
  },
  {
    category: "search",
    taxonomy: "tool.data.search",
    count: 3,
    targetPriceUsd: 0.002,
    prompts: [
      "Find top 5 ADHD productivity blogs with DA > 40",
      "Find ADHD-focused newsletter sponsorship opportunities",
      "Find TikTok creators in ADHD niche with 10k-100k followers",
    ],
  },
  {
    category: "todo",
    taxonomy: "tool.productivity.todo",
    count: 1,
    targetPriceUsd: 0.001,
    prompts: [
      "Create launch-day checklist: 8 tasks w/ owners + due times across US/EU/JP timezones",
    ],
  },
  {
    category: "database",
    taxonomy: "infra.database.postgres",
    count: 1,
    targetPriceUsd: 0.001,
    prompts: [
      "Insert campaign_metrics row: run_id, total_cost, txs, ts — for later dashboard query",
    ],
  },
  {
    category: "deploy",
    taxonomy: "tool.devops.deployment",
    count: 1,
    targetPriceUsd: 0.002,
    prompts: [
      "Deploy landing page to production, return public URL",
    ],
  },
];

// ── Generator ────────────────────────────────────────────────

export interface GenerateOptions {
  /**
   * If true, interleave categories so the task stream doesn't look
   * blocky (all image-gen, then all copywrite...). Default: true.
   */
  interleave?: boolean;
}

/**
 * Generate all 50 benchmark subtasks.
 *
 * The total is guaranteed to be 50 (validated at runtime).
 * By default tasks are interleaved across categories for a more
 * realistic agent-workflow appearance.
 */
export function generateBenchmarkTasks(
  opts: GenerateOptions = {},
): BenchmarkSubtask[] {
  const { interleave = true } = opts;

  // Validate distribution sums to 50
  const total = CATEGORY_SPECS.reduce((sum, s) => sum + s.count, 0);
  if (total !== 50) {
    throw new Error(
      `Benchmark task distribution must sum to 50, got ${total}. ` +
      `Fix CATEGORY_SPECS in benchmark-tasks.ts.`,
    );
  }

  // Expand each spec into individual tasks
  const blocks: BenchmarkSubtask[][] = CATEGORY_SPECS.map((spec) => {
    const out: BenchmarkSubtask[] = [];
    for (let i = 0; i < spec.count; i++) {
      out.push({
        id: 0, // assigned after interleaving
        category: spec.category,
        taxonomy: spec.taxonomy,
        prompt: spec.prompts[i % spec.prompts.length],
        targetPriceUsd: spec.targetPriceUsd,
      });
    }
    return out;
  });

  // Flatten, optionally interleaved
  const flat: BenchmarkSubtask[] = interleave
    ? interleaveBlocks(blocks)
    : blocks.flat();

  // Assign ordinal IDs (1-indexed)
  return flat.map((task, i) => ({ ...task, id: i + 1 }));
}

/**
 * Round-robin across blocks so categories are mixed. Preserves the
 * declared distribution counts exactly.
 */
function interleaveBlocks<T>(blocks: T[][]): T[] {
  const queues = blocks.map((b) => [...b]);
  const out: T[] = [];
  let remaining = queues.reduce((s, q) => s + q.length, 0);
  while (remaining > 0) {
    for (const q of queues) {
      if (q.length > 0) {
        out.push(q.shift() as T);
        remaining--;
      }
    }
  }
  return out;
}

/** Summarise generated tasks for logging. */
export function summarizeTasks(tasks: BenchmarkSubtask[]): {
  total: number;
  byCategory: Record<string, number>;
  totalTargetCostUsd: number;
} {
  const byCategory: Record<string, number> = {};
  let totalTargetCostUsd = 0;
  for (const t of tasks) {
    byCategory[t.category] = (byCategory[t.category] ?? 0) + 1;
    totalTargetCostUsd += t.targetPriceUsd;
  }
  return {
    total: tasks.length,
    byCategory,
    totalTargetCostUsd: Number(totalTargetCostUsd.toFixed(4)),
  };
}
