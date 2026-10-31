/**
 * Typed API Client for ResolveX AI.
 * Handles JWT authentication, tenant scoping, and calls FastAPI /api/v1 endpoints.
 */

import {
  Approval,
  ApprovalDecision,
  Case,
  CaseStatus,
  CaseType,
  EvidenceAsset,
  EvidenceClaim,
  FraudSeverity,
  Payment,
  PaymentEvent,
  StructuredInvestigationResult,
  UserRole,
  VerificationState,
} from './types/contracts';

const API_BASE = '/api/v1';

export interface AuditRecord {
  id: string;
  tenant_id: string;
  actor_id: string;
  action: string;
  resource_type: string;
  resource_id: string;
  timestamp: string;
  metadata_hash: string;
  details: Record<string, unknown>;
}

export interface GraphNode {
  id: string;
  label: string;
  properties: Record<string, unknown>;
}

export interface GraphEdgeData {
  id: string;
  source_id: string;
  target_id: string;
  label: string;
  confidence: number;
  inferred: boolean;
}

export interface GraphNeighborhoodResponse {
  center_vertex_id: string;
  depth: number;
  vertices: GraphNode[];
  edges: GraphEdgeData[];
  total_nodes: number;
  total_edges: number;
}

export interface InvestigateResponse {
  case_id: string;
  run_id: string;
  execution_status: string;
  requires_human_approval: boolean;
  approval_id: string | null;
  step_count: number;
  findings_count: number;
  latency_ms: number;
  summary: string;
  structured_result: StructuredInvestigationResult | null;
}

export interface FraudEvaluationResponse {
  case_id: string;
  is_alert: boolean;
  severity: FraudSeverity;
  reason_codes: string[];
  summary: string;
  requires_human_review: boolean;
  evidence_ids: string[];
}

export class ResolveXApiClient {
  private token: string = '';
  public currentRole: UserRole = 'SUPPORT_ANALYST';
  public currentUserId: string = 'usr_support_01';
  public currentTenantId: string = 'tenant_finops_01';

  constructor() {
    this.setPersona('SUPPORT_ANALYST');
  }

  public setPersona(role: UserRole) {
    this.currentRole = role;
    if (role === 'PLATFORM_ADMIN') {
      this.currentUserId = 'usr_admin_01';
    } else if (role === 'SUPERVISOR') {
      this.currentUserId = 'usr_supervisor_01';
    } else if (role === 'FRAUD_ANALYST') {
      this.currentUserId = 'usr_fraud_01';
    } else if (role === 'CUSTOMER') {
      this.currentUserId = 'usr_cust_01';
    } else {
      this.currentUserId = 'usr_support_01';
    }
  }

