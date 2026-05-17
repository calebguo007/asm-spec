# RFC: Trust Delta receipt extension v0.1

**Status**: Draft, open for review
**Authors**: Yi Guo (ASM) · Rahat Hasan, Akkhar-Labs (reference integration)
**Target version**: ASM v0.3.1
**Tracking issue**: (link to be added when issue is created)
**Reference integration**: [`docs/integrations/akkhar-code-receipt-spec.md`](../integrations/akkhar-code-receipt-spec.md)

## 1. Motivation

ASM Trust Delta (§3.4, §6.3 of the paper) is defined as

```
trust(s) = g( Σ_t |declared_t − observed_t| × decay(t) )
```

but the protocol does not yet specify the **shape of the observation** that goes into the sum. Without that shape, every consumer reinvents the receipt format, defeating the protocol's interoperability claim.

This RFC adds:

1. A **canonical receipt envelope** for delivering receipts from publisher to consumer (push or poll).
2. A **`delegates_to` attribution chain** for receipts emitted by pipelines that wrap sub-services.
3. A new **`tool.code.orchestration`** taxonomy leaf.
4. An ASM-side **verifier path** that recomputes `billing.cost` from `token_counts × manifest.pricing` and surfaces the delta as a first-class trust signal.

The reference integration is the Akkhar-Code Execution Receipt format, delivered 2026-05-16 (see linked spec). This RFC is generalised from that case but is not Akkhar-specific; any pipeline-level service should be able to emit receipts in this shape.

## 2. Spec changes

### 2.1 Receipt envelope (push + poll)

Publishers emit receipts to a consumer's `payment.receipt_endpoint` (already in the v0.3 schema, currently unused). Envelope:

```json
{
  "envelope_version": "0.1",
  "publisher": "akkhar-labs",
  "service_id": "akkhar-labs/akkhar-code@1.0",
  "issued_at": "2026-05-16T20:52:00Z",
  "receipts": [ { /* per-receipt body */ }, ... ],
  "signature": {
    "algorithm": "ed25519",
    "public_key_url": "https://akkhar-labs.example/.well-known/asm-pubkey.pem",
    "value": "ed25519-hex..."
  }
}
```

- **Push**: publisher POSTs envelope to consumer's `receipt_endpoint`.
- **Poll**: consumer GETs `{publisher_origin}/.well-known/asm-receipts?service_id=...&since=...`.

Both modes carry the same envelope; deployment chooses transport. Consumers without a public endpoint use poll.

### 2.2 Receipt body

Per-receipt schema is a superset of what is needed for Trust Delta and what is needed for billing. Common fields (this RFC defines):

```
receipt_version     (string, semver)
pipeline_id         (string, opaque, unique per invocation)
service_id          (string, ASM service_id of the receipt emitter)
timestamp_start     (RFC3339 datetime)
timestamp_end       (RFC3339 datetime)
duration_ms         (int)
seal                ({ algorithm, scope, digest, byte_range_spec })
billing             ({ dimension, unit, quantity, cost_currency, cost,
                       observed_input_tokens, observed_output_tokens })
delegates_to        (optional array, see §2.3)
```

