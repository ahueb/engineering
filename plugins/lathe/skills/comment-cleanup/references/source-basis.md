# Source basis for comment guidance (maintainer reference)

Optional reading. Load this file only when rationale for the comment-guidance rules, or revalidation of them, is explicitly requested — not as part of an ordinary cleanup or review.

## External evidence (E01-E09)

- **E01** - Macke and Doyle (2024), *Testing the Effect of Code Documentation on Large Language Model Code Understanding*. <https://aclanthology.org/2024.findings-naacl.66/>. Establishes: published abstract indicates documentation affects LLM code-understanding performance in the studied setting. Does not establish: full-method replication, or an effect size for current agentic coding models.
- **E02** - Dainese, Ilin, and Marttinen (2024), *Can docstring reformulation with an LLM improve code generation?*. <https://aclanthology.org/2024.eacl-srw.24/>. Establishes: docstring reformulation affected code-generation outcomes in the studied function-generation setting. Does not establish: applicability outside that narrow generation task, or to comment cleanup/editing tasks.
- **E03** - PEP 257, *Docstring Conventions*. <https://peps.python.org/pep-0257/>. Establishes: Python docstring semantics, multiline conventions, and what is caller-relevant. Does not establish: anything about LLM behavior; it is a language convention, not an empirical study.
- **E04** - Claude Code, *Plugins reference*. <https://code.claude.com/docs/en/plugins-reference>. Establishes: current path/content-variable and plugin/eval interfaces (for example `${CLAUDE_PLUGIN_ROOT}` is a content substitution, not a shell environment variable). Does not establish: behavior of versions other than the one inspected; verify locally against the installed version.
- **E05** - Claude Code, *Extend Claude with skills*. <https://code.claude.com/docs/en/skills>. Establishes: current skill resource and progressive-disclosure guidance (load detail on demand rather than inline). Does not establish: guarantees for future SDK versions.
- **E06** - Claude Code, *How Claude remembers your project*. <https://code.claude.com/docs/en/memory>. Establishes: current CLAUDE.md guidance. Does not establish: this repository's specific 120-newline cap, which is a repository-local check (`ci.sh`) and takes precedence here.
- **E07** - Claude Code, *Test plugins with evals*. <https://code.claude.com/docs/en/plugin-evals>. Establishes: currently supported grader types, file targets, isolation, retained workspaces, tool grants, cost, and partial-result behavior. Does not establish: guarantees beyond the inspected CLI version.
- **E08** - Go command, *Build constraints*. <https://pkg.go.dev/cmd/go#hdr-Build_constraints>. Establishes: placement and grouping rules for `//go:build` and `// +build` constraints, and that moving them can change which files are compiled. Does not establish: behavior for a project pinned to an older Go toolchain; recheck the project's supported Go version.
- **E09** - ESLint, *Configure Rules*. <https://eslint.org/docs/latest/use/configure/rules>. Establishes: inline rule configuration and next-line directive syntax and scope. Does not establish: behavior under a project's specific ESLint version/config; verify against the real configuration in use.

## Applicability limits

These sources support general claims that (a) documentation quality can affect both human and model code understanding, (b) several ecosystems have real machine-readable comment directives whose placement and scope matter, and (c) the plugin/eval interfaces referenced elsewhere in this plugin behave as described at the inspected versions. They do not by themselves prove any specific numeric benefit, nor do they cover every language or consumer this repository might contain. Treat E01/E02 as motivating context for keeping useful documentation, not as a quantified requirement; treat E04-E07 as needing local reverification whenever the installed Claude Code version changes; treat E08/E09 as authoritative for their own ecosystems only.

## Repository-specific findings and motivations (F01-F12)

| ID | Finding | Motivation for the change |
|---|---|---|
| F01 | The prior cleanup skill compressed flagged comments into one sentence. | Removed the sentence quota; guidance now requires preserving semantic completeness. |
| F02 | The prior skill flagged dates, spec/plan names, tickets, and version/history references, and forbade relocating content elsewhere. | Guidance now distinguishes transient implementation history (safe to drop) from durable compatibility constraints and references (must be preserved), and allows relocation only with explicit scope authorization. |
| F03 | The prior skill treated any changed check result as proof a comment was a directive, and ran a full formatter despite claiming to preserve non-comment whitespace. | Guidance now requires a pre-edit baseline, check-only formatting by default, and distinguishing consumer-caused failures from unrelated or flaky ones. |
| F04 | The global policy only mentioned generating comments when code is hard to understand; implementation/verification skills lacked an explicit documentation-drift obligation. | Added the compact "Comments and docstrings" policy section with an explicit authoring and verification obligation. |
| F05 | The prior cleanup checker verified line membership, not directive attachment, full code preservation, or immutable inputs, and its snapshot was missing a legacy Go build directive. | Guidance requires evaluating actual artifacts (attachment, grouping, byte-identity) with negative controls, not just presence of expected text. |
| F06 | A regex grader accepted a `DIRECTIVES_INTACT` token in the model's final message, and an LLM rubric graded the model's claims rather than the edited files. | Guidance and evaluation both require checking artifacts, not self-reported success markers. |
| F07 | `plan-auditor` required implementing code even for plan items that were documentation deliverables. | Out of scope for this reference; tracked as a plan-auditor-specific fix elsewhere. |
| F08 | The session-start hook's header comment described the opposite of its executable branches. | Out of scope for this reference (a stale comment fix, not a policy change); tracked separately. |
| F09 | The production-readiness-review skill incorrectly stated that `browser-tester` has Bash. | Out of scope for this reference; tracked as a separate stale-sentence fix. |
| F10 | `ci.sh -h` extracts header comments to build CLI help. | Directly motivates the "shell-comment-derived help" entry in the machine-semantics protected list and the CLI-help synthetic example. |
| F11 | `docs/plans/` is gitignored, and a prior commit removed references to uncommitted plan documents. | Motivates the durability rule: do not depend on invisible planning files as a comment's justification, while still allowing checkpoints to reference such plans legitimately. |
| F12 | The browser-testing conventions require an issue reference for a skipped test. | Motivates preserving issue references that explain an active exception rather than stripping all ticket-shaped text. |

F07-F09 are recorded here for completeness because they came from the same review; they are implemented as targeted fixes to their own files, not as content of this comment-guidance reference.

## F13: release-preparation note

**F13** - `CHANGELOG.md` contains two `## [Unreleased]` headings near the top of the file. This is a release-preparation ambiguity, not a comment-cleanup matter: any change note added by this work should target the first `## [Unreleased]` section only. The maintainer should verify how the two sections are intended to fold together before the next release; this reference does not resolve that on its own and comment cleanup must not rewrite changelog history to "fix" it.
