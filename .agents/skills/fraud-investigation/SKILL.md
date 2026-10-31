---
name: fraud-investigation
description: Build graph-based transaction investigation, explainable fraud indicators, provenance, and human-reviewed case recommendations.
---
# Fraud Investigation
- Risk signals trigger investigation; they are not a final fraud verdict.
- Use the `GraphStore` interface; keep Apache AGE default and TigerGraph optional.
- Tokenize identifiers with tenant-scoped keyed HMAC before graph insertion.
- Bound traversal depth, node count, and query duration.
- Label observed versus inferred edges and preserve source record IDs/timestamps.
- Use deterministic rules for reason codes and approval routing.
- Every AI finding must cite evidence IDs and expose uncertainty/unknowns.
- Never let the model auto-block accounts, freeze funds, or submit regulatory reports.
