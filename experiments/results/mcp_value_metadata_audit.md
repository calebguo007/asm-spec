# MCP Value Metadata Audit

Generated at: 2026-05-02T14:10:48Z
Sample size: 600 entries

This audit samples MCP registries, directories, and MCPCorpus records to measure whether service-selection value metadata is exposed before invocation.

Label meanings:

- `absent`: no direct signal found in the registry/directory/corpus record.
- `human_readable`: text mentions the concept, but not in a machine-actionable schema.
- `structured_unverified`: structured field exists, but without independent verification semantics.
- `machine_actionable`: structured field is directly usable by an agent for provenance/security-style decisions.

## Overall Coverage

| Field | Absent | Human-readable | Structured | Machine-actionable |
|---|---:|---:|---:|---:|
| pricing | 539 | 61 | 0 | 0 |
| sla_rate_limit | 590 | 9 | 1 | 0 |
| quality_benchmark | 136 | 47 | 417 | 0 |
| payment | 584 | 16 | 0 | 0 |
| provenance | 0 | 1 | 0 | 599 |
| security_trust | 120 | 71 | 32 | 377 |

Entries with all four core value classes (pricing + SLA/rate-limit + quality/benchmark + payment): **0 / 600 (0.0%)**.

## By Source

| Source | n | All core classes | Any structured class | Any machine-actionable class |
|---|---:|---:|---:|---:|
| findmcp | 1 | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) |
| glama | 138 | 0 (0.0%) | 138 (100.0%) | 138 (100.0%) |
| mcp_atlas | 42 | 0 (0.0%) | 42 (100.0%) | 42 (100.0%) |
| mcpcorpus | 279 | 0 (0.0%) | 279 (100.0%) | 279 (100.0%) |
| official_mcp_registry | 140 | 0 (0.0%) | 140 (100.0%) | 140 (100.0%) |

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
| official_mcp_registry | ai.haymon/dbmcp | absent | absent | absent | absent | machine_actionable | absent |
| mcp_atlas | neondatabase/mcp-server-neon | human_readable | absent | human_readable | human_readable | machine_actionable | human_readable |
| mcpcorpus | agentcare-mcp-azalea | absent | absent | structured_unverified | absent | machine_actionable | machine_actionable |
| mcpcorpus | liveblocks_liveblocks-mcp-server | absent | absent | structured_unverified | absent | machine_actionable | machine_actionable |
| official_mcp_registry | ai.geodesiclabs/governance-platform | absent | absent | absent | absent | machine_actionable | absent |
| glama | @prosodyai/mcp-docs | absent | absent | structured_unverified | absent | machine_actionable | machine_actionable |
| mcpcorpus | slack-mcp-server-by-cdata | absent | absent | structured_unverified | absent | machine_actionable | machine_actionable |
| mcpcorpus | mcp-server-developer-tool | absent | absent | structured_unverified | absent | machine_actionable | machine_actionable |
| mcpcorpus | payai-mcp-server | absent | absent | structured_unverified | absent | machine_actionable | machine_actionable |
| mcpcorpus | jacobgoren-sb_workato-mcp-server | absent | absent | structured_unverified | absent | machine_actionable | machine_actionable |
| mcpcorpus | cambridge-dict-mcp-server | absent | absent | structured_unverified | absent | machine_actionable | machine_actionable |
| mcpcorpus | mcp-servers | absent | absent | structured_unverified | absent | machine_actionable | machine_actionable |
| mcpcorpus | alphaguts | absent | absent | structured_unverified | absent | machine_actionable | machine_actionable |
| mcpcorpus | plumed2-mcp-server | absent | absent | structured_unverified | absent | machine_actionable | machine_actionable |
| mcpcorpus | Google MCP Remote | absent | absent | structured_unverified | absent | machine_actionable | machine_actionable |
| glama | Arthas MCP Proxy | absent | absent | structured_unverified | absent | machine_actionable | structured_unverified |
| official_mcp_registry | ac.tandem/docs-mcp | absent | absent | absent | absent | machine_actionable | absent |
| official_mcp_registry | ai.donethat/donethat | absent | absent | absent | absent | machine_actionable | absent |
| official_mcp_registry | ai.haymon/database | absent | absent | absent | absent | machine_actionable | absent |
| glama | mcp-patent | absent | absent | structured_unverified | absent | machine_actionable | structured_unverified |
| official_mcp_registry | ai.filegraph/document-processing | absent | absent | absent | absent | machine_actionable | absent |
| mcpcorpus | notify-completion-mcp-server | absent | absent | structured_unverified | absent | machine_actionable | machine_actionable |
| official_mcp_registry | ai.adramp/google-ads | absent | absent | absent | absent | machine_actionable | absent |
| mcpcorpus | mixelpixx_Google-Search-MCP-Server | absent | absent | structured_unverified | absent | machine_actionable | machine_actionable |
| mcp_atlas | semgrep/mcp-server-semgrep | human_readable | absent | human_readable | human_readable | machine_actionable | human_readable |
| glama | obscura-mcp | absent | absent | structured_unverified | absent | machine_actionable | machine_actionable |
| mcpcorpus | remote-mcp-server | absent | absent | structured_unverified | absent | machine_actionable | machine_actionable |
| glama | memtrace | absent | absent | structured_unverified | absent | machine_actionable | structured_unverified |
| mcpcorpus | uncover-mcp | absent | absent | structured_unverified | absent | machine_actionable | machine_actionable |
| mcpcorpus | js-mcp-server | absent | absent | structured_unverified | absent | machine_actionable | machine_actionable |
| mcpcorpus | agentic-mcp-client | absent | absent | structured_unverified | absent | machine_actionable | machine_actionable |
| mcpcorpus | openapi-mcp-server | absent | absent | structured_unverified | absent | machine_actionable | machine_actionable |
| official_mcp_registry | ai.datamerge/mcp | human_readable | absent | absent | absent | machine_actionable | human_readable |
| mcpcorpus | vidu-mcp-server | absent | absent | structured_unverified | absent | machine_actionable | machine_actionable |
| official_mcp_registry | ai.example4/xmp4 | absent | absent | absent | absent | machine_actionable | absent |
| mcpcorpus | GBD-MCP-Server | absent | absent | structured_unverified | absent | machine_actionable | machine_actionable |
| mcpcorpus | pixeltable-mcp-server | absent | absent | structured_unverified | absent | machine_actionable | machine_actionable |
| glama | Packrift MCP Server | human_readable | absent | structured_unverified | human_readable | machine_actionable | machine_actionable |
| mcpcorpus | mcp-ntopng | absent | absent | structured_unverified | absent | machine_actionable | machine_actionable |
| mcpcorpus | aws-boto3-mcp-private | absent | absent | structured_unverified | absent | machine_actionable | machine_actionable |
