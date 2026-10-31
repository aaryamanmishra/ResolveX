import React, { useState, useEffect } from 'react';
import { Payment, PaymentEvent } from '../types/contracts';
import {
  Search,
  RefreshCw,
  Play,
  X,
  AlertTriangle,
} from 'lucide-react';

interface PaymentsTabProps {
  payments: Payment[];
  exceptions: Array<{ payment_id: string; exception_type: string; details: Record<string, unknown> }>;
  onRefresh: () => void;
  onSimulate: (scenario: string) => Promise<void>;
  onReportDebit: (paymentId: string, utr: string) => Promise<void>;
  onFetchTimeline: (paymentId: string) => Promise<PaymentEvent[]>;
  initialSelectedPaymentId?: string | null;
}

export const PaymentsTab: React.FC<PaymentsTabProps> = ({
  payments,
  exceptions,
  onRefresh,
  onSimulate,
  onReportDebit,
  onFetchTimeline,
  initialSelectedPaymentId,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [selectedPayment, setSelectedPayment] = useState<Payment | null>(null);
  const [timeline, setTimeline] = useState<PaymentEvent[]>([]);
  const [isLoadingTimeline, setIsLoadingTimeline] = useState(false);
  const [simulating, setSimulating] = useState(false);
  const [showSimModal, setShowSimModal] = useState(false);

  // Customer debit claim modal
  const [showDebitModal, setShowDebitModal] = useState(false);
  const [claimedUtr, setClaimedUtr] = useState('');
  const [submittingDebit, setSubmittingDebit] = useState(false);

  // Auto-select payment if requested from Overview
  useEffect(() => {
    if (initialSelectedPaymentId) {
      const match = payments.find((p) => p.id === initialSelectedPaymentId);
      if (match) {
        handleSelectPayment(match);
      }
    }
  }, [initialSelectedPaymentId, payments]);

  const exceptionPaymentIds = new Set(exceptions.map((e) => e.payment_id));

  const filteredPayments = payments.filter((p) => {
    const matchesSearch =
      p.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.order_ref.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.provider_payment_id.toLowerCase().includes(searchTerm.toLowerCase());

    if (!matchesSearch) return false;

    if (statusFilter === 'ALL') return true;
    if (statusFilter === 'EXCEPTIONS') return exceptionPaymentIds.has(p.id);
    if (statusFilter === 'SUCCEEDED') return p.payment_status === 'SUCCEEDED';
    if (statusFilter === 'PENDING') return p.payment_status === 'PENDING' || p.payment_status === 'INITIATED';
    if (statusFilter === 'FAILED') return p.payment_status === 'FAILED';
    if (statusFilter === 'REVERSED') return p.payment_status === 'REVERSED';
    return true;
  });

  const handleSelectPayment = async (payment: Payment) => {
    setSelectedPayment(payment);
    setIsLoadingTimeline(true);
    try {
      const events = await onFetchTimeline(payment.id);
      setTimeline(events);
    } catch {
      setTimeline([]);
    } finally {
      setIsLoadingTimeline(false);
    }
  };

  const handleRunSimulation = async (scenario: string) => {
    setSimulating(true);
    setShowSimModal(false);
    try {
      await onSimulate(scenario);
    } finally {
      setSimulating(false);
    }
  };

  const handleSubmitDebit = async () => {
    if (!selectedPayment) return;
    setSubmittingDebit(true);
    try {
      const utr = claimedUtr.trim() || `UPI${Date.now()}`;
      await onReportDebit(selectedPayment.id, utr);
      setShowDebitModal(false);
      setClaimedUtr('');
      await handleSelectPayment(selectedPayment);
    } finally {
      setSubmittingDebit(false);
    }
  };

  const formatCurrency = (amountMinor: number, currency = 'INR') => {
    const major = (amountMinor / 100).toFixed(2);
    return `${currency === 'INR' ? '₹' : currency} ${major}`;
  };

  const getPaymentStatusBadge = (status: string) => {
    switch (status) {
      case 'SUCCEEDED':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200';
      case 'PENDING':
      case 'INITIATED':
        return 'bg-amber-50 text-amber-700 border-amber-200';
      case 'FAILED':
      case 'EXPIRED':
        return 'bg-rose-50 text-rose-700 border-rose-200';
      case 'REVERSED':
        return 'bg-purple-50 text-purple-700 border-purple-200';
      default:
        return 'bg-slate-50 text-slate-700 border-slate-200';
    }
  };

  const getFundsStatusBadge = (status: string) => {
    switch (status) {
      case 'PROVIDER_CONFIRMED_CREDIT':
        return 'text-emerald-700 font-medium';
      case 'CUSTOMER_REPORTED_DEBIT':
        return 'text-rose-700 font-semibold bg-rose-50 px-1.5 py-0.5 rounded border border-rose-200 inline-block';
      case 'REFUND_IN_TRANSIT':
      case 'PROVIDER_INITIATED_REFUND':
        return 'text-purple-700 font-medium';
      default:
        return 'text-slate-500';
    }
  };

  return (
    <div className="space-y-5 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-2 border-b border-slate-200/80">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Payments & Reconciliation</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Authoritative gateway transactions, status lifecycle dimensions, and ledger reconciliation exceptions.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => setShowSimModal(true)}
            disabled={simulating}
            className="px-3 py-1.5 rounded-md bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-medium shadow-2xs transition-colors flex items-center space-x-1.5"
          >
            <Play className="w-3 h-3 text-blue-600" />
            <span>Simulate Scenario</span>
          </button>
          <button
            onClick={onRefresh}
            className="p-1.5 rounded-md bg-white border border-slate-200 hover:bg-slate-50 text-slate-500 hover:text-slate-900 shadow-2xs"
            title="Refresh payments"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Filter Bar & Quick Tabs */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-2.5 rounded-lg border border-slate-200 shadow-2xs">
        <div className="flex items-center space-x-1 overflow-x-auto pb-1 sm:pb-0">
          {[
            { id: 'ALL', label: 'All Transactions', count: payments.length },
            { id: 'EXCEPTIONS', label: 'Exceptions', count: exceptions.length, alert: exceptions.length > 0 },
            { id: 'SUCCEEDED', label: 'Succeeded', count: payments.filter((p) => p.payment_status === 'SUCCEEDED').length },
            { id: 'PENDING', label: 'Pending', count: payments.filter((p) => p.payment_status === 'PENDING' || p.payment_status === 'INITIATED').length },
            { id: 'FAILED', label: 'Failed', count: payments.filter((p) => p.payment_status === 'FAILED').length },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setStatusFilter(tab.id)}
              className={`px-2.5 py-1.5 rounded-md text-xs font-medium whitespace-nowrap transition-colors flex items-center space-x-1.5 ${
                statusFilter === tab.id
                  ? 'bg-slate-100 text-slate-900 font-semibold'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
              }`}
            >
              <span>{tab.label}</span>
              <span
                className={`text-[10px] px-1.5 py-0.2 rounded-full font-semibold ${
                  tab.alert
                    ? 'bg-amber-100 text-amber-800'
                    : statusFilter === tab.id
                    ? 'bg-white text-slate-700 shadow-2xs'
                    : 'bg-slate-200/60 text-slate-500'
                }`}
              >
                {tab.count}
              </span>
            </button>
          ))}
        </div>

        <div className="relative w-full sm:w-64">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
          <input
            type="text"
            placeholder="Search order, payment or UTR..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-slate-50 border border-slate-200 rounded-md pl-8 pr-3 py-1.5 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:bg-white transition-colors"
          />
        </div>
      </div>

      {/* Main Content: Table + Side Drawer (if selected) */}
      <div className="flex gap-5 items-start">
        {/* Payments Table */}
        <div className={`bg-white border border-slate-200 rounded-lg shadow-2xs overflow-hidden flex-1 ${selectedPayment ? 'hidden lg:block' : 'w-full'}`}>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/70 text-slate-500 text-[11px] font-semibold uppercase tracking-wider">
                  <th className="py-2.5 px-4">Order / Payment ID</th>
                  <th className="py-2.5 px-4 text-right">Amount</th>
                  <th className="py-2.5 px-4">Gateway Status</th>
                  <th className="py-2.5 px-4">Funds Status (Truth vs Claim)</th>
                  <th className="py-2.5 px-4">Settlement / Refund</th>
                  <th className="py-2.5 px-4">Created</th>
                  <th className="py-2.5 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {filteredPayments.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="text-center py-12 text-slate-500 text-xs">
                      No transaction records matched the current filter.
                    </td>
                  </tr>
                ) : (
                  filteredPayments.map((p) => {
                    const isSelected = selectedPayment?.id === p.id;
                    const hasException = exceptionPaymentIds.has(p.id);

                    return (
                      <tr
                        key={p.id}
                        onClick={() => handleSelectPayment(p)}
                        className={`hover:bg-slate-50/80 transition-colors cursor-pointer ${
                          isSelected ? 'bg-blue-50/40' : ''
                        }`}
                      >
                        <td className="py-3 px-4">
                          <div className="font-semibold text-slate-900 flex items-center space-x-1.5">
                            <span>{p.order_ref}</span>
                            {hasException && (
                              <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" title="Reconciliation exception detected" />
                            )}
                          </div>
                          <div className="font-mono text-[11px] text-slate-400 mt-0.5">
                            {p.id}
                          </div>
                        </td>

                        <td className="py-3 px-4 text-right font-mono font-semibold text-slate-900">
                          {formatCurrency(p.amount_minor, p.currency)}
                        </td>

                        <td className="py-3 px-4">
                          <span className={`inline-block px-2 py-0.5 rounded-xs text-[10px] font-semibold border ${getPaymentStatusBadge(p.payment_status)}`}>
                            {p.payment_status}
                          </span>
                        </td>

                        <td className="py-3 px-4 text-xs">
                          <span className={getFundsStatusBadge(p.funds_status)}>
                            {p.funds_status.replace(/_/g, ' ')}
                          </span>
                        </td>

                        <td className="py-3 px-4 text-xs text-slate-500">
                          {p.payment_status === 'REVERSED' ? (
                            <span className="inline-block px-1.5 py-0.5 bg-purple-50 text-purple-700 border border-purple-200 rounded-xs text-[10px] font-semibold">
                              REVERSED
                            </span>
                          ) : (
                            <span className="text-slate-400 font-mono text-[11px]">—</span>
                          )}
                        </td>

                        <td className="py-3 px-4 text-slate-500 text-[11px]">
                          {new Date(p.created_at).toLocaleDateString([], {
                            month: 'short',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </td>

                        <td className="py-3 px-4 text-right">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleSelectPayment(p);
                            }}
                            className="text-xs text-blue-600 hover:text-blue-700 font-semibold"
                          >
                            Details →
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Payment Detail Side Drawer (When a payment is selected) */}
        {selectedPayment && (
          <div className="w-full lg:w-96 bg-white border border-slate-200 rounded-lg shadow-sm p-4 space-y-4 shrink-0 animate-in fade-in">
            {/* Drawer Header */}
            <div className="flex items-start justify-between pb-3 border-b border-slate-200">
              <div>
                <div className="flex items-center space-x-2">
                  <span className="text-xs font-mono font-semibold text-slate-900">{selectedPayment.order_ref}</span>
                  <span className={`px-2 py-0.5 rounded-xs text-[10px] font-semibold border ${getPaymentStatusBadge(selectedPayment.payment_status)}`}>
                    {selectedPayment.payment_status}
                  </span>
                </div>
                <div className="font-mono text-[11px] text-slate-400 mt-0.5">
                  {selectedPayment.id}
                </div>
              </div>

              <button
                onClick={() => setSelectedPayment(null)}
                className="text-slate-400 hover:text-slate-700 p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Financial Overview Card */}
            <div className="bg-slate-50 p-3 rounded-md border border-slate-200/80 space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Transaction Amount</span>
                <span className="font-mono font-bold text-slate-900 text-sm">
                  {formatCurrency(selectedPayment.amount_minor, selectedPayment.currency)}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Provider Ref</span>
                <span className="font-mono text-[11px] text-slate-700">
                  {selectedPayment.provider_payment_id || '—'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Funds Settlement</span>
                <span className={getFundsStatusBadge(selectedPayment.funds_status)}>
                  {selectedPayment.funds_status.replace(/_/g, ' ')}
                </span>
              </div>
            </div>

            {/* Reconciliation Discrepancy Alert (if any) */}
            {exceptionPaymentIds.has(selectedPayment.id) && (
              <div className="bg-amber-50 border border-amber-200 rounded-md p-3 text-xs text-amber-900 space-y-1">
                <div className="flex items-center space-x-1.5 font-semibold text-amber-800">
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                  <span>Reconciliation Discrepancy</span>
                </div>
                <p className="text-[11px] text-amber-800 leading-relaxed">
                  Customer reported debit or out-of-order event differs from provider settlement records.
                </p>
              </div>
            )}

            {/* Actions Bar */}
            <div className="flex items-center gap-2 pt-1">
              <button
                onClick={() => setShowDebitModal(true)}
                className="flex-1 py-1.5 px-3 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-semibold rounded-md shadow-2xs transition-colors flex items-center justify-center space-x-1.5"
              >
                <span>Report Customer Debit</span>
              </button>
            </div>

            {/* Chronological Event Timeline */}
            <div className="space-y-2 pt-2 border-t border-slate-200">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-900">Event Timeline</span>
                <span className="text-[10px] text-slate-400">
                  {isLoadingTimeline ? 'Loading...' : `${timeline.length} events recorded`}
                </span>
              </div>

              {isLoadingTimeline ? (
                <div className="p-4 text-center text-xs text-slate-400">
                  Loading timeline events...
                </div>
              ) : timeline.length === 0 ? (
                <div className="p-4 text-center text-xs text-slate-500 bg-slate-50 rounded border border-slate-200/60">
                  No webhook events received yet for this payment.
                </div>
              ) : (
                <div className="relative pl-4 space-y-3 before:absolute before:left-1.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
                  {timeline.map((evt) => (
                    <div key={evt.id} className="relative text-xs space-y-0.5">
                      <div className="w-2 h-2 rounded-full bg-blue-600 absolute -left-[14px] top-1" />
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-slate-800 font-mono text-[11px]">{evt.event_type}</span>
                        <span className="text-[10px] text-slate-400 font-mono">
                          {new Date(evt.event_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                        </span>
                      </div>
                      <div className="text-[11px] text-slate-500">
                        Status: <strong className="text-slate-700">{evt.normalized_status}</strong> (Source: {evt.source})
                      </div>
                      {evt.payload_hash && (
                        <div className="text-[10px] font-mono text-slate-400">
                          hash: {evt.payload_hash.slice(0, 10)}...
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Customer Debit Claim Modal */}
      {showDebitModal && selectedPayment && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 rounded-lg max-w-md w-full p-5 shadow-xl space-y-4 animate-in fade-in">
            <div className="flex items-center justify-between border-b border-slate-200 pb-3">
              <h3 className="font-bold text-slate-900 text-sm">
                Report Customer Account Debit
              </h3>
              <button onClick={() => setShowDebitModal(false)} className="text-slate-400 hover:text-slate-700">
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed">
              Record a payer claim stating funds were debited from their bank/UPI account for order{' '}
              <strong className="text-slate-900">{selectedPayment.order_ref}</strong>.
              This updates <span className="font-mono text-slate-800">funds_status</span> to{' '}
              <span className="font-semibold text-rose-600">CUSTOMER_REPORTED_DEBIT</span> without altering provider truth.
            </p>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Claimed Bank Reference Number (UTR / RRN)
              </label>
              <input
                type="text"
                placeholder="e.g. UPI429810928301"
                value={claimedUtr}
                onChange={(e) => setClaimedUtr(e.target.value)}
                className="w-full bg-slate-50 border border-slate-200 rounded-md px-3 py-2 text-xs text-slate-900 font-mono focus:outline-none focus:border-blue-500 focus:bg-white"
              />
              <span className="text-[11px] text-slate-400 mt-1 block">
                Leave empty to auto-generate synthetic test reference.
              </span>
            </div>

            <div className="flex justify-end space-x-2 pt-2 border-t border-slate-100">
              <button
                onClick={() => setShowDebitModal(false)}
                className="px-3 py-1.5 rounded-md border border-slate-200 text-slate-700 text-xs font-medium hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmitDebit}
                disabled={submittingDebit}
                className="px-3.5 py-1.5 rounded-md bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold transition-colors"
              >
                {submittingDebit ? 'Recording Claim...' : 'Record Debit Claim'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Payment Scenario Simulator Modal */}
      {showSimModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 rounded-lg max-w-lg w-full p-5 shadow-xl space-y-4 animate-in fade-in">
            <div className="flex items-center justify-between border-b border-slate-200 pb-3">
              <div>
                <h3 className="font-bold text-slate-900 text-sm">Simulate Payment Lifecycle Scenario</h3>
                <p className="text-[11px] text-slate-500">Inject deterministic PRD §15.1 test scenarios</p>
              </div>
              <button onClick={() => setShowSimModal(false)} className="text-slate-400 hover:text-slate-700">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="grid grid-cols-1 gap-2 text-xs">
              {[
                { id: 'scenario_1_success', title: 'Scenario 1: Clean Successful Payment', desc: 'Authorized and captured via provider webhook (₹500.00)' },
                { id: 'scenario_2_pending', title: 'Scenario 2: Pending Transaction', desc: 'Order created, awaiting bank confirmation' },
                { id: 'scenario_3_failed', title: 'Scenario 3: Gateway Failed Payment', desc: 'Card declined or timeout at banking partner' },
                { id: 'scenario_4_debit_mismatch', title: 'Scenario 4: Customer Debit Discrepancy', desc: 'Gateway marks failed, but customer statement shows debited funds' },
                { id: 'scenario_6_out_of_order', title: 'Scenario 6: Out-of-Order Webhooks', desc: 'Captured event arrives before authorized event' },
                { id: 'scenario_8_amount_mismatch', title: 'Scenario 8: Amount Mismatch', desc: 'Cart total does not match gateway capture amount' },
              ].map((scen) => (
                <button
                  key={scen.id}
                  onClick={() => handleRunSimulation(scen.id)}
                  className="w-full text-left p-3 rounded-md border border-slate-200 hover:bg-slate-50 hover:border-blue-300 transition-colors flex items-start space-x-3 group"
                >
                  <Play className="w-4 h-4 text-blue-600 mt-0.5 shrink-0 group-hover:scale-110 transition-transform" />
                  <div>
                    <div className="font-semibold text-slate-900 group-hover:text-blue-600">{scen.title}</div>
                    <div className="text-[11px] text-slate-500 mt-0.5">{scen.desc}</div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
