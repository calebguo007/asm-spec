import * as fs from "fs";
import * as path from "path";
import type { TaxonomyRecord } from "./index.js";

/**
 * Rich per-taxonomy metadata: description is a prose sentence that blends
 * what the service does with canonical user-facing use-cases; aliases are
 * common phrasings a user/agent might actually say.
 *
 * `buildIndex()` embeds `taxonomy + description + aliases` together, so both
 * fields directly drive semantic retrieval quality.
 */
type CatalogEntry = { description: string; aliases: string[] };

const CATALOG: Record<string, CatalogEntry> = {
  // ---- AI ----
  "ai.llm.chat": {
    description:
      "Large language model chat and text generation. Produces freeform writing: social-media captions (Instagram, Twitter/X, LinkedIn), blog posts, ad copy, email drafts, product descriptions, founder-voice posts, summaries, Q&A answers, witty one-liners, headlines, slogans.",
    aliases: [
      "LLM chat", "chatbot", "conversational AI", "text generation", "copywriting",
      "Instagram caption", "Twitter post", "X post", "LinkedIn post", "social media copy",
      "ad copy", "headline", "tagline", "slogan", "email draft", "blog post",
      "summarization", "Q&A", "answer generation", "rewrite", "paraphrase",
    ],
  },
  "ai.llm.embedding": {
    description:
      "Text embedding / vectorization. Turns sentences or documents into dense vectors for semantic search, retrieval-augmented generation (RAG), similarity, clustering, and recommendation.",
    aliases: [
      "text embedding", "vectorization", "semantic vectors", "sentence embeddings",
      "RAG embeddings", "similarity search vectors",
    ],
  },
  "ai.code.completion": {
    description:
      "Code generation and completion. Produces code snippets, installation scripts, analytics tags (Google Analytics, TikTok Pixel, Facebook Pixel), tracking snippets, unit tests, refactored code, code explanations, SDK usage examples, config files, SQL queries written from natural language.",
    aliases: [
      "code generation", "code completion", "autocomplete", "coding assistant",
      "generate snippet", "install snippet", "tracking pixel snippet",
      "Google Analytics snippet", "TikTok Pixel", "Facebook Pixel",
      "write code", "generate SQL", "write function", "unit test generation",
    ],
  },
  "ai.vision.image_generation": {
    description:
      "AI image generation from text prompts. Produces hero images, product shots, illustrations, logos, mascots, marketing visuals, lifestyle images, avatars, banners, thumbnails, calm/minimal/vibrant palette imagery, 1024x1024 and larger PNG/JPG outputs.",
    aliases: [
      "image generation", "text to image", "AI art", "generate image",
      "hero image", "product image", "illustration", "logo image", "mascot art",
      "marketing visual", "lifestyle photo", "Midjourney-style", "DALL-E-style",
      "render image", "creative visual", "banner image",
    ],
  },
  "ai.video.generation": {
    description:
      "AI video generation from text or image prompts. Produces short clips (3-10 seconds), product demos, logo stings, lifestyle clips, screen-recording-style demos, animated mascots, reels, b-roll, marketing videos, brand animations.",
    aliases: [
      "video generation", "text to video", "AI video",
      "generate clip", "product demo video", "logo sting", "lifestyle clip",
      "animated mascot", "reel", "short video", "marketing video",
      "Runway-style", "Sora-style", "screen recording style",
    ],
  },
  "ai.audio.tts": {
    description:
      "Text-to-speech synthesis. Turns written scripts into spoken audio: voiceovers, narration, ads, podcast intros, IVR prompts, audiobook snippets, multilingual voiceover.",
    aliases: [
      "text to speech", "TTS", "voiceover", "narration", "voice synthesis",
      "AI voice", "speak text", "script to audio", "ElevenLabs-style voice",
    ],
  },
  "ai.audio.stt": {
    description:
      "Speech-to-text transcription. Converts audio recordings, podcasts, interviews, meetings, voice notes, and call recordings into written transcripts with timestamps and speaker labels.",
    aliases: [
      "speech to text", "STT", "transcription", "transcribe audio", "audio to text",
      "meeting transcript", "podcast transcript", "voice note transcription",
      "Whisper-style transcription",
    ],
  },
  "ai.vision.ocr": {
    description:
      "Optical character recognition. Extracts text from images, PDFs, scanned documents, receipts, screenshots, handwritten notes, signage, and whiteboards.",
    aliases: [
      "OCR", "text extraction from image", "scan document",
      "read receipt", "extract text from PDF image", "handwriting recognition",
    ],
  },
  "ai.nlp.translation": {
    description:
      "Natural-language translation. Translates text between languages, localizes product copy and marketing content, supports multilingual campaigns and i18n.",
    aliases: [
      "translate", "translation", "localization", "i18n",
      "English to Spanish", "multilingual", "language conversion",
    ],
  },

  // ---- TOOL: data ----
  "tool.data.search": {
    description:
      "Web search and retrieval. Finds blogs, articles, newsletters, forum threads, sponsorship opportunities, competitor sites, top-N lists (e.g. top 5 blogs with DA>40), domain research results from the open web.",
    aliases: [
      "web search", "search api", "find websites", "find blogs",
      "find newsletters", "search results", "SERP api",
      "top 5 blogs", "sponsorship research", "domain authority lookup",
      "competitor search", "Brave search", "SerpAPI", "Exa search",
    ],
  },
  "tool.data.scraping": {
    description:
      "Website scraping and structured extraction. Crawls pages, extracts product info, pricing tables, reviews, article bodies, sitemaps, and converts HTML into clean markdown or JSON.",
    aliases: [
      "web scraping", "crawler", "scrape website", "extract page data",
      "HTML to markdown", "Firecrawl-style", "article extraction",
      "product listing scrape", "sitemap crawl",
    ],
  },
  "tool.data.screenshot": {
    description:
      "Webpage screenshot capture. Generates PNG/JPG screenshots of rendered web pages (full-page or viewport) for QA, monitoring, social previews, and documentation.",
    aliases: [
      "screenshot website", "page screenshot", "render page to image",
      "full-page screenshot", "social preview image",
    ],
  },
  "tool.data.pdf": {
    description:
      "PDF generation and parsing. Renders HTML/reports into PDFs (invoices, receipts, summaries), extracts text/tables from existing PDFs, merges and watermarks PDFs.",
    aliases: [
      "generate PDF", "HTML to PDF", "invoice PDF", "receipt PDF",
      "parse PDF", "extract PDF text", "PDF to text",
    ],
  },
  "tool.data.analytics": {
    description:
      "Product / marketing analytics ingestion and querying. Records events, sessions, funnels, conversion metrics, campaign performance across ad channels.",
    aliases: [
      "analytics", "event tracking", "funnel analysis", "conversion metrics",
      "marketing analytics", "Mixpanel-style", "Amplitude-style",
    ],
  },
  "tool.data.visualization": {
    description:
      "Chart and dashboard rendering. Produces bar/line/pie/sankey charts, KPI dashboards, embeddable visualizations from tabular data.",
    aliases: [
      "chart", "graph", "data viz", "dashboard render",
      "bar chart", "sankey diagram", "plot data",
    ],
  },
  "tool.data.conversion": {
    description:
      "File / format conversion. Converts between document formats (docx↔pdf, csv↔xlsx, html↔markdown, image format conversions).",
    aliases: [
      "file conversion", "format convert", "docx to pdf", "csv to xlsx",
      "png to jpg", "image format", "media transcode",
    ],
  },
  "tool.data.weather": {
    description:
      "Weather data lookup. Retrieves current conditions, forecasts, and historical weather by location.",
    aliases: [
      "weather api", "forecast", "current weather", "weather lookup",
    ],
  },
  "tool.data.geolocation": {
    description:
      "Geolocation and geocoding. Converts IP addresses, ZIP codes, or address strings into lat/lng; reverse-geocodes coordinates into places; computes distance and timezones.",
    aliases: [
      "geocoding", "IP geolocation", "lat lng lookup", "reverse geocode",
      "timezone lookup", "distance calculation",
    ],
  },

  // ---- TOOL: communication ----
  "tool.communication.email": {
    description:
      "Transactional and marketing email delivery. Sends campaign blasts, launch announcements, welcome flows, receipts; handles bounces, opens, clicks.",
    aliases: [
      "send email", "email delivery", "SMTP", "transactional email",
      "marketing email", "email blast", "SendGrid-style", "Resend",
    ],
  },
  "tool.communication.sms": {
    description:
      "SMS messaging. Sends text messages, OTP verification codes, alerts, appointment reminders.",
    aliases: [
      "SMS", "text message", "OTP SMS", "appointment reminder SMS", "Twilio SMS",
    ],
  },
  "tool.communication.chat": {
    description:
      "Team / user chat messaging. Posts messages to Slack, Discord, Teams channels; direct-messages users; reads thread history.",
    aliases: [
      "Slack message", "Discord message", "team chat", "post to channel",
      "chat notification", "post to Slack",
    ],
  },

  // ---- TOOL: productivity ----
  "tool.productivity.todo": {
    description:
      "Task list / to-do management. Creates checklists, launch-day task lists, action items, assigns owners, tracks due dates, marks tasks complete.",
    aliases: [
      "todo list", "task list", "checklist", "action items",
      "launch day checklist", "task tracker", "to-do management",
    ],
  },
  "tool.productivity.calendar": {
    description:
      "Calendar events. Creates, updates, lists calendar events; books meetings; handles timezone-aware scheduling.",
    aliases: [
      "calendar event", "book meeting", "schedule event",
      "Google Calendar", "Outlook calendar",
    ],
  },
  "tool.productivity.scheduling": {
    description:
      "Booking / appointment scheduling. Provides bookable time slots, Calendly-style links, availability lookup, rescheduling, cancellation.",
    aliases: [
      "appointment booking", "Calendly", "schedule meeting link",
      "availability", "book slot",
    ],
  },
  "tool.productivity.document": {
    description:
      "Document editing and generation. Creates and edits Google Docs / Notion pages / Word documents from prompts; formats long-form text.",
    aliases: [
      "document editor", "Google Docs", "Notion page", "Word document",
      "generate document", "long-form document",
    ],
  },
  "tool.productivity.spreadsheet": {
    description:
      "Spreadsheet operations. Reads/writes Google Sheets, Excel files; computes formulas, pivot tables, data cleanup, CSV manipulation.",
    aliases: [
      "spreadsheet", "Google Sheets", "Excel", "CSV manipulation",
      "pivot table", "xlsx edit",
    ],
  },
  "tool.productivity.forms": {
    description:
      "Form builder and response collection. Builds intake forms, surveys, waitlist signups; reads Typeform / Google Forms responses.",
    aliases: [
      "form builder", "survey", "Typeform", "Google Forms", "waitlist signup",
    ],
  },
  "tool.productivity.project": {
    description:
      "Project management. Creates issues / tickets / cards in Jira, Linear, Asana, Trello; tracks sprints, epics, assignments.",
    aliases: [
      "project management", "Jira ticket", "Linear issue", "Asana task", "Trello card",
      "sprint planning",
    ],
  },
  "tool.productivity.knowledge": {
    description:
      "Knowledge base / wiki. Reads and writes Confluence, Notion databases, internal docs; retrieves company-specific facts.",
    aliases: [
      "knowledge base", "wiki", "Confluence", "Notion database",
      "internal docs lookup",
    ],
  },

  // ---- TOOL: business / automation / payment ----
  "tool.business.crm": {
    description:
      "Customer relationship management. Reads/writes Salesforce, HubSpot contacts, deals, pipelines, activities.",
    aliases: [
      "CRM", "Salesforce", "HubSpot", "contact management", "deal pipeline",
    ],
  },
  "tool.automation.browser": {
    description:
      "Browser automation. Drives headless Chromium / Playwright / Puppeteer to fill forms, click buttons, scrape gated content, run visual tests.",
    aliases: [
      "browser automation", "Playwright", "Puppeteer", "headless browser",
      "web automation", "fill form", "click element",
    ],
  },
  "tool.payment.processing": {
    description:
      "Payment processing for fiat or stablecoins. Charges credit cards, handles subscriptions, issues refunds, emits invoices (Stripe, Adyen, Circle).",
    aliases: [
      "payment", "Stripe charge", "credit card payment", "subscription billing",
      "refund", "invoice",
    ],
  },

  // ---- TOOL: devops ----
  "tool.devops.ci": {
    description:
      "Continuous integration. Triggers builds, runs test suites, reports pass/fail from GitHub Actions, CircleCI, GitLab CI.",
    aliases: [
      "CI pipeline", "GitHub Actions", "CircleCI", "build trigger",
      "run tests in CI",
    ],
  },
  "tool.devops.deployment": {
    description:
      "App deployment and hosting. Ships releases to Vercel, Netlify, Render, Fly, Cloudflare; runs blue/green, canary, rollback.",
    aliases: [
      "deploy", "deployment", "Vercel deploy", "Netlify deploy",
      "ship release", "hosting", "canary deploy", "rollback",
    ],
  },
  "tool.devops.logging": {
    description:
      "Log aggregation and search. Ships application logs to Datadog, Loki, ELK; queries by level, service, timestamp.",
    aliases: [
      "log aggregation", "Datadog logs", "Loki", "ELK", "application logs",
    ],
  },
  "tool.devops.monitoring": {
    description:
      "Application performance monitoring and alerting. Tracks latency, error rate, uptime; pages on-call when thresholds breach.",
    aliases: [
      "APM", "monitoring", "uptime check", "error tracking", "alerting",
      "Sentry", "Datadog APM", "New Relic",
    ],
  },

  // ---- INFRA: database ----
  "infra.database.postgres": {
    description:
      "Relational SQL database (PostgreSQL). Inserts rows (e.g. campaign_metrics, orders, events), runs ACID transactions, executes SELECT/INSERT/UPDATE/DELETE, joins, indexes.",
    aliases: [
      "postgres", "PostgreSQL", "SQL database", "relational database",
      "insert row", "SQL insert", "transactional database", "RDS", "Supabase Postgres",
    ],
  },
  "infra.database.kv": {
    description:
      "Key-value datastore. Caches session tokens, feature flags, rate-limit counters, ephemeral data (Redis, DynamoDB, Cloudflare KV).",
    aliases: [
      "key value store", "Redis", "DynamoDB", "Cloudflare KV",
      "cache", "session store",
    ],
  },
  "infra.database.vector": {
    description:
      "Vector database for embedding search. Stores and queries high-dimensional vectors for RAG, semantic search, similarity (Pinecone, Weaviate, pgvector).",
    aliases: [
      "vector database", "Pinecone", "Weaviate", "pgvector",
      "embedding search", "similarity search db",
    ],
  },

  // ---- INFRA: compute ----
  "infra.compute.gpu": {
    description:
      "GPU compute rental. Runs GPU-heavy training or inference jobs (RunPod, Modal, Lambda Labs) for fine-tuning, custom model hosting, batch inference.",
    aliases: [
      "GPU rental", "GPU compute", "training GPU", "RunPod",
      "Modal GPU", "Lambda Labs", "inference cluster",
    ],
  },
  "infra.compute.sandbox": {
    description:
      "Isolated code execution sandbox. Runs untrusted Python / Node / shell code in ephemeral containers (E2B, Modal sandbox, CodeInterpreter-style).",
    aliases: [
      "code sandbox", "E2B", "code interpreter", "python sandbox",
      "untrusted code execution", "ephemeral container",
    ],
  },
  "infra.compute.serverless": {
    description:
      "Serverless function runtime. Runs short request/response handlers on demand (AWS Lambda, Cloudflare Workers, Vercel Functions).",
    aliases: [
      "serverless function", "Lambda", "Cloudflare Workers",
      "Vercel Functions", "function as a service",
    ],
  },

  // ---- INFRA: storage / network / auth / messaging / security ----
  "infra.storage.object": {
    description:
      "Object storage. Uploads and serves files, images, videos, backups (S3, R2, GCS).",
    aliases: [
      "object storage", "S3", "R2", "GCS", "file upload", "blob storage",
    ],
  },
  "infra.network.dns": {
    description:
      "DNS management. Creates, updates, queries DNS records (A, CNAME, TXT, MX) for domains.",
    aliases: [
      "DNS", "DNS record", "domain config", "A record", "CNAME", "TXT record",
    ],
  },
  "infra.auth.identity": {
    description:
      "Authentication / identity provider. Issues user login, OAuth flows, JWT tokens, magic links, session cookies (Auth0, Clerk, Cognito).",
    aliases: [
      "auth", "authentication", "OAuth", "JWT", "login", "user identity",
      "Auth0", "Clerk", "Cognito",
    ],
  },
  "infra.messaging.queue": {
    description:
      "Message queue / event bus. Publishes and consumes messages for async workflows (SQS, Kafka, RabbitMQ, NATS).",
    aliases: [
      "message queue", "event bus", "SQS", "Kafka", "RabbitMQ", "pub/sub",
    ],
  },
  "infra.security.secrets": {
    description:
      "Secret management. Stores and fetches API keys, DB passwords, tokens (AWS Secrets Manager, HashiCorp Vault, Doppler).",
    aliases: [
      "secrets manager", "Vault", "API key storage", "credential storage",
      "Doppler", "AWS Secrets Manager",
    ],
  },
};

function defaultEntry(taxonomy: string): CatalogEntry {
  const pretty = taxonomy.split(".").slice(1).join(" ").replaceAll("_", " ");
  return {
    description: `Service category for ${pretty}`,
    aliases: [],
  };
}

export function loadTaxonomyCatalogFromManifests(repoRoot: string): TaxonomyRecord[] {
  const manifestDir = path.join(repoRoot, "manifests");
  const files = fs.readdirSync(manifestDir).filter((f) => f.endsWith(".asm.json"));
  const set = new Set<string>();
  for (const file of files) {
    const fullPath = path.join(manifestDir, file);
    const raw = fs.readFileSync(fullPath, "utf-8");
    const parsed = JSON.parse(raw) as { taxonomy?: string };
    if (parsed.taxonomy) set.add(parsed.taxonomy);
  }
  return Array.from(set)
    .sort()
    .map((taxonomy) => {
      const entry = CATALOG[taxonomy] ?? defaultEntry(taxonomy);
      return {
        taxonomy,
        description: entry.description,
        aliases: entry.aliases,
      };
    });
}
