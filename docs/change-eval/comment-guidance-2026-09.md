# Comment-guidance change eval: pinned baseline vs. candidate (2026-09)

Question: does the candidate comment/docstring guidance (policy patch, cleanup skill rewrite,
skill/agent integration clauses, and the strengthened `comment-guidance-*` eval suite) improve
semantic preservation, protected-directive/consumer integrity, and honest reporting over the
pinned baseline instructions, without a regression in unauthorized edits or task completion? This
is old-guidance-versus-new-guidance testing, not a with-plugin-versus-without-plugin ablation; the
`--ablation none` flag in the commands below answers a different question and is not a substitute
for the comparison below.

## Arms

- **baseline**: the pinned baseline instructions at commit `e158b1e6` (policy, cleanup skill,
  agent/skill integration prose) — the tree byte-for-byte before this handoff's changes, per the
  frozen contract in `plugins/engineering/evals/comment-guidance-support/` and the manifest table
  embedded in `scripts/comment_guidance_checks.py`.
- **candidate**: this handoff's tree (policy patch, cleanup rewrite, integration clauses,
  reference files, strengthened `comment-guidance-*` cases).

Both arms run under the **same strengthened evaluation overlay** (the `comment-guidance-*` cases,
fixtures, manifest, and `scripts/comment_guidance_checks.py`), so the harness itself is held
constant across arms. Overlay hash: `TBD — record the combined sha256 of fixtures.json,
manifest.json, and scripts/comment_guidance_checks.py at run time`.

Baseline policy/skill/agent bytes are preserved as originally committed; only the evaluation
harness is overlaid on top for an equal comparison, never the reverse.

## Frozen inputs

- Case IDs and tags: `behaviour-comment-cleanup` (`behaviour`, `behaviour-cleanup`,
  `comment-guidance-write`), `comment-guidance-review-only` (`comment-guidance-read`),
  `comment-guidance-implementation` (`comment-guidance-write`), `comment-guidance-plan`
  (`comment-guidance-write`), `comment-guidance-change-review` (`comment-guidance-read`),
  `comment-guidance-mechanical` (`comment-guidance-write`), `comment-guidance-repair`
  (`comment-guidance-write`), `comment-guidance-doc-plan` (`comment-guidance-read`).
- Checker/fixture/manifest hashes: `scripts/comment_guidance_checks.py` = `TBD`,
  `plugins/engineering/evals/comment-guidance-support/fixtures.json` = `TBD`,
  `plugins/engineering/evals/comment-guidance-support/manifest.json` = `TBD` (fill at run time;
  a report built against a hash mismatch is rejected per the checker's own contract).
- CLI: Claude Code 2.1.273 (verified locally for `--keep-temp`; the eval sandbox additionally
  requires bubblewrap and socat on Linux for `Bash` grants).
- Models: subject model `$COMMENT_SUBJECT_MODEL`, judge model `$COMMENT_JUDGE_MODEL` (record the
  actual resolved model for the parent and for every forked skill/agent invocation observed in
  the trace; a top-level `--model` does not by itself establish what a child agent used).
- Budgets: `$COMMENT_WRITE_BUDGET_USD`, `$COMMENT_READ_BUDGET_USD` (explicit authorized-budget
  inputs, not recommended dollar amounts; set before running, recorded after).

## Runs

Three runs per case per arm as a smoke/reliability screen (8 behavioural cases B01-B08 plus the 4 installation/context checks I01-I04; the latter are not runs of `claude plugin eval`, counting installation/context
tests separately from the eight behavioral cases; a full accuracy claim needs more than three
runs per case). Counterbalance execution order between the baseline and candidate arms across the
three repetitions rather than always running baseline first. Use a fresh, isolated workspace per
run; do not share transcripts, findings, or prior candidate output across arms or across runs of
the same case.

## Analysis constraints

Coverage distinction: the eight cases do not independently measure every wording change in
every agent. The `architect` and `auditor` additions are covered only by static review, plus a
bounded direct smoke invocation under their existing tool restrictions when their behaviour is
materially relied upon; record that invocation here if it is run.

- Report every run's outcome and the denominator it is out of; do not drop timeouts, cost-limit
  aborts, denied-tool runs, or missing-workspace runs from the reported total. Such a run is
  **unverified**, not a pass or a fail.
- Primary outcomes: valid task completion, contract/semantic-fact preservation, protected-
  directive and protected-consumer integrity, and absence of unauthorized edits (per case's
  `manifest.json` entry, checked by `scripts/comment_guidance_checks.py artifacts` against each
  retained workspace).
- Secondary outcomes: verified-token use, latency, number of repairs, human intervention,
  retrieval effort, and unnecessary diff size. Counts of deleted comments or shorter final output
  are explicitly not success metrics.
- A confirmed critical preservation or scope regression in the candidate arm blocks acceptance of
  this change pending repair; zero observed failures in a small screen is not proof of zero
  failure probability.
- Do not infer a general accuracy or reliability claim from a three-run screen; report it only as
  a screen.

## Evidence record

For every command/trial, record: exact command and working directory; candidate commit and any
dirty diff identity; fixture/grader/checker hashes; CLI and relevant tool versions; resolved
parent/child/judge models; permitted tools; exit status; stdout/stderr or artifact paths; the
actual retained workspace path used for the external checker; budget/usage/latency when
available; and the limits of what each check actually establishes (e.g. `semantic_status` is
always `REQUIRES_REVIEW` from the deterministic checker; only the `llm` graders and human review
speak to semantics). Do not invent an unavailable field or substitute a model's self-report for
measured usage or timing. Keep credentials and sensitive environment values out of the record.

## Results

NOT_RUN.

| Case | Baseline (3 runs) | Candidate (3 runs) | Verdict |
|---|---|---|---|
| B01 `behaviour-comment-cleanup` | NOT_RUN | NOT_RUN | NOT_RUN |
| B02 `comment-guidance-review-only` | NOT_RUN | NOT_RUN | NOT_RUN |
| B03 `comment-guidance-implementation` | NOT_RUN | NOT_RUN | NOT_RUN |
| B04 `comment-guidance-plan` | NOT_RUN | NOT_RUN | NOT_RUN |
| B05 `comment-guidance-change-review` | NOT_RUN | NOT_RUN | NOT_RUN |
| B06 `comment-guidance-mechanical` | NOT_RUN | NOT_RUN | NOT_RUN |
| B07 `comment-guidance-repair` | NOT_RUN | NOT_RUN | NOT_RUN |
| B08 `comment-guidance-doc-plan` | NOT_RUN | NOT_RUN | NOT_RUN |
| I01 local `--plugin-dir` execution | NOT_RUN | NOT_RUN | NOT_RUN |
| I02 marketplace/cache installation | NOT_RUN | NOT_RUN | NOT_RUN |
| I03 policy path fallback/installed/legacy/stale | NOT_RUN | NOT_RUN | NOT_RUN |
| I04 supported-version and forked/direct-agent context | NOT_RUN | NOT_RUN | NOT_RUN |

**Overall: NOT_RUN.** No comparison has been executed yet; this document freezes the protocol
before any run so results cannot be silently re-scoped after the fact.
