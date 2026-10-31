/**
 * ResolveX AI — Frontend Canonical TypeScript Contracts.
 * Mirrored directly from backend/app/domain for contract-first consistency.
 */

export type PaymentStatus =
  | "CREATED"
  | "INITIATED"
  | "PENDING"
  | "SUCCEEDED"
  | "FAILED"
  | "EXPIRED"
  | "REVERSED"
  | "UNKNOWN";

export type FundsStatus =
  | "NOT_REPORTED"
  | "CUSTOMER_REPORTED_DEBIT"
  | "PROVIDER_CONFIRMED_DEBIT"
  | "PROVIDER_CONFIRMED_CREDIT"
  | "UNKNOWN";

export type RefundStatus =
  | "NOT_APPLICABLE"
  | "NOT_INITIATED"
  | "REQUESTED"
  | "PENDING"
  | "PROCESSED"
  | "FAILED"
  | "UNKNOWN";

export type SettlementStatus =
  | "NOT_APPLICABLE"
  | "PENDING"
  | "SETTLED"
  | "MISMATCH"
  | "UNKNOWN";

export type CaseStatus =
  | "NEW"
  | "TRIAGING"
  | "AWAITING_EVIDENCE"
  | "REVIEW_REQUIRED"
  | "ESCALATED"
  | "RESOLVED"
  | "CLOSED";

export type CaseType =
  | "PAYMENT_DISCREPANCY"
  | "FRAUD_INVESTIGATION"
  | "REFUND_DELAY"
  | "UNRECOGNIZED_TRANSACTION";

export type FraudSeverity = "NONE" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export type UserRole =
  | "CUSTOMER"
  | "SUPPORT_ANALYST"
  | "FRAUD_ANALYST"
  | "SUPERVISOR"
  | "PLATFORM_ADMIN";

export type EvidenceSourceType =
  | "RECEIPT_IMAGE"
  | "PDF_STATEMENT"
  | "VOICE_NOTE"
  | "NOTIFICATION_SCREENSHOT"
  | "WEBHOOK_PAYLOAD"
  | "SYSTEM_LOG";

export type VerificationState =
  | "UNVERIFIED"
  | "USER_CONFIRMED"
  | "REJECTED"
  | "PROVIDER_MATCHED";

export type ApprovalDecision =
  | "PENDING"
  | "APPROVED"
  | "REJECTED"
  | "RETURNED_FOR_EVIDENCE";

export interface Payment {
  id: string;
  tenant_id: string;
  merchant_id: string;
  order_ref: string;
  provider: string;
  provider_payment_id: string;
  amount_minor: number; // Integer minor units (e.g. paise)
  currency: string;
  payment_status: PaymentStatus;
  funds_status: FundsStatus;
  created_at: string;
  updated_at: string;
}

export interface PaymentEvent {
  id: string;
  payment_id: string;
  provider_event_id: string;
  event_type: string;
  raw_status: string;
  normalized_status: PaymentStatus;
  source: string;
  event_time: string;
  received_at: string;
  payload_hash: string;
  idempotency_key: string;
}

export interface Refund {
  id: string;
  payment_id: string;
  provider_refund_id: string;
  amount_minor: number;
  currency: string;
  refund_status: RefundStatus;
  requested_at: string;
  updated_at: string;
}

export interface Case {
  id: string;
  tenant_id: string;
  case_type: CaseType;
  title: string;
  description: string;
  linked_payment_ids: string[];
  priority: FraudSeverity;
  case_status: CaseStatus;
  owner_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface EvidenceAsset {
  id: string;
  tenant_id: string;
  case_id: string;
  storage_key: string;
  mime_type: string;
  file_size_bytes: number;
  content_hash: string;
  source_type: EvidenceSourceType;
  scan_status: string;
  retention_until: string;
  created_at: string;
}

export interface EvidenceClaim {
  id: string;
  evidence_asset_id: string;
  field_name: string;
  candidate_value: string;
  confidence: number;
  verification_state: VerificationState;
  source_location: Record<string, unknown>;
  created_at: string;
}

export interface Approval {
  id: string;
  case_id: string;
  tenant_id: string;
  action_draft: Record<string, unknown>;
  requested_by: string;
  decision: ApprovalDecision;
  reviewed_by?: string | null;
  reason?: string | null;
  timestamp: string;
}

export interface InvestigationFinding {
  code: string;
  statement: string;
  evidence_ids: string[];
  confidence: number;
  uncertainty?: string | null;
}

export interface RecommendedNextStep {
  action: string;
  requires_human_approval: boolean;
  external_side_effect: boolean;
  action_payload?: Record<string, string>;
}

export interface StructuredInvestigationResult {
  case_id: string;
  track: "payment_issue" | "fraud_investigation";
  summary: string;
  payment_state: {
    normalized_status: PaymentStatus;
    source: string;
    as_of: string;
  };
  findings: InvestigationFinding[];
  unknowns: string[];
  recommended_next_step: RecommendedNextStep;
  model_metadata: {
    provider: string;
    model_id: string;
    prompt_version: string;
    execution_time_ms: number;
  };
}

export interface GraphVertex {
  id: string;
  tenant_id: string;
  label: string;
  properties: Record<string, unknown>;
  is_tokenized: boolean;
  created_at: string;
}

export interface GraphEdge {
  id: string;
  tenant_id: string;
  source_id: string;
  target_id: string;
  label: string;
  source_record_id: string;
  observed_at: string;
  confidence: number;
  source_type: string;
  inferred: boolean;
  properties: Record<string, unknown>;
}

export interface GraphNeighborhood {
  center_vertex_id: string;
  depth: number;
  vertices: GraphVertex[];
  edges: GraphEdge[];
  total_nodes: number;
  total_edges: number;
}
