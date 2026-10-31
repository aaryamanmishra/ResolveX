# ResolveX AI

**Agentic Payment Intelligence, Fraud Investigation & Resolution Platform**

ResolveX AI is an evidence-first financial operations platform featuring two unified tracks:
1. **Payment Issue Tracking & Resolution:** Ingests gateway events, normalizes multi-dimensional payment/refund states, reconciles ledger discrepancies, and drafts auditable resolutions.
2. **Agentic Graph-Based Fraud Investigation:** Traverses tokenized relationship graphs, detects syndicates, computes deterministic indicators, and generates grounded, evidence-cited findings with human-in-the-loop review.

---

## Architecture Overview

```text
resolvex-ai/
├── .agents/skills/                 # Build-time Antigravity skills
├── frontend/                       # React + TypeScript UI
│   └── src/types/contracts.ts      # Canonical frontend TypeScript contracts
├── backend/
│   ├── app/
│   │   ├── api/                    # FastAPI routers
│   │   ├── domain/                 # Canonical entities, enums, Pydantic schemas
│   │   ├── services/               # Payment, case, evidence, approval services
│   │   ├── providers/              # Payment (Simulator/Razorpay) & Model (Gemma/Gemini/Stub)
│   │   ├── agents/                 # LangGraph workflows and typed state
│   │   ├── agent_skills/           # Trusted product runtime skill registry
│   │   ├── mcp/                    # MCP tools and permission checks
│   │   ├── policies/               # Deterministic policy engine
│   │   ├── graph/                  # GraphStore adapter (Memory / Apache AGE / TigerGraph)
│   │   ├── models/                 # ORM models and repositories
│   │   └── security/               # Tenant context & HMAC tokenization
│   ├── migrations/                 # PostgreSQL & Apache AGE DDL baselines
│   └── tests/                      # Pytest suite with contract validation
├── infra/                          # Docker Compose & container specs
├── docs/                           # Architecture specifications and diagrams
├── scripts/                        # Synthetic scenario generator and quality runners
├── pyproject.toml                  # Python package configuration and tools
├── docker-compose.yml              # Local services (PostgreSQL, Valkey, API)
└── .env.example                    # Environment variable contract and API key flags
```

---

## Core Invariants & Safety Principles

1. **Separation of Status Dimensions (PRD §7.1):** Independent lifecycle tracking for `payment_status` (provider truth), `funds_status` (customer claim vs provider credit/debit), `refund_status`, `settlement_status`, and `case_status`.
2. **Authority Boundary:** Authentic signed provider events are the **only** authority for payment state. Uploaded customer receipts and OCR/multimodal extractions are stored strictly as **claims** (`EvidenceClaim`).
3. **No Unchecked Financial Mutations:** LLMs cannot change payment status, execute refunds, or freeze accounts. Sensitive actions generate drafts requiring explicit human authorization (`Approval`).
4. **Interchangeable Models & Zero-Key Demo Mode:** Runs out of the box in `DEMO_MODE=true` with `StubModelProvider` and `SimulatorPaymentProvider`. Swap between open-weight **Gemma 4** and managed **Gemini API** via configuration.
5. **Integer Minor Units:** All monetary values stored as positive 64-bit integers (`amount_minor`, e.g. paise/cents) with ISO 4217 currency codes. Floating-point money arithmetic is prohibited.
6. **Tenant-Scoped HMAC Tokenization:** Sensitive customer, device, and instrument identifiers are cryptographically tokenized per tenant before graph insertion or logging.

---

## External API Keys & Configuration Flags

The platform runs completely offline in `DEMO_MODE=true` with no external keys required. When connecting to production or cloud environments, configure the following keys in your `.env` file:

