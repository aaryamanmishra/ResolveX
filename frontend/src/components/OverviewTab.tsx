import React from 'react';
import { Case, Payment } from '../types/contracts';
import { AuditRecord } from '../api';
import {
  ArrowRight,
  AlertCircle,
  ShieldAlert,
  CreditCard,
  FolderOpen,
  CheckCircle2,
  History,
} from 'lucide-react';

interface OverviewTabProps {
  paymentCount: number;
  caseCount: number;
  exceptionCount: number;
  approvalCount: number;
  cases: Case[];
  payments: Payment[];
  exceptions: Array<{ payment_id: string; exception_type: string; details: Record<string, unknown> }>;
  auditLogs: AuditRecord[];
  onNavigate: (tab: string) => void;
  onSelectCase: (caseId: string) => void;
  onSelectPayment: (paymentId: string) => void;
}

export const OverviewTab: React.FC<OverviewTabProps> = ({
  paymentCount,
  caseCount,
  exceptionCount,
  approvalCount,
  cases,
  payments,
  exceptions,
  auditLogs,
  onNavigate,
  onSelectCase,
  onSelectPayment,
}) => {
  const pendingCases = cases.filter(
    (c) => c.case_status === 'REVIEW_REQUIRED' || c.priority === 'HIGH' || c.priority === 'CRITICAL'
  );

  const formatCurrency = (amountMinor?: number, currency = 'INR') => {
    if (amountMinor === undefined) return '—';
    const major = (amountMinor / 100).toFixed(2);
    return `${currency === 'INR' ? '₹' : currency} ${major}`;
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

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2 border-b border-slate-200/80">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Overview</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            A quick look at payment operations and investigations requiring attention.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => onNavigate('payments')}
            className="px-3 py-1.5 rounded-md border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-xs font-medium shadow-2xs transition-colors flex items-center space-x-1.5"
          >
            <span>Review payments</span>
            <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
          </button>
          <button
            onClick={() => onNavigate('investigations')}
            className="px-3 py-1.5 rounded-md bg-slate-900 hover:bg-slate-800 text-white text-xs font-medium shadow-xs transition-colors flex items-center space-x-1.5"
          >
            <span>Open investigations</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* First Section: Needs Attention (Key Operational Metrics) */}
      <section>
        <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
          Needs Attention
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
          {/* Card 1: Open Investigations */}
          <div
            onClick={() => onNavigate('investigations')}
            className="bg-white border border-slate-200 rounded-lg p-4 shadow-2xs hover:border-slate-300 transition-colors cursor-pointer group"
          >
            <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
              <span>Open investigations</span>
              <FolderOpen className="w-4 h-4 text-blue-600 group-hover:scale-105 transition-transform" />
            </div>
            <div className="mt-2 text-2xl font-bold text-slate-900 tracking-tight">
              {caseCount}
            </div>
            <div className="text-[11px] text-slate-500 mt-1 flex items-center space-x-1">
              <span>{cases.filter((c) => c.priority === 'HIGH' || c.priority === 'CRITICAL').length} high/critical priority</span>
            </div>
          </div>

          {/* Card 2: Reconciliation Exceptions */}
          <div
            onClick={() => onNavigate('payments')}
            className="bg-white border border-slate-200 rounded-lg p-4 shadow-2xs hover:border-slate-300 transition-colors cursor-pointer group"
          >
            <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
              <span>Reconciliation exceptions</span>
              <AlertCircle className="w-4 h-4 text-amber-600 group-hover:scale-105 transition-transform" />
            </div>
            <div className="mt-2 text-2xl font-bold text-slate-900 tracking-tight">
              {exceptionCount}
            </div>
            <div className="text-[11px] text-slate-500 mt-1">
              Customer debit claims & SLA breaches
            </div>
          </div>

          {/* Card 3: Pending Approvals */}
          <div
            onClick={() => onNavigate('investigations')}
            className="bg-white border border-slate-200 rounded-lg p-4 shadow-2xs hover:border-slate-300 transition-colors cursor-pointer group"
          >
            <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
              <span>Pending approvals</span>
              <ShieldAlert className="w-4 h-4 text-purple-600 group-hover:scale-105 transition-transform" />
            </div>
            <div className="mt-2 text-2xl font-bold text-slate-900 tracking-tight">
              {approvalCount}
            </div>
            <div className="text-[11px] text-slate-500 mt-1">
              Requires supervisor sign-off
            </div>
          </div>

          {/* Card 4: Ingested Transactions */}
          <div
            onClick={() => onNavigate('payments')}
            className="bg-white border border-slate-200 rounded-lg p-4 shadow-2xs hover:border-slate-300 transition-colors cursor-pointer group"
          >
            <div className="flex items-center justify-between text-slate-500 text-xs font-medium">
              <span>Payments ingested</span>
              <CreditCard className="w-4 h-4 text-emerald-600 group-hover:scale-105 transition-transform" />
            </div>
            <div className="mt-2 text-2xl font-bold text-slate-900 tracking-tight">
              {payments.length > 0 ? payments.length : paymentCount}
            </div>
            <div className="text-[11px] text-slate-500 mt-1">
              Gateway authenticated timeline
            </div>
          </div>
        </div>
      </section>

      {/* Next Section: Actionable Queues (Two Columns) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column: Recent Payment Exceptions */}
        <div className="bg-white border border-slate-200 rounded-lg shadow-2xs overflow-hidden flex flex-col">
          <div className="px-4 py-3 border-b border-slate-200 bg-slate-50/50 flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <span className="w-2 h-2 rounded-full bg-amber-500" />
              <h2 className="text-xs font-semibold text-slate-900 uppercase tracking-wider">
                Recent Payment Exceptions
              </h2>
            </div>
            <span className="text-[11px] text-slate-500 font-medium">
              {exceptions.length} detected
            </span>
          </div>

          <div className="divide-y divide-slate-100 flex-1">
            {exceptions.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500">
                <CheckCircle2 className="w-6 h-6 text-emerald-500 mx-auto mb-1.5 opacity-80" />
                No unconfirmed debit discrepancies or SLA breaches.
              </div>
            ) : (
              exceptions.slice(0, 4).map((ex, idx) => (
                <div
                  key={idx}
                  onClick={() => {
                    onSelectPayment(ex.payment_id);
                    onNavigate('payments');
                  }}
                  className="p-3.5 hover:bg-slate-50/80 transition-colors cursor-pointer flex items-start justify-between gap-3 text-xs"
                >
                  <div className="space-y-1 truncate">
                    <div className="flex items-center space-x-2">
                      <span className="font-mono text-[11px] font-semibold text-slate-900">
                        {ex.payment_id}
                      </span>
                      <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-xs border bg-amber-50 text-amber-700 border-amber-200">
                        {ex.exception_type}
                      </span>
                    </div>
                    <p className="text-slate-500 text-[11px] truncate">
                      {String(ex.details?.order_ref ? `Order ${ex.details.order_ref}` : 'Unconfirmed customer debit')}
                      {ex.details?.amount_minor ? ` • ${formatCurrency(Number(ex.details.amount_minor))}` : ''}
                    </p>
                  </div>
                  <button className="text-[11px] text-blue-600 hover:text-blue-700 font-medium shrink-0 flex items-center space-x-0.5 pt-0.5">
                    <span>Inspect</span>
                    <ArrowRight className="w-3 h-3" />
                  </button>
                </div>
              ))
            )}
          </div>

          <div className="p-2.5 bg-slate-50/50 border-t border-slate-100 text-center">
            <button
              onClick={() => onNavigate('payments')}
              className="text-xs text-slate-600 hover:text-slate-900 font-medium"
            >
              View all payment records →
            </button>
          </div>
        </div>

        {/* Right Column: Investigations Requiring Review */}
        <div className="bg-white border border-slate-200 rounded-lg shadow-2xs overflow-hidden flex flex-col">
          <div className="px-4 py-3 border-b border-slate-200 bg-slate-50/50 flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <span className="w-2 h-2 rounded-full bg-blue-500" />
              <h2 className="text-xs font-semibold text-slate-900 uppercase tracking-wider">
                Investigations Requiring Review
              </h2>
            </div>
            <span className="text-[11px] text-slate-500 font-medium">
              {pendingCases.length} prioritized
            </span>
          </div>

          <div className="divide-y divide-slate-100 flex-1">
            {pendingCases.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500">
                <CheckCircle2 className="w-6 h-6 text-emerald-500 mx-auto mb-1.5 opacity-80" />
                All operational cases reviewed and assigned.
              </div>
            ) : (
              pendingCases.slice(0, 4).map((c) => (
                <div
                  key={c.id}
                  onClick={() => {
                    onSelectCase(c.id);
                    onNavigate('investigations');
                  }}
                  className="p-3.5 hover:bg-slate-50/80 transition-colors cursor-pointer flex items-start justify-between gap-3 text-xs"
                >
                  <div className="space-y-1 truncate">
                    <div className="flex items-center space-x-2">
                      <span className="font-mono text-[11px] font-semibold text-slate-900">
                        {c.id}
                      </span>
                      <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-xs border ${getPriorityBadge(c.priority)}`}>
                        {c.priority}
                      </span>
                      <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-xs border ${getStatusBadge(c.case_status)}`}>
                        {c.case_status}
                      </span>
                    </div>
                    <div className="text-slate-700 text-xs font-medium truncate">
                      {c.title}
                    </div>
                  </div>
                  <button className="text-[11px] text-blue-600 hover:text-blue-700 font-medium shrink-0 flex items-center space-x-0.5 pt-0.5">
                    <span>Review</span>
                    <ArrowRight className="w-3 h-3" />
                  </button>
                </div>
              ))
            )}
          </div>

          <div className="p-2.5 bg-slate-50/50 border-t border-slate-100 text-center">
            <button
              onClick={() => onNavigate('investigations')}
              className="text-xs text-slate-600 hover:text-slate-900 font-medium"
            >
              Open all operational cases →
            </button>
          </div>
        </div>
      </div>

      {/* Third Section: Recent Activity (Audit Trail Snapshot) */}
      <section className="bg-white border border-slate-200 rounded-lg shadow-2xs overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-200 bg-slate-50/50 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <History className="w-4 h-4 text-slate-500" />
            <h2 className="text-xs font-semibold text-slate-900 uppercase tracking-wider">
              Recent Activity & Tamper-Evident Audit Ledger
            </h2>
          </div>
          <button
            onClick={() => onNavigate('audit')}
            className="text-[11px] text-blue-600 hover:text-blue-700 font-medium"
          >
            Full audit log →
          </button>
        </div>

        <div className="divide-y divide-slate-100">
          {auditLogs.length === 0 ? (
            <div className="p-6 text-center text-xs text-slate-500">
              No audit events logged yet.
            </div>
          ) : (
            auditLogs.slice(0, 5).map((log) => (
              <div key={log.id} className="px-4 py-3 flex items-center justify-between text-xs hover:bg-slate-50/50">
                <div className="flex items-center space-x-3 truncate">
                  <span className="font-mono text-[11px] text-slate-400 shrink-0">
                    {new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </span>
                  <div className="truncate">
                    <span className="font-semibold text-slate-800">{log.action}</span>
                    <span className="text-slate-500 ml-1.5 truncate">
                      on {log.resource_type} <span className="font-mono text-[11px] text-slate-700">{log.resource_id}</span>
                    </span>
                  </div>
                </div>
                <div className="flex items-center space-x-3 shrink-0 text-slate-400 text-[11px]">
                  <span className="font-mono">{log.actor_id}</span>
                  <span className="font-mono text-[10px] bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200 text-slate-600 hidden sm:inline">
                    sha256:{log.metadata_hash.slice(0, 8)}...
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
};
