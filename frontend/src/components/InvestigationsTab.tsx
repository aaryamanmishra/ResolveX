import React, { useState, useEffect } from 'react';
import {
  Approval,
  Case,
  CaseStatus,
  CaseType,
  FraudSeverity,
  StructuredInvestigationResult,
  UserRole,
} from '../types/contracts';
import {
  FolderOpen,
  Play,
  CheckCircle2,
  AlertTriangle,
  Clock,
  ShieldAlert,
  HelpCircle,
  ArrowRight,
  Plus,
  RefreshCw,
  X,
} from 'lucide-react';

interface InvestigationsTabProps {
  cases: Case[];
  selectedCaseId: string | null;
  currentRole: UserRole;
  onSwitchRole?: (role: UserRole) => void;
  onSelectCase: (caseId: string) => void;
  onRunInvestigation: (caseId: string, track: 'payment_issue' | 'fraud_investigation') => Promise<void>;
  onFetchFindings: (caseId: string) => Promise<StructuredInvestigationResult | null>;
  onFetchApprovals: (caseId: string) => Promise<Approval[]>;
  onApproveAction: (approvalId: string, decision: 'APPROVED' | 'REJECTED', reason: string) => Promise<void>;
  onCreateCase: (type: CaseType, title: string, linkedPaymentIds: string[], priority: FraudSeverity) => Promise<void>;
  onRefresh: () => void;
}

