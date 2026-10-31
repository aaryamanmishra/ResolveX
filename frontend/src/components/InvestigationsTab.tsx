import React, { useState, useEffect } from 'react';
import {
  Approval,
  Case,
  CaseType,
  FraudSeverity,
  StructuredInvestigationResult,
  UserRole,
} from '../types/contracts';
import { GraphNeighborhoodResponse, GraphNode, FraudEvaluationResponse } from '../api';
import {
  Play,
  CheckCircle2,
  AlertTriangle,
  Clock,
  ShieldAlert,
  HelpCircle,
  Plus,
  RefreshCw,
  X,
  Search,
  Network,
} from 'lucide-react';

interface InvestigationsTabProps {
  cases: Case[];
  selectedCaseId: string | null;
  currentRole: UserRole;
  onSwitchRole: (role: UserRole) => void;
  onSelectCase: (caseId: string) => void;
  onRunInvestigation: (caseId: string, track: 'payment_issue' | 'fraud_investigation') => Promise<void>;
  onFetchFindings: (caseId: string) => Promise<StructuredInvestigationResult | null>;
  onFetchApprovals: (caseId: string) => Promise<Approval[]>;
  onApproveAction: (approvalId: string, decision: 'APPROVED' | 'REJECTED', reason: string) => Promise<void>;
  onCreateCase: (type: CaseType, title: string, linkedPaymentIds: string[], priority: FraudSeverity) => Promise<void>;
  onRefresh: () => void;
  graphNeighborhood: GraphNeighborhoodResponse | null;
  fraudEval: FraudEvaluationResponse | null;
  onSearchNeighborhood: (entityToken: string, depth?: number) => Promise<void>;
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
  graphNeighborhood,
  fraudEval,
  onSearchNeighborhood,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [activeSection, setActiveSection] = useState<'summary' | 'graph' | 'findings' | 'approvals'>('summary');

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

  // Graph state inside case
  const [selectedGraphNode, setSelectedGraphNode] = useState<GraphNode | null>(null);

  const selectedCase = cases.find((c) => c.id === selectedCaseId) || cases[0] || null;

  const filteredCases = cases.filter((c) => {
    const matchesSearch =
      c.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.linked_payment_ids.some((pid) => pid.toLowerCase().includes(searchTerm.toLowerCase()));

    if (!matchesSearch) return false;
    if (statusFilter === 'ALL') return true;
    return c.case_status === statusFilter;
  });

  // Auto-fetch findings, approvals, and graph when selected case changes
  useEffect(() => {
    if (selectedCase) {
      onFetchFindings(selectedCase.id)
        .then((f) => setActiveFindings(f))
        .catch(() => setActiveFindings(null));

      onFetchApprovals(selectedCase.id)
        .then((apprs) => setApprovals(apprs))
        .catch(() => setApprovals([]));

      // Query graph centered on case entity if available
      const centerToken = selectedCase.linked_payment_ids[0] || selectedCase.id;
      if (centerToken) {
        onSearchNeighborhood(centerToken, 2).catch(() => {});
      }
    }
  }, [selectedCase?.id]);

