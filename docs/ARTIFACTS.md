# Artifact schema, version 1.1

All run JSON files use this envelope:

```json
{"schema_version": "1.1", "kind": "final_content", "data": []}
```

`schemas/artifact.schema.json` defines the envelope. The adjacent generated
Pydantic schemas define plan slots, KB entries, post type manifests, research
choices, drafts, review judgments and image specs. Unknown agent-output fields
are forbidden. Run aggregation fields follow the layouts below; aggregate
serialization is deterministic Python code, not model-authored JSON.

| Kind | `data` layout |
|---|---|
| `plan` | `{slots: [{id, type, focus}]}`; effective overridden input |
| `input_snapshot` | Map from relative filename to `{sha256, content}` |
| `resolved_plan` | Array of `{id, type, focus, topic: string or null, source: string or null, status}` |
| `research_log` | Array of `{slot_id, status, research: object or null, reasons: string[]}` |
| `drafts` | Array of `{slot_id, status, drafts: [{attempt, draft}] or null, reasons}` |
| `review_report` | Array of `{slot_id, status, reviews: [ReviewReport] or null, reasons}` |
| `final_content` | Array of `{slot_id, type, topic, posts: Post[], image_spec}` |
| `image_spec` | `{prompt, alt_text, artifact_type, width, height, source_ids: string[]}` |
| `usage` | Array of `CallUsage` |
| `events` | Array of `{slot, stage, event: start/end, time: ISO-8601, status?: string}` |
| `piece_state` | Current LangGraph state including slot, candidates and fields produced so far |
| `run_summary` | Run times, mode, demo notice, counts, dropped slots, aggregate usage and export contract |

`Post` has `{text: string, evidence_ids: string[]}`. Reference IDs are
`kb:<entry-id>:<field>`, where the field is `name`, `description`, `root_cause`,
or `mitigation`. The evidence map includes the actual corresponding text.
Questions without factual assertions may have no evidence IDs. There is no
hidden source attribution injected into public-facing post text.

A research object has `kb_id`, `source`, `background_url`, `source_mode`,
`reason`, and an `evidence` map. It explicitly distinguishes local knowledge
from a fetched page. A failed source has a null research entry and a reason.

A ReviewReport has `attempt` (1 or 2), `accepted`, numeric `scores`, `total`,
`hard_errors`, `reasons`, and the entire typed `judgment`. Judgment includes
`approve`, four rubric scores, `support` decisions for every zero-based post
index, and textual reasons. Missing/duplicate support decisions reject the
piece. Model approval alone does not determine `accepted`.

CallUsage includes `slot`, `role`, `agent`, `model`, nullable `input_tokens`, nullable
`output_tokens`, nullable `cost_usd`, `status`, `latency_seconds`, and optional
`error_type`. `fixture` status means demo behavior; `ok`/`error` indicate live
calls. Unknown usage is never silently converted into a complete zero total.
Aggregate token fields sum recorded values only; `token_totals_complete` tells
whether those totals cover all calls. Live cost is a configured-rate estimate.

Terminal statuses: `shipped` (accepted and has a spec), `dropped` (two editorial
rejections), `failed` (source/provider/visual/workflow failure). Summary
`pieces_dropped` counts both dropped and failed pieces; each detailed entry
preserves the distinction. Only shipped pieces appear in CSV/final content.

State snapshots are replaced atomically after each node. Draft/review history
is retained in state. They are not durable execution checkpoints; a killed
process may leave a partial run without aggregate artifacts. Start a new run
instead of appending to a partial folder.

Rate-limit update: live CallUsage adds `request_id`, `transport_attempt`,
`budget_wait_seconds`, and, on failure, `http_status`, `retry_after_seconds`
and `will_retry` where applicable. `status=rate_limited` records an actual
rejected API attempt that will be retried. Usage for that attempt stays unknown
unless the provider supplied it; complete totals are not fabricated. Summary
usage adds `rate_limit_responses` and safe `provider_settings`.

Version 1.1 adds `kb:<entry-id>:fact:<fact-id>` evidence and a per-reference
`provenance` map in research. Judgment adds `claims`: every sentence/semicolon
unit has a `unit_id`, kind, support decision, reason and `citations` containing
`evidence_id` and an exact `quote`. Missing or duplicate units fail review.
Image specs add the typed `concept`, code-generated `checks`, and
`evidence_context`. `VisualConcept.schema.json` is the current visual-agent
handoff; `Visual.schema.json` documents the legacy freeform handoff.
Historical 1.0 runs remain readable and are not migrated or rewritten.

Review reports also preserve `scope_warnings` (unit ID, marker and message).
These are advisory semantic-review inputs, not hard errors or acceptance overrides.
