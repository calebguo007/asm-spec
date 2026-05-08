# ASM for MCP Aggregators

MCP aggregators such as Glama, MCP Atlas, MCP Find, MCPCorpus-style datasets, and private enterprise catalogs can consume ASM without changing MCP invocation. ASM is an indexing and settlement layer: it helps agents decide which service is worth calling.

## Minimal indexing pipeline

```text
fetch server.json
  -> read _meta.io.modelcontextprotocol.registry/publisher-provided.asm
  -> if missing, mark value_metadata_status = missing
  -> if present, validate against schema/asm-v0.3.schema.json
  -> normalize pricing/SLA fields for search facets
  -> preserve quality metric name + benchmark as semantic dimensions
  -> expose ranking/search API for agents
```

## Suggested aggregator fields

| Index field | Source | Notes |
|---|---|---|
| `asm_present` | `_meta...asm` | Boolean coverage signal |
| `asm_valid` | schema validation | Invalid ASM should not block MCP indexing |
| `taxonomy` | `asm.taxonomy` | Prefix queryable, e.g. `tool.data.*` |
| `representative_cost` | `pricing.billing_dimensions` | Keep original dimensions too |
| `latency_p50` | `sla.latency_p50` | Parse for sorting/filtering |
| `uptime` | `sla.uptime` | Reliability facet |
| `quality_metric` | `quality.metrics[].name` | Do not merge unlike metrics |
| `quality_benchmark` | `quality.metrics[].benchmark` | Required for semantic comparison |
| `verification_status` | `provenance.verification_status` | Trust/provenance facet |
| `payment_methods` | `payment.methods` | Useful for AP2/payment routing |

## Ranking guidance

Aggregators should not publish one universal "best MCP server" ranking. ASM is preference-parameterized:

- Cost-first users rank differently from quality-first users.
- Quality scores are only comparable within the same metric/benchmark construct.
- Usage popularity is not quality; OpenRouter-style usage is a revealed-preference signal affected by price, ecosystem fit, and free-tier availability.

The recommended API shape is:

```json
{
  "taxonomy": "tool.data.search",
  "constraints": {
    "max_latency_s": 1.0,
    "min_uptime": 0.99
  },
  "preferences": {
    "cost": 0.4,
    "quality": 0.3,
    "speed": 0.2,
    "reliability": 0.1
  }
}
```

Return:

```json
{
  "ranked_services": [
    {
      "service_id": "example/search@1.0",
      "score": 0.84,
      "reason": "Lowest cost among services satisfying latency and uptime constraints."
    }
  ],
  "rejected_services": [
    {
      "service_id": "example/slow-search@1.0",
      "reason": "latency_p50 exceeds max_latency_s"
    }
  ]
}
```

## Validation behavior

Use the local validator:

```bash
asm-mcp-validate path/to/server.json --json
```

Expected policy:

- Missing ASM: warning, keep indexing the MCP server.
- Invalid ASM: mark `asm_valid=false`, surface schema errors.
- Valid ASM: extract and index value metadata.
- `asm_url` only: record the URL and optionally fetch it in a second pass.

## Why this helps aggregators

ASM gives aggregators a defensible answer to "which MCP server should an agent choose?" without inventing proprietary scoring fields. The aggregator remains a discovery surface; ASM supplies a portable value contract.
