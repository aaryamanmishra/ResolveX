import React, { useState } from 'react';
import {
  Menu,
  RefreshCw,
  ChevronDown,
  Play,
} from 'lucide-react';

interface HeaderProps {
  activeTab: string;
  onRefresh: () => void;
  isLoading: boolean;
  onRunTrack1Demo: () => void;
  onRunTrack2Demo: () => void;
  onToggleMobileMenu: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  onRefresh,
  isLoading,
  onRunTrack1Demo,
  onRunTrack2Demo,
  onToggleMobileMenu,
}) => {
  const [showDemoMenu, setShowDemoMenu] = useState(false);

  const breadcrumbMap: Record<string, { category: string; page: string }> = {
    overview: { category: 'Workspace', page: 'Overview' },
    payments: { category: 'Operations', page: 'Payments & Reconciliation' },
    investigations: { category: 'Operations', page: 'Investigations & Cases' },
    evidence: { category: 'Records', page: 'Multimodal Evidence' },
    audit: { category: 'Records', page: 'Audit Trail' },
  };

  const current = breadcrumbMap[activeTab] || { category: 'Workspace', page: 'Overview' };

  return (
    <header className="h-14 border-b border-slate-200 bg-white px-4 sm:px-6 flex items-center justify-between sticky top-0 z-30 shadow-2xs">
      {/* Left: Mobile Toggle & Breadcrumb */}
      <div className="flex items-center space-x-3">
        <button
          onClick={onToggleMobileMenu}
          className="p-1.5 rounded-md text-slate-500 hover:text-slate-900 hover:bg-slate-100 lg:hidden"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div className="flex items-center space-x-2 text-xs">
          <span className="text-slate-400 font-medium">{current.category}</span>
          <span className="text-slate-300">/</span>
          <span className="text-slate-900 font-semibold">{current.page}</span>
        </div>
      </div>

      {/* Right: Actions & Demo Scenarios */}
      <div className="flex items-center space-x-2.5">
        <button
          onClick={onRefresh}
          disabled={isLoading}
          className="p-1.5 rounded-md text-slate-500 hover:text-slate-900 hover:bg-slate-100 text-xs font-medium flex items-center space-x-1 transition-colors border border-transparent hover:border-slate-200"
          title="Refresh current data"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          <span className="hidden sm:inline text-slate-600">Sync</span>
        </button>

        {/* Understated Demo Scenarios Dropdown */}
        <div className="relative">
          <button
            onClick={() => setShowDemoMenu(!showDemoMenu)}
            className="px-2.5 py-1.5 rounded-md bg-slate-100 hover:bg-slate-200/80 text-slate-700 text-xs font-medium border border-slate-200 flex items-center space-x-1.5 transition-colors shadow-2xs"
          >
            <Play className="w-3 h-3 text-blue-600" />
            <span>Demo Scenarios</span>
            <ChevronDown className="w-3 h-3 text-slate-400" />
          </button>

          {showDemoMenu && (
            <>
              <div
                className="fixed inset-0 z-30"
                onClick={() => setShowDemoMenu(false)}
              />
              <div className="absolute right-0 mt-1.5 w-72 bg-white rounded-lg border border-slate-200 shadow-lg z-40 p-1.5 space-y-1 text-xs animate-in fade-in zoom-in-95">
                <div className="px-2.5 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400 border-b border-slate-100">
                  Pre-configured Test Scenarios
                </div>

                <button
                  onClick={() => {
                    setShowDemoMenu(false);
                    onRunTrack1Demo();
                  }}
                  className="w-full text-left p-2 rounded-md hover:bg-slate-50 flex items-start space-x-2 transition-colors group"
                >
                  <div className="w-6 h-6 rounded bg-blue-50 text-blue-600 flex items-center justify-center shrink-0 mt-0.5 border border-blue-100">
                    <span className="text-[10px] font-bold">T1</span>
                  </div>
                  <div>
                    <div className="font-semibold text-slate-900 group-hover:text-blue-600">
                      Track 1: UPI Debit Discrepancy
                    </div>
                    <div className="text-[11px] text-slate-500 leading-tight mt-0.5">
                      Simulates customer debit claim on failed order, opens dispute case, and runs LangGraph agent.
                    </div>
                  </div>
                </button>

                <button
                  onClick={() => {
                    setShowDemoMenu(false);
                    onRunTrack2Demo();
                  }}
                  className="w-full text-left p-2 rounded-md hover:bg-slate-50 flex items-start space-x-2 transition-colors group"
                >
                  <div className="w-6 h-6 rounded bg-rose-50 text-rose-600 flex items-center justify-center shrink-0 mt-0.5 border border-rose-100">
                    <span className="text-[10px] font-bold">T2</span>
                  </div>
                  <div>
                    <div className="font-semibold text-slate-900 group-hover:text-rose-600">
                      Track 2: Syndicate Fraud Cluster
                    </div>
                    <div className="text-[11px] text-slate-500 leading-tight mt-0.5">
                      Detects 4 accounts sharing single device, evaluates deterministic policy rules, and opens investigation.
                    </div>
                  </div>
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
};
