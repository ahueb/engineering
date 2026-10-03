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
constant across arms. Overlay hash (sha256 of fixtures.json, manifest.json, and scripts/comment_guidance_checks.py
concatenated in that order), identical in both arms on 2026-10-03:
`0f5aad5953392b7a0c689b7917b907ddc30cd45b43c67d852e73c5b1549b0361`.

Baseline policy/skill/agent bytes are preserved as originally committed; only the evaluation
harness is overlaid on top for an equal comparison, never the reverse.

## Frozen inputs

- Case IDs and tags: `behaviour-comment-cleanup` (`behaviour`, `behaviour-cleanup`,
  `comment-guidance-write`), `comment-guidance-review-only` (`comment-guidance-read`),
  `comment-guidance-implementation` (`comment-guidance-write`), `comment-guidance-plan`
  (`comment-guidance-write`), `comment-guidance-change-review` (`comment-guidance-read`),
  `comment-guidance-mechanical` (`comment-guidance-write`), `comment-guidance-repair`
  (`comment-guidance-write`), `comment-guidance-doc-plan` (`comment-guidance-read`).
- Checker/fixture/manifest hashes (sha256, 2026-10-03): `scripts/comment_guidance_checks.py` =
  `19585396d6ed693a23c72165b00bc25587a823ea9c9789f0ddb170efc9ce95de`,
  `plugins/engineering/evals/comment-guidance-support/fixtures.json` =
  `739584d1b29ae2f255dd3d2d1cc02d709d2f20f3a097774b19c2ef67b1f321f7`,
  `plugins/engineering/evals/comment-guidance-support/manifest.json` =
  `af7f275d126ae15c329cc18fe1e1d342d79cdbecd24e899b154abaf50dbabcb3` (a report built against a
  hash mismatch is rejected per the checker's own contract).
- CLI: Claude Code 2.1.288 for the 2026-10-03 run (2.1.273 or later is needed for `--keep-temp`;
  the eval sandbox additionally requires bubblewrap and socat on Linux for `Bash` grants).
- Models: subject model `claude-sonnet-5-5`, judge model `claude-sonnet-5-5`. Resolved from the 48
  eval traces of the 2026-10-03 run: every parent message in both arms came from `claude-sonnet-5-5`;
  subagent messages came from `claude-sonnet-5-5` or `claude-opus-5-5` according to each agent's
  own model setting, in both arms (a top-level `--model` does not by itself establish what a
  child agent used). The I01 and I04 probes ran with the CLI's default model, `claude-opus-5-5`.
- Budgets: no cap (owner decision); actual spend 9.02 USD across the 24 invocations, judge
  included.

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

Run on 2026-10-03 with Claude Code 2.1.288: baseline at `e158b1e6` with the overlay above, candidate
at the release tree (`39fdf93`, with uncommitted readiness-review edits later committed in
`2fab53c`; those touch no comment-guidance file, and the one grader pattern they change gives the
same result on every trace here). Three repetitions per arm, one run per
case per repetition, in the order baseline, candidate, candidate, baseline, baseline, candidate.
Every retained workspace went through `scripts/comment_guidance_checks.py artifacts`, and every
failed `llm` grader was rechecked with `scripts/eval_recheck.py` and against its trace or file.
"Verified" counts a run as a pass when its evidence satisfies every grader (a FAIL the evidence
contradicts is a judge error), as unverified when its required command was denied and the run
then stopped, and otherwise as a fail; an ambiguous judgment is counted as a fail.

| Case | Baseline (3 runs) | Candidate (3 runs) | Verdict |
|---|---|---|---|
| B01 `behaviour-comment-cleanup` | 0/3 verified pass: every run kept the unsupported thread-safety claim and changed the Python < 3.11 workaround comment's justification or removal condition | 3/3 verified pass (one harness FAIL is a judge error) | improved |
| B02 `comment-guidance-review-only` | 0/3: `comment-cleanup` was never invoked, and one report endorsed the thread-safety claim | 1/3: one run did not invoke `comment-cleanup`, and the run that did called the thread-safety claim plausible | improved in skill invocation only; spotting the unsupported claim is 2/3 in both arms |
| B03 `comment-guidance-implementation` | 0/3 verified, 3 unverified: each run's test command was denied and the run stopped without `test_output.txt` | 3/3 verified pass: each run retried the denied command in plain form and recorded the test output | inconclusive under this protocol (every baseline run is unverified); the candidate completed the task in every run |
| B04 `comment-guidance-plan` | 0/3 verified, 3 unverified: each parent's verification was denied and it stopped, with no `verification_output.txt` and no `plan-auditor`; all three contract documents passed `doc-contract-preserved` | 2/3 verified pass; in the third, the contract document adds that the reversed-bounds check happens before any filtering, wording an earlier run's recheck judged a real failure, so it is counted as a contract-preservation miss | mixed: completion improved (every baseline run is unverified), contract preservation 2/3 against 3/3; not a critical preservation regression |
| B05 `comment-guidance-change-review` | 2/3: one run skipped `security-reviewer` and reported a style-only finding (one other harness FAIL is a judge error) | 3/3 | improved |
| B06 `comment-guidance-mechanical` | 3/3 | 3/3 | no difference |
| B07 `comment-guidance-repair` | 3/3 | 3/3 | no difference |
| B08 `comment-guidance-doc-plan` | 2/3: one audit counted three plan items where the plan has two | 2/3: the same miss | no difference |
| I01 local `--plugin-dir` execution | pass: own plugin (2.9.1) loaded, 12 skills, 11 agents, SessionStart hook exit 0 | pass: own plugin (2.10.0) loaded, 12 skills, 11 agents, hook exit 0 | no difference |
| I02 marketplace/cache installation | not run (the baseline tree's `ci.sh --full` is not part of this comparison) | pass: `ci.sh --full` exit 0, including the official-marketplace install (S20) and the rules-file load (S21); `actionlint` is not installed here, so that lint was skipped | candidate only: pass |
| I03 policy path fallback/installed/legacy/stale | pass: 16/16 hook-contract checks | pass: 16/16 hook-contract checks | no difference |
| I04 supported-version and forked/direct-agent context | version gate: 3/3 `S19a` checks ok (its gate is 2.1.267); context: `plan-auditor` quoted the baseline's own completion sentence; the comment-guidance reference does not exist at baseline (N/A), and the skill declined to invent one | version gate: 3/3 `S19a` checks ok (its gate is 2.1.284); context: both quotes match the candidate's own text verbatim | no difference |

The artifacts checker passed every candidate workspace (24/24); at baseline only the six
unverified B03 and B04 runs failed it, each missing its required output file. No candidate run
made an unauthorized edit or broke a protected directive.

**Overall: Accepted, as a three-run screen.** The candidate improved B01, B05, and B02 (in skill invocation), matched the baseline on B06-B08, I01, I03, and I04, and passed I02, which ran on the candidate only. B03 is inconclusive under this protocol because every baseline run stopped, unverified, at its denied command, while the candidate completed it. B04 is mixed: the candidate completed it where the baseline stopped, but one candidate contract document adds an evaluation-order guarantee that no baseline document had. That is the only candidate-only miss and not a critical preservation regression, and no candidate run made an unauthorized edit. A three-run screen is not an accuracy claim.

Evidence record: each arm ran `claude plugin eval <root>/plugins/engineering` with `--scaffold
--trust-plugin --ablation none --runs 1 --model claude-sonnet-5-5 --judge-model claude-sonnet-5-5
--keep-temp --no-publish`, once with `--tag comment-guidance-write` (grants `Read Grep Glob Skill
Agent Edit Write "Bash(python3 *)" "Bash(git *)"`, `-j 2`), once each with `--case
comment-guidance-review-only` and `--case comment-guidance-doc-plan` (grants `Read Grep Glob Skill
Agent`), and once with `--case comment-guidance-change-review` (grants `Read Grep Glob Skill Agent
"Bash(git *)"`), where `<root>` is `<baseline>` or `<candidate>`. I01 and I04 used `claude
--plugin-dir <root>/plugins/engineering -p ... --setting-sources project --strict-mcp-config
--no-session-persistence`; I02 and I03 used each tree's `ci.sh`. Raw traces and workspaces are kept
locally and are not part of the repository.
