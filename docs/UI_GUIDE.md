# Local interface guide

## Windows quick start

Extract the new archive separately. Copy your existing `.env` into the new project
root, beside `app.py`. Do not copy old Python source files over the new version.
Double-click `launch_ui.bat`. It uses `.venv` if present, otherwise Python on PATH.
If dependencies are incomplete, run `python -m pip install -r requirements.lock`.
Keep the launcher open; closing it stops the server and any active job.

Choose Demo for a free offline check. Choose Live and Groq to use your existing
GPT-OSS setup. The sidebar exposes concurrency, token budget and completion cap;
leave the conservative defaults for your first run. Wait messages are expected.
Changing settings does not reset a provider quota. Cost is based on the configured
rates; zero rates mean a zero estimate, not a billing verification.

The Create content tab supports weekly plan editing, saving the default plan,
and single-piece runs. Results & history shows accepted posts, sources, decisions,
visual JSON specs, raw artifacts and CSV/ZIP downloads. A visual spec is not a
rendered image. Brand & instructions validates edits before saving. Every run
keeps a frozen input snapshot, including the prompts it actually used.

## Recovery

The background run continues if you close only the browser tab, while the server
stays alive. Reopen the app and check history after completion. Refreshing can lose
the active progress view. Only one UI run can hold the job lock; use the CLI for
advanced automation. Do not run another process on the same free account while
relying on the app's local token budget.

A dropped piece is a completed quality decision; inspect review_report.json.
A failed piece is a source/provider/processing error. Other slots still complete.
No API key is included in the archive. Typed keys remain in server memory for the
session; local `.env` is not part of run downloads. Do not expose this app publicly.

## Studio layout

- Create content: saved-plan counts, editable topic table, whole-plan/single-piece
  controls and live agent activity. Waiting messages reflect the local budget.
- Results & history: newest run by recorded start time, acceptance/cost metrics,
  topic search, post-type filter, readable previews and copyable text. Evidence
  and visual briefs expand on demand. Rejected runs use a warning, not an
  all-success banner. CSV includes only accepted pieces.
- Brand & instructions: validated file editing. Existing runs stay unchanged.

The local stylesheet lives in `assets/studio.css`; escaped HTML presentation
helpers live in `pipeline/ui_design.py`. Generated content cannot inject HTML.
