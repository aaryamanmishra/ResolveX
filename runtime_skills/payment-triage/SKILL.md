---
name: payment-triage
version: 1.0.0
description: Investigate a payment issue using authenticated provider facts, event history, reconciliation results, and approved policy references.
allowed_tools:
  - get_payment
  - get_payment_events
  - get_provider_payment_status
  - get_refund_status
  - retrieve_policy
  - create_case_draft
  - request_additional_evidence
---
# Payment Triage Skill
1. Fetch canonical payment record and provider events before forming a conclusion.
2. Keep provider-confirmed status separate from customer-reported debit and extracted evidence claims.
3. Compare amount, currency, merchant/order mapping, event timestamps, and refund events.
4. Cite evidence IDs for every factual statement. If a required fact is absent, return it as unknown.
5. Recommend the next operational step from the retrieved policy; do not issue a refund or modify a provider payment.
6. Return structured findings matching the application's Pydantic schema.
