# Good First Issues

These issues are intentionally scoped for first-time contributors.

## 1. Add ASM metadata to an MCP `server.json`

Take an existing MCP server and add `_meta.io.modelcontextprotocol.registry/publisher-provided.asm` using `examples/mcp-server-json/basic-with-asm.server.json` as the template. Validate with:

```bash
asm-mcp-validate path/to/server.json
```

## 2. Add a new manifest with provenance

Pick one service with public pricing/SLA docs, add `manifests/<provider-service>.asm.json`, and run:

```bash
python -m pytest scorer/test_manifests_schema.py -q
```

## 3. Add a new benchmark mapping

Find a quality benchmark used by multiple services in one taxonomy. Add examples and document when it is comparable vs not comparable.

## 4. Improve CLI output

Make `asm score "cheap reliable TTS under 1s"` easier to scan without changing the scoring algorithm.

## 5. Add an aggregator import script

Build a script that reads a directory of MCP `server.json` files, extracts ASM metadata with `mcp_server_json_asm.py`, and writes a CSV of `service_id`, `taxonomy`, `pricing`, `latency`, `quality_metric`, and `verification_status`.
