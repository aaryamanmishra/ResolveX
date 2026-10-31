import React, { useState } from 'react';
import { Payment, PaymentEvent } from '../types/contracts';
import {
  Search,
  RefreshCw,
  Play,
  FileText,
  Clock,
  AlertCircle,
  Hash,
  X,
  CreditCard,
  Send,
} from 'lucide-react';

interface PaymentsTabProps {
  payments: Payment[];
  exceptions: Array<{ payment_id: string; exception_type: string; details: Record<string, unknown> }>;
  onRefresh: () => void;
  onSimulate: (scenario: string) => Promise<void>;
  onReportDebit: (paymentId: string, utr: string) => Promise<void>;
  onFetchTimeline: (paymentId: string) => Promise<PaymentEvent[]>;
}

export const PaymentsTab: React.FC<PaymentsTabProps> = ({
  payments,
  exceptions,
  onRefresh,
  onSimulate,
  onReportDebit,
  onFetchTimeline,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedPayment, setSelectedPayment] = useState<Payment | null>(null);
  const [timeline, setTimeline] = useState<PaymentEvent[]>([]);
  const [isLoadingTimeline, setIsLoadingTimeline] = useState(false);
  const [simulating, setSimulating] = useState(false);

  // Debit report modal
  const [debitModalPayment, setDebitModalPayment] = useState<Payment | null>(null);
  const [claimedUtr, setClaimedUtr] = useState('');

  const filteredPayments = payments.filter(
    (p) =>
      p.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.order_ref.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.provider_payment_id.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleOpenTimeline = async (payment: Payment) => {
    setSelectedPayment(payment);
    setIsLoadingTimeline(true);
    try {
      const events = await onFetchTimeline(payment.id);
      setTimeline(events);
    } finally {
      setIsLoadingTimeline(false);
    }
  };

  const handleSimulateScenario = async (scenario: string) => {
    setSimulating(true);
    try {
      await onSimulate(scenario);
    } finally {
      setSimulating(false);
    }
  };

  const handleSubmitDebit = async () => {
    if (!debitModalPayment) return;
    await onReportDebit(debitModalPayment.id, claimedUtr || `UPI${Date.now()}`);
    setDebitModalPayment(null);
    setClaimedUtr('');
  };

  const formatCurrency = (amountMinor: number, currency: string) => {
    const major = (amountMinor / 100).toFixed(2);
    return `${currency === 'INR' ? '₹' : currency} ${major}`;
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'SUCCEEDED':
        return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
      case 'PENDING':
      case 'INITIATED':
        return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
      case 'FAILED':
      case 'EXPIRED':
        return 'bg-rose-500/10 text-rose-400 border-rose-500/20';
      case 'REVERSED':
        return 'bg-purple-500/10 text-purple-400 border-purple-500/20';
      default:
        return 'bg-slate-700 text-slate-300 border-slate-600';
    }
  };

  return (
    <div className="space-y-6">
      {/* Interactive Scenario Simulator Controller */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 sm:p-5">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-3">
          <div>
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <Play className="w-4 h-4 text-sky-400" />
              <span>Interactive Payment Simulator (Zero-Key Gateway Controller)</span>
            </h2>
            <p className="text-xs text-slate-400">
              Emit signed webhook events and test terminal state invariants without third-party credentials.
            </p>
          </div>
          <button
            onClick={onRefresh}
            disabled={simulating}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-md bg-slate-800 hover:bg-slate-700 text-xs text-slate-300 border border-slate-700 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${simulating ? 'animate-spin' : ''}`} />
            <span>Refresh Ledger</span>
          </button>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => handleSimulateScenario('scenario_1_success')}
            disabled={simulating}
            className="px-2.5 py-1.5 rounded bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/20 text-xs font-medium transition"
          >
            + Success Payment
          </button>
          <button
            onClick={() => handleSimulateScenario('scenario_2_pending')}
            disabled={simulating}
            className="px-2.5 py-1.5 rounded bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/20 text-xs font-medium transition"
          >
            + Pending Payment
          </button>
          <button
            onClick={() => handleSimulateScenario('scenario_3_failed')}
            disabled={simulating}
            className="px-2.5 py-1.5 rounded bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/20 text-xs font-medium transition"
          >
            + Failed Payment
          </button>
          <button
            onClick={() => handleSimulateScenario('scenario_4_debit_mismatch')}
            disabled={simulating}
            className="px-2.5 py-1.5 rounded bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 border border-blue-500/20 text-xs font-medium transition"
          >
            + Customer Debit Mismatch
          </button>
          <button
            onClick={() => handleSimulateScenario('scenario_6_out_of_order')}
            disabled={simulating}
            className="px-2.5 py-1.5 rounded bg-purple-500/10 hover:bg-purple-500/20 text-purple-400 border border-purple-500/20 text-xs font-medium transition"
          >
            + Out of Order Webhook
          </button>
          <button
            onClick={() => handleSimulateScenario('scenario_8_amount_mismatch')}
            disabled={simulating}
            className="px-2.5 py-1.5 rounded bg-yellow-500/10 hover:bg-yellow-500/20 text-yellow-400 border border-yellow-500/20 text-xs font-medium transition"
          >
            + Amount Mismatch Exception
          </button>
        </div>
      </div>

      {/* Reconciliation Exceptions Queue */}
      {exceptions.length > 0 && (
        <div className="bg-amber-950/20 border border-amber-500/30 rounded-xl p-4">
          <div className="flex items-center space-x-2 text-amber-400 font-semibold text-sm mb-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>Reconciliation Exceptions Queue ({exceptions.length} Active Discrepancies)</span>
          </div>
          <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-3">
            {exceptions.map((exc, idx) => (
              <div key={idx} className="bg-slate-900/80 border border-amber-500/20 rounded-lg p-3 text-xs">
                <div className="flex items-center justify-between text-slate-400">
                  <span className="font-mono text-white">{exc.payment_id}</span>
                  <span className="bg-amber-500/20 text-amber-300 px-1.5 py-0.5 rounded text-[10px] uppercase font-bold">
                    {exc.exception_type}
                  </span>
                </div>
                <p className="mt-1 text-slate-300">
                  {typeof exc.details === 'object' && exc.details !== null
                    ? String(exc.details.message || exc.details.reason || JSON.stringify(exc.details))
                    : 'Discrepancy detected'}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Search and Filters */}
      <div className="flex items-center justify-between">
        <div className="relative w-full max-w-md">
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
          <input
            type="text"
            placeholder="Search payments by ID, order ref, or provider ID..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-slate-900 border border-slate-800 rounded-lg pl-9 pr-4 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-sky-500"
          />
        </div>
        <div className="text-xs text-slate-400">
          Showing {filteredPayments.length} of {payments.length} transactions
        </div>
      </div>

      {/* Payments Ledger Table */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden shadow">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/80 text-slate-400 border-b border-slate-800 uppercase font-semibold text-[10px] tracking-wider">
              <tr>
                <th className="py-3 px-4">Payment ID / Order</th>
                <th className="py-3 px-4">Amount</th>
                <th className="py-3 px-4">Provider Truth</th>
                <th className="py-3 px-4">Funds Status (Claim)</th>
                <th className="py-3 px-4">Refund</th>
                <th className="py-3 px-4">Provider / Reference</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {filteredPayments.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-slate-500">
                    No payments found. Use the Simulator above to create test transactions.
                  </td>
                </tr>
              ) : (
                filteredPayments.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-800/40 transition">
                    <td className="py-3 px-4">
                      <div className="font-mono text-white font-medium">{p.id}</div>
                      <div className="text-[11px] text-slate-500">Order: {p.order_ref}</div>
                    </td>
                    <td className="py-3 px-4 font-semibold text-slate-200">
                      {formatCurrency(p.amount_minor, p.currency)}
                    </td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-0.5 rounded-full border text-[10px] font-bold ${getStatusBadge(p.payment_status)}`}>
                        {p.payment_status}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      {p.funds_status === 'CUSTOMER_REPORTED_DEBIT' ? (
                        <span className="px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20 text-[10px] font-bold inline-flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-ping" />
                          Customer Claim
                        </span>
                      ) : (
                        <span className="text-slate-400">{p.funds_status}</span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      {p.payment_status === 'REVERSED' ? (
                        <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px] font-bold">
                          REVERSED
                        </span>
                      ) : (
                        <span className="text-slate-500">-</span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <div className="text-slate-300 uppercase font-mono text-[11px]">{p.provider}</div>
                      <div className="text-[10px] text-slate-500 font-mono truncate max-w-[120px]">{p.provider_payment_id}</div>
                    </td>
                    <td className="py-3 px-4 text-right space-x-2">
                      <button
                        onClick={() => handleOpenTimeline(p)}
                        className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-sky-400 border border-slate-700 text-[11px] font-medium transition"
                      >
                        Timeline
                      </button>
                      {p.payment_status !== 'SUCCEEDED' && p.funds_status !== 'CUSTOMER_REPORTED_DEBIT' && (
                        <button
                          onClick={() => setDebitModalPayment(p)}
                          className="px-2.5 py-1 rounded bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 border border-blue-500/20 text-[11px] font-medium transition"
                        >
                          Report Debit
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Payment Timeline Drawer / Modal */}
      {selectedPayment && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl max-h-[85vh] overflow-hidden flex flex-col shadow-2xl">
            {/* Header */}
            <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/80">
              <div className="flex items-center space-x-2">
                <FileText className="w-4 h-4 text-sky-400" />
                <h3 className="font-bold text-white text-sm">
                  Payment Event Timeline: <span className="font-mono text-sky-400">{selectedPayment.id}</span>
                </h3>
              </div>
              <button
                onClick={() => setSelectedPayment(null)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Body */}
            <div className="p-5 overflow-y-auto space-y-4">
              <div className="grid grid-cols-2 gap-3 bg-slate-950/50 p-3 rounded-lg border border-slate-800 text-xs">
                <div>
                  <span className="text-slate-500">Provider Status:</span>
                  <span className={`ml-2 px-2 py-0.5 rounded text-[10px] font-bold border ${getStatusBadge(selectedPayment.payment_status)}`}>
                    {selectedPayment.payment_status}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500">Funds Status:</span>
                  <span className="ml-2 font-semibold text-slate-300">{selectedPayment.funds_status}</span>
                </div>
                <div>
                  <span className="text-slate-500">Amount:</span>
                  <span className="ml-2 font-semibold text-slate-200">
                    {formatCurrency(selectedPayment.amount_minor, selectedPayment.currency)}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500">Provider Payment ID:</span>
                  <span className="ml-2 font-mono text-slate-400 truncate">{selectedPayment.provider_payment_id}</span>
                </div>
              </div>

              <div>
                <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                  Append-Only Event Stream ({timeline.length} Events)
                </h4>

                {isLoadingTimeline ? (
                  <div className="py-8 text-center text-slate-500 text-xs flex items-center justify-center gap-2">
                    <RefreshCw className="w-4 h-4 animate-spin text-sky-400" />
                    <span>Loading immutable timeline...</span>
                  </div>
                ) : timeline.length === 0 ? (
                  <div className="py-6 text-center text-slate-500 text-xs">
                    No timeline events recorded yet.
                  </div>
                ) : (
                  <div className="space-y-3 relative before:absolute before:inset-0 before:left-3 before:w-0.5 before:bg-slate-800">
                    {timeline.map((evt) => (
                      <div key={evt.id} className="relative pl-7 text-xs">
                        <div className="absolute left-1.5 top-1.5 w-3 h-3 rounded-full bg-slate-900 border-2 border-sky-400" />
                        <div className="bg-slate-950/70 border border-slate-800 rounded-lg p-3">
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-semibold text-white">{evt.event_type}</span>
                            <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${getStatusBadge(evt.normalized_status)}`}>
                              {evt.normalized_status}
                            </span>
                          </div>
                          <div className="text-[11px] text-slate-400 flex items-center gap-3">
                            <span className="flex items-center gap-1">
                              <Clock className="w-3 h-3 text-slate-500" />
                              {new Date(evt.event_time).toLocaleTimeString()}
                            </span>
                            <span>Source: {evt.source}</span>
                          </div>
                          <div className="mt-2 text-[10px] font-mono text-slate-500 truncate flex items-center gap-1">
                            <Hash className="w-3 h-3 text-slate-600" />
                            <span>Payload Hash: {evt.payload_hash}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Customer Debit Claim Modal */}
      {debitModalPayment && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md p-5 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="font-bold text-white text-sm flex items-center gap-2">
                <CreditCard className="w-4 h-4 text-blue-400" />
                <span>Report Customer Debit Claim</span>
              </h3>
              <button onClick={() => setDebitModalPayment(null)} className="text-slate-400 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-slate-300">
              Record customer claim that money was debited from their account for payment{' '}
              <span className="font-mono text-white">{debitModalPayment.id}</span>.
              This sets <code className="text-blue-400">funds_status=CUSTOMER_REPORTED_DEBIT</code> without altering provider truth.
            </p>

            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">Claimed UTR / RRN (Optional)</label>
              <input
                type="text"
                placeholder="e.g. UPI428198739182"
                value={claimedUtr}
                onChange={(e) => setClaimedUtr(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-blue-500"
              />
            </div>

            <div className="flex justify-end space-x-2 pt-2">
              <button
                onClick={() => setDebitModalPayment(null)}
                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs text-slate-300"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmitDebit}
                className="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-xs text-white font-medium flex items-center space-x-1.5"
              >
                <Send className="w-3.5 h-3.5" />
                <span>Submit Claim</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
