# MCP Value Metadata Audit

Generated at: 2026-05-02T15:10:30Z
Sample size: 14519 entries

This audit samples MCP registries, directories, and MCPCorpus records to measure whether service-selection value metadata is exposed before invocation.

Label meanings:

- `absent`: no direct signal found in the registry/directory/corpus record.
- `human_readable`: text mentions the concept, but not in a machine-actionable schema.
- `structured_unverified`: structured field exists, but without independent verification semantics.
- `machine_actionable`: structured field is directly usable by an agent for provenance/security-style decisions.

## Overall Coverage

| Field | Absent | Human-readable | Structured | Machine-actionable |
|---|---:|---:|---:|---:|
| pricing | 14342 | 175 | 2 | 0 |
| sla_rate_limit | 14453 | 65 | 1 | 0 |
| quality_benchmark | 14325 | 194 | 0 | 0 |
| payment | 14448 | 71 | 0 | 0 |
| provenance | 0 | 1 | 0 | 14518 |
| security_trust | 1020 | 181 | 86 | 13232 |

Entries with all four core value classes (pricing + SLA/rate-limit + quality/benchmark + payment): **0 / 14519 (0.0%)**.

## By Source

| Source | n | All core classes | Any structured class | Any machine-actionable class |
|---|---:|---:|---:|---:|
| findmcp | 1 | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| glama | 300 | 0 (0.0%) | 300 (100.0%) | 300 (100.0%) |
| mcp_atlas | 43 | 0 (0.0%) | 43 (100.0%) | 43 (100.0%) |
| mcpcorpus | 13875 | 0 (0.0%) | 13875 (100.0%) | 13875 (100.0%) |
| official_mcp_registry | 300 | 0 (0.0%) | 300 (100.0%) | 300 (100.0%) |

## Source Notes

- Official MCP Registry: sampled via `https://registry.modelcontextprotocol.io/v0/servers`.
- Glama: sampled via `https://glama.ai/api/mcp/v1/servers`.
- MCP Atlas: sampled by extracting GitHub links and surrounding snippets from `https://mcpatlas.dev/browse`.
- FindMCP: homepage metadata recorded; no stable public listing endpoint was found during this audit.
- MCPCorpus: sampled from `Website/mcpso_servers_cleaned.json` on Hugging Face.

## Methodological Caveats

- This is a metadata-surface audit, not a full crawl of every linked repository or pricing page.
- Keyword patterns can over-count human-readable mentions such as a tool that manages billing data but does not expose its own pricing.
- Structured provenance/security fields are common because registries naturally contain repository, package, license, and auth metadata; this should not be confused with structured economic value metadata.
- The strongest ASM claim should focus on the low rate of complete core value coverage, especially pricing + SLA + quality + payment in the same entry.

## Sample Rows

