---
name: fraud-investigation
version: 1.0.0
description: Investigate a risk trigger by retrieving bounded graph context, deterministic reason codes, and prior case/policy evidence.
allowed_tools:
  - get_graph_neighborhood
  - search_transactions
  - get_case_history
  - retrieve_policy
  - create_case_draft
  - request_additional_evidence
---
# Fraud Investigation Skill
1. Treat the risk trigger as a reason to investigate, not as a verdict.
2. Retrieve bounded, tenant-scoped graph context and record every source entity/edge ID.
3. Distinguish directly observed relationships from inferred/similarity relationships.
4. Consider benign explanations and missing evidence; identify uncertainty explicitly.
5. Never call a block/freeze/refund tool. Recommend human review according to deterministic policy rules.
6. Return a concise, evidence-linked investigation summary and structured reason codes.
