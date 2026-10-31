---
name: payment-domain
description: Implement payment providers, webhooks, normalized status, event timelines, refund tracking, and reconciliation safely.
---
# Payment Domain
- Treat authenticated provider API responses and verified provider events as the only provider-confirmed source of payment truth.
- Keep payment, funds, refund, settlement, and case states separate.
- Preserve raw provider status/source while mapping to canonical enums.
- Use integer minor units for money; never floating-point amounts.
- Validate raw-body webhook signatures, event timestamps, replay, tenant mapping, and idempotency.
- Append events; do not silently overwrite event history.
- A customer report or uploaded screenshot is a claim, not a provider-confirmed debit.
- Do not implement automatic refunds, reversals, account blocks, or credential capture.