  public async login(): Promise<string> {
    const emailMap: Record<UserRole, string> = {
      PLATFORM_ADMIN: 'admin@apex.example.com',
      SUPERVISOR: 'supervisor@apex.example.com',
      FRAUD_ANALYST: 'fraud.analyst@apex.example.com',
      SUPPORT_ANALYST: 'support@apex.example.com',
      CUSTOMER: 'customer@apex.example.com',
    };

    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: emailMap[this.currentRole],
        password: 'password123',
        tenant_id: this.currentTenantId,
      }),
    });

    if (!res.ok) {
      throw new Error(`Login failed with status ${res.status}`);
    }

    const data = await res.json();
    this.token = data.access_token;
    return this.token;
  }

  private async getHeaders(): Promise<HeadersInit> {
    if (!this.token) {
      await this.login();
    }
    return {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${this.token}`,
    };
  }

  // --- Payments API ---
  public async getPayments(limit: number = 50): Promise<Payment[]> {
    const headers = await this.getHeaders();
    const res = await fetch(`${API_BASE}/payments?limit=${limit}`, { headers });
    if (!res.ok) throw new Error('Failed to fetch payments');
    return res.json();
  }

  public async getPayment(paymentId: string): Promise<Payment> {
    const headers = await this.getHeaders();
    const res = await fetch(`${API_BASE}/payments/${paymentId}`, { headers });
    if (!res.ok) throw new Error(`Payment ${paymentId} not found`);
    return res.json();
  }

  public async getPaymentTimeline(paymentId: string): Promise<PaymentEvent[]> {
    const headers = await this.getHeaders();
    const res = await fetch(`${API_BASE}/payments/${paymentId}/timeline`, { headers });
    if (!res.ok) throw new Error('Failed to fetch payment timeline');
    return res.json();
  }

  public async reportCustomerDebit(paymentId: string, utr?: string): Promise<Payment> {
    const headers = await this.getHeaders();
    const res = await fetch(`${API_BASE}/payments/${paymentId}/report-debit`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        claimed_utr: utr || `UPI${Date.now()}`,
        statement_reference: 'Customer mobile screenshot claim',
      }),
    });
    if (!res.ok) throw new Error('Failed to report customer debit');
    return res.json();
  }

  public async simulatePaymentScenario(scenario: string): Promise<{ payment: Payment; event: PaymentEvent }> {
    const headers = await this.getHeaders();
    const res = await fetch(`${API_BASE}/payments/simulate`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        scenario,
        amount_minor: 50000,
        currency: 'INR',
        merchant_id: 'merch_apex_01',
      }),
    });
    if (!res.ok) throw new Error('Failed to simulate scenario');
    return res.json();
  }

  public async getReconciliationExceptions(): Promise<Array<{ payment_id: string; exception_type: string; details: Record<string, unknown> }>> {
    const headers = await this.getHeaders();
    const res = await fetch(`${API_BASE}/payments/exceptions/queue`, { headers });
    if (!res.ok) throw new Error('Failed to fetch exceptions');
    return res.json();
  }

  // --- Cases API ---
  public async getCases(status?: CaseStatus): Promise<Case[]> {
    const headers = await this.getHeaders();
    const url = status ? `${API_BASE}/cases?status=${status}` : `${API_BASE}/cases`;
    const res = await fetch(url, { headers });
    if (!res.ok) throw new Error('Failed to fetch cases');
    return res.json();
  }

  public async createCase(caseType: CaseType, title: string, linkedPaymentIds: string[] = [], priority: FraudSeverity = 'LOW'): Promise<Case> {
    const headers = await this.getHeaders();
    const res = await fetch(`${API_BASE}/cases`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        case_type: caseType,
        title,
        linked_payment_ids: linkedPaymentIds,
        priority,
      }),
    });
    if (!res.ok) throw new Error('Failed to create case');
    return res.json();
  }

  public async investigateCase(caseId: string, track: 'payment_issue' | 'fraud_investigation' = 'payment_issue'): Promise<InvestigateResponse> {
    const headers = await this.getHeaders();
    const res = await fetch(`${API_BASE}/cases/${caseId}/investigate`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ track }),
    });
    if (!res.ok) throw new Error('Investigation failed');
    return res.json();
  }

  public async getCaseFindings(caseId: string): Promise<StructuredInvestigationResult> {
    const headers = await this.getHeaders();
    const res = await fetch(`${API_BASE}/cases/${caseId}/findings`, { headers });
    if (!res.ok) throw new Error('No findings for case');
    return res.json();
  }

  public async decideApproval(approvalId: string, decision: ApprovalDecision, reason?: string): Promise<Approval> {
    const headers = await this.getHeaders();
    const res = await fetch(`${API_BASE}/cases/approvals/${approvalId}/decision`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ decision, reason }),
    });
    if (!res.ok) throw new Error('Failed to record approval decision');
    return res.json();
  }

  // --- Graph API ---
  public async getGraphNeighborhood(entityToken: string, depth: number = 2): Promise<GraphNeighborhoodResponse> {
    const headers = await this.getHeaders();
    const res = await fetch(`${API_BASE}/graph/neighborhood/${entityToken}?depth=${depth}`, { headers });
    if (!res.ok) throw new Error('Failed to fetch graph neighborhood');
    return res.json();
  }

  public async evaluateCaseFraud(caseId: string): Promise<FraudEvaluationResponse> {
    const headers = await this.getHeaders();
    const res = await fetch(`${API_BASE}/cases/${caseId}/evaluate-fraud`, {
      method: 'POST',
      headers,
    });
    if (!res.ok) throw new Error('Failed to evaluate fraud');
    return res.json();
  }

  // --- Evidence API ---
  public async uploadEvidence(caseId: string, file: File, sourceType: string = 'RECEIPT_IMAGE', consentGranted: boolean = true): Promise<{ asset: EvidenceAsset; download_url: string; claims: EvidenceClaim[] }> {
    if (!this.token) {
      await this.login();
    }
    const formData = new FormData();
    formData.append('case_id', caseId);
    formData.append('source_type', sourceType);
    formData.append('consent_granted', String(consentGranted));
    formData.append('file', file);

    const res = await fetch(`${API_BASE}/evidence/upload`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${this.token}` },
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to upload evidence');
    }
    return res.json();
  }

  public async getEvidenceDetail(evidenceId: string): Promise<{ asset: EvidenceAsset; download_url: string; claims: EvidenceClaim[] }> {
    const headers = await this.getHeaders();
    const res = await fetch(`${API_BASE}/evidence/${evidenceId}`, { headers });
    if (!res.ok) throw new Error('Failed to fetch evidence detail');
    return res.json();
  }

  public async confirmClaim(evidenceId: string, claimId: string, decision: VerificationState, confirmedValue?: string): Promise<EvidenceClaim> {
    const headers = await this.getHeaders();
    const res = await fetch(`${API_BASE}/evidence/${evidenceId}/confirm`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        claim_id: claimId,
        decision,
        confirmed_value: confirmedValue,
      }),
    });
    if (!res.ok) throw new Error('Failed to confirm claim');
    return res.json();
  }

  // --- Audit API ---
  public async getAuditLogs(limit: number = 50): Promise<AuditRecord[]> {
    const headers = await this.getHeaders();
    const res = await fetch(`${API_BASE}/audit?limit=${limit}`, { headers });
    if (!res.ok) throw new Error('Failed to fetch audit records');
    return res.json();
  }

  // --- Health Check ---
  public async getHealth(): Promise<{ status: string; demo_mode: boolean; payment_provider: string; model_provider: string; graph_engine: string }> {
    const res = await fetch('/health');
    if (!res.ok) throw new Error('Health check failed');
    return res.json();
  }
}

export const apiClient = new ResolveXApiClient();
