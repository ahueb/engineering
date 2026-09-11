---
name: literature-review
description: Conduct an explicitly requested evidence-driven scientific or technical literature review to inform a consequential design, architecture, algorithm, or research decision.
argument-hint: "[research question or decision]"
disable-model-invocation: true
context: fork
agent: general-purpose
model: opus
effort: medium
background: false
disallowed-tools: Edit, Write, NotebookEdit, Agent, Skill, Artifact
---

Review $ARGUMENTS for decision-relevant evidence rather than source count.

1. Define the decision, scope, constraints, credible alternatives, and evidence that could change the recommendation.
2. Prefer primary authoritative evidence: standards/specifications and official source for systems work; systematic reviews to map scientific fields, followed by important primary studies.
3. Evaluate applicability and quality: versions, workloads, populations, controls, methodology, uncertainty, reproducibility, external validity, conflicts, and recency as relevant.
4. Follow consequential claims to primary evidence when practical and deduplicate sources that derive from the same evidence.
5. Actively search for contradictory findings, negative results, failure modes, boundary conditions, and credible alternatives.
6. Distinguish established fact, empirical finding, documented behavior, claim, inference, and recommendation.
7. Stop at evidence saturation: further searching is unlikely to materially change the conclusion, alternatives, or important uncertainty. Expand toward exhaustive coverage only when explicitly requested.

Return a concise synthesis: recommendation; strongest evidence; alternatives/tradeoffs; contradictory evidence/limitations; applicability assumptions; residual uncertainty; material citations.
