---
name: case-summary
version: 1.0.0
description: Produce customer-facing and analyst-facing summaries citing exact evidence IDs and preserving uncertainty.
allowed_tools:
  - get_payment
  - get_case_history
  - get_evidence_metadata
---
# Case Summary Skill
1. Read verified payment facts, timeline events, and attached evidence assets.
2. Formulate concise, grounded summaries that explicitly separate provider-confirmed facts from customer-reported claims.
3. Every factual assertion must cite one or more valid evidence IDs.
4. If bank-side fund status or external merchant actions are not verified, explicitly mark them as unknown.
5. Provide zero external side effects and do not execute financial or account actions.
