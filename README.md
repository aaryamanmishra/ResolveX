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
cd ResolveX

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

---

## Phase 2 Status & Verification Report (Payment Ingestion, Tracking & Reconciliation)

- [x] Payment provider abstraction supporting both `SimulatorPaymentProvider` and `RazorpayPaymentProvider`.
- [x] Signed webhook receiver (`POST /api/v1/webhooks/{provider}`) with exact raw-body HMAC-SHA256 signature verification.
- [x] Idempotency engine deduplicating replayed webhooks via `{tenant}:{provider}:{event_id}` without duplicate state application.
- [x] Status normalizer mapping provider states to canonical `PaymentStatus` and `FundsStatus`.
- [x] Append-only event timeline (`GET /api/v1/payments/{payment_id}/timeline`) preserving event times and received timestamps.
- [x] Out-of-order webhook delivery handling: terminal states (`SUCCEEDED`, `FAILED`, `REVERSED`) cannot regress to intermediate states.
- [x] Separate claim vs truth tracking: customer debit reporting (`POST /api/v1/payments/{payment_id}/report-debit`) sets `funds_status=CUSTOMER_REPORTED_DEBIT` without claiming provider debit.
- [x] Reconciliation engine (`GET /api/v1/payments/exceptions/queue`) automatically detecting:
  - Scenario 1: Normal payment success
  - Scenario 2: Pending payment
  - Scenario 3: Failed payment
  - Scenario 4: Customer reported debit mismatch
  - Scenario 5: Duplicate webhook
  - Scenario 6: Out-of-order delivery
  - Scenario 7: Refund pending past SLA (> 5 days)
  - Scenario 8: Amount mismatch (order expected vs provider reported)
  - Scenario 9: Missing order mapping
- [x] Quality gates passing: 44/44 tests passing with Ruff format/lint and mypy static typing clean.

---

## Phase 3 Status & Verification Report (Graph Model & Fraud Investigation Base)

