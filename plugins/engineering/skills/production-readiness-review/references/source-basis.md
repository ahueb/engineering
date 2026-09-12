# Literature and Documentation Basis

Last independently rechecked: 2026-09-08.

This file records the public/official sources used to design the skill and rubric. It is methodological provenance, not evidence that any particular repository is production-ready. Revalidate time-sensitive standards, regulations, product behavior, vulnerability status, and provider limits when they materially affect a live decision.

## Claude / Agent Skill construction

1. Anthropic, **Extend Claude with skills** (Claude Code documentation). Project skills live at `.claude/skills/<name>/SKILL.md`; descriptions support automatic discovery/invocation; supporting files use progressive disclosure; user/model invocation controls and variable substitution are documented here.  
   https://code.claude.com/docs/en/skills

2. Agent Skills specification, **Specification**. Defines the portable minimum skill format, naming/description constraints, progressive disclosure, and supporting `scripts/`, `references/`, and `assets/` conventions.  
   https://agentskills.io/specification

3. Anthropic, **Skills repository**. Public examples and reusable skill patterns.  
   https://github.com/anthropics/skills

4. Anthropic Claude Code plugins, **skill-creator**. Evaluation/description-tuning patterns for should-trigger and should-not-trigger prompts and skill-output evaluation.  
   https://github.com/anthropics/claude-plugins-official/tree/main/plugins/skill-creator

5. Anthropic, **Prompting best practices**. Supports explicit sequential instructions for completeness-critical workflows, examples when they add signal, and investigation-before-answering for code tasks.  
   https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices

## Product quality and lifecycle

6. ISO/IEC 25010:2023, **Systems and software Quality Requirements and Evaluation (SQuaRE) - Product quality model**. Current product-quality model; public ISO abstract identifies nine product-quality characteristics and use for requirements, testing objectives, quality control, and acceptance criteria.  
   https://www.iso.org/standard/78176.html

7. ISO/IEC 25019:2023, **SQuaRE - Quality-in-use model**. Public ISO abstract emphasizes quality in a specified context of use.  
   https://www.iso.org/standard/78177.html

8. ISO/IEC/IEEE 12207:2026, **Software life cycle processes**. Current lifecycle-process standard spans acquisition/supply, development, operation, maintenance, and disposal.  
   https://www.iso.org/standard/90219.html

9. ISO/IEC 25012:2008, **Data quality model**. Used only as high-level provenance for the data-quality overlay; detailed proprietary standard text is not reproduced.  
   https://www.iso.org/standard/35736.html

## Production and operational readiness

10. Google SRE, **Evolving SRE engagement model / Production Readiness Review**. PRR validates production setup and operational readiness and covers service-specific operational risks, SLO/SLA implications, change risk, and training/operational handoff.  
    https://sre.google/sre-book/evolving-sre-engagement-model/

11. Google SRE, **Monitoring distributed systems**. Important basis for symptom/user-impact monitoring and the warning that protocol success can coexist with wrong user-visible results.  
    https://sre.google/sre-book/monitoring-distributed-systems/

12. AWS Well-Architected, **The ORR tool**. Operational Readiness Review questions should be informed by incidents, near-misses, and plausible failure modes and tailored to the workload.  
    https://docs.aws.amazon.com/wellarchitected/latest/operational-readiness-reviews/the-orr-tool.html

13. AWS Well-Architected, **OPS07 - Prepare for operational readiness**. Covers workload, process/procedure, and personnel readiness; runbooks/playbooks, support plans, and informed deployment decisions.  
    https://docs.aws.amazon.com/wellarchitected/latest/framework/ops-07.html

14. AWS Well-Architected Reliability Pillar, **Back up data**. Basis for distinguishing configured backups from demonstrated restore/recovery capability.  
    https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/back-up-data.html

15. Kubernetes SIG Architecture, **Production Readiness Review**. Requires features to be observable, scalable, supportable, and safely operable, including rollback/disable behavior and independent review.  
    https://github.com/kubernetes/community/blob/main/sig-architecture/production-readiness.md

16. UK Infrastructure and Projects Authority, **Gate 4 Review: Readiness for service** (updated 2026-08-20). Covers completed testing, contingency/continuity/reversion, dependencies, resources, management controls, handover/training/support, documented go/no-go, and early-life support.  
    https://www.gov.uk/government/publications/gate-review-4-readiness-for-service/gate-4-review-readiness-for-service

## Secure development, verification, and supply chain

17. NIST SP 800-218, **Secure Software Development Framework (SSDF) Version 1.1**. Secure-development practices intended to reduce vulnerabilities and their impact and address root causes.  
    https://csrc.nist.gov/pubs/sp/800/218/final

18. NIST IR 8397, **Guidelines on Minimum Standards for Developer Verification of Software**. Identifies multiple complementary verification techniques and explicitly does not present any single technique as the totality of verification.  
    https://csrc.nist.gov/pubs/ir/8397/final

19. OWASP, **Application Security Verification Standard (ASVS)**, current stable line at time of review: 5.0.0. Used as a source family for application-security verification breadth, not as a claim that every project must implement every ASVS control.  
    https://owasp.org/www-project-application-security-verification-standard/

20. SLSA v1.1, **Requirements**. Basis for artifact/build provenance concepts such as artifact identity, build process provenance, and progressively stronger integrity guarantees.  
    https://slsa.dev/spec/v1.1/requirements

## Delivery evidence and metrics

21. DORA, **DORA's software delivery performance metrics** (current guide reviewed 2026-09-08). Current guide uses five delivery metrics and warns against setting metrics as goals, a single metric "to rule them all", gaming, and comparing unlike applications without context.  
    https://dora.dev/guides/dora-metrics/

22. Inozemtseva & Holmes, ICSE 2014, **Coverage is not strongly correlated with test suite effectiveness**. Empirical basis for rejecting code coverage as standalone correctness/readiness evidence.  
    https://www.cs.ubc.ca/~rtholmes/papers/icse_2014_inozemtseva.pdf

## Assurance and objective evidence

23. Software Engineering Institute / assurance-case literature, **Assurance Cases for Medical Devices and Other Systems** (public article). Basis for claim-argument-evidence reasoning and skepticism toward process labels/certifications as release-specific assurance.  
    https://pmc.ncbi.nlm.nih.gov/articles/PMC4548534/

24. NASA Safety and Mission Assurance, **Identifying objective evidence improves requirement implementation** (2026-03-25). Reinforces documented, tangible, unbiased evidence and traceability rather than unsupported assertion.  
    https://sma.nasa.gov/news/articles/newsitem/2026/03/25/identifying-objective-evidence-improves-requirement-implementation

## Domain overlays

25. W3C, **Web Content Accessibility Guidelines (WCAG) 2.2**. Current W3C Recommendation for web accessibility requirements.  
    https://www.w3.org/TR/WCAG22/

26. NIST, **AI Risk Management Framework (AI RMF 1.0)**. Risk-management structure for AI systems; NIST has announced revision work, so current status must be rechecked for a live compliance/governance decision.  
    https://www.nist.gov/itl/ai-risk-management-framework

## Synthesis limits

- No single source above defines a universal production-readiness score or complete checklist for every domain.
- ISO abstracts establish model scope and current versions; this skill does not reproduce paywalled ISO normative text.
- Vendor operational frameworks are valuable cross-checks but are not treated as universally mandatory controls.
- The hard-gate set is a synthesis of recurring concern families, strengthened by adversarial failure analysis and a mandatory domain-overlay gate.
- Readiness thresholds must remain relative to the release's consequence, exposure, and explicit obligations.
