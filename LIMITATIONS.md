# Known limitations and next work

1. **Model evaluation remains limited.** The latest live sample completed all
   six slots, accepting five and dropping one. The reviewer still sometimes
   treats a scope advisory as a banned word, and the writer can introduce new
   issues during repair. These limitations are preserved in the audit trail.
   Next: a broader human-labelled evaluation set before claiming production quality.
2. **Model grounding is fallible.** Reference integrity and complete review
   coverage are enforced, but semantic truth is judged by a model. Next: a small
   adversarial evaluation set, calibrated acceptance scores and human sign-off.
3. **KB-only retrieval.** Unknown topics fail rather than inventing a source.
   Links in the KB are background references, not live-validated evidence.
   Next: an allowlisted fetcher with timeouts, snapshots, content hashes and
   explicit citation spans; do not pass unsanitized pages in the system prompt.
4. **Specs rather than rendered images.** The visual agent returns an accepted
   brief, not media bytes. Next: an image adapter, visual QA, media upload and
   provider-specific image usage. Generated specs should also be checked for
   factual text before sending to a renderer; the current prompt forbids text.
5. **Conservative X formatting.** Only ASCII text is supported and its literal
   length must fit 280 characters. Code identifiers are allowlisted separately
   from URLs. This intentionally over-restricts some valid X posts. Next: the
   official weighted-length parser, Unicode/emoji support and URL normalization.
6. **Scheduler-specific import remains.** The exact two-column CSV groups thread
   text in one cell and points to specs. Next: choose a real scheduler, map its
   thread delimiter and media format, and test import end to end.
7. **No resumable durable execution or distributed rate budget.** State snapshots
   are diagnostic artifacts. The current process shares a token gate and retries
   HTTP 429, but cannot see other processes or guarantee a daily quota. Next:
   persistent jobs, distributed budgets and a resumable LangGraph checkpointer.
8. **Demonstration brand and severity.** No company metrics are asserted. Severity
   varies with context, and the KB is intentionally small. Next: approved brand
   claims and a security specialist's review of source coverage and mitigations.
9. **Cost is an estimate.** Configured input/output rates do not apply cache
   discounts or reconcile invoices. Missing usage makes totals incomplete.

10. **Conservative claim audit.** Sentence/semicolon units, exact source quotes,
    citation integrity are checked in code; scope words trigger advisory model review. This does
    not prove semantic entailment; compound claims can still escape model review.
    The model may still reject valid paraphrases. Next: targeted regression
    cases and finer claim extraction with calibrated human-labelled examples.
11. **Local UI lifecycle.** No authentication, distributed jobs or resume after
    server shutdown. Browser refresh can lose the active progress view; completed
    runs remain in history. Use a durable queue and authentication before hosting.
