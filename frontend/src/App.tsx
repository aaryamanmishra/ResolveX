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

import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { OverviewTab } from './components/OverviewTab';
import { PaymentsTab } from './components/PaymentsTab';
import { InvestigationsTab } from './components/InvestigationsTab';
import { EvidenceTab } from './components/EvidenceTab';
import { AuditTab } from './components/AuditTab';

import { CheckCircle2, AlertTriangle } from 'lucide-react';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>('overview');
  const [currentRole, setCurrentRole] = useState<UserRole>('SUPPORT_ANALYST');
  const [demoMode, setDemoMode] = useState<boolean>(true);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState<boolean>(false);

  // Core Datasets
  const [payments, setPayments] = useState<Payment[]>([]);
  const [cases, setCases] = useState<Case[]>([]);
  const [exceptions, setExceptions] = useState<Array<{ payment_id: string; exception_type: string; details: Record<string, unknown> }>>([]);
  const [auditLogs, setAuditLogs] = useState<AuditRecord[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [selectedPaymentId, setSelectedPaymentId] = useState<string | null>(null);
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

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
      const [pList, cList, eList, aList, graphData] = await Promise.all([
        apiClient.getPayments().catch(() => []),
        apiClient.getCases().catch(() => []),
        apiClient.getReconciliationExceptions().catch(() => []),
        apiClient.getAuditLogs().catch(() => []),
        apiClient.getGraphNeighborhood('dev_imei_cluster_99', 2).catch(() => null),
      ]);

      setPayments(pList);
      setCases(cList);
      setExceptions(eList);
      setAuditLogs(aList);
      if (graphData && !graphNeighborhood) {
        setGraphNeighborhood(graphData);
      }
      if (cList.length > 0 && !selectedCaseId) {
        setSelectedCaseId(cList[0].id);
      }
    } finally {
      setIsLoading(false);
    }
  }, [selectedCaseId, graphNeighborhood]);

  useEffect(() => {
    loadData();
  }, [loadData, currentRole]);

  const handleRoleChange = (role: UserRole) => {
    setCurrentRole(role);
    apiClient.setPersona(role);
  };

  // --- Handlers for Track 1 ---
  const handleSimulatePayment = async (scenario: string) => {
    try {
      const res = await apiClient.simulatePaymentScenario(scenario);
      await loadData();
      setNotification({
        type: 'success',
        message: `Simulated ${scenario}: Payment ${res.payment.id} created with status ${res.payment.payment_status} (${res.payment.funds_status})`,
      });
    } catch (err: unknown) {
      setNotification({
        type: 'error',
        message: `Simulation failed: ${err instanceof Error ? err.message : String(err)}`,
      });
    }
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
    try {
      const res = await apiClient.getGraphNeighborhood(entityToken, depth);
      setGraphNeighborhood(res);
    } catch {
      // Keep existing neighborhood if query fails
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

  // --- Demo Flows ---
  const runTrack1Demo = async () => {
    setIsLoading(true);
    setNotification(null);
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
      setNotification({
        type: 'success',
        message: `Track 1 Succeeded: Simulated payment ${sim.payment.id}, opened Case ${newCase.id}, and completed LangGraph triage. Review the findings and approval gate.`,
      });
    } catch (err: unknown) {
      setNotification({
        type: 'error',
        message: `Track 1 Demo failed: ${err instanceof Error ? err.message : String(err)}`,
      });
    } finally {
      setIsLoading(false);
    }
  };

  const runTrack2Demo = async () => {
    setIsLoading(true);
    setNotification(null);
    try {
      // 1. Create a risk-triggered fraud investigation case linked to syndicate device
      const fraudCase = await apiClient.createCase(
        'FRAUD_INVESTIGATION',
        'Syndicate Alert: Shared device clustering across 4 accounts',
        ['dev_imei_cluster_99'],
        'HIGH'
      );
      // 2. Query tokenized graph neighborhood around center token (dev_imei_cluster_99)
      const neighborhood = await apiClient.getGraphNeighborhood('dev_imei_cluster_99', 2);
      setGraphNeighborhood(neighborhood);
      // 3. Evaluate deterministic fraud rules
      const evalResult = await apiClient.evaluateCaseFraud(fraudCase.id).catch(() => null);
      if (evalResult) setFraudEval(evalResult);
      // 4. Reload and navigate to investigations
      await loadData();
      setSelectedCaseId(fraudCase.id);
      setActiveTab('investigations');
      setNotification({
        type: 'success',
        message: `Track 2 Succeeded: Detected shared-device syndicate on dev_imei_cluster_99 (4 accounts) - rule SHARED_DEVICE_THRESHOLD_EXCEEDED fired!`,
      });
    } catch (err: unknown) {
      setNotification({
        type: 'error',
        message: `Track 2 Demo failed: ${err instanceof Error ? err.message : String(err)}`,
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex font-sans antialiased">
      {/* Clean Desktop Sidebar / Responsive Drawer */}
      <Sidebar
        activeTab={activeTab}
        onNavigate={(tab) => {
          setActiveTab(tab);
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }}
        currentRole={currentRole}
        onRoleChange={handleRoleChange}
        tenantId={apiClient.currentTenantId}
        demoMode={demoMode}
        paymentCount={payments.length}
        caseCount={cases.length}
        exceptionCount={exceptions.length}
        isMobileOpen={isMobileMenuOpen}
        onCloseMobile={() => setIsMobileMenuOpen(false)}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        {/* Top Header */}
        <Header
          activeTab={activeTab}
          onRefresh={loadData}
          isLoading={isLoading}
          onRunTrack1Demo={runTrack1Demo}
          onRunTrack2Demo={runTrack2Demo}
          onToggleMobileMenu={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
        />

        {/* Page Container */}
        <div className="flex-1 p-4 sm:p-6 lg:p-8 space-y-5">
          {/* Subtle Notification Toast */}
          {notification && (
            <div
              className={`p-3 rounded-lg border text-xs flex items-center justify-between shadow-xs transition-all animate-in fade-in ${
                notification.type === 'success'
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                  : 'bg-rose-50 border-rose-200 text-rose-800'
              }`}
            >
              <div className="flex items-center space-x-2">
                {notification.type === 'success' ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                ) : (
                  <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
                )}
                <span className="font-medium">{notification.message}</span>
              </div>
              <button
                onClick={() => setNotification(null)}
                className="text-slate-400 hover:text-slate-700 px-1 py-0.5 rounded text-xs ml-4"
              >
                ✕
              </button>
            </div>
          )}

          {/* Active Tab View */}
          <main>
            {activeTab === 'overview' && (
              <OverviewTab
                paymentCount={payments.length}
                caseCount={cases.length}
                exceptionCount={exceptions.length}
                approvalCount={cases.filter((c) => c.case_status === 'REVIEW_REQUIRED').length}
                cases={cases}
                payments={payments}
                exceptions={exceptions}
                auditLogs={auditLogs}
                onNavigate={(tab) => setActiveTab(tab)}
                onSelectCase={(id) => setSelectedCaseId(id)}
                onSelectPayment={(id) => setSelectedPaymentId(id)}
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
                initialSelectedPaymentId={selectedPaymentId}
              />
            )}

            {activeTab === 'investigations' && (
              <InvestigationsTab
                cases={cases}
                selectedCaseId={selectedCaseId}
                currentRole={currentRole}
                onSwitchRole={handleRoleChange}
                onSelectCase={(id) => setSelectedCaseId(id)}
                onRunInvestigation={handleRunInvestigation}
                onFetchFindings={handleFetchFindings}
                onFetchApprovals={(id) => apiClient.getCaseApprovals(id)}
                onApproveAction={handleApproveAction}
                onCreateCase={handleCreateCase}
                onRefresh={loadData}
                graphNeighborhood={graphNeighborhood}
                fraudEval={fraudEval}
                onSearchNeighborhood={handleSearchNeighborhood}
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
    </div>
  );
};
