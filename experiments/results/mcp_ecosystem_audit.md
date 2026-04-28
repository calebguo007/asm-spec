# MCP Ecosystem Value Metadata Audit

Generated at: 2026-04-28T09:53:05Z
Sample size: 50 public GitHub repositories

This audit samples public repositories likely to contain MCP servers and scans public README/config text for value metadata that an agent could use before invocation. It is a conservative text audit, not a manual legal or pricing verification.

## Coverage

| Metadata class | Repos | Rate |
|---|---:|---:|
| pricing | 16 / 50 | 32.0% |
| sla | 9 / 50 | 18.0% |
| quality | 22 / 50 | 44.0% |
| payment | 5 / 50 | 10.0% |
| structured_asm | 0 / 50 | 0.0% |
| all_value_fields | 0 / 50 | 0.0% |

## Sample

| Repo | Stars | Pricing | SLA/rate | Quality | Payment | ASM/x-asm |
|---|---:|---:|---:|---:|---:|---:|
| [n8n-io/n8n](https://github.com/n8n-io/n8n) | 185921 | no | no | yes | no | no |
| [google-gemini/gemini-cli](https://github.com/google-gemini/gemini-cli) | 102608 | yes | no | no | yes | no |
| [sansan0/TrendRadar](https://github.com/sansan0/TrendRadar) | 55677 | no | no | no | no | no |
| [upstash/context7](https://github.com/upstash/context7) | 53954 | no | no | yes | no | no |
| [D4Vinci/Scrapling](https://github.com/D4Vinci/Scrapling) | 39145 | yes | no | yes | no | no |
| [ChromeDevTools/chrome-devtools-mcp](https://github.com/ChromeDevTools/chrome-devtools-mcp) | 37473 | yes | yes | yes | no | no |
| [ruvnet/ruflo](https://github.com/ruvnet/ruflo) | 33748 | no | no | yes | no | no |
| [bytedance/UI-TARS-desktop](https://github.com/bytedance/UI-TARS-desktop) | 29547 | no | no | no | no | no |
| [github/github-mcp-server](https://github.com/github/github-mcp-server) | 29311 | no | no | yes | yes | no |
| [assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher) | 26754 | no | no | yes | no | no |
| [oraios/serena](https://github.com/oraios/serena) | 23528 | yes | no | yes | no | no |
| [activepieces/activepieces](https://github.com/activepieces/activepieces) | 21952 | yes | no | no | yes | no |
| [1Panel-dev/MaxKB](https://github.com/1Panel-dev/MaxKB) | 20845 | no | no | no | no | no |
| [czlonkowski/n8n-mcp](https://github.com/czlonkowski/n8n-mcp) | 18836 | yes | no | yes | no | no |
| [nukeop/nuclear](https://github.com/nukeop/nuclear) | 17378 | no | no | no | no | no |
| [microsoft/mcp-for-beginners](https://github.com/microsoft/mcp-for-beginners) | 15965 | no | no | no | no | no |
| [triggerdotdev/trigger.dev](https://github.com/triggerdotdev/trigger.dev) | 14693 | no | no | no | no | no |
| [open-metadata/OpenMetadata](https://github.com/open-metadata/OpenMetadata) | 13701 | no | yes | yes | no | no |
| [yusufkaraaslan/Skill_Seekers](https://github.com/yusufkaraaslan/Skill_Seekers) | 13152 | yes | yes | yes | no | no |
| [xpzouying/xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp) | 13117 | no | no | no | no | no |
| [tadata-org/fastapi_mcp](https://github.com/tadata-org/fastapi_mcp) | 11829 | no | no | no | no | no |
| [0xJacky/nginx-ui](https://github.com/0xJacky/nginx-ui) | 11095 | yes | no | yes | no | no |
| [JoeanAmier/XHS-Downloader](https://github.com/JoeanAmier/XHS-Downloader) | 10971 | no | no | no | no | no |
| [mksglu/context-mode](https://github.com/mksglu/context-mode) | 10817 | yes | no | yes | yes | no |
| [mcp-use/mcp-use](https://github.com/mcp-use/mcp-use) | 9840 | no | no | no | no | no |

## Method

GitHub repository search queries:

- `topic:mcp-server`
- `mcp server in:name,description`
- `modelcontextprotocol server in:readme`
- `mcp-server in:name,description`

Scanned files when present: `README.md`, `README.mdx`, `package.json`, `pyproject.toml`, `mcp.json`.
