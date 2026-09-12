---
name: plan-execution
description: Execute a written implementation plan by fanning every task out to parallel implementers at once, with no building or testing until all implementations are merged, followed by a single integrated build-and-test pass and an adversarial audit for correctness and completeness. Use when the user has a plan, spec, or task list and wants it implemented as fast as possible.
argument-hint: "[plan file or task list]"
---

# Plan execution

Goal: shortest wall-clock time to a fully implemented, verified, audited plan. Implementation is parallel and unverified; verification and audit happen once, after everything is merged.

## 1. Partition

1. Read the plan and the repository areas it touches. Use `engineering:scout` in one batch for any call sites, tests, or config the plan does not already name.
2. Split the plan into work packages. Every package must have:
   - a disjoint set of files it may create or modify, listed explicitly;
   - the interfaces it provides and consumes (function signatures, types, schemas, endpoints, CLI flags), stated exactly;
   - its acceptance criteria copied from the plan.
3. If two tasks need the same file, merge them into one package or split the file's responsibilities so ownership is disjoint. If a package cannot be made disjoint, it runs after the batch, not inside it.
4. When packages share a new type, schema, or interface, write the stub or declaration yourself before fan-out so every implementer codes against the same contract. This is the only implementation the main session does before dispatch.
5. Use `engineering:architect` only if the partition itself needs a cross-cutting design decision the plan did not settle.

## 2. Fan out

Dispatch every package in a single message as parallel `engineering:bulk-implementer` calls, up to the concurrency limit. Each dispatch contains the package spec from step 1 and these instructions verbatim:

- Implement only the listed files. Do not touch any other file.
- Code against the stated interfaces exactly. If an interface is missing or ambiguous, choose the simplest reading, implement it, and report the assumption.
- Do not build, compile, run tests, lint, or commit. The parent runs all verification after integration.
- Return: files changed, interfaces provided, assumptions made, anything in the package left unimplemented and why.

Do not review, build, or test any package while others are still running.

## 3. Integrate

1. Collect every report. Reconcile assumptions that conflict across packages by editing the affected files directly; this is expected and is cheaper than a second implementer round.
2. Diff the working tree against the plan's file list. Any file changed outside its package's ownership is a defect to resolve now.
3. Run one integrated verification with `/engineering:verification-loop`: build, type check, lint, then the full test suite. Launch independent checks in parallel.
4. On failure, compress the output with `engineering:test-triage`, then repair in the main session. Use `engineering:hard-repair` for a failure that survives two repair attempts. Rerun the exact failing check, then the full pass.

## 4. Adversarial audit

Only after the integrated pass is green:

1. Dispatch in one batch: `engineering:plan-auditor` with the plan and the full diff, and `engineering:semantic-reviewer` with the diff. Add `engineering:security-reviewer` when any package touched a trust boundary.
2. The auditor's job is to prove the plan is not done: every task, acceptance criterion, and interface in the plan is checked against the code, and every gap, partial implementation, silent scope reduction, or unverified claim is reported.
3. Fix every confirmed finding, rerun the integrated verification, and re-audit only the fixed areas.

## 5. Report

Per the completion report policy: what changed per package, the verification commands and results, audit findings and their resolution, and residual risk. Write `/engineering:checkpoint` if the work continues in another session.