| Service / Provider | Environment Variable | Purpose | Required When |
|---|---|---|---|
| **Razorpay Gateway** | `RAZORPAY_KEY_ID` | Gateway API authentication | `PAYMENT_PROVIDER=razorpay` |
| **Razorpay Gateway** | `RAZORPAY_KEY_SECRET` | Gateway API secret key | `PAYMENT_PROVIDER=razorpay` |
| **Razorpay Gateway** | `RAZORPAY_WEBHOOK_SECRET` | HMAC-SHA256 webhook signature validation | `PAYMENT_PROVIDER=razorpay` |
| **Google Gemini API** | `GEMINI_API_KEY` | Google GenAI SDK multimodal document analysis | `MODEL_PROVIDER=gemini` |
| **Gemma 4 Inference** | `GEMMA_ENDPOINT_URL` | DigitalOcean GPU Droplet / vLLM serving endpoint | `MODEL_PROVIDER=gemma` |
| **Gemma 4 Inference** | `GEMMA_AUTH_TOKEN` | Bearer token for private GPU inference | `MODEL_PROVIDER=gemma` |
| **PostgreSQL / AGE** | `DATABASE_URL` | Relational store & Apache AGE connection string | Production database |
| **Valkey Queue** | `VALKEY_URL` | Background task queue & idempotency cache | Production queue |
| **DO Spaces / MinIO** | `SPACES_ACCESS_KEY` | Object storage for encrypted evidence files | Object storage sync |
| **DO Spaces / MinIO** | `SPACES_SECRET_KEY` | Object storage secret key | Object storage sync |
| **TigerGraph (Optional)** | `TIGERGRAPH_HOST`, `TIGERGRAPH_SECRET` | Commercial graph cluster access | `GRAPH_ENGINE=tigergraph` |

---

## Local Development & Quickstart

### Prerequisites
- Python 3.12+ (managed with `uv`)
- Node.js v20+ / npm 10+
- Docker & Docker Compose (optional for local database)

### Setup & Testing
```bash
# 1. Clone & Enter repository
cd resolveX

# 2. Setup Python environment and install dependencies
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# 3. Copy default demo configuration
cp .env.example .env

# 4. Run the deterministic synthetic scenario generator
python scripts/seed_synthetic_scenarios.py

# 5. Run full quality gates (formatting, linter, typing, unit tests)
./scripts/run_quality_gates.sh

# 6. Start the FastAPI development server
uvicorn backend.app.main:app --reload --port 8000
```

Inspect API documentation at `http://localhost:8000/docs`.

---

## Phase 0 Status & Verification Report

- [x] Repository scaffolded and monorepo structure established.
- [x] Canonical domain enums, models, and Pydantic schemas built with strict validation.
- [x] Monetary integer minor unit invariants enforced (floats strictly rejected).
- [x] Payment (`SimulatorPaymentProvider`), Model (`StubModelProvider`), and Graph (`MemoryGraphStore`) protocols implemented.
- [x] Structured AI finding contract with strict evidence ID citations implemented.
- [x] Trusted runtime `SkillRegistry` with SHA-256 validation implemented.
- [x] PostgreSQL relational DDL (`001_initial_schema.sql`) and Apache AGE graph DDL (`002_apache_age_setup.sql`) created.
- [x] Deterministic synthetic scenario seed script (`scripts/seed_synthetic_scenarios.py`) operational.
- [x] Frontend mirrored TypeScript contracts created (`frontend/src/types/contracts.ts`).

---

## Phase 1 Status & Verification Report (Identity, Tenancy, Database & Audit)

- [x] Server-side authentication and JWT token generation/verification (`POST /api/v1/auth/login`, `GET /api/v1/auth/me`).
- [x] Server-side RBAC dependencies (`require_roles`) enforcing Customer, Support Analyst, Fraud Analyst, Supervisor, and Platform Admin access boundaries.
- [x] Tenant context middleware and request-scoped `X-Correlation-ID` propagation.
- [x] SQLAlchemy asynchronous models (`TenantModel`, `UserModel`, `PaymentModel`, `CaseModel`, `ApprovalModel`, `AuditEventModel`).
- [x] Tenant-scoped database repository (`TenantScopedRepository`) enforcing database-level tenant isolation.
- [x] Cross-tenant access tests fail closed (HTTP 403 / `SecurityError`).
- [x] Structured audit logging (`AuditService` & `GET /api/v1/audit`) recording tamper-evident SHA-256 metadata hashes on every state mutation.
- [x] Human approval recording (`Approval` workflow) for high-risk actions.
- [x] Quality gates passing: 33/33 tests passing with Ruff format/lint and mypy static typing clean.
