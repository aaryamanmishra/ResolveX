# Antigravity Build Plan — ResolveX AI

Read `PRD.md` before writing code. This file defines the execution sequence. Implement one phase per run; do not generate the entire platform in one pass.

## Repository layout target

```text
resolvex-ai/
├── .agents/skills/                 # Antigravity build-time skills
├── frontend/                       # React + TypeScript
├── backend/
│   ├── app/
│   │   ├── api/                    # FastAPI routers
│   │   ├── domain/                 # Canonical entities, enums, Pydantic schemas
│   │   ├── services/               # Payment, case, evidence, approval services
│   │   ├── providers/              # Payment/model/graph adapters
│   │   ├── agents/                 # LangGraph workflows and typed state
│   │   ├── agent_skills/           # Product runtime skills, trusted only
│   │   ├── mcp/                    # MCP tools and permission checks
│   │   ├── policies/               # Deterministic policy engine
│   │   ├── graph/                  # GraphStore adapter and graph queries
│   │   ├── models/                 # ORM models and repositories
│   │   └── security/               # Auth, tenant context, tokenization
│   ├── migrations/
│   └── tests/
├── infra/                          # Docker, DigitalOcean specs, observability
├── docs/                           # Architecture, ERD, runbooks, evaluations
├── scripts/                        # Seed, test, demo, migration utilities
├── docker-compose.yml
├── .env.example
└── README.md
```

## Execution sequence and gates

### Phase 0 — Contracts and scaffold
- Create monorepo and code-quality tooling.
- Add provider protocols: `PaymentProviderAdapter`, `ModelProvider`, `GraphStore`.
- Add canonical enums, Pydantic schemas, migrations baseline, seed-data contract.
- Add workspace skills from `.agents/skills/`.
- Gate: fresh clone boots; lint, typing, and schema tests pass.

### Phase 1 — Auth, tenancy, audit
- Implement authentication, server-side RBAC, tenant context, tenant-scoped repositories, audit service.
- Gate: cross-tenant access tests fail closed; mutations emit audit events.

### Phase 2 — Payment ingestion and tracking
- Build simulator first, then Razorpay Test Mode behind the same adapter.
- Validate webhook signatures, persist durable receipts, dedupe by provider event/idempotency key.
- Implement status normalization, immutable timeline, refund state, reconciliation exceptions.
- Gate: all payment scenarios in PRD §15.1 pass.

### Phase 3 — Graph fraud investigation
- Implement GraphStore with Apache AGE as open-source default; keep TigerGraph adapter optional.
- Tokenize identifiers before graph insertion. Add bounded traversals and deterministic indicators.
- Gate: synthetic fraud network is explainable; benign shared-device test does not become an automatic fraud verdict.

### Phase 4 — Agent harness and Skills
- Implement LangGraph typed state/checkpointing, trusted SkillRegistry, MCP tools, LiteLLM gateway, Gemma/Gemini adapters, Pydantic result validation, policy gate, human review pause.
- Gate: no agent can mutate payment truth, execute a refund, or call forbidden tools; unsupported evidence is marked unknown.

### Phase 5 — Multimodal evidence
- Add secure upload, private Spaces bucket, malware scan, hash, image/PDF/audio extraction, Gemma capability smoke tests, consent-gated Gemini fallback, field-confirmation UI.
- Gate: extraction includes confidence/source location; provider state cannot be overwritten by an uploaded document.

### Phase 6 — Complete UX and case workflows
- Complete payment and fraud journeys, analyst queue, graph detail, approvals, reports, and demo scenarios.
- Gate: both demo journeys run end-to-end without manual DB edits.

### Phase 7 — Deploy, test, evaluate
- Deploy frontend/API/worker/data/object store/model endpoint to DigitalOcean.
- Add security, performance and model evaluation. Rehearse from a clean environment.
- Gate: all P0 requirements, smoke tests, security checks, and deployment health checks pass.

## Mandatory coding rules

1. Read relevant skill files before changing a subsystem.
2. Use small, reviewable commits and keep modules layered.
3. No secrets in source, prompts, screenshots, logs, test fixtures, or browser code.
4. Do not collect PINs, OTPs, CVVs, bank passwords, or full payment credentials.
5. Only signed provider events or authenticated provider API results can set provider-confirmed payment state.
6. Uploaded documents and model extraction produce claims, never authoritative payment state.
7. No model-generated action may issue a refund, reverse/block a payment, freeze an account, or file a regulatory report.
8. Model outputs must validate against Pydantic schemas and cite evidence IDs.
9. All MCP tools validate tenant, actor, permission, schema, and rate limit server-side.
10. Mark simulated/test data clearly in UI and docs.
11. Do not copy code/data from the TigerGraph reference until licence and reuse permission are confirmed.
12. At phase completion, run format, lint, type check, unit/integration tests, and a smoke test; update README, `.env.example`, and phase report.

## Prompt to start a phase

```text
Read PRD.md, Antigravity_Build_Plan.md, and the relevant .agents/skills/*/SKILL.md files. Implement Phase [N] only. First inspect the repository, identify existing working code, and give me a concise file-level plan. Implement the plan with tests for every acceptance criterion. Do not skip tests or silently mock a feature that the UI describes as real. Use the provider, model, and graph adapter interfaces. Keep all financial actions human-approved. At the end, run formatter, linter, type checks, tests, and smoke checks; update docs and report files changed, commands run, test outcomes, limitations, and the next phase gate. Do not proceed to the next phase.
```
