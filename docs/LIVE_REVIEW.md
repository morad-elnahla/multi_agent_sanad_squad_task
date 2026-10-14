# Historical live run review

The original user-provided `output/groq-week-1` is retained without edits.
It demonstrates end-to-end live orchestration and successful provider pacing.
It does not establish that all six pieces are publication ready.

Findings included unsupported prevalence wording ("Contracts often"), overly
broad execution wording ("any caller"), repetitive thread structure, and an
image prompt mixing a no-text instruction with requested labels. Reviewer
scores were too generous to reveal these concerns reliably.

The current version adds more curated primary-source facts, exact-quote review
units, conservative scope checks, stronger editorial instructions, and enum-only
visual concepts composed through a consistent no-text template. These changes
are covered by deterministic tests. They still require a fresh live run and
human inspection; historical output is deliberately not rewritten to appear fixed.
