---
name: deep-audit
description: Perform an explicitly requested high-assurance adversarial audit of software or system architecture on Fable. Use only when the user invokes it for difficult or consequential verification.
argument-hint: "[implementation, architecture, or audit scope]"
disable-model-invocation: true
context: fork
agent: engineering:auditor
background: false
---

Audit $ARGUMENTS independently and adversarially. Do not modify the implementation.

The auditor runs at Fable/xhigh effort with Read, Grep, Glob, and Bash; its Bash is guarded by a plugin hook allowlist keyed to that agent, which blocks writes, redirection, and everything except a short list of read-only inspection commands. This is a guard against accidental mutation during the audit, not a sandbox: it cannot execute tests or builds. If the audit scope depends on test results, build output, or other command output, supply it in $ARGUMENTS or gather it yourself before dispatch; the auditor cannot produce it.

Return the auditor's verdict, blocking findings, other material findings by severity, residual uncertainty, verification considered, and readiness, to the user or caller.
