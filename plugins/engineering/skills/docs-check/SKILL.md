---
name: docs-check
description: Confirm one current or version-dependent technical fact against authoritative documentation. Use when a design or implementation decision depends on a library, API, protocol, platform, or CLI behavior that could have changed, when a version, default, deprecation, or compatibility claim must be confirmed against official docs, or when the user asks to verify or look up such a fact. Not for broad research or general programming knowledge.
argument-hint: "[technical question]"
context: fork
agent: general-purpose
model: sonnet
effort: medium
background: false
disallowed-tools: Bash, PowerShell, Edit, Write, NotebookEdit, Agent, Skill, Artifact
---

No shell: use Read, WebFetch, and WebSearch.

Resolve $ARGUMENTS using the minimum external research necessary.

- Establish relevant package, API, protocol, platform, and version from repository evidence when available.
- Prefer official specifications, version-matched documentation, authoritative source, release notes, and maintainer material.
- Use search for discovery, then inspect the underlying authoritative source.
- Check version differences, deprecations, defaults, compatibility, platform constraints, and documented limitations that could change the answer.
- Use secondary/community sources only when primary sources are insufficient or operational experience is itself relevant.
- Stop once authoritative evidence resolves the material uncertainty; do not accumulate sources for their own sake.

Return only: verified answer; primary evidence/citations; applicable versions/constraints; design implication; remaining material uncertainty.
