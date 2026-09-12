# Evidence Protocol

Use this protocol when an apparent finding is ambiguous or when evidence from multiple sources conflicts.

## Claim -> argument -> evidence

For each important readiness claim:

1. **Claim** - state the exact proposition that must be true for the proposed exposure.
2. **Argument** - explain why the observed controls/architecture would make the claim true, including assumptions.
3. **Evidence** - identify direct artifacts, measurements, executions, or observations that support the argument.
4. **Defeaters** - identify plausible conditions under which the claim would still be false.
5. **Disposition** - show how each material defeater is prevented, detected, bounded, recovered from, or accepted.

Example:

- Claim: database state can be recovered within the required outage/data-loss window.
- Weak evidence: `backup_enabled = true` in IaC.
- Stronger evidence: candidate-compatible restore drill, integrity checks, measured recovery time/data loss, and documented dependency assumptions.
- Defeaters: corrupted backup, missing encryption key, incompatible schema, control-plane outage, restore procedure needing unavailable staff.

## Evidence precedence

Prefer evidence that is:

- more direct rather than inferential;
- tied to the exact candidate rather than an earlier version;
- representative of the target environment rather than a toy environment;
- recent enough that the relevant system/control has not materially changed;
- repeatable/reproducible rather than anecdotal;
- measured under failure/adverse conditions when the claim concerns failure behavior;
- independently observed when consequence warrants stronger assurance.

Do not automatically discard older evidence. Judge whether the relevant mechanism has changed and whether the evidence remains representative.

## Repository evidence

Useful repository evidence can include:

- source/configuration with `path:line` support;
- exact CI workflow and required-check configuration;
- lockfiles and build scripts;
- tests with meaningful assertions;
- deployment/IaC and policy-as-code;
- runbooks, but only for the claim that a procedure exists unless exercise evidence is present;
- dated test/drill/benchmark reports committed to the repository;
- release metadata, provenance, SBOM, signatures, attestation configuration;
- ownership/CODEOWNERS/support docs, recognizing that staffing reality may still be external.

Repository presence is not proof that an external production control is enabled or used.

## Command evidence

When running a validation command, record:

- exact command;
- working directory;
- candidate commit/working-tree state;
- exit status;
- relevant concise result (counts, failures, measured latency, etc.);
- environmental limitations;
- whether the command changed local build/cache state.

Do not hide skipped tests or warnings that affect the claim. Distinguish test-framework exit success from substantive acceptance criteria.

## Unknown versus fail

Use **UNKNOWN** when the claim may be true but material evidence is unavailable or nonrepresentative.

Use **FAIL** when evidence directly contradicts the gate or when an explicit mandatory criterion is not satisfied.

For the overall readiness verdict, a material UNKNOWN that is necessary for the claimed exposure blocks READY just as effectively as a failed gate, but preserve UNKNOWN in the table so the reason is epistemically accurate.

## Negative evidence

Absence of a conventional file name is not proof of absence of a control. Search for reasonable alternatives and inspect architecture/context before marking a gate unknown or failed.

Examples:
- no `Dockerfile` does not mean no reproducible build;
- no `runbook.md` does not mean no operating procedure;
- no `k6` config does not mean no load testing;
- no `SECURITY.md` does not mean no security verification.

Conversely, presence is not proof of execution.

## Confidence language

Use confidence to describe the **quality and completeness of the evidence**, not subjective certainty about the software.

Evidence confidence is the minimum evidence strength across applicable hard gates: E3/E4 everywhere → High; any E2 on a critical gate → Moderate; any E0/E1 on a critical gate → Low.

Never use confidence to turn a FAIL into a PASS.

## Argument validity

Rate separately whether the evidence entails the claim (the weak-oracle check), and record an argument gap as a defeater even when the evidence is E3.