export const InvestigationsTab: React.FC<InvestigationsTabProps> = ({
  cases,
  selectedCaseId,
  currentRole,
  onSwitchRole,
  onSelectCase,
  onRunInvestigation,
  onFetchFindings,
  onFetchApprovals,
  onApproveAction,
  onCreateCase,
  onRefresh,
}) => {
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [activeFindings, setActiveFindings] = useState<StructuredInvestigationResult | null>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [investigating, setInvestigating] = useState(false);
  const [approvalReason, setApprovalReason] = useState('');
  const [approving, setApproving] = useState(false);

  // New Case Modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newType, setNewType] = useState<CaseType>('PAYMENT_DISCREPANCY');
  const [newPriority, setNewPriority] = useState<FraudSeverity>('MEDIUM');
  const [newPaymentId, setNewPaymentId] = useState('');

  const selectedCase = cases.find((c) => c.id === selectedCaseId) || cases[0] || null;

  const filteredCases = cases.filter(
    (c) => statusFilter === 'ALL' || c.case_status === statusFilter
  );

  // Auto-fetch findings and approvals when selected case changes
  useEffect(() => {
    if (selectedCase) {
      onFetchFindings(selectedCase.id)
        .then((f) => setActiveFindings(f))
        .catch(() => setActiveFindings(null));
      onFetchApprovals(selectedCase.id)
        .then((apprs) => setApprovals(apprs))
        .catch(() => setApprovals([]));
    }
  }, [selectedCase?.id]);

  const handleSelectCase = async (c: Case) => {
    onSelectCase(c.id);
    setActiveFindings(null);
    setApprovals([]);
    try {
      const [findings, apprs] = await Promise.all([
        onFetchFindings(c.id).catch(() => null),
        onFetchApprovals(c.id).catch(() => []),
      ]);
      setActiveFindings(findings);
      setApprovals(apprs);
    } catch {
      setActiveFindings(null);
      setApprovals([]);
    }
  };

  const handleTriggerInvestigation = async () => {
    if (!selectedCase) return;
    setInvestigating(true);
    try {
      const track = selectedCase.case_type === 'FRAUD_INVESTIGATION' ? 'fraud_investigation' : 'payment_issue';
      await onRunInvestigation(selectedCase.id, track);
      const [findings, apprs] = await Promise.all([
        onFetchFindings(selectedCase.id).catch(() => null),
        onFetchApprovals(selectedCase.id).catch(() => []),
      ]);
      setActiveFindings(findings);
      setApprovals(apprs);
      onRefresh();
    } finally {
      setInvestigating(false);
    }
  };

  const handleDecision = async (approvalId: string, decision: 'APPROVED' | 'REJECTED') => {
    setApproving(true);
    try {
      await onApproveAction(approvalId, decision, approvalReason || (decision === 'APPROVED' ? 'Approved by supervisor' : 'Rejected'));
      setApprovalReason('');
      onRefresh();
      if (selectedCase) {
        const [findings, apprs] = await Promise.all([
          onFetchFindings(selectedCase.id).catch(() => null),
          onFetchApprovals(selectedCase.id).catch(() => []),
        ]);
        setActiveFindings(findings);
        setApprovals(apprs);
      }
    } finally {
      setApproving(false);
    }
  };

  const handleCreateSubmit = async () => {
    if (!newTitle.trim()) return;
    const pids = newPaymentId.trim() ? [newPaymentId.trim()] : [];
    await onCreateCase(newType, newTitle, pids, newPriority);
    setShowCreateModal(false);
    setNewTitle('');
    setNewPaymentId('');
  };

  const getPriorityBadge = (p: string) => {
    switch (p) {
      case 'CRITICAL':
        return 'bg-rose-500/10 text-rose-400 border-rose-500/20';
      case 'HIGH':
        return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
      case 'MEDIUM':
        return 'bg-blue-500/10 text-blue-400 border-blue-500/20';
      default:
        return 'bg-slate-700 text-slate-300 border-slate-600';
    }
  };

  const getStatusBadge = (s: CaseStatus) => {
    switch (s) {
      case 'RESOLVED':
        return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
      case 'REVIEW_REQUIRED':
        return 'bg-purple-500/10 text-purple-400 border-purple-500/20';
      case 'TRIAGING':
        return 'bg-sky-500/10 text-sky-400 border-sky-500/20';
      case 'ESCALATED':
        return 'bg-rose-500/10 text-rose-400 border-rose-500/20';
      default:
        return 'bg-slate-800 text-slate-400 border-slate-700';
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      {/* Left Column: Case Queue */}
      <div className="lg:col-span-4 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <FolderOpen className="w-4 h-4 text-sky-400" />
            <h2 className="font-bold text-white text-sm">Case Queue ({cases.length})</h2>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-2.5 py-1 rounded-md bg-sky-600 hover:bg-sky-500 text-white text-xs font-medium flex items-center space-x-1"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>New Case</span>
          </button>
        </div>

        {/* Filter Pills */}
        <div className="flex flex-wrap gap-1 text-[11px]">
          {['ALL', 'NEW', 'TRIAGING', 'REVIEW_REQUIRED', 'RESOLVED'].map((filter) => (
            <button
              key={filter}
              onClick={() => setStatusFilter(filter)}
              className={`px-2.5 py-1 rounded-md font-medium transition ${
                statusFilter === filter
                  ? 'bg-sky-600 text-white'
                  : 'bg-slate-900 text-slate-400 hover:bg-slate-800'
              }`}
            >
              {filter.replace('_', ' ')}
            </button>
          ))}
        </div>

        {/* Case List */}
        <div className="space-y-2 max-h-[650px] overflow-y-auto pr-1">
          {filteredCases.length === 0 ? (
            <div className="text-center py-10 bg-slate-900/40 rounded-xl border border-slate-800 text-slate-500 text-xs">
              No cases matching status filter.
            </div>
          ) : (
            filteredCases.map((c) => (
              <div
                key={c.id}
                onClick={() => handleSelectCase(c)}
                className={`p-3.5 rounded-xl border transition cursor-pointer ${
                  selectedCase?.id === c.id
                    ? 'bg-slate-800/90 border-sky-500 shadow-md'
                    : 'bg-slate-900/60 border-slate-800/80 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className="font-mono text-xs font-semibold text-white">{c.id}</span>
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${getStatusBadge(c.case_status)}`}>
                    {c.case_status}
                  </span>
                </div>
                <h4 className="text-xs font-medium text-slate-200 line-clamp-1">{c.title}</h4>
                <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400">
                  <span className={`px-1.5 py-0.2 rounded border text-[10px] font-semibold ${getPriorityBadge(c.priority)}`}>
                    {c.priority}
                  </span>
                  <span>{new Date(c.created_at).toLocaleDateString()}</span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Right Column: Case Detail & LangGraph Investigation Canvas */}
      <div className="lg:col-span-8 space-y-4">
        {selectedCase ? (
          <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-5 space-y-5">
            {/* Case Header */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pb-4 border-b border-slate-800">
              <div>
                <div className="flex items-center space-x-2">
                  <span className="font-mono text-xs font-bold text-sky-400">{selectedCase.id}</span>
                  <span className={`px-2 py-0.5 rounded-full border text-[10px] font-bold ${getStatusBadge(selectedCase.case_status)}`}>
                    {selectedCase.case_status}
                  </span>
                  <span className={`px-2 py-0.5 rounded-full border text-[10px] font-bold ${getPriorityBadge(selectedCase.priority)}`}>
                    {selectedCase.priority} Priority
                  </span>
                </div>
                <h2 className="text-base font-bold text-white mt-1">{selectedCase.title}</h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  Type: <span className="text-slate-300 font-medium">{selectedCase.case_type}</span>
                  {selectedCase.linked_payment_ids.length > 0 && (
                    <span className="ml-2">
                      | Linked Payments:{' '}
                      <span className="font-mono text-sky-400">{selectedCase.linked_payment_ids.join(', ')}</span>
                    </span>
                  )}
                </p>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center space-x-2">
                <button
                  onClick={handleTriggerInvestigation}
                  disabled={investigating}
                  className="px-3.5 py-2 rounded-lg bg-gradient-to-r from-sky-600 to-indigo-600 hover:from-sky-500 hover:to-indigo-500 text-white text-xs font-semibold shadow-lg shadow-sky-600/20 flex items-center space-x-1.5 transition"
                >
                  {investigating ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Investigating...</span>
                    </>
                  ) : (
                    <>
                      <Play className="w-3.5 h-3.5" />
                      <span>Run LangGraph Agent</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Structured Investigation Findings Card (PRD §9.5) */}
            {activeFindings ? (
              <div className="space-y-4">
                <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      <span>Canonical AI Investigation Output (PRD §9.5 Schema)</span>
                    </h3>
                    <span className="text-[10px] font-mono text-slate-500">
                      Model: {activeFindings.model_metadata.provider} ({activeFindings.model_metadata.model_id})
                    </span>
                  </div>

                  {/* Summary */}
                  <div className="bg-slate-900/90 rounded-lg p-3 border border-slate-800 text-xs text-slate-200 leading-relaxed">
                    <span className="font-semibold text-sky-400">Executive Summary: </span>
                    {activeFindings.summary}
                  </div>

                  {/* Grounded Findings */}
                  <div>
                    <h4 className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-2">
                      Evidence-Grounded Findings ({activeFindings.findings.length})
                    </h4>
                    <div className="space-y-2">
                      {activeFindings.findings.map((f, i) => (
                        <div key={i} className="bg-slate-900/60 border border-slate-800 rounded-lg p-3 text-xs space-y-1.5">
                          <div className="flex items-center justify-between">
                            <span className="font-mono text-xs font-bold text-white">{f.code}</span>
                            <span className="text-[11px] text-emerald-400 font-semibold">
                              {(f.confidence * 100).toFixed(0)}% confidence
                            </span>
                          </div>
                          <p className="text-slate-300">{f.statement}</p>
                          <div className="flex items-center gap-1.5 pt-1">
                            <span className="text-[10px] text-slate-500">Cited Evidence IDs:</span>
                            {f.evidence_ids.map((eid) => (
                              <span
                                key={eid}
                                className="px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20 font-mono text-[10px]"
                              >
                                {eid}
                              </span>
                            ))}
                          </div>
                          {f.uncertainty && (
                            <div className="text-[11px] text-amber-400/90 flex items-start gap-1 pt-1">
                              <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                              <span>Caveat: {f.uncertainty}</span>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Unknowns List */}
                  {activeFindings.unknowns.length > 0 && (
                    <div className="bg-amber-950/20 border border-amber-500/20 rounded-lg p-3 text-xs">
                      <div className="flex items-center space-x-1.5 text-amber-400 font-semibold mb-1">
                        <HelpCircle className="w-3.5 h-3.5" />
                        <span>Explicit Unknowns / Missing Records</span>
                      </div>
                      <ul className="list-disc list-inside space-y-0.5 text-slate-300 text-[11px]">
                        {activeFindings.unknowns.map((u, i) => (
                          <li key={i}>{u}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Recommended Next Step */}
                  <div className="bg-indigo-950/30 border border-indigo-500/30 rounded-lg p-3 text-xs flex items-center justify-between">
                    <div>
                      <span className="text-[10px] text-indigo-400 font-bold uppercase tracking-wider block">
                        Recommended Operational Step
                      </span>
                      <span className="font-mono font-bold text-white text-sm">
                        {activeFindings.recommended_next_step.action}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      {activeFindings.recommended_next_step.requires_human_approval && (
                        <span className="px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20 text-[10px] font-bold">
                          Requires Approval
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Human-in-the-Loop Review Gate (PRD §6 FR-020) */}
                {selectedCase.case_status === 'REVIEW_REQUIRED' && (
                  <div className="bg-gradient-to-r from-purple-950/40 to-slate-950 border border-purple-500/40 rounded-xl p-4 space-y-3 shadow-lg">
                    <div className="flex items-center space-x-2 text-purple-300 font-bold text-sm">
                      <ShieldAlert className="w-4 h-4 text-purple-400" />
                      <span>Human Approval Gate (Operations Supervisor Sign-off Required)</span>
                    </div>
                    <p className="text-xs text-slate-300">
                      The LangGraph workflow has paused because the proposed action involves external financial implications or high-risk fraud alerts.
                      Review the evidence and recorded claims before signing off.
                    </p>

                    {/* Pending Action Summary */}
                    {(() => {
                      const pendingApproval = approvals.find((a) => a.decision === 'PENDING') || approvals[0];
                      const canApprove = currentRole === 'SUPERVISOR' || currentRole === 'PLATFORM_ADMIN';

                      return (
                        <>
                          {pendingApproval && (
                            <div className="bg-slate-900/90 rounded-lg p-3 border border-slate-800 text-xs space-y-1.5">
                              <div className="flex items-center justify-between text-slate-400">
                                <span className="font-mono text-purple-400 font-bold">{pendingApproval.id}</span>
                                <span className="text-[10px]">Status: <strong className="text-amber-400">{pendingApproval.decision}</strong></span>
                              </div>
                              <div className="text-slate-200">
                                <span className="text-slate-400">Proposed Action: </span>
                                <span className="font-semibold text-white">{String(pendingApproval.action_draft.action_type || 'ESCALATION')}</span>
                                {pendingApproval.action_draft.amount_minor !== undefined && (
                                  <span className="ml-2 font-mono text-emerald-400 font-semibold">
                                    ₹{((Number(pendingApproval.action_draft.amount_minor)) / 100).toFixed(2)}
                                  </span>
                                )}
                              </div>
                              {Boolean(pendingApproval.action_draft.reason) && (
                                <p className="text-slate-400 text-[11px]">
                                  Justification: {String(pendingApproval.action_draft.reason)}
                                </p>
                              )}
                            </div>
                          )}

                          {!canApprove && (
                            <div className="bg-amber-950/40 border border-amber-500/30 rounded-lg p-2.5 text-xs text-amber-300 flex items-center justify-between">
                              <span>
                                Persona Notice: Current role (<strong>{currentRole}</strong>) is read-only for approvals. Switch to <strong>Supervisor</strong> to sign off.
                              </span>
                              {onSwitchRole && (
                                <button
                                  type="button"
                                  onClick={() => onSwitchRole('SUPERVISOR')}
                                  className="px-2.5 py-1 bg-amber-600 hover:bg-amber-500 text-white font-semibold rounded text-[11px] transition shrink-0 ml-2 shadow"
                                >
                                  Switch to Supervisor
                                </button>
                              )}
                            </div>
                          )}

                          <div>
                            <label className="block text-xs font-medium text-slate-400 mb-1">
                              Supervisor Review Rationale / Notes
                            </label>
                            <input
                              type="text"
                              placeholder="e.g. Verified customer statement and approved refund escalation"
                              value={approvalReason}
                              onChange={(e) => setApprovalReason(e.target.value)}
                              disabled={!canApprove}
                              className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-purple-500 disabled:opacity-50"
                            />
                          </div>

                          <div className="flex justify-end space-x-2 pt-2">
                            <button
                              onClick={() => pendingApproval && handleDecision(pendingApproval.id, 'REJECTED')}
                              disabled={approving || !pendingApproval || !canApprove}
                              className="px-4 py-1.5 rounded-lg bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 border border-rose-500/30 text-xs font-semibold transition disabled:opacity-50"
                            >
                              Reject Action
                            </button>
                            <button
                              onClick={() => pendingApproval && handleDecision(pendingApproval.id, 'APPROVED')}
                              disabled={approving || !pendingApproval || !canApprove}
                              className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center space-x-1.5 shadow-lg shadow-emerald-600/20 transition disabled:opacity-50"
                            >
                              <CheckCircle2 className="w-3.5 h-3.5" />
                              <span>Approve & Finalize Action</span>
                            </button>
                          </div>
                        </>
                      );
                    })()}
                  </div>
                )}
              </div>
            ) : (
              <div className="py-12 text-center bg-slate-950/40 rounded-xl border border-slate-800 space-y-2">
                <Clock className="w-8 h-8 text-slate-600 mx-auto" />
                <h4 className="text-xs font-semibold text-slate-300">No AI Findings Yet</h4>
                <p className="text-[11px] text-slate-500 max-w-sm mx-auto">
                  Click "Run LangGraph Agent" above to fetch canonical context, evaluate evidence, and run deterministic policy rules.
                </p>
              </div>
            )}
          </div>
        ) : (
          <div className="py-20 text-center bg-slate-900/40 rounded-2xl border border-slate-800 text-slate-500 text-xs">
            Select a case from the queue on the left to inspect and investigate.
          </div>
        )}
      </div>

      {/* New Case Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md p-5 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="font-bold text-white text-sm flex items-center gap-2">
                <FolderOpen className="w-4 h-4 text-sky-400" />
                <span>Create Operational Case</span>
              </h3>
              <button onClick={() => setShowCreateModal(false)} className="text-slate-400 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">Case Title</label>
              <input
                type="text"
                placeholder="e.g. Customer reported UPI debit on failed transaction"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-sky-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Case Type</label>
                <select
                  value={newType}
                  onChange={(e) => setNewType(e.target.value as CaseType)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none"
                >
                  <option value="PAYMENT_DISCREPANCY">Payment Discrepancy</option>
                  <option value="FRAUD_INVESTIGATION">Fraud Investigation</option>
                  <option value="REFUND_DELAY">Refund Delay</option>
                  <option value="UNRECOGNIZED_TRANSACTION">Unrecognized Transaction</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Priority</label>
                <select
                  value={newPriority}
                  onChange={(e) => setNewPriority(e.target.value as FraudSeverity)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none"
                >
                  <option value="LOW">Low</option>
                  <option value="MEDIUM">Medium</option>
                  <option value="HIGH">High</option>
                  <option value="CRITICAL">Critical</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">Linked Payment ID (Optional)</label>
              <input
                type="text"
                placeholder="e.g. pay_demo_001"
                value={newPaymentId}
                onChange={(e) => setNewPaymentId(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-sky-500"
              />
            </div>

            <div className="flex justify-end space-x-2 pt-2">
              <button
                onClick={() => setShowCreateModal(false)}
                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs text-slate-300"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateSubmit}
                className="px-4 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-xs text-white font-medium flex items-center space-x-1"
              >
                <span>Create Case</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
