# SanadSquad Content Pipeline

A small, file-configured LangGraph system for one week of grounded X content.
It researches six slots, selects the appropriate writer, reviews each piece,
allows **one editorial retry**, creates an image specification only after
acceptance, and exports `posts.csv` with a complete JSON audit trail.

## Start with the interface

On Windows, unzip into a new folder, copy your existing `.env` into that folder,
and double-click **`launch_ui.bat`**. Python 3.11+ must already be installed.
The launcher installs dependencies if needed and opens the local Streamlit app.
Keep the launcher window open while using it. No terminal commands are needed
for normal runs after setup.

Alternatively, after installing dependencies:

```bash
python -m streamlit run app.py
```

1. Choose **Demo** (offline) or **Live** in the sidebar.
2. For Live, choose the provider/model and use your existing `.env` key or the
   masked API-key field. A typed key is session-only and is not saved to artifacts.
3. Edit the weekly slots or select a single piece, then click **Run pipeline**.
4. Watch agent stages and rate-budget waits. Open **Results & history** to inspect
   posts, evidence, reviews, visual specs, tokens and cost, and download CSV/ZIP.
5. **Brand & instructions** edits validated configuration for future runs.

Runs use unique output folders. One UI job runs at a time across browser tabs;
its slots still run concurrently. The app binds to localhost and is intended
for one trusted local user, not public hosting. See `docs/UI_GUIDE.md`.

## Submission sample and interface

`output/live-week-latest/` is the latest **unaltered live run** from the user:
5 accepted pieces, 1 dropped thread, 27 API calls, 67,511 recorded tokens,
zero recorded rate-limit responses, approximately 21 minutes 39 seconds.
The dropped thread failed after its one editorial rewrite; accepted pieces
were exported. A completed run need not ship every requested piece.
The zero cost is an estimate using the user's configured zero rates, not a
billing verification. Visuals are written specifications, as permitted by the brief.

The refreshed Streamlit studio includes a plan editor, background agent progress,
readable post previews, topic search, type filters, review history, sources and
CSV/ZIP downloads. It uses local styling assets and makes no external font or
image requests. It is a local application, not a public hosted service.

`output/sample-ui-v2/` and `output/sample-week/` are offline fixtures;
`output/groq-week-1/` is an older live run. All retain their original input snapshots.
The latest live run validates the pipeline before the presentation-only redesign.
The refreshed interface is tested offline; no new API calls were made for its redesign.
See `docs/SUBMISSION.md` for the evaluation map and a short walkthrough.

## Setup

Python 3.11 or newer. Run commands from this repository's root.

```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell instead:
# .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock
python -m pip install -e . --no-deps
```

`requirements.lock` pins the tested dependency set. For development, install
`python -m pip install -e '.[dev]'`. No API key is needed for the demo or tests.

```bash
python run_week.py --mode demo --plan plan.json --output output/local-demo
python -m pytest -q
```

Output directories must be **new**. This prevents accidentally mixing runs.
Omit `--output` to create a UTC timestamped folder automatically.

## Live model run

Copy `.env.example` to `.env`, set `OPENAI_API_KEY`, and choose `LLM_MODEL`.
The default is `gpt-4.1-mini`; your account must have access and the selected
model must support LangChain's JSON-schema structured output. The live adapter
uses `langchain-openai`; an optional `OPENAI_BASE_URL` can target a compatible
endpoint. The environment takes precedence over `.env`. Never commit keys.

```bash
python run_week.py --plan plan.json --output output/week-42
python run_week.py --plan plan.json --set thread_2="oracle manipulation"
python run_piece.py --type tech-thread --topic "reentrancy"
```

For PowerShell or bash the quoted overrides above work as written.
Repeat `--set` for multiple overrides. `--set thread_2=""` restores auto-selection.
`--concurrency 3` bounds simultaneously active pieces. `--config-dir PATH`
loads an alternate brand, KB, prompts, rubric, skills and post type registry.
Use `--plan PATH` as well when that alternate configuration has its own plan.

Set both `INPUT_USD_PER_MILLION` and `OUTPUT_USD_PER_MILLION` to rates for your
exact model. Without rates, cost is **null/unknown**, not zero. Counts come from
provider usage metadata, including editorial retries and failed parses where
usage is available. Cost is an estimate at configured uncached token rates;
cache discounts, platform fees and billing adjustments are not modeled. A
failed request may have unknown usage. Per-call records preserve that uncertainty.

Exit codes: **0** all shipped; **1** completed with dropped/failed slots;
**2** invalid configuration or filesystem setup error. Partial runs still export
accepted pieces. HTTP 429 responses receive up to three bounded transport retries, independently
of the one editorial retry. SDK automatic retries remain disabled so each
physical request is recorded. Other provider errors fail only that slot.

## Inputs and changes

| File | Responsibility |
|---|---|
| `brand-voice.md` | Tone and one machine-readable JSON block for hard rules |
| `kb.json` | 15 curated vulnerability entries, mechanisms and mitigations |
| `plan.json` | Ordered slots with type and optional focus |
| `rubric.json` | Acceptance thresholds |
| `prompts/reviewer.md` | Written scoring rubric and support checking |
| `prompts/research.md`, `prompts/visual.md` | Role instructions |
| `post_types/*/type.json`, `writer.md` | Post count, length and writer instructions |
| `pipeline/skills/` | Shared source lookup, hard gates and image brief |

