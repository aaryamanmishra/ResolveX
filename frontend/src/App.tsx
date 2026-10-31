import React, { useState, useEffect, useCallback } from 'react';
import {
  apiClient,
  AuditRecord,
  GraphNeighborhoodResponse,
  FraudEvaluationResponse,
} from './api';
import {
  Case,
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

import { Navbar } from './components/Navbar';
import { OverviewTab } from './components/OverviewTab';
import { PaymentsTab } from './components/PaymentsTab';
import { InvestigationsTab } from './components/InvestigationsTab';
import { GraphCanvas } from './components/GraphCanvas';
import { EvidenceTab } from './components/EvidenceTab';
import { AuditTab } from './components/AuditTab';

import {
  LayoutDashboard,
  CreditCard,
  FolderOpen,
  Network,
  UploadCloud,
  Shield,
} from 'lucide-react';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>('overview');
  const [currentRole, setCurrentRole] = useState<UserRole>('SUPPORT_ANALYST');
  const [demoMode, setDemoMode] = useState<boolean>(true);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  // Core Data State
  const [payments, setPayments] = useState<Payment[]>([]);
  const [cases, setCases] = useState<Case[]>([]);
  const [exceptions, setExceptions] = useState<Array<{ payment_id: string; exception_type: string; details: Record<string, unknown> }>>([]);
  const [auditLogs, setAuditLogs] = useState<AuditRecord[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);

  // Graph State
  const [graphNeighborhood, setGraphNeighborhood] = useState<GraphNeighborhoodResponse | null>(null);
  const [fraudEval, setFraudEval] = useState<FraudEvaluationResponse | null>(null);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    try {
      // Login with current persona
      await apiClient.login();

      // Fetch health & configuration
      const health = await apiClient.getHealth().catch(() => ({ demo_mode: true }));
      setDemoMode(health.demo_mode ?? true);

      // Fetch core datasets
      const [pList, cList, eList, aList] = await Promise.all([
        apiClient.getPayments().catch(() => []),
        apiClient.getCases().catch(() => []),
        apiClient.getReconciliationExceptions().catch(() => []),
        apiClient.getAuditLogs().catch(() => []),
      ]);

      setPayments(pList);
      setCases(cList);
      setExceptions(eList);
      setAuditLogs(aList);
      if (cList.length > 0 && !selectedCaseId) {
        setSelectedCaseId(cList[0].id);
      }
    } finally {
      setIsLoading(false);
    }
  }, [selectedCaseId]);

  useEffect(() => {
    loadData();
  }, [loadData, currentRole]);

  const handleRoleChange = (role: UserRole) => {
    setCurrentRole(role);
    apiClient.setPersona(role);
  };

  // --- Handlers for Track 1 ---
  const handleSimulatePayment = async (scenario: string) => {
    await apiClient.simulatePaymentScenario(scenario);
    await loadData();
  };

  const handleReportDebit = async (paymentId: string, utr: string) => {
    await apiClient.reportCustomerDebit(paymentId, utr);
    await loadData();
  };

  const handleFetchTimeline = async (paymentId: string): Promise<PaymentEvent[]> => {
    return apiClient.getPaymentTimeline(paymentId);
  };

  // --- Handlers for Track 2 & Cases ---
  const handleCreateCase = async (type: CaseType, title: string, linkedPaymentIds: string[], priority: FraudSeverity) => {
    await apiClient.createCase(type, title, linkedPaymentIds, priority);
    await loadData();
  };

  const handleRunInvestigation = async (caseId: string, track: 'payment_issue' | 'fraud_investigation') => {
    await apiClient.investigateCase(caseId, track);
    await loadData();
  };

  const handleFetchFindings = async (caseId: string): Promise<StructuredInvestigationResult | null> => {
    try {
      return await apiClient.getCaseFindings(caseId);
    } catch {
      return null;
    }
  };

  const handleApproveAction = async (approvalId: string, decision: 'APPROVED' | 'REJECTED', reason: string) => {
    await apiClient.decideApproval(approvalId, decision, reason);
    await loadData();
  };

  // --- Handlers for Graph ---
  const handleSearchNeighborhood = async (entityToken: string, depth: number = 2) => {
    setIsLoading(true);
    try {
      const res = await apiClient.getGraphNeighborhood(entityToken, depth);
      setGraphNeighborhood(res);
    } finally {
      setIsLoading(false);
    }
  };

  const handleEvaluateFraud = async (caseId: string) => {
    setIsLoading(true);
    try {
      const res = await apiClient.evaluateCaseFraud(caseId);
      setFraudEval(res);
    } finally {
      setIsLoading(false);
    }
  };

  // --- Handlers for Evidence ---
  const handleUploadEvidence = async (
    caseId: string,
    file: File,
    sourceType: string,
    consentGranted: boolean
  ): Promise<{ asset: EvidenceAsset; download_url: string; claims: EvidenceClaim[] }> => {
    const res = await apiClient.uploadEvidence(caseId, file, sourceType, consentGranted);
    await loadData();
    return res;
  };

  const handleConfirmClaim = async (
    evidenceId: string,
    claimId: string,
    decision: VerificationState,
    confirmedValue?: string
  ) => {
    await apiClient.confirmClaim(evidenceId, claimId, decision, confirmedValue);
    await loadData();
  };

  // --- Automated 1-Click Demo Journey Runners (PRD Phase 6 Gate) ---
  const runTrack1Demo = async () => {
    setIsLoading(true);
    try {
      // 1. Simulate payment with customer reported debit mismatch
      const sim = await apiClient.simulatePaymentScenario('scenario_4_debit_mismatch');
      // 2. Open payment dispute case
      const newCase = await apiClient.createCase(
        'PAYMENT_DISCREPANCY',
        `Discrepancy: Debit reported for pending transaction ${sim.payment.id}`,
        [sim.payment.id],
        'HIGH'
      );
      // 3. Trigger LangGraph investigation agent
      await apiClient.investigateCase(newCase.id, 'payment_issue');
      // 4. Reload and navigate
      await loadData();
      setSelectedCaseId(newCase.id);
      setActiveTab('investigations');
    } finally {
      setIsLoading(false);
    }
  };

  const runTrack2Demo = async () => {
    setIsLoading(true);
    try {
      // 1. Create a risk-triggered fraud investigation case
      const fraudCase = await apiClient.createCase(
        'FRAUD_INVESTIGATION',
        'Syndicate Alert: Shared device clustering across 4 accounts',
        [],
        'HIGH'
      );
      // 2. Query tokenized graph neighborhood around center token
      const neighborhood = await apiClient.getGraphNeighborhood('cust_tok_synth_001', 2);
      setGraphNeighborhood(neighborhood);
      // 3. Evaluate deterministic fraud rules
      const evalResult = await apiClient.evaluateCaseFraud(fraudCase.id).catch(() => null);
      if (evalResult) setFraudEval(evalResult);
      // 4. Reload and navigate to graph canvas
      await loadData();
      setSelectedCaseId(fraudCase.id);
      setActiveTab('graph');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <Navbar
        currentRole={currentRole}
        onRoleChange={handleRoleChange}
        tenantId={apiClient.currentTenantId}
        demoMode={demoMode}
        onRunTrack1Demo={runTrack1Demo}
        onRunTrack2Demo={runTrack2Demo}
      />

      {/* Main Container */}
      <div className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Navigation Tabs */}
        <div className="flex space-x-1 border-b border-slate-800 pb-2 overflow-x-auto">
          {[
            { id: 'overview', label: 'Overview', icon: LayoutDashboard },
            { id: 'payments', label: 'Payments & Reconciliation', icon: CreditCard, count: payments.length },
            { id: 'investigations', label: 'Investigations & Cases', icon: FolderOpen, count: cases.length },
            { id: 'graph', label: 'Graph Fraud Canvas', icon: Network },
            { id: 'evidence', label: 'Multimodal Evidence', icon: UploadCloud },
            { id: 'audit', label: 'Audit Trail', icon: Shield, count: auditLogs.length },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center space-x-2 px-3.5 py-2 rounded-lg text-xs font-semibold whitespace-nowrap transition ${
                  isActive
                    ? 'bg-sky-600 text-white shadow-md shadow-sky-600/30'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                }`}
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span>{tab.label}</span>
                {tab.count !== undefined && (
                  <span
                    className={`px-1.5 py-0.5 rounded-full text-[10px] font-bold ${
                      isActive ? 'bg-sky-700 text-white' : 'bg-slate-800 text-slate-400'
                    }`}
                  >
                    {tab.count}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Tab Views */}
        <main>
          {activeTab === 'overview' && (
            <OverviewTab
              paymentCount={payments.length}
              caseCount={cases.length}
              exceptionCount={exceptions.length}
              approvalCount={cases.filter((c) => c.case_status === 'REVIEW_REQUIRED').length}
              fraudAlertCount={cases.filter((c) => c.case_type === 'FRAUD_INVESTIGATION').length}
              onNavigate={(tab) => setActiveTab(tab)}
              onRunTrack1Demo={runTrack1Demo}
              onRunTrack2Demo={runTrack2Demo}
            />
          )}

          {activeTab === 'payments' && (
            <PaymentsTab
              payments={payments}
              exceptions={exceptions}
              onRefresh={loadData}
              onSimulate={handleSimulatePayment}
              onReportDebit={handleReportDebit}
              onFetchTimeline={handleFetchTimeline}
            />
          )}

          {activeTab === 'investigations' && (
            <InvestigationsTab
              cases={cases}
              selectedCaseId={selectedCaseId}
              onSelectCase={(id) => setSelectedCaseId(id)}
              onRunInvestigation={handleRunInvestigation}
              onFetchFindings={handleFetchFindings}
              onApproveAction={handleApproveAction}
              onCreateCase={handleCreateCase}
              onRefresh={loadData}
            />
          )}

          {activeTab === 'graph' && (
            <GraphCanvas
              neighborhood={graphNeighborhood}
              fraudEval={fraudEval}
              onSearchNeighborhood={handleSearchNeighborhood}
              onEvaluateFraud={handleEvaluateFraud}
              isLoading={isLoading}
            />
          )}

          {activeTab === 'evidence' && (
            <EvidenceTab
              cases={cases}
              onUploadEvidence={handleUploadEvidence}
              onConfirmClaim={handleConfirmClaim}
              isLoading={isLoading}
            />
          )}

          {activeTab === 'audit' && (
            <AuditTab
              logs={auditLogs}
              onRefresh={loadData}
              isLoading={isLoading}
            />
          )}
        </main>
      </div>
    </div>
  );
};