- [x] GraphStore abstraction implementing `ApacheAGEGraphStore` (open-source default with openCypher builder) and optional `TigerGraphGraphStore`.
- [x] Graph materialization pipeline (`GraphService`) tokenizing customer, device, instrument, and UPI references via tenant-scoped HMAC.
- [x] Bounded graph traversals (depth clamped strictly between 1 and 4, max node limits enforced).
- [x] Tenant-isolated graph store queries (Tenant B cannot traverse Tenant A's relationships).
- [x] Deterministic fraud policy engine (`DeterministicFraudRuleEngine`) with reproducible reason codes:
  - Scenario 1: Shared device syndicate ($> 3$ customer tokens on 1 device) $\rightarrow$ `SHARED_DEVICE_THRESHOLD_EXCEEDED` (`HIGH` severity, requires human review).
  - Scenario 2: Repeated attempts across multiple instruments $\rightarrow$ `REPEATED_ATTEMPTS_MULTI_INSTRUMENTS` (`HIGH` severity).
  - Scenario 3: Transaction velocity bursts $\rightarrow$ `UNUSUAL_TRANSACTION_VELOCITY` (`MEDIUM` severity).
  - Scenario 4: Direct or 2-hop connection to prior flagged fraud cases $\rightarrow$ `CONNECTED_TO_HISTORICAL_FRAUD_CASE` (`CRITICAL` severity).
  - Scenario 5: Benign shared device filter ($\le 2$ users sharing family tablet) $\rightarrow$ automated fraud alert suppressed (preventing false-positive verdicts).
  - Scenario 6: Strict query bounding and provenance tracking.
- [x] REST API endpoints (`GET /api/v1/cases/{case_id}/graph`, `GET /api/v1/graph/neighborhood/{entity_token}`, `POST /api/v1/cases/{case_id}/evaluate-fraud`).
- [x] Quality gates passing: 53/53 tests passing with Ruff format/lint and mypy static typing clean.

---

## Phase 4 Status & Verification Report (Agent Harness, Skills & Human Review Gate)

- [x] **LangGraph Investigation Workflow (`InvestigationWorkflowRunner`):** Stateful bounded state graph executing `fetch_context` $\rightarrow$ `synthesize_findings` $\rightarrow$ `validate_findings` $\rightarrow$ `evaluate_policy` $\rightarrow$ `pause_for_approval` / `finalize`.
- [x] **Trusted Skill Registry:** Loads and verifies product runtime skills (`payment-triage`, `fraud-investigation`, `evidence-intake`, `refund-resolution`, `case-summary`) with immutable SHA-256 integrity verification.
- [x] **Model Context Protocol (MCP) Tool Server:** Exposes 13 typed, narrow tools (`get_payment`, `get_payment_events`, `get_provider_payment_status`, `get_refund_status`, `search_transactions`, `get_graph_neighborhood`, `get_case_history`, `retrieve_policy`, `get_evidence_metadata`, `extract_evidence_claims`, `create_case_draft`, `request_additional_evidence`, `draft_resolution_recommendation`).
- [x] **Safety Invariant Enforcement:** Server-side verification strictly blocks prohibited tools (`execute_refund`, `freeze_account`, `block_beneficiary`, `execute_sql`, `run_shell`). Attempts fail closed and log security audit records.
- [x] **Citation & Anti-Hallucination Validator:** Strict Pydantic schema validation (`StructuredInvestigationResult`) ensuring all findings cite genuine context evidence IDs. Fabricated or ungrounded assertions are rejected and moved to `unknowns`.
- [x] **Interchangeable Model Gateway (`ModelRouter`):** Seamless switching between Google Gemini API (`GeminiModelProvider`), open-weight Gemma 4 (`GemmaModelProvider`), and zero-key offline `StubModelProvider`.
- [x] **Deterministic Policy & Approval Routing:** Evaluates payment and fraud patterns to route recommendations. Any proposed financial modification (e.g. refund escalation) or high-severity alert triggers an approval pause (`CaseStatus.REVIEW_REQUIRED`) until supervisor review.
- [x] **REST API Endpoints:** Added `POST /api/v1/cases/{case_id}/investigate` and `GET /api/v1/cases/{case_id}/findings`.
- [x] **Quality gates passing:** 62/62 tests passing with Ruff format/lint and mypy static typing clean.

---

## Phase 5 Status & Verification Report (Multimodal Evidence Intake & Extraction)

- [x] **Secure Upload & Private Storage:** `SpacesStorageProvider` (DigitalOcean Spaces / S3) and zero-dependency `MemoryStorageProvider` with short-lived presigned upload/download URLs.
- [x] **MIME Magic Byte Verification:** Detects and verifies actual file headers (`image/png`, `image/jpeg`, `image/webp`, `application/pdf`, `audio/ogg`, `audio/mpeg`, `audio/wav`, `audio/webm`); detects and rejects extension spoofing.
- [x] **Antivirus & Malware Scanning (`MalwareScannerService`):** Scans files for EICAR virus signatures, executable ELF/PE binary headers, and active `<script>` injections; automatically quarantines malicious payloads.
- [x] **Multimodal Claim Extraction Pipeline (`MultimodalExtractionPipeline`):**
  - **Receipt Images:** Extracts `amount_minor`, `utr`, and merchant metadata with confidence scores ($0.0 \dots 1.0$) and 2D bounding boxes (`box_2d: [ymin, xmin, ymax, xmax]`).
  - **Bank Statement PDFs:** Extracts debit claims with page and line number locations.
  - **Customer Voice Notes:** Extracts customer claims with precise audio start/end timestamps.
- [x] **Consent Gate & Identifier Redaction:** Strict privacy gate preventing unauthorized transmission to external Gemini API without explicit tenant/customer consent; automatically redacts/masks 12-16 digit account numbers and 10-digit phone numbers before external calls.
- [x] **Payment Truth Protection Invariant:** Extracted claims generate `EvidenceClaim` records (`verification_state = UNVERIFIED`) and cannot overwrite provider-confirmed `Payment.payment_status`.
- [x] **User Confirmation Workflow:** Analysts or customers can confirm, correct, or reject candidate values (`POST /api/v1/evidence/{evidence_id}/confirm`), updating `VerificationState` to `USER_CONFIRMED` or `REJECTED`.
- [x] **Tenant Boundary Protection:** All evidence assets and candidate claims fail closed against cross-tenant access.
- [x] **REST API Endpoints:** `POST /api/v1/evidence/presign`, `POST /api/v1/evidence/upload`, `GET /api/v1/evidence/{evidence_id}`, `GET /api/v1/evidence/{evidence_id}/claims`, `POST /api/v1/evidence/{evidence_id}/confirm`.
- [x] **Quality gates passing:** 72/72 tests passing with Ruff format/lint and mypy static typing clean.

---

## Phase 6 Status & Verification Report (Frontend & Integrated Case Workflows)

- [x] **React 19 + TypeScript + Vite Frontend (`frontend/`):** Clean, high-density financial operations cockpit with dark modern UI, tabbed navigation, and zero-key local demo mode.
- [x] **Navbar & Persona Switcher (`Navbar.tsx`):**
  - Switch between `CUSTOMER`, `SUPPORT_ANALYST`, `FRAUD_ANALYST`, and `SUPERVISOR` roles with live RBAC token switching.
  - Live tenant indicator (`tenant_bank_alpha`), offline zero-key demo mode pill, and 1-click demo buttons.
- [x] **Overview Dashboard (`OverviewTab.tsx`):**
  - Key operational metrics: Total Payments, Active Cases, Pending Human Approvals, and Reconciled Funds.
  - Track 1 & Track 2 quick-start cards and 1-click end-to-end automated demo scenarios.
- [x] **Track 1 Payment Operations (`PaymentsTab.tsx`):**
  - Searchable, filterable transactions table with multi-dimensional status chips (`PaymentStatus`, `FundsStatus`, `RefundStatus`).
  - Interactive payment simulator with scenario presets (Success, Pending, Failed, Debit Discrepancy).
  - Out-of-order event timeline modal with provider payload hashes and raw timestamps.
  - Customer debit claim reporting modal with bank reference / UTR intake.
  - Unresolved reconciliation exceptions queue (detecting all 9 PRD §15.1 scenarios).
- [x] **Track 2 Fraud Investigation Cockpit (`InvestigationsTab.tsx` & `GraphCanvas.tsx`):**
  - Case queue filterable by status and priority severity (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
  - 1-Click LangGraph Agent Runner executing bounded investigation steps with real-time progress indicators.
  - Canonical Structured Findings Card conforming strictly to PRD §9.5 (synthesis summary, provider truth vs customer claims, grounded citations, explicit unknowns, and model metadata).
  - SVG Graph Visualizer rendering tokenized entity relationships (customers, devices, cards, UPI IDs, merchants) with vertex inspector, deterministic rule indicators, and benign household filter indicator.
  - Human Review Gate Card for sensitive actions (refund authorization, account freezes) with supervisor approval/rejection sign-off.
- [x] **Multimodal Evidence Intake (`EvidenceTab.tsx`):**
  - Secure upload dropzone for receipt images, statement PDFs, and voice note audio.
  - Antivirus & malware validation badges (quarantines malicious uploads).
  - Bounded candidate claim cards showing extracted amounts, UTRs, and 2D bounding boxes / page numbers / audio timestamps.
  - Explicit consent toggle governing Gemini API fallback with automatic PII redaction.
  - User confirmation workflow allowing customers or analysts to confirm or correct candidate values.
- [x] **Tamper-Evident Audit Inspector (`AuditTab.tsx`):**
  - Immutable audit trail table with actor IDs, action verbs, resource targets, and SHA-256 metadata hash inspector.
- [x] **Automated End-to-End Demo Journey Tests (`test_demo_journeys.py`):**
  - Track 1 end-to-end: payment simulation $\rightarrow$ discrepancy claim $\rightarrow$ agent triage $\rightarrow$ receipt upload $\rightarrow$ claim confirmation $\rightarrow$ supervisor approval $\rightarrow$ audit verification.
  - Track 2 end-to-end: syndicate graph generation $\rightarrow$ deterministic rule detection $\rightarrow$ agent graph investigation $\rightarrow$ supervisor freeze sign-off $\rightarrow$ audit trail.
  - Verified 100% operational in `DEMO_MODE=true` with zero external API keys.
- [x] **Quality gates passing:** 74/74 tests passing, Ruff linting clean, Ruff format clean, Mypy typing clean, and Vite production bundle compiling in < 1s.

---

## Phase 7 Status & Release Report (Security, Evaluation & DigitalOcean Deployment)

- [x] **DigitalOcean App Platform Deployment Specification (`infra/digitalocean-app.yaml`):**
  - High-availability dual-instance backend web service (`resolvex-api`) with healthcheck on `/health`.
  - Production Single Page Application web service (`resolvex-frontend`) with Nginx reverse proxy.
  - DigitalOcean Managed PostgreSQL 16 database cluster configuration.
  - DigitalOcean Managed Valkey / Redis instance for task queueing and caching.
  - DigitalOcean Spaces private object storage integration (`blr1` region) with presigned S3 URLs.
  - Private VPC network scoping (`10.245.0.0/16`) to GPU Droplet running Gemma 4 inference.
- [x] **Production Multi-Stage Containerization:**
  - `infra/Dockerfile.frontend`: Node.js 20 build stage $\rightarrow$ hardened Nginx 1.27 Alpine runtime with CSP, XSS, and frame protection headers.
  - `infra/Dockerfile.api`: Python 3.12 slim with uv installer, non-root `appuser`, and Docker healthcheck.
  - `infra/Dockerfile.age`: PostgreSQL 16 + Apache AGE graph engine extension container.
  - `docker-compose.yml`: Full-stack local orchestration including frontend, backend, PostgreSQL, and Valkey.
- [x] **Security Evaluation Suite (`backend/tests/test_security_evaluations.py`):**
  - Indirect prompt injection defense: Verified that malicious text inside OCR receipts or case titles cannot force refunds or bypass approvals.
  - Secret & credential leakage prevention: Verified responses, OpenAPI docs, and logs never expose private keys or passwords.
  - Cross-tenant penetration defense: Verified strict tenant scoping across cases, graph vertices, and audit trails.
  - Human review enforcement: Verified non-supervisors receive `403 Forbidden` on sensitive financial approval actions.
- [x] **Quantitative Model & Policy Evaluation Benchmark (`scripts/evaluate_models.py` & `backend/tests/test_model_evaluations.py`):**
  - Track 1 Citation Precision: **100.0%** (80/80 valid claims verified against provider evidence).
  - Track 1 Hallucination Quarantine: **100.0%** (20/20 fabricated claims isolated into explicit unknowns).
  - Track 2 Benign False-Positive Rate: **0.0%** (25/25 family devices suppressed from false fraud alerts).
  - Track 2 Syndicate Detection Recall: **100.0%** (25/25 multi-account device rings detected with HIGH severity).
  - Latency: **0.22ms** per deterministic graph evaluation pass.
- [x] **Clean-Environment Deployment Smoke Rehearsal (`scripts/deploy_smoke_test.sh`):**
  - Automated 7-step deployment rehearsal script testing live API health, UI availability, authentication, payment simulation, LangGraph triage, graph fraud rules, supervisor sign-offs, and SHA-256 audit logs.
- [x] **Production Documentation:**
  - `docs/DEPLOYMENT_GUIDE.md`: Architecture diagram, deployment runbook, disaster recovery/backups, and rollbacks.
  - `docs/EVALUATION_REPORT.md`: Comprehensive empirical evaluation benchmark, invariant adherence, and disclosed limitations.
- [x] **Final Quality Gates Passing:** 83/83 unit, integration, security, and model evaluation tests passing cleanly; 100% type-safe and format-checked.
