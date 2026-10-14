# Submission guide

## What to submit

Submit the git repository containing the code, inputs, docs, tests and
`output/live-week-latest/`. This sample is an unmodified completed live run,
including one dropped piece. It demonstrates the requested reject/retry/drop
behavior; six accepted pieces are not required to show that the run completed.

No remote repository is configured in this archive. Create an empty GitHub
repository, then use the commands in README to push the included main branch.
Do not include `.env`, API keys, virtual environments or personal screenshots.

## Five-minute walkthrough

1. Open `launch_ui.bat` on Windows, or `python -m streamlit run app.py` after setup.
2. Show the plan: three technical threads, three marketing slots, empty topics
   reserved by the researcher. Show the brand/instruction editor.
3. Run Demo to demonstrate the full workflow without spending provider quota.
   Explain that demo content and scores are fixtures.
4. In Results & history, select the latest Live sample. Inspect a technical
   thread, its evidence, reviewer decisions and visual specification.
5. Open the dropped thread's two attempts. Explain that the final unsupported
   claim and formatting violations prevented export. Show CSV and ZIP downloads.
6. Refer to ARCHITECTURE.md for agent boundaries, parallelism and extensions,
   and LIMITATIONS.md for known model-review and scheduling limitations.

## Evaluation map

| Requirement | Implementation |
|---|---|
| Orchestration and isolated failures | pipeline/orchestrator.py, pipeline/graph.py |
| Research and provenance | pipeline/skills/knowledge.py, kb.json |
| Two specialised writers | post_types/tech-thread and post_types/marketing |
| Rubric and editorial retry | prompts/reviewer.md, rubric.json, graph review branch |
| Code-enforced rules | pipeline/skills/brand.py and claims.py |
| Accepted-only visual specs | pipeline/skills/visuals.py, visual-style.json |
| Shared reusable skills | knowledge.py and image_brief.md |
| Plan overrides and single pieces | run_week.py, run_piece.py |
| File-driven extension | post_types manifests and writer files |
| CSV and full audit trail | pipeline/artifacts.py, output/live-week-latest |
| Usage and cost uncertainty | pipeline/providers.py and rate_limits.py |
| Local UI | app.py, pipeline/ui_design.py, assets/studio.css |

## Honest sample interpretation

Latest live run: 5 accepted / 6 requested; 1 dropped after two editorial attempts.
Recorded usage: 40,159 input + 27,352 output = 67,511 tokens across 27 calls.
No HTTP 429 responses were recorded. Elapsed time: about 21m 39s. Cost is the
configured-rate estimate. The reviewer can still over-reject or miss nuance;
acceptance is not proof of semantic correctness. This is an engineering-task
submission with explicit limitations, not a claim of autonomous publication safety.
