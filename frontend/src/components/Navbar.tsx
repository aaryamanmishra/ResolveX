import React from 'react';
import { UserRole } from '../types/contracts';
import { ShieldCheck, User, Building2, Activity, PlayCircle } from 'lucide-react';

interface NavbarProps {
  currentRole: UserRole;
  onRoleChange: (role: UserRole) => void;
  tenantId: string;
  demoMode: boolean;
  onRunTrack1Demo: () => void;
  onRunTrack2Demo: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentRole,
  onRoleChange,
  tenantId,
  demoMode,
  onRunTrack1Demo,
  onRunTrack2Demo,
}) => {
  const roles: UserRole[] = [
    'SUPPORT_ANALYST',
    'FRAUD_ANALYST',
    'SUPERVISOR',
    'CUSTOMER',
    'PLATFORM_ADMIN',
  ];

  return (
    <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand */}
        <div className="flex items-center space-x-3">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-sky-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-sky-500/20">
            <ShieldCheck className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-bold text-lg text-white tracking-tight">ResolveX AI</span>
              <span className="text-[10px] uppercase font-semibold bg-sky-500/10 text-sky-400 border border-sky-500/20 px-2 py-0.5 rounded-full">
                Phase 6 UX
              </span>
              {demoMode && (
                <span className="text-[10px] uppercase font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded-full flex items-center gap-1">
                  <Activity className="w-3 h-3 animate-pulse" /> Zero-Key Demo
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400 hidden sm:block">
              Agentic Payment Intelligence & Graph-Based Fraud Resolution
            </p>
          </div>
        </div>

        {/* Quick Demo Controls */}
        <div className="flex items-center space-x-2">
          <button
            onClick={onRunTrack1Demo}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-md bg-slate-800 hover:bg-slate-700 text-xs font-medium text-sky-400 border border-slate-700 transition shadow-sm"
            title="Auto-runs Track 1 payment discrepancy triage demo"
          >
            <PlayCircle className="w-3.5 h-3.5 text-sky-400" />
            <span className="hidden sm:inline">Track 1 Demo</span>
            <span className="sm:hidden">T1 Demo</span>
          </button>
          <button
            onClick={onRunTrack2Demo}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-md bg-slate-800 hover:bg-slate-700 text-xs font-medium text-rose-400 border border-slate-700 transition shadow-sm"
            title="Auto-runs Track 2 graph syndicate fraud investigation demo"
          >
            <PlayCircle className="w-3.5 h-3.5 text-rose-400" />
            <span className="hidden sm:inline">Track 2 Demo</span>
            <span className="sm:hidden">T2 Demo</span>
          </button>
        </div>

        {/* Persona Switcher & Tenant Boundary */}
        <div className="flex items-center space-x-4">
          <div className="hidden lg:flex items-center space-x-1.5 text-xs text-slate-400 bg-slate-950/60 px-2.5 py-1.5 rounded-md border border-slate-800">
            <Building2 className="w-3.5 h-3.5 text-slate-500" />
            <span>{tenantId}</span>
          </div>

          <div className="flex items-center space-x-2 bg-slate-950/80 px-2.5 py-1 rounded-lg border border-slate-800">
            <User className="w-3.5 h-3.5 text-sky-400" />
            <select
              value={currentRole}
              onChange={(e) => onRoleChange(e.target.value as UserRole)}
              className="bg-transparent text-xs text-slate-200 font-medium focus:outline-none cursor-pointer"
            >
              {roles.map((r) => (
                <option key={r} value={r} className="bg-slate-900 text-slate-200">
                  {r.replace('_', ' ')}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>
    </header>
  );
};