Service-specific fields (e.g. Akkhar's `phase_summary`, `plan_hash`, `outcome`) are allowed under an `extensions` namespace keyed by the publisher's `service_id`. Consumers ignore unknown extensions.

### 2.3 `delegates_to` chain

When a pipeline-level service composes sub-services (e.g., Akkhar-Code Phase 2 calls Claude Sonnet), the receipt MAY carry:

```json
"delegates_to": [
  {
    "phase": "phase2_planning",
    "asm_service_id": "anthropic/claude-sonnet-4@4.0",
    "model_id": "anthropic/claude-sonnet-4-20250514@1.0:phase2-planner",
    "tokens_consumed": { "input": 1200, "output": 4800 },
    "upstream_receipt_id": "optional reference to a separate ASM receipt",
    "upstream_seal_digest": "optional sha256 if upstream emitted its own seal"
  }
]
```

**v0.1 minimum**: pipeline-level seal sufficient. The parent receipt is the settlement object.

**v0.2 (future)**: each delegate carries its own provider-signed receipt; Trust Delta walks the chain recursively to verify end-to-end provenance. Opt-in.

### 2.4 Cost re-derivation (the Trust Delta primitive this RFC adds)

When Trust Delta receives a receipt, it computes both:

- `claimed_cost = receipt.billing.cost`
- `recomputed_cost = Σ over billing_dimensions of (observed_quantity × manifest.pricing.cost_per_unit)`

and emits a **per-receipt cost delta**:

```
cost_delta = claimed_cost − recomputed_cost
```

This delta accumulates into the publisher's trust score the same way latency / quality deltas do. The first time a publisher's `claimed_cost` diverges from the manifest-derived rate by more than some tolerance, Trust Delta surfaces it. Neither value is treated as "true"; the divergence itself is the signal.

### 2.5 Taxonomy addition

Adds one leaf to the ASM 47-taxonomy set, becoming 48:

```
tool.code.orchestration
```

Rationale: agentic code IDEs (Akkhar-Code, Cursor's agent mode, Devin, etc.) are not inline-completion (`ai.code.completion`) and are not CI runners (`tool.devops.ci`). They orchestrate multi-phase plan-then-execute flows. New leaf needed.

Existing taxonomies are unchanged; this is purely additive. Updates `tools/asm-gen/asm_gen.py` allowlist and the recognized-taxonomy list in `README.md`.

## 3. Schema diff (preview)

Changes to `schema/asm-v0.3.schema.json`:

```diff
"payment": {
  "properties": {
    ...
    "receipt_endpoint": { "type": "string", "format": "uri" },
+   "receipt_envelope_version": {
+     "type": "string",
+     "description": "Latest envelope version this endpoint accepts (e.g. '0.1').",
+     "default": "0.1"
+   },
+   "delegates_to_supported": {
+     "type": "boolean",
+     "description": "Whether the receipt envelope from this service may carry a delegates_to chain.",
+     "default": false
+   }
  }
},
"taxonomy": {
  "type": "string",
  "pattern": "^[a-z]+\\.[a-z_]+(?:\\.[a-z_]+)?$",
  "examples": [..., "tool.code.orchestration"]
}
```

The receipt envelope itself is specified in `schema/asm-receipt-envelope-v0.1.schema.json` (new file in this RFC).

## 4. Acceptance criteria for v0.3.1

This RFC lands when:

1. ✅ Receipt envelope schema added at `schema/asm-receipt-envelope-v0.1.schema.json` and validating with jsonschema.
2. ✅ `tool.code.orchestration` added to taxonomy list and accepted by `scorer/test_manifests_schema.py`.
3. ✅ One reference receipt example accepted: `examples/receipts/akkhar-code-receipt.json`.
4. ✅ `cost_delta` recompute logic added to `scorer/scorer.py` and unit-tested.
5. ✅ `docs/integrations/akkhar-code-receipt-spec.md` (this RFC's reference integration) shipped.
6. ✅ Paper §7.2 cross-reference: receipts mechanism now has a concrete external implementer.

## 5. Open questions (for discussion in this issue)

- **Q1**: Envelope signature — Ed25519 (chosen here) or pluggable algorithm list? Ed25519 is small + fast; pluggable adds complexity. Recommendation: Ed25519 only in v0.1, pluggable from v0.2.
- **Q2**: Push retry semantics — exponential backoff, dead-letter, or fire-and-forget? Probably standard webhook semantics + dead-letter after N hours. Open to a more concrete spec.
- **Q3**: Replay protection — `pipeline_id` MUST be unique, but should the envelope also carry an idempotency key for the consumer to dedupe? Lean yes.
- **Q4**: Receipt size limits — Akkhar's receipt with full `phase_summary` is ~2 KB. Cap at 64 KB per receipt? Per envelope?

## 6. Timeline

- T+0 (today): Open issue, post this RFC.
- T+1 week: Comments + schema diff draft PR.
- T+2 weeks: Merge schema changes to `main` as v0.3.1-rc1. Akkhar-Code first reference integration ships its `.well-known/asm-receipts` endpoint.
- T+3 weeks: v0.3.1 tagged + released; ASM paper v2 adds §6.5c citing the first reference integration.

## 7. Acknowledgements

The receipt schema, seal construction, and `delegates_to` convention in §2.2–§2.3 are Akkhar-Labs' authorship, delivered to the ASM project under attribution. This RFC generalises that work to a protocol-level spec applicable to any pipeline-level publisher.
