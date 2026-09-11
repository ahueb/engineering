---
name: docs-check
description: Perform an explicitly requested narrow authoritative documentation check for a specific current or version-dependent technical fact or design decision.
argument-hint: "[technical question]"
disable-model-invocation: true
context: fork
agent: general-purpose
model: sonnet
effort: medium
background: false
disallowed-tools: Edit, Write, NotebookEdit, Agent, Skill, Artifact
---

Resolve $ARGUMENTS using the minimum external research necessary.

- Establish relevant package, API, protocol, platform, and version from repository evidence when available.
- Prefer official specifications, version-matched documentation, authoritative source, release notes, and maintainer material.
- Use search for discovery, then inspect the underlying authoritative source.
- Check version differences, deprecations, defaults, compatibility, platform constraints, and documented limitations that could change the answer.
- Use secondary/community sources only when primary sources are insufficient or operational experience is itself relevant.
- Stop once authoritative evidence resolves the material uncertainty; do not accumulate sources for their own sake.

Return only: verified answer; primary evidence/citations; applicable versions/constraints; design implication; remaining material uncertainty.
