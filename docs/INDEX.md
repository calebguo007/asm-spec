# ASM Documentation Index

> This file is the central entry point for all documentation. Each subdirectory has its own INDEX.md.

## Directory Structure

```
docs/
├── INDEX.md              ← you are here
├── hackathon/            ← Hackathon materials (gitignored)
│   ├── INDEX.md
│   ├── HACKATHON.md          Hackathon handbook + rules
│   ├── SUBMISSION-DRAFT.md   Submission form draft
│   ├── DEMO-SCRIPT.md        Recording script (Chinese)
│   ├── VIDEO-RECORDING-GUIDE.md  Recording guide (English)
│   ├── CIRCLE-PRODUCT-FEEDBACK.md  Circle Product feedback
│   └── WORKLOG-2026-04-14.md      Work log
├── internal/             ← Internal docs (gitignored)
│   ├── INDEX.md
│   ├── ASM-STRATEGIC-ANALYSIS.md  Strategic analysis + Roadmap
│   ├── GIT-GUIDE.md               3-repo Git guide
│   ├── PROJECT-CONTEXT.md         Project context (for AI)
│   ├── research.md                 Full research (1873 lines)  [Chinese filename]
│   ├── paper-reading-guide.md             Paper reading notes  [Chinese filename]
│   ├── sprint-april.md             Current sprint tasks  [Chinese filename]
│   ├── hackathon-selection.md           Hackathon selection (done)  [Chinese filename]
│   ├── exposure-academic-plan.md        Promotion roadmap  [Chinese filename]
│   ├── github-discussion-69-reply.md  Community reply draft
│   ├── update-20260407.md        4/7 Update log  [Chinese filename]
│   └── update-20260414.md        4/14 Update log  [Chinese filename]
└── specs/                ← Technical specs (public)
    ├── INDEX.md
    └── x-asm-metadata-spec.md     x-asm MCP metadata extension spec

paper/                    ← Academic paper (public)
├── INDEX.md
└── asm-paper-draft.md             Full paper draft

sep/                      ← Standard Extension Proposals (public)
├── INDEX.md
└── sep-asm-service-value.md       SEP-001: Service Value Annotations

tools/asm-lint/           ← CLI tool (public)
└── README.md                      asm-lint Usage docs
```

## Quick Lookup

| I want to... | Go to |
|-------|--------|
| Check hackathon rules & deadline | `docs/hackathon/HACKATHON.md` |
| Submit to hackathon | `docs/hackathon/SUBMISSION-DRAFT.md` |
| Record demo video | `docs/hackathon/VIDEO-RECORDING-GUIDE.md` |
| Push code | `docs/internal/GIT-GUIDE.md` |
| Make strategic decisions | `docs/internal/ASM-STRATEGIC-ANALYSIS.md` |
| Check research materials | `docs/internal/` (research docs) |
| Write paper | `paper/asm-paper-draft.md` + `docs/internal/` (reading guide) |
| Submit MCP proposal | `sep/sep-asm-service-value.md` + `docs/specs/x-asm-metadata-spec.md` |
| Scan with asm-lint | `tools/asm-lint/README.md` |
| Feed context to new AI assistant | `docs/internal/PROJECT-CONTEXT.md` |

## Visibility Rules

| Marker | Meaning |
|------|------|
| ✅ public | Will be pushed to GitHub public repo |
| ⚠️ gitignored | Local + private repo only, not in public |
