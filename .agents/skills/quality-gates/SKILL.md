---
name: quality-gates
description: Run ResolveX AI test, security, model-evaluation, accessibility, and release checks before closing a phase.
---
# Quality Gates
- Run formatter, linter, static typing, unit tests, integration tests, and UI smoke tests.
- Test tenant isolation, webhook replay/idempotency, invalid evidence references, prompt injection, and forbidden tool calls.
- Use deterministic synthetic fixtures; do not put real customer financial data in tests.
- Evaluate model outputs against fixed golden datasets and report metrics, false positives, abstentions, latency, and cost.
- Confirm payment state is provider-sourced and the model cannot execute sensitive actions.
- Update README, `.env.example`, migration docs, and phase report.