KB severity values are illustrative test-data ratings, not universal security
judgments. The KB is the runtime source of truth; its `source_url` values are
background reading, **not assertions that the run fetched or verified a URL**.
No invented company statistics are approved. Review this small KB and brand
policy before use with a real company.

Empty slots reserve different KB entries in deterministic plan order after
explicit topics are reserved. Explicit duplicate focuses are allowed because
they may intentionally ask for distinct angles. Unknown focuses fail visibly;
the researcher cannot substitute an unrelated topic. This version uses the KB
route allowed by the brief, not live web search.

### Add a post type without editing the orchestrator

Create `post_types/checklist/type.json`:

```json
{
  "name": "checklist",
  "min_posts": 1,
  "max_posts": 1,
  "max_characters": 280,
  "writer": "writer.md"
}
```

Add `writer.md` in the same directory and use `"type": "checklist"` in a slot.
The generic writer node loads those instructions and constraints automatically.
This works for text types within the existing output schema. A genuinely new
workflow role needs a new node and explicit graph edges; it is not magic
configuration. See `ARCHITECTURE.md` for extension boundaries.

## Output contract

Every JSON artifact has `schema_version`, `kind`, and `data`. Model handoff
schemas are in `schemas/`; the run envelope and layouts are documented in
`docs/ARTIFACTS.md`. Each run contains:

```text
input_plan.json        effective plan after CLI overrides
input_snapshot.json    exact input/prompt contents and hashes
resolved_plan.json     chosen topic, KB reference and status per slot
research_log.json      source details and evidence fields
drafts.json            all successfully parsed drafts, including retries
review_report.json     hard errors, scores, support checks and decisions
final_content.json     accepted content with per-post evidence references
run_summary.json       shipped/dropped counts, reasons and total usage
usage.json             individual agent calls, tokens and costs
events.json            timestamped stage start/end events
posts.csv              accepted pieces only, in original plan order
pieces/<id>/state.json state snapshot after each completed node
visuals/<id>.json      written image specification and alt text
```

`posts.csv` has **exactly** `Post Text,Image`. One row represents one piece; a
thread's tweets are separated by blank lines inside its quoted CSV cell. The
`Image` cell is a relative JSON **specification path**, not an image URL.
This is the image-spec fallback explicitly permitted by the brief. Before
scheduling, render these specs and map thread boundaries to the chosen scheduler.
There is no universally portable thread import format across scheduling tools.
`final_content.json` preserves individual tweets for a scheduler-specific adapter.

## Validation and delivery

```bash
python -m pytest -q
python scripts/export_schemas.py
```

Tests exercise success, retries, permanent rejection, hard rules, source failures,
provider-stage isolation, bounded parallel execution, cost uncertainty, output
ordering and a file-only post type addition. Live provider behavior is separately
checked with a fake LangChain response; it is not a network integration test.
See `docs/TEST_REPORT.md` for the executed result and `LIMITATIONS.md` for next work.

The archive contains a local git repository. To publish to your own empty repo:

```bash
git remote add origin YOUR_REPOSITORY_URL
git push -u origin main
```

No remote account, publishing action or API key is included.

## Groq free-tier protection (update)

When `OPENAI_BASE_URL=https://api.groq.com/openai/v1`, the adapter defaults to
a shared 7,500-token/minute local budget. It reserves approximate input plus
up to 4,096 completion tokens and updates the budget using actual response usage.
Budgeted API calls are serialized; slot workflows remain independent and
concurrently scheduled. Waiting messages appear in the terminal. This local
budget is a conservative estimate, not a guarantee against server rate limits.

On HTTP 429, it honors `Retry-After` when available, otherwise waits 61 seconds
and uses exponential backoff with a little jitter. Up to three retries are
logged separately from editorial attempts. A requested wait beyond 300 seconds
or explicit insufficient-quota error fails visibly instead of looping forever.
No daily quota is bypassed. Other processes using the same account are not part
of this process-local budget.

Environment overrides: `LLM_TOKENS_PER_MINUTE`, `LLM_MAX_COMPLETION_TOKENS`,
`LLM_RATE_LIMIT_RETRIES`, `LLM_RETRY_BASE_SECONDS`, `LLM_MAX_RETRY_WAIT_SECONDS`.
Set `LLM_REASONING_EFFORT=low` optionally for GPT-OSS to reduce reasoning work;
leave it unset for models that do not support this option. Shorter writer
instructions target 140–220 characters while the hard 280-character gate remains.

The rate-limit tests use simulated responses and a fake clock. The bundled historical
live run demonstrates the prior provider update, not the new UI or claim audit.

## Review fix (2026-10-13)

Updated lexical scope checks now generate reviewer warnings instead of automatic
vetoes. Exact evidence quotes and all structural hard gates remain enforced.
The reviewer accepts supported paraphrases while checking actual changes in
certainty and meaning. The writer preserves supported sentences during repair.
Tests include replay of the user's real dropped-thread handoffs. This change
has not yet been validated with a new live generation.
