---
name: refund-resolution
version: 1.0.0
description: Explain refund state and prepare a support or escalation draft using authenticated provider records and approved policy.
allowed_tools:
  - get_payment
  - get_payment_events
  - get_refund_status
  - retrieve_policy
  - create_case_draft
---
# Refund Resolution Skill
1. Retrieve authenticated provider refund records and payment timeline before forming a recommendation.
2. Confirm refund status: REQUESTED, PENDING, PROCESSED, or FAILED. Never infer completion from model inference or customer screenshots alone.
3. Check configured provider refund SLAs (e.g. 5-7 business days for standard banking rails).
4. Mark unconfirmed bank account crediting as unknown until verified by provider or settlement confirmation.
5. Draft customer communication or escalation actions strictly for human review. Never execute refunds automatically.
