# Validation report

Executed 2026-10-12 in the build environment.

| Check | Result |
|---|---|
| `python -m pytest -q` | 73 passed |
| Streamlit AppTest | Demo button ships six pieces; results display; missing live key rejected |
| Configuration editing | Invalid edits preserve original; path traversal blocked; run snapshot frozen |
| Download packaging | Secret files excluded |
| Claim audit | Missing/duplicate units, fabricated quotes, uncited sources, model-declared unsupported claims rejected |
| Visual concept | Invalid source/layout rejected; prompt composed with no visible text |
| Provider transport | Simulated rate limits, retries, usage and shared budget tested |
| New live API execution | Not run: no API key supplied |

Existing tests also cover editorial repair/drop, stage failures, no visual for
rejected pieces, hard rules, bounded parallelism, output order, unknown usage,
and adding a post type through files. Fake model responses do not establish
live model quality. `output/sample-ui-v2` is an extractive offline fixture.

The user-supplied `output/groq-week-1` is an unmodified historical live run from
before this change: six shipped, 26 calls, zero recorded rate-limit responses.
Its generous reviews and weaker source checks motivated this update. It is not
an evaluation of the current claim schema or interface.

## 2026-10-13 live-run regression fix

The user's second live weekly run shipped three marketing pieces and dropped
three threads. Recorded final handoffs are preserved in a compact test fixture.
Thread 1 was approved by the live model but vetoed by a lexical "any" check.
Thread 2 had a false lexical "never" flag plus model rejections; its rewrite also
strengthened "can leave" into "then proceeds". Thread 3 introduced an unsupported
causal consequence during revision and was correctly rejected by the reviewer.

Scope markers now enter the reviewer payload and saved report as advisory
warnings. Exact quotation applies to evidence quotes, not public paraphrases.
The writer is told to preserve supported sentences during repair. Regression
tests replay recorded handoffs and demonstrate that model rejections still block
shipping. They do not predict how a fresh model call will score a draft.
No new live API call was made for this fix; fresh validation remains necessary.

## Presentation release, 2026-10-13

The latest user-supplied run is bundled byte-for-byte in `output/live-week-latest`.
It has 5 accepted pieces, 1 editorial drop, 27 calls, 67,511 recorded tokens and
0 rate-limit responses. The dropped thread's final attempt contains disallowed
Unicode hyphens and an unsupported state-corruption claim. Its first reviewer
also incorrectly treats an advisory marker as a banned term. Both are retained;
no rejected piece is manually promoted to create a 6/6 sample.

The UI redesign passes the full test suite, including launching a demo, result
rendering, selecting the latest live history, searching previews, missing-key
validation and configuration preservation. Live API calls were not repeated
for a presentation change. The historical output validates the content pipeline,
not every wording decision or production readiness.

Browser screenshot validation was unavailable in the build environment because
the Chromium download failed. Functional UI checks used Streamlit AppTest;
final desktop appearance can be inspected locally by opening the launcher.