| Source | Name | Pricing | SLA/rate | Quality | Payment | Provenance | Security/trust |
|---|---|---|---|---|---|---|---|
| official_mcp_registry | ac.inference.sh/mcp | absent | absent | absent | absent | machine_actionable | absent |
| official_mcp_registry | ac.inference.sh/mcp | absent | absent | absent | absent | machine_actionable | absent |
| official_mcp_registry | ac.tandem/docs-mcp | absent | absent | absent | absent | machine_actionable | absent |
| official_mcp_registry | ac.tandem/docs-mcp | absent | absent | absent | absent | machine_actionable | absent |
| official_mcp_registry | ac.tandem/docs-mcp | absent | absent | absent | absent | machine_actionable | absent |
| official_mcp_registry | agency.lona/trading | absent | absent | absent | absent | machine_actionable | absent |
| official_mcp_registry | ai.aarna/atars-mcp | absent | absent | absent | absent | machine_actionable | absent |
| official_mcp_registry | ai.abmeter/abmeter | absent | absent | absent | absent | machine_actionable | absent |
| official_mcp_registry | ai.adadvisor/mcp-server | absent | absent | absent | absent | machine_actionable | human_readable |
| official_mcp_registry | ai.adadvisor/mcp-server | absent | absent | absent | absent | machine_actionable | human_readable |
| official_mcp_registry | ai.adramp/google-ads | absent | absent | absent | absent | machine_actionable | absent |
| official_mcp_registry | ai.adramp/google-ads | absent | absent | absent | absent | machine_actionable | absent |
| official_mcp_registry | ai.adramp/google-ads | absent | absent | absent | absent | machine_actionable | absent |
| official_mcp_registry | ai.adramp/google-ads | absent | absent | absent | absent | machine_actionable | absent |
| official_mcp_registry | ai.adweave/meta-ads-mcp | absent | absent | absent | absent | machine_actionable | human_readable |
| official_mcp_registry | ai.agentdm/agentdm | absent | absent | absent | absent | machine_actionable | human_readable |
| official_mcp_registry | ai.agentic-news/mcp | absent | absent | absent | absent | machine_actionable | absent |
| official_mcp_registry | ai.agentrapay/agentra | absent | absent | absent | absent | machine_actionable | human_readable |
| official_mcp_registry | ai.agenttrust/mcp-server | absent | absent | absent | absent | machine_actionable | human_readable |
| official_mcp_registry | ai.aliengiraffe/spotdb | absent | absent | absent | absent | machine_actionable | human_readable |
| official_mcp_registry | ai.alpic.mcp/alpic-mcp | absent | absent | absent | absent | machine_actionable | absent |
| official_mcp_registry | ai.alpic.test/test-mcp-server | absent | absent | absent | absent | machine_actionable | absent |
| official_mcp_registry | ai.ankimcp/anki-mcp-server | absent | absent | absent | absent | machine_actionable | absent |
| official_mcp_registry | ai.ankimcp/anki-mcp-server | absent | absent | absent | absent | machine_actionable | absent |
| official_mcp_registry | ai.ankimcp/anki-mcp-server | absent | absent | absent | absent | machine_actionable | absent |
| official_mcp_registry | ai.ankimcp/anki-mcp-server-addon | absent | absent | absent | absent | machine_actionable | absent |
| official_mcp_registry | ai.anomalyarmor/armor-mcp | absent | absent | human_readable | absent | machine_actionable | human_readable |
| official_mcp_registry | ai.anzenna/anzenna | absent | absent | absent | absent | machine_actionable | absent |
| official_mcp_registry | ai.appdeploy/deploy-app | absent | absent | absent | absent | machine_actionable | absent |
| official_mcp_registry | ai.artidrop/artidrop | absent | absent | absent | absent | machine_actionable | absent |
| official_mcp_registry | ai.artidrop/artidrop | absent | absent | absent | absent | machine_actionable | absent |
| official_mcp_registry | ai.auteng/docs | absent | absent | absent | absent | machine_actionable | absent |
| official_mcp_registry | ai.auteng/mcp | absent | absent | absent | absent | machine_actionable | absent |
| official_mcp_registry | ai.auteng/mcp | absent | absent | absent | absent | machine_actionable | absent |
| official_mcp_registry | ai.autoblocks/contextlayer-mcp | absent | absent | absent | absent | machine_actionable | absent |
| official_mcp_registry | ai.autoblocks/ctxl | absent | absent | absent | absent | machine_actionable | absent |
| official_mcp_registry | ai.autoblocks/ctxl-mcp | absent | absent | absent | absent | machine_actionable | absent |
| official_mcp_registry | ai.bankee/inferventis-mcp | absent | absent | absent | absent | machine_actionable | human_readable |
| official_mcp_registry | ai.baselight/baselight | absent | absent | absent | absent | machine_actionable | human_readable |
| official_mcp_registry | ai.bezal/local-commerce | absent | absent | absent | absent | machine_actionable | absent |
