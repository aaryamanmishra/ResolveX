import React from 'react';
import {
  CreditCard,
  AlertTriangle,
  FolderOpen,
  UserCheck,
  Network,
  ArrowRight,
  Sparkles,
  CheckCircle2,
} from 'lucide-react';

interface OverviewTabProps {
  paymentCount: number;
  caseCount: number;
  exceptionCount: number;
  approvalCount: number;
  fraudAlertCount: number;
  onNavigate: (tab: string) => void;
  onRunTrack1Demo: () => void;
  onRunTrack2Demo: () => void;
}

export const OverviewTab: React.FC<OverviewTabProps> = ({
  paymentCount,
  caseCount,
  exceptionCount,
  approvalCount,
  fraudAlertCount,
  onNavigate,
  onRunTrack1Demo,
  onRunTrack2Demo,
}) => {
  return (
    <div className="space-y-6">
      {/* Hero Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-sky-900/40 via-indigo-900/30 to-slate-900 border border-sky-500/20 p-6 md:p-8">
        <div className="max-w-3xl">
          <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-sky-500/10 border border-sky-500/20 text-sky-400 text-xs font-semibold mb-3">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Dual-Track Autonomous Financial Operations</span>
          </div>
          <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">
            Evidence-Grounded Payment Resolution & Graph Fraud Intelligence
          </h1>
          <p className="mt-2 text-slate-300 text-sm md:text-base leading-relaxed">
            ResolveX AI unifies payment lifecycle tracking and agentic relationship graph analytics.
            Every AI finding is cryptographically cited to verified receipts or timeline events, with deterministic
            policy governance and mandatory human approval for financial side effects.
          </p>

          <div className="mt-6 flex flex-wrap gap-3">
            <button
              onClick={onRunTrack1Demo}
              className="px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-sm font-semibold shadow-lg shadow-sky-600/30 flex items-center space-x-2 transition"
            >
              <span>Run Track 1 Demo (Payment Triage)</span>
              <ArrowRight className="w-4 h-4" />
            </button>
            <button
              onClick={onRunTrack2Demo}
              className="px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-sm font-semibold shadow-lg shadow-rose-600/30 flex items-center space-x-2 transition"
            >
              <span>Run Track 2 Demo (Syndicate Fraud)</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* KPI Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div
          onClick={() => onNavigate('payments')}
          className="bg-slate-900/70 border border-slate-800 rounded-xl p-4 hover:border-sky-500/40 transition cursor-pointer"
        >
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-medium">Payments Ingested</span>
            <CreditCard className="w-4 h-4 text-sky-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-white">{paymentCount}</div>
          <p className="text-[11px] text-slate-500 mt-1">Gateway verified events</p>
        </div>

        <div
          onClick={() => onNavigate('investigations')}
          className="bg-slate-900/70 border border-slate-800 rounded-xl p-4 hover:border-indigo-500/40 transition cursor-pointer"
        >
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-medium">Open Cases</span>
            <FolderOpen className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-white">{caseCount}</div>
          <p className="text-[11px] text-slate-500 mt-1">Triage & fraud hub</p>
        </div>

        <div
          onClick={() => onNavigate('payments')}
          className="bg-slate-900/70 border border-slate-800 rounded-xl p-4 hover:border-amber-500/40 transition cursor-pointer"
        >
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-medium">Reconciliation Alerts</span>
            <AlertTriangle className="w-4 h-4 text-amber-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-amber-400">{exceptionCount}</div>
          <p className="text-[11px] text-slate-500 mt-1">Discrepancy queue</p>
        </div>

        <div
          onClick={() => onNavigate('investigations')}
          className="bg-slate-900/70 border border-slate-800 rounded-xl p-4 hover:border-purple-500/40 transition cursor-pointer"
        >
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-medium">Pending Approvals</span>
            <UserCheck className="w-4 h-4 text-purple-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-purple-400">{approvalCount}</div>
          <p className="text-[11px] text-slate-500 mt-1">Human review gate</p>
        </div>

        <div
          onClick={() => onNavigate('graph')}
          className="bg-slate-900/70 border border-slate-800 rounded-xl p-4 hover:border-rose-500/40 transition cursor-pointer"
        >
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-medium">Fraud Ring Alerts</span>
            <Network className="w-4 h-4 text-rose-400" />
          </div>
          <div className="mt-2 text-2xl font-bold text-rose-400">{fraudAlertCount}</div>
          <p className="text-[11px] text-slate-500 mt-1">Graph syndicates</p>
        </div>
      </div>

      {/* Track Explanatory Cards */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Track 1 Card */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6">
          <div className="flex items-center space-x-3 mb-3">
            <div className="w-8 h-8 rounded-lg bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400">
              <CreditCard className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-semibold text-white text-base">Track 1: Payment Issue Resolution</h3>
              <p className="text-xs text-slate-400">Webhook ingress, state machine, SLA & debit reconciliation</p>
            </div>
          </div>
          <ul className="space-y-2 text-xs text-slate-300">
            <li className="flex items-start space-x-2">
              <CheckCircle2 className="w-4 h-4 text-sky-400 shrink-0 mt-0.5" />
              <span>Normalizes gateway states (`payment_status`) distinctly from customer claims (`funds_status`).</span>
            </li>
            <li className="flex items-start space-x-2">
              <CheckCircle2 className="w-4 h-4 text-sky-400 shrink-0 mt-0.5" />
              <span>Append-only event timeline preventing out-of-order regression of terminal states.</span>
            </li>
            <li className="flex items-start space-x-2">
              <CheckCircle2 className="w-4 h-4 text-sky-400 shrink-0 mt-0.5" />
              <span>Automated reconciliation detects unconfirmed debits, amount mismatches, and refund SLA breaches (&gt; 5 days).</span>
            </li>
          </ul>
          <div className="mt-4 pt-4 border-t border-slate-800 flex justify-between items-center">
            <span className="text-xs text-slate-400">PRD §15.1 Scenarios Verified</span>
            <button
              onClick={() => onNavigate('payments')}
              className="text-xs font-semibold text-sky-400 hover:text-sky-300 flex items-center space-x-1"
            >
              <span>Open Payments Console</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Track 2 Card */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-6">
          <div className="flex items-center space-x-3 mb-3">
            <div className="w-8 h-8 rounded-lg bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-400">
              <Network className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-semibold text-white text-base">Track 2: Agentic Fraud Investigation</h3>
              <p className="text-xs text-slate-400">Tokenized relationship graph, syndicate detection & policy gate</p>
            </div>
          </div>
          <ul className="space-y-2 text-xs text-slate-300">
            <li className="flex items-start space-x-2">
              <CheckCircle2 className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <span>HMAC-tokenized entities (`CustomerToken`, `DeviceToken`, `PaymentInstrumentToken`, `UPIReferenceToken`).</span>
            </li>
            <li className="flex items-start space-x-2">
              <CheckCircle2 className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <span>Deterministic heuristics detect shared device rings (&gt; 3 accounts) and smurfing without false positives.</span>
            </li>
            <li className="flex items-start space-x-2">
              <CheckCircle2 className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <span>LangGraph agent harness synthesizes findings citing evidence IDs; sensitive actions pause for supervisor approval.</span>
            </li>
          </ul>
          <div className="mt-4 pt-4 border-t border-slate-800 flex justify-between items-center">
            <span className="text-xs text-slate-400">PRD §15.2 Scenarios Verified</span>
            <button
              onClick={() => onNavigate('graph')}
              className="text-xs font-semibold text-rose-400 hover:text-rose-300 flex items-center space-x-1"
            >
              <span>Explore Graph Canvas</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