  const handleSelectCase = async (c: Case) => {
    onSelectCase(c.id);
    setActiveFindings(null);
    setApprovals([]);
    setSelectedGraphNode(null);
    try {
      const [findings, apprs] = await Promise.all([
        onFetchFindings(c.id).catch(() => null),
        onFetchApprovals(c.id).catch(() => []),
      ]);
      setActiveFindings(findings);
      setApprovals(apprs);

      const centerToken = c.linked_payment_ids[0] || c.id;
      if (centerToken) {
        await onSearchNeighborhood(centerToken, 2).catch(() => {});
      }
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
      await onApproveAction(
        approvalId,
        decision,
        approvalReason || (decision === 'APPROVED' ? 'Approved by supervisor' : 'Rejected')
      );
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

  const getPriorityBadge = (priority: string) => {
    switch (priority) {
      case 'CRITICAL':
        return 'bg-rose-50 text-rose-700 border-rose-200';
      case 'HIGH':
        return 'bg-amber-50 text-amber-700 border-amber-200';
      case 'MEDIUM':
        return 'bg-blue-50 text-blue-700 border-blue-200';
      default:
        return 'bg-slate-50 text-slate-600 border-slate-200';
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'REVIEW_REQUIRED':
        return 'bg-purple-50 text-purple-700 border-purple-200';
      case 'IN_PROGRESS':
        return 'bg-blue-50 text-blue-700 border-blue-200';
      case 'NEW':
        return 'bg-amber-50 text-amber-700 border-amber-200';
      case 'RESOLVED':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200';
      default:
        return 'bg-slate-50 text-slate-600 border-slate-200';
    }
  };

  // Node visualization properties
  const nodes = graphNeighborhood?.vertices || [];
  const edges = graphNeighborhood?.edges || [];
  const width = 640;
  const height = 360;
  const centerX = width / 2;
  const centerY = height / 2;
  const radius = Math.min(centerX, centerY) - 60;

  const nodePositions: Record<string, { x: number; y: number }> = {};
  nodes.forEach((n, idx) => {
    if (idx === 0) {
      nodePositions[n.id] = { x: centerX, y: centerY };
    } else {
      const angle = ((idx - 1) / Math.max(nodes.length - 1, 1)) * 2 * Math.PI;
      nodePositions[n.id] = {
        x: centerX + radius * Math.cos(angle),
        y: centerY + radius * Math.sin(angle),
      };
    }
  });

  const getNodeColor = (label: string) => {
    switch (label) {
      case 'CustomerToken':
        return '#2563eb'; // blue-600
      case 'DeviceToken':
        return '#e11d48'; // rose-600
      case 'PaymentInstrumentToken':
        return '#d97706'; // amber-600
      case 'Payment':
        return '#059669'; // emerald-600
      default:
        return '#64748b'; // slate-500
    }
  };

  return (
    <div className="space-y-5 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-2 border-b border-slate-200/80">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Investigations & Cases</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Analyst workflow console for discrepancy triage, graph relationship intelligence, and human review sign-offs.
          </p>
        </div>

        <button
          onClick={() => setShowCreateModal(true)}
          className="px-3.5 py-1.5 rounded-md bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold shadow-xs transition-colors flex items-center space-x-1.5 shrink-0 self-start sm:self-auto"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>New Investigation</span>
        </button>
      </div>

      {/* Main Two-Column Layout (Master-Detail) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Left Column: Case Queue (4 cols) */}
        <div className="lg:col-span-4 bg-white border border-slate-200 rounded-lg shadow-2xs overflow-hidden flex flex-col">
          {/* Queue Filter Bar */}
          <div className="p-3 border-b border-slate-200 bg-slate-50/60 space-y-2">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
              <input
                type="text"
                placeholder="Search case, entity or payment..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full bg-white border border-slate-200 rounded-md pl-8 pr-3 py-1.5 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-blue-500"
              />
            </div>

            <div className="flex items-center space-x-1 overflow-x-auto text-[11px]">
              {['ALL', 'REVIEW_REQUIRED', 'IN_PROGRESS', 'NEW', 'RESOLVED'].map((status) => (
                <button
                  key={status}
                  onClick={() => setStatusFilter(status)}
                  className={`px-2 py-1 rounded-sm font-medium whitespace-nowrap transition-colors ${
                    statusFilter === status
                      ? 'bg-slate-200 text-slate-900 font-semibold'
                      : 'text-slate-500 hover:text-slate-900'
                  }`}
                >
                  {status === 'ALL' ? 'All' : status.replace(/_/g, ' ')}
                </button>
              ))}
            </div>
          </div>

          {/* Cases List */}
          <div className="divide-y divide-slate-100 max-h-[720px] overflow-y-auto">
            {filteredCases.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500">
                No cases matched the current search.
              </div>
            ) : (
              filteredCases.map((c) => {
                const isSelected = selectedCase?.id === c.id;
                return (
                  <div
                    key={c.id}
                    onClick={() => handleSelectCase(c)}
                    className={`p-3.5 hover:bg-slate-50 transition-colors cursor-pointer text-xs space-y-1.5 ${
                      isSelected ? 'bg-blue-50/50 border-l-2 border-l-blue-600' : ''
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-[11px] font-semibold text-slate-900">
                        {c.id}
                      </span>
                      <div className="flex items-center space-x-1.5">
                        <span className={`text-[10px] px-1.5 py-0.2 rounded-xs font-semibold border ${getPriorityBadge(c.priority)}`}>
                          {c.priority}
                        </span>
                        <span className={`text-[10px] px-1.5 py-0.2 rounded-xs font-semibold border ${getStatusBadge(c.case_status)}`}>
                          {c.case_status}
                        </span>
                      </div>
                    </div>

                    <div className="text-slate-800 font-medium line-clamp-1">
                      {c.title}
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-slate-400">
                      <span>{c.case_type.replace(/_/g, ' ')}</span>
                      <span className="font-mono text-[10px] text-slate-500">
                        {c.owner_id || 'unassigned'}
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Organized Investigation Detail Page (8 cols) */}
        <div className="lg:col-span-8 bg-white border border-slate-200 rounded-lg shadow-2xs overflow-hidden">
          {selectedCase ? (
            <div>
              {/* Case Header Banner */}
              <div className="p-5 border-b border-slate-200 bg-slate-50/40 space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="font-mono text-xs font-bold text-slate-900">{selectedCase.id}</span>
                      <span className={`px-2 py-0.5 rounded-xs text-[10px] font-semibold border ${getStatusBadge(selectedCase.case_status)}`}>
                        {selectedCase.case_status}
                      </span>
                      <span className={`px-2 py-0.5 rounded-xs text-[10px] font-semibold border ${getPriorityBadge(selectedCase.priority)}`}>
                        {selectedCase.priority} Priority
                      </span>
                    </div>
                    <h2 className="text-base font-bold text-slate-900 mt-1">{selectedCase.title}</h2>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Subject Entity: <span className="font-mono text-slate-800 font-medium">{selectedCase.linked_payment_ids[0] || 'Direct Entity Alert'}</span>
                      {selectedCase.owner_id && (
                        <span className="ml-2 font-normal">
                          • Assigned: <strong className="font-mono text-slate-700">{selectedCase.owner_id}</strong>
                        </span>
                      )}
                    </p>
                  </div>

                  <button
                    onClick={handleTriggerInvestigation}
                    disabled={investigating}
                    className="px-3.5 py-1.5 rounded-md bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow-xs flex items-center space-x-1.5 transition-colors shrink-0"
                  >
                    {investigating ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        <span>Running Agent...</span>
                      </>
                    ) : (
                      <>
                        <Play className="w-3.5 h-3.5" />
                        <span>Run LangGraph Agent</span>
                      </>
                    )}
                  </button>
                </div>

                {/* Sub-Navigation Tabs */}
                <div className="flex items-center space-x-1 border-t border-slate-200 pt-3 overflow-x-auto text-xs">
                  {[
                    { id: 'summary', label: 'Summary' },
                    { id: 'graph', label: 'Transaction Relationships (Graph)', count: nodes.length },
                    { id: 'findings', label: 'AI Findings', count: activeFindings?.findings.length },
                    { id: 'approvals', label: 'Review & Approvals', badge: selectedCase.case_status === 'REVIEW_REQUIRED' ? 'Action Required' : undefined },
                  ].map((subTab) => (
                    <button
                      key={subTab.id}
                      onClick={() => setActiveSection(subTab.id as any)}
                      className={`px-3 py-1.5 rounded-md font-medium whitespace-nowrap transition-colors flex items-center space-x-1.5 ${
                        activeSection === subTab.id
                          ? 'bg-white text-slate-900 border border-slate-200 shadow-2xs font-semibold'
                          : 'text-slate-500 hover:text-slate-900 hover:bg-slate-100'
                      }`}
                    >
                      <span>{subTab.label}</span>
                      {subTab.count !== undefined && (
                        <span className="text-[10px] px-1.5 rounded-full bg-slate-100 text-slate-600 font-semibold">
                          {subTab.count}
                        </span>
                      )}
                      {subTab.badge && (
                        <span className="text-[10px] px-1.5 py-0.2 rounded bg-purple-100 text-purple-800 font-semibold">
                          {subTab.badge}
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              </div>

              {/* Sub-Tab 1: Summary */}
              {activeSection === 'summary' && (
                <div className="p-5 space-y-4 text-xs">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="bg-slate-50 p-3 rounded-lg border border-slate-200/80 space-y-1">
                      <span className="text-slate-500 text-[11px] font-semibold uppercase tracking-wider">Case Details</span>
                      <div className="text-slate-900 font-medium">Type: {selectedCase.case_type}</div>
                      <div className="text-slate-600">Created: {new Date(selectedCase.created_at).toLocaleString()}</div>
                      <div className="text-slate-600">Tenant: <span className="font-mono">{selectedCase.tenant_id}</span></div>
                    </div>

                    <div className="bg-slate-50 p-3 rounded-lg border border-slate-200/80 space-y-1">
                      <span className="text-slate-500 text-[11px] font-semibold uppercase tracking-wider">Linked Records</span>
                      <div className="text-slate-900">
                        Linked Payments: {selectedCase.linked_payment_ids.length > 0 ? (
                          <span className="font-mono text-blue-600 font-semibold">{selectedCase.linked_payment_ids.join(', ')}</span>
                        ) : 'None'}
                      </div>
                      <div className="text-slate-600">Graph Entities: <span className="font-semibold">{nodes.length} nodes connected</span></div>
                    </div>
                  </div>

                  {selectedCase.description && (
                    <div className="bg-white p-3.5 rounded-lg border border-slate-200 space-y-1">
                      <span className="text-slate-500 text-[11px] font-semibold uppercase tracking-wider">Description & Trigger Rationale</span>
                      <p className="text-slate-700 leading-relaxed text-xs">{selectedCase.description}</p>
                    </div>
                  )}

                  {/* Summary of AI findings if present */}
                  {activeFindings && (
                    <div className="bg-blue-50/60 p-3.5 rounded-lg border border-blue-200/80 space-y-1.5">
                      <div className="flex items-center justify-between text-blue-900 font-semibold">
                        <span>AI Executive Summary (LangGraph Grounded Run)</span>
                        <span className="text-[10px] font-mono text-blue-700">Model: {activeFindings.model_metadata.provider}</span>
                      </div>
                      <p className="text-blue-950 text-xs leading-relaxed">{activeFindings.summary}</p>
                    </div>
                  )}
                </div>
              )}

              {/* Sub-Tab 2: Transaction Relationships (Integrated Graph Canvas) */}
              {activeSection === 'graph' && (
                <div className="p-5 space-y-4">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-slate-100">
                    <div>
                      <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-1.5">
                        <Network className="w-4 h-4 text-rose-600" />
                        <span>Tokenized Relationship Graph (Apache AGE / In-Memory Adapter)</span>
                      </h3>
                      <p className="text-[11px] text-slate-500">
                        HMAC-tokenized graph topology around subject entity. Click any node to inspect attributes.
                      </p>
                    </div>

                    <div className="text-[11px] font-mono text-slate-500">
                      Nodes: <strong>{nodes.length}</strong> | Edges: <strong>{edges.length}</strong>
                    </div>
                  </div>

                  {/* Deterministic Fraud Policy Indicator (if alert) */}
                  {fraudEval?.is_alert && (
                    <div className="bg-rose-50 border border-rose-200 rounded-lg p-3 text-xs text-rose-900 space-y-1">
                      <div className="flex items-center space-x-1.5 font-bold text-rose-700">
                        <AlertTriangle className="w-4 h-4" />
                        <span>Deterministic Fraud Policy Alert Fired ({fraudEval.severity})</span>
                      </div>
                      <p className="text-[11px] text-rose-800">{fraudEval.summary}</p>
                      <div className="flex items-center gap-1 pt-1">
                        <span className="text-[10px] text-slate-500 font-semibold">Reason Codes:</span>
                        {fraudEval.reason_codes.map((code) => (
                          <span key={code} className="px-1.5 py-0.2 rounded bg-rose-100 text-rose-800 font-mono text-[10px] font-bold">
                            {code}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* SVG Graph Viewport */}
                  <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 flex flex-col items-center justify-center min-h-[380px] relative overflow-hidden">
                    <div className="absolute top-3 left-3 text-[11px] text-slate-500 flex items-center space-x-3 bg-white/90 px-2 py-1 rounded border border-slate-200/80 shadow-2xs">
                      <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-blue-600" /> Customer</span>
                      <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-rose-600" /> Device</span>
                      <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-600" /> Instrument</span>
                      <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-600" /> Payment</span>
                    </div>

                    {nodes.length === 0 ? (
                      <div className="text-center py-12 text-slate-400 text-xs">
                        No relationship graph records found for this case entity.
                      </div>
                    ) : (
                      <svg width={width} height={height} className="max-w-full">
                        {/* Edges */}
                        {edges.map((e) => {
                          const src = nodePositions[e.source_id];
                          const tgt = nodePositions[e.target_id];
                          if (!src || !tgt) return null;
                          return (
                            <line
                              key={e.id}
                              x1={src.x}
                              y1={src.y}
                              x2={tgt.x}
                              y2={tgt.y}
                              stroke="#cbd5e1"
                              strokeWidth={1.5}
                              strokeDasharray={e.inferred ? '4 2' : undefined}
                            />
                          );
                        })}

                        {/* Nodes */}
                        {nodes.map((n) => {
                          const pos = nodePositions[n.id];
                          if (!pos) return null;
                          const isSelected = selectedGraphNode?.id === n.id;
                          const color = getNodeColor(n.label);

                          return (
                            <g
                              key={n.id}
                              transform={`translate(${pos.x}, ${pos.y})`}
                              onClick={() => setSelectedGraphNode(n)}
                              className="cursor-pointer transition-transform hover:scale-110"
                            >
                              <circle
                                r={isSelected ? 16 : 12}
                                fill={color}
                                stroke="#ffffff"
                                strokeWidth={2}
                                className="shadow-xs"
                              />
                              <text
                                y={24}
                                textAnchor="middle"
                                className="text-[10px] fill-slate-700 font-mono font-medium pointer-events-none"
                              >
                                {n.id.length > 14 ? `${n.id.slice(0, 12)}...` : n.id}
                              </text>
                            </g>
                          );
                        })}
                      </svg>
                    )}
                  </div>

                  {/* Entity Inspector (when a node is clicked) */}
                  {selectedGraphNode && (
                    <div className="bg-white border border-slate-200 rounded-lg p-3 text-xs space-y-1.5 animate-in fade-in">
                      <div className="flex items-center justify-between border-b border-slate-100 pb-1.5">
                        <span className="font-bold text-slate-900">Entity Details: <span className="font-mono text-blue-600">{selectedGraphNode.id}</span></span>
                        <span className="text-[10px] font-semibold bg-slate-100 text-slate-700 px-1.5 py-0.2 rounded">
                          {selectedGraphNode.label}
                        </span>
                      </div>
                      <div className="text-slate-600 space-y-0.5 text-[11px]">
                        <div>HMAC Token: <span className="font-mono text-slate-800">{selectedGraphNode.id}</span></div>
                        <div>Properties: <span className="font-mono text-slate-800">{JSON.stringify(selectedGraphNode.properties)}</span></div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Sub-Tab 3: AI Findings (PRD §9.5 Canonical Result) */}
              {activeSection === 'findings' && (
                <div className="p-5 space-y-4 text-xs">
                  {activeFindings ? (
                    <div className="space-y-4">
                      {/* Summary Banner */}
                      <div className="bg-slate-50 p-3.5 rounded-lg border border-slate-200 space-y-1">
                        <div className="flex items-center justify-between text-slate-900 font-semibold">
                          <span className="flex items-center gap-1.5">
                            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                            <span>Executive Investigation Findings</span>
                          </span>
                          <span className="font-mono text-[10px] text-slate-400">
                            Execution: {activeFindings.model_metadata.execution_time_ms}ms
                          </span>
                        </div>
                        <p className="text-slate-700 text-xs leading-relaxed">{activeFindings.summary}</p>
                      </div>

                      {/* Evidence-Grounded Findings List */}
                      <div>
                        <h4 className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-2">
                          Grounded Findings ({activeFindings.findings.length})
                        </h4>
                        <div className="space-y-2">
                          {activeFindings.findings.map((f, i) => (
                            <div key={i} className="bg-white border border-slate-200 rounded-lg p-3 text-xs space-y-1">
                              <div className="flex items-center justify-between">
                                <span className="font-mono text-xs font-semibold text-slate-900">{f.code}</span>
                                <span className="text-[11px] text-emerald-700 font-semibold">
                                  {(f.confidence * 100).toFixed(0)}% confidence
                                </span>
                              </div>
                              <p className="text-slate-700">{f.statement}</p>
                              <div className="flex items-center gap-1 pt-1 text-[11px] text-slate-400">
                                <span>Evidence Citations:</span>
                                {f.evidence_ids.map((eid) => (
                                  <span key={eid} className="font-mono text-[10px] bg-slate-100 text-slate-700 px-1 rounded border border-slate-200">
                                    {eid}
                                  </span>
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Explicit Unknowns */}
                      {activeFindings.unknowns.length > 0 && (
                        <div className="bg-amber-50/70 border border-amber-200 rounded-lg p-3 text-xs text-amber-900 space-y-1">
                          <div className="flex items-center space-x-1.5 font-semibold text-amber-800">
                            <HelpCircle className="w-3.5 h-3.5 text-amber-600" />
                            <span>Explicit Unknowns / Missing Records</span>
                          </div>
                          <ul className="list-disc list-inside space-y-0.5 text-[11px] text-amber-800">
                            {activeFindings.unknowns.map((u, i) => (
                              <li key={i}>{u}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Recommended Operational Next Step */}
                      <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 text-xs flex items-center justify-between">
                        <div>
                          <span className="text-[10px] text-slate-500 uppercase font-semibold block">Recommended Next Step</span>
                          <span className="font-mono font-bold text-slate-900 text-xs">
                            {activeFindings.recommended_next_step.action}
                          </span>
                        </div>
                        {activeFindings.recommended_next_step.requires_human_approval && (
                          <span className="px-2 py-0.5 bg-purple-50 text-purple-700 border border-purple-200 rounded-xs text-[10px] font-semibold">
                            Human Approval Required
                          </span>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="py-12 text-center text-slate-500">
                      <Clock className="w-8 h-8 text-slate-400 mx-auto mb-2 opacity-80" />
                      <p className="font-semibold text-slate-800">No AI investigation findings generated yet.</p>
                      <p className="text-[11px] text-slate-400 mt-0.5">Click "Run LangGraph Agent" above to synthesize evidence and policy checks.</p>
                    </div>
                  )}
                </div>
              )}

              {/* Sub-Tab 4: Review & Approvals */}
              {activeSection === 'approvals' && (
                <div className="p-5 space-y-4 text-xs">
                  {selectedCase.case_status === 'REVIEW_REQUIRED' || approvals.length > 0 ? (
                    <div className="bg-white border border-purple-200 rounded-lg p-4 space-y-3 shadow-2xs">
                      <div className="flex items-center space-x-2 text-purple-900 font-bold text-sm">
                        <ShieldAlert className="w-4 h-4 text-purple-700" />
                        <span>Human Approval Gate (Operations Supervisor Sign-off Required)</span>
                      </div>
                      <p className="text-slate-600 leading-relaxed text-xs">
                        The LangGraph workflow has paused because the proposed operational action has external financial implications or represents a high-risk fraud finding.
                      </p>

                      {/* Action Details */}
                      {(() => {
                        const pendingApproval = approvals.find((a) => a.decision === 'PENDING') || approvals[0];
                        const canApprove = currentRole === 'SUPERVISOR' || currentRole === 'PLATFORM_ADMIN';

                        return (
                          <>
                            {pendingApproval && (
                              <div className="bg-slate-50 rounded-lg p-3 border border-slate-200 text-xs space-y-1.5">
                                <div className="flex items-center justify-between">
                                  <span className="font-mono text-purple-700 font-bold">{pendingApproval.id}</span>
                                  <span className="text-[10px] px-1.5 py-0.2 rounded bg-amber-100 text-amber-800 font-semibold">
                                    {pendingApproval.decision}
                                  </span>
                                </div>
                                <div className="text-slate-800 font-medium">
                                  Action: <strong className="text-slate-900">{String(pendingApproval.action_draft.action_type || 'ESCALATION')}</strong>
                                  {pendingApproval.action_draft.amount_minor !== undefined && (
                                    <span className="ml-2 font-mono text-emerald-700 font-semibold">
                                      ₹{(Number(pendingApproval.action_draft.amount_minor) / 100).toFixed(2)}
                                    </span>
                                  )}
                                </div>
                                {Boolean(pendingApproval.action_draft.reason) && (
                                  <div className="text-[11px] text-slate-500">
                                    Reason: {String(pendingApproval.action_draft.reason)}
                                  </div>
                                )}
                              </div>
                            )}

                            {!canApprove && (
                              <div className="bg-amber-50 border border-amber-200 rounded-md p-2.5 text-xs text-amber-900 flex items-center justify-between">
                                <span>
                                  Active Persona: <strong>{currentRole}</strong> (Read-Only). Switch to <strong>Supervisor</strong> to sign off.
                                </span>
                                <button
                                  type="button"
                                  onClick={() => onSwitchRole('SUPERVISOR')}
                                  className="px-2.5 py-1 bg-amber-600 hover:bg-amber-700 text-white font-semibold rounded text-[11px] transition-colors shrink-0 ml-2"
                                >
                                  Switch to Supervisor
                                </button>
                              </div>
                            )}

                            <div>
                              <label className="block text-xs font-semibold text-slate-700 mb-1">
                                Supervisor Review Rationale & Justification
                              </label>
                              <input
                                type="text"
                                placeholder="e.g. Verified customer statement and approved refund escalation"
                                value={approvalReason}
                                onChange={(e) => setApprovalReason(e.target.value)}
                                disabled={!canApprove}
                                className="w-full bg-slate-50 border border-slate-200 rounded-md px-3 py-2 text-xs text-slate-900 focus:outline-none focus:border-blue-500 disabled:opacity-50"
                              />
                            </div>

                            <div className="flex justify-end space-x-2 pt-2 border-t border-slate-100">
                              <button
                                onClick={() => pendingApproval && handleDecision(pendingApproval.id, 'REJECTED')}
                                disabled={approving || !pendingApproval || !canApprove}
                                className="px-3.5 py-1.5 rounded-md border border-slate-200 text-slate-700 text-xs font-semibold hover:bg-slate-50 disabled:opacity-50"
                              >
                                Reject Action
                              </button>
                              <button
                                onClick={() => pendingApproval && handleDecision(pendingApproval.id, 'APPROVED')}
                                disabled={approving || !pendingApproval || !canApprove}
                                className="px-3.5 py-1.5 rounded-md bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow-xs disabled:opacity-50 flex items-center space-x-1"
                              >
                                <CheckCircle2 className="w-3.5 h-3.5" />
                                <span>Approve & Finalize Action</span>
                              </button>
                            </div>
                          </>
                        );
                      })()}
                    </div>
                  ) : (
                    <div className="py-12 text-center text-slate-500">
                      <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2 opacity-80" />
                      <p className="font-semibold text-slate-800">No pending operational approvals required for this case.</p>
                      <p className="text-[11px] text-slate-400 mt-0.5">Status is currently {selectedCase.case_status}.</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="py-24 text-center text-slate-400 text-xs">
              Select a case from the queue on the left to inspect and investigate.
            </div>
          )}
        </div>
      </div>

      {/* New Case Creation Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 rounded-lg max-w-md w-full p-5 shadow-xl space-y-4 animate-in fade-in">
            <div className="flex items-center justify-between border-b border-slate-200 pb-3">
              <h3 className="font-bold text-slate-900 text-sm">Create Operational Investigation Case</h3>
              <button onClick={() => setShowCreateModal(false)} className="text-slate-400 hover:text-slate-700">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Case Title</label>
              <input
                type="text"
                placeholder="e.g. Discrepancy: Payer debited on failed transaction ORD-104"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-md px-3 py-2 text-xs text-slate-900 focus:outline-none focus:border-blue-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Case Type</label>
                <select
                  value={newType}
                  onChange={(e) => setNewType(e.target.value as CaseType)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-md px-3 py-2 text-xs text-slate-900 focus:outline-none"
                >
                  <option value="PAYMENT_DISCREPANCY">Payment Discrepancy</option>
                  <option value="FRAUD_INVESTIGATION">Fraud Investigation</option>
                  <option value="REFUND_DELAY">Refund Delay</option>
                  <option value="UNRECOGNIZED_TRANSACTION">Unrecognized Transaction</option>
                </select>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Priority</label>
                <select
                  value={newPriority}
                  onChange={(e) => setNewPriority(e.target.value as FraudSeverity)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-md px-3 py-2 text-xs text-slate-900 focus:outline-none"
                >
                  <option value="LOW">Low</option>
                  <option value="MEDIUM">Medium</option>
                  <option value="HIGH">High</option>
                  <option value="CRITICAL">Critical</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Linked Payment / Entity ID (Optional)</label>
              <input
                type="text"
                placeholder="e.g. pay_scen_mismatch_004 or dev_imei_cluster_99"
                value={newPaymentId}
                onChange={(e) => setNewPaymentId(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-md px-3 py-2 text-xs text-slate-900 font-mono focus:outline-none focus:border-blue-500"
              />
            </div>

            <div className="flex justify-end space-x-2 pt-2 border-t border-slate-100">
              <button
                onClick={() => setShowCreateModal(false)}
                className="px-3 py-1.5 rounded-md border border-slate-200 text-slate-700 text-xs font-medium hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateSubmit}
                className="px-3.5 py-1.5 rounded-md bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow-xs"
              >
                Create Case
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
