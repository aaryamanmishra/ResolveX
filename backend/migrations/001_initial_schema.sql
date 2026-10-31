-- ResolveX AI — Migration 001: Canonical Relational Schema
-- PRD §7.2: All financial amounts stored as BIGINT integer minor units (paise/cents).
-- Enforces tenant isolation, idempotency keys, and audit logging.

CREATE TABLE IF NOT EXISTS tenants (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    retention_days INT NOT NULL DEFAULT 90,
    settings JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    role VARCHAR(32) NOT NULL,
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_users_tenant_email ON users(tenant_id, email);

CREATE TABLE IF NOT EXISTS merchants (
    id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    external_ref VARCHAR(128) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_merchants_tenant ON merchants(tenant_id, external_ref);

CREATE TABLE IF NOT EXISTS payments (
    id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    merchant_id VARCHAR(64) NOT NULL REFERENCES merchants(id),
    order_ref VARCHAR(128) NOT NULL,
    provider VARCHAR(64) NOT NULL,
    provider_payment_id VARCHAR(128) NOT NULL,
    amount_minor BIGINT NOT NULL CHECK (amount_minor > 0),
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',
    payment_status VARCHAR(32) NOT NULL DEFAULT 'CREATED',
    funds_status VARCHAR(32) NOT NULL DEFAULT 'NOT_REPORTED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_payments_tenant_order ON payments(tenant_id, order_ref);
CREATE INDEX IF NOT EXISTS idx_payments_tenant_provider_pay ON payments(tenant_id, provider, provider_payment_id);
CREATE INDEX IF NOT EXISTS idx_payments_tenant_status ON payments(tenant_id, payment_status);

CREATE TABLE IF NOT EXISTS payment_events (
    id VARCHAR(64) PRIMARY KEY,
    payment_id VARCHAR(64) NOT NULL REFERENCES payments(id) ON DELETE CASCADE,
    provider_event_id VARCHAR(128) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    raw_status VARCHAR(64) NOT NULL,
    normalized_status VARCHAR(32) NOT NULL,
    source VARCHAR(64) NOT NULL,
    event_time TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    payload_hash VARCHAR(64) NOT NULL,
    idempotency_key VARCHAR(255) NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_payment_events_pay_time ON payment_events(payment_id, event_time ASC);

CREATE TABLE IF NOT EXISTS refunds (
    id VARCHAR(64) PRIMARY KEY,
    payment_id VARCHAR(64) NOT NULL REFERENCES payments(id) ON DELETE CASCADE,
    provider_refund_id VARCHAR(128) NOT NULL,
    amount_minor BIGINT NOT NULL CHECK (amount_minor > 0),
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',
    refund_status VARCHAR(32) NOT NULL DEFAULT 'REQUESTED',
    requested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_refunds_payment ON refunds(payment_id);

CREATE TABLE IF NOT EXISTS settlement_records (
    id VARCHAR(64) PRIMARY KEY,
    merchant_id VARCHAR(64) NOT NULL REFERENCES merchants(id) ON DELETE CASCADE,
    provider VARCHAR(64) NOT NULL,
    settlement_ref VARCHAR(128) NOT NULL,
    amount_minor BIGINT NOT NULL CHECK (amount_minor > 0),
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',
    settlement_status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    settlement_time TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_settlements_merchant ON settlement_records(merchant_id, settlement_ref);

CREATE TABLE IF NOT EXISTS cases (
    id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    case_type VARCHAR(64) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    linked_payment_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    priority VARCHAR(32) NOT NULL DEFAULT 'LOW',
    case_status VARCHAR(32) NOT NULL DEFAULT 'NEW',
    owner_id VARCHAR(64) REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_cases_tenant_status ON cases(tenant_id, case_status);

CREATE TABLE IF NOT EXISTS evidence_assets (
    id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    case_id VARCHAR(64) NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    storage_key VARCHAR(255) NOT NULL,
    mime_type VARCHAR(128) NOT NULL,
    file_size_bytes BIGINT NOT NULL CHECK (file_size_bytes > 0),
    content_hash VARCHAR(64) NOT NULL,
    source_type VARCHAR(64) NOT NULL,
    scan_status VARCHAR(32) NOT NULL DEFAULT 'CLEAN',
    retention_until TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_evidence_case ON evidence_assets(case_id);

CREATE TABLE IF NOT EXISTS evidence_claims (
    id VARCHAR(64) PRIMARY KEY,
    evidence_asset_id VARCHAR(64) NOT NULL REFERENCES evidence_assets(id) ON DELETE CASCADE,
    field_name VARCHAR(64) NOT NULL,
    candidate_value TEXT NOT NULL,
    confidence NUMERIC(5, 4) NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    verification_state VARCHAR(32) NOT NULL DEFAULT 'UNVERIFIED',
    source_location JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_evidence_claims_asset ON evidence_claims(evidence_asset_id);

CREATE TABLE IF NOT EXISTS approvals (
    id VARCHAR(64) PRIMARY KEY,
    case_id VARCHAR(64) NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    tenant_id VARCHAR(64) NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    action_draft JSONB NOT NULL,
    requested_by VARCHAR(64) NOT NULL,
    decision VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    reviewed_by VARCHAR(64) REFERENCES users(id) ON DELETE SET NULL,
    reason TEXT,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_approvals_case_status ON approvals(case_id, decision);

CREATE TABLE IF NOT EXISTS audit_events (
    id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    actor_id VARCHAR(64) NOT NULL,
    action VARCHAR(64) NOT NULL,
    resource_type VARCHAR(64) NOT NULL,
    resource_id VARCHAR(64) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata_hash VARCHAR(64) NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_audit_tenant_time ON audit_events(tenant_id, timestamp DESC);

CREATE TABLE IF NOT EXISTS agent_runs (
    id VARCHAR(64) PRIMARY KEY,
    case_id VARCHAR(64) NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    workflow VARCHAR(64) NOT NULL,
    skill_versions JSONB NOT NULL DEFAULT '[]'::jsonb,
    model_provider VARCHAR(32) NOT NULL,
    model_id VARCHAR(64) NOT NULL,
    prompt_version VARCHAR(64) NOT NULL,
    tool_trace_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    status VARCHAR(32) NOT NULL DEFAULT 'COMPLETED',
    latency_ms INT NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_agent_runs_case ON agent_runs(case_id);
