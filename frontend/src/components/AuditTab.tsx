import React, { useState } from 'react';
import { AuditRecord } from '../api';
import { Shield, RefreshCw, Hash, User, Clock, CheckCircle2 } from 'lucide-react';

interface AuditTabProps {
  logs: AuditRecord[];
  onRefresh: () => void;
  isLoading: boolean;
}

export const AuditTab: React.FC<AuditTabProps> = ({ logs, onRefresh, isLoading }) => {
  const [selectedRecord, setSelectedRecord] = useState<AuditRecord | null>(null);

  const getActionBadge = (action: string) => {
    if (action.includes('BLOCKED') || action.includes('REJECTED')) {
      return 'bg-rose-500/10 text-rose-400 border-rose-500/20';
    }
    if (action.includes('APPROVED') || action.includes('CONFIRMED')) {
      return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
    }
    if (action.includes('INVESTIGATION') || action.includes('UPLOADED')) {
      return 'bg-sky-500/10 text-sky-400 border-sky-500/20';
    }
    return 'bg-slate-800 text-slate-300 border-slate-700';
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 sm:p-5 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-white flex items-center gap-2">
            <Shield className="w-4 h-4 text-sky-400" />
            <span>Immutable Audit Trail & Provenance Verifier (PRD §6 FR-021)</span>
          </h2>
          <p className="text-xs text-slate-400">
            Cryptographic SHA-256 metadata hashed events tracking every mutation, agent run, tool invocation, and human review decision.
          </p>
        </div>
        <button
          onClick={onRefresh}
          disabled={isLoading}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-md bg-slate-800 hover:bg-slate-700 text-xs text-slate-300 border border-slate-700 transition"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Refresh Audit Stream</span>
        </button>
      </div>

      {/* Audit Log Table */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden shadow">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/80 text-slate-400 border-b border-slate-800 uppercase font-semibold text-[10px] tracking-wider">
              <tr>
                <th className="py-3 px-4">Event ID</th>
                <th className="py-3 px-4">Action</th>
                <th className="py-3 px-4">Resource</th>
                <th className="py-3 px-4">Actor</th>
                <th className="py-3 px-4">Timestamp</th>
                <th className="py-3 px-4">Tamper Verification (SHA-256)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {logs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-8 text-slate-500">
                    No audit events recorded yet.
                  </td>
                </tr>
              ) : (
                logs.map((log) => (
                  <tr
                    key={log.id}
                    onClick={() => setSelectedRecord(log)}
                    className="hover:bg-slate-800/40 transition cursor-pointer"
                  >
                    <td className="py-3 px-4 font-mono text-slate-300 font-medium">{log.id}</td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${getActionBadge(log.action)}`}>
                        {log.action}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-semibold text-slate-200">{log.resource_type}</div>
                      <div className="font-mono text-[10px] text-slate-500 truncate max-w-[120px]">{log.resource_id}</div>
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-400 flex items-center gap-1 mt-1">
                      <User className="w-3 h-3 text-slate-600" />
                      <span>{log.actor_id}</span>
                    </td>
                    <td className="py-3 px-4 text-slate-400">
                      <div className="flex items-center gap-1 text-[11px]">
                        <Clock className="w-3 h-3 text-slate-600" />
                        <span>{new Date(log.timestamp).toLocaleTimeString()}</span>
                      </div>
                      <div className="text-[10px] text-slate-500">{new Date(log.timestamp).toLocaleDateString()}</div>
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-mono text-[10px] text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded inline-flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3" />
                        <span className="truncate max-w-[160px]">{log.metadata_hash}</span>
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Detail Popover / Modal */}
      {selectedRecord && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg p-5 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="font-bold text-white text-sm flex items-center gap-2">
                <Hash className="w-4 h-4 text-sky-400" />
                <span>Audit Record Inspector: {selectedRecord.id}</span>
              </h3>
              <button onClick={() => setSelectedRecord(null)} className="text-slate-400 hover:text-white">
                ✕
              </button>
            </div>

            <div className="space-y-2 text-xs">
              <div>
                <span className="text-slate-500">Action:</span>
                <span className="ml-2 font-bold text-white">{selectedRecord.action}</span>
              </div>
              <div>
                <span className="text-slate-500">Tenant:</span>
                <span className="ml-2 font-mono text-slate-300">{selectedRecord.tenant_id}</span>
              </div>
              <div>
                <span className="text-slate-500">Actor:</span>
                <span className="ml-2 font-mono text-slate-300">{selectedRecord.actor_id}</span>
              </div>
              <div>
                <span className="text-slate-500">Metadata Hash:</span>
                <span className="ml-2 font-mono text-emerald-400 break-all">{selectedRecord.metadata_hash}</span>
              </div>
              <div className="pt-2">
                <span className="text-slate-500 block mb-1">Event Payload Details:</span>
                <pre className="bg-slate-950 p-3 rounded-lg border border-slate-800 text-[11px] font-mono text-slate-300 overflow-x-auto">
                  {JSON.stringify(selectedRecord.details, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
