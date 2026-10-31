import React from 'react';
import { UserRole } from '../types/contracts';
import {
  LayoutDashboard,
  CreditCard,
  FolderOpen,
  FileText,
  ShieldCheck,
  ChevronDown,
} from 'lucide-react';

interface NavItem {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
  badgeColor?: string;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

interface SidebarProps {
  activeTab: string;
  onNavigate: (tab: string) => void;
  currentRole: UserRole;
  onRoleChange: (role: UserRole) => void;
  tenantId: string;
  demoMode: boolean;
  paymentCount: number;
  caseCount: number;
  exceptionCount: number;
  isMobileOpen: boolean;
  onCloseMobile: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  onNavigate,
  currentRole,
  onRoleChange,
  tenantId,
  demoMode,
  exceptionCount,
  caseCount,
  isMobileOpen,
  onCloseMobile,
}) => {
  const navSections: NavSection[] = [
    {
      title: 'Workspace',
      items: [
        { id: 'overview', label: 'Overview', icon: LayoutDashboard },
      ],
    },
    {
      title: 'Operations',
      items: [
        {
          id: 'payments',
          label: 'Payments',
          icon: CreditCard,
          badge: exceptionCount > 0 ? `${exceptionCount} exceptions` : undefined,
          badgeColor: 'bg-amber-50 text-amber-700 border-amber-200',
        },
        {
          id: 'investigations',
          label: 'Investigations',
          icon: FolderOpen,
          badge: caseCount > 0 ? `${caseCount}` : undefined,
          badgeColor: 'bg-blue-50 text-blue-700 border-blue-200',
        },
      ],
    },
    {
      title: 'Records',
      items: [
        { id: 'evidence', label: 'Evidence', icon: FileText },
        { id: 'audit', label: 'Audit Trail', icon: ShieldCheck },
      ],
    },
  ];

  const roleNames: Record<UserRole, { title: string; subtitle: string }> = {
    SUPPORT_ANALYST: { title: 'Support Analyst', subtitle: 'usr_support_01' },
    FRAUD_ANALYST: { title: 'Fraud Analyst', subtitle: 'usr_fraud_01' },
    SUPERVISOR: { title: 'Operations Supervisor', subtitle: 'usr_supervisor_01' },
    PLATFORM_ADMIN: { title: 'Platform Admin', subtitle: 'usr_admin_01' },
    CUSTOMER: { title: 'Customer Account', subtitle: 'usr_cust_01' },
  };

  const handleSelectTab = (id: string) => {
    onNavigate(id);
    onCloseMobile();
  };

  return (
    <>
      {/* Mobile Backdrop */}
      {isMobileOpen && (
        <div
          className="fixed inset-0 bg-slate-900/30 backdrop-blur-xs z-40 lg:hidden"
          onClick={onCloseMobile}
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={`fixed lg:static top-0 bottom-0 left-0 z-50 w-64 bg-slate-50 border-r border-slate-200 flex flex-col justify-between transition-transform duration-200 ease-in-out ${
          isMobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        <div className="flex flex-col flex-1 overflow-y-auto">
          {/* Brand Header */}
          <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
            <div className="flex items-center space-x-2.5">
              <div className="w-8 h-8 rounded-lg bg-slate-900 text-white flex items-center justify-center font-bold text-sm tracking-tight shadow-xs">
                RX
              </div>
              <div>
                <div className="flex items-center space-x-1.5">
                  <span className="font-semibold text-slate-900 text-sm tracking-tight">ResolveX</span>
                  <span className="text-[10px] font-medium bg-slate-200/80 text-slate-700 px-1.5 py-0.2 rounded">
                    FinOps
                  </span>
                </div>
                <div className="text-[11px] text-slate-500 font-medium truncate max-w-[150px]">
                  {tenantId}
                </div>
              </div>
            </div>
          </div>

          {/* Navigation Groups */}
          <nav className="p-3 space-y-5 flex-1">
            {navSections.map((section) => (
              <div key={section.title} className="space-y-1">
                <div className="px-3 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                  {section.title}
                </div>
                <div className="space-y-0.5">
                  {section.items.map((item) => {
                    const Icon = item.icon;
                    const isActive = activeTab === item.id;
                    return (
                      <button
                        key={item.id}
                        onClick={() => handleSelectTab(item.id)}
                        className={`w-full flex items-center justify-between px-3 py-2 rounded-md text-xs font-medium transition-colors ${
                          isActive
                            ? 'bg-white text-slate-900 shadow-xs border border-slate-200/90 font-semibold'
                            : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/80'
                        }`}
                      >
                        <div className="flex items-center space-x-2.5 truncate">
                          <Icon
                            className={`w-4 h-4 shrink-0 ${
                              isActive ? 'text-blue-600' : 'text-slate-400'
                            }`}
                          />
                          <span className="truncate">{item.label}</span>
                        </div>
                        {item.badge && (
                          <span
                            className={`text-[10px] font-medium px-1.5 py-0.5 rounded-sm border shrink-0 ${
                              item.badgeColor || 'bg-slate-100 text-slate-600 border-slate-200'
                            }`}
                          >
                            {item.badge}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </nav>
        </div>

        {/* Bottom Area: Persona & System Status */}
        <div className="p-3 border-t border-slate-200 bg-slate-50/50 space-y-2">
          {/* Mode Pill */}
          <div className="px-3 py-1.5 rounded-md bg-white border border-slate-200/80 flex items-center justify-between text-[11px]">
            <div className="flex items-center space-x-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              <span className="text-slate-600 font-medium">
                {demoMode ? 'Simulator & Demo Mode' : 'Live Gateway Active'}
              </span>
            </div>
          </div>

          {/* Persona Switcher Menu */}
          <div className="bg-white rounded-lg border border-slate-200 p-2 text-xs shadow-xs">
            <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1 px-1">
              Active Persona (RBAC)
            </div>
            <div className="relative">
              <select
                value={currentRole}
                onChange={(e) => onRoleChange(e.target.value as UserRole)}
                className="w-full bg-slate-50 border border-slate-200 rounded px-2.5 py-1.5 text-xs text-slate-900 font-medium focus:outline-none focus:border-blue-500 cursor-pointer appearance-none pr-7"
              >
                <option value="SUPPORT_ANALYST">Support Analyst (usr_support_01)</option>
                <option value="SUPERVISOR">Supervisor (usr_supervisor_01)</option>
                <option value="FRAUD_ANALYST">Fraud Analyst (usr_fraud_01)</option>
                <option value="PLATFORM_ADMIN">Platform Admin (usr_admin_01)</option>
                <option value="CUSTOMER">Customer Account (usr_cust_01)</option>
              </select>
              <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-2 top-2.5 pointer-events-none" />
            </div>
            <div className="text-[10px] text-slate-500 mt-1 px-1 flex items-center justify-between">
              <span>{roleNames[currentRole].title}</span>
              <span className="font-mono text-[9px] text-slate-400">
                {currentRole === 'SUPERVISOR' || currentRole === 'PLATFORM_ADMIN' ? 'Approval Allowed' : 'Read-Only Gate'}
              </span>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
};
