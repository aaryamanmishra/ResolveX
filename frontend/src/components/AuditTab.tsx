import React, { useState } from 'react';
import { AuditRecord } from '../api';
import {
  RefreshCw,
  Search,
  X,
  Copy,
  Check,
} from 'lucide-react';

interface AuditTabProps {
  logs: AuditRecord[];
  onRefresh: () => void;
  isLoading: boolean;
}

export const AuditTab: React.FC<AuditTabProps> = ({ logs, onRefresh, isLoading }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedRecord, setSelectedRecord] = useState<AuditRecord | null>(null);
  const [copiedHash, setCopiedHash] = useState(false);

  const filteredLogs = logs.filter((log) => {
    const term = searchTerm.toLowerCase();
    return (
      log.id.toLowerCase().includes(term) ||
      log.action.toLowerCase().includes(term) ||
      log.actor_id.toLowerCase().includes(term) ||
      log.resource_id.toLowerCase().includes(term) ||
      log.resource_type.toLowerCase().includes(term) ||
      log.metadata_hash.toLowerCase().includes(term)
    );
  });

  const handleCopyHash = (hash: string) => {
    navigator.clipboard.writeText(hash);
    setCopiedHash(true);
    setTimeout(() => setCopiedHash(false), 2000);
  };

  const getActionBadge = (action: string) => {
    if (action.includes('BLOCKED') || action.includes('REJECTED')) {
      return 'bg-rose-50 text-rose-700 border-rose-200';
    }
    if (action.includes('APPROVED') || action.includes('CONFIRMED')) {
      return 'bg-emerald-50 text-emerald-700 border-emerald-200';
    }
    if (action.includes('INVESTIGATION') || action.includes('UPLOADED') || action.includes('SEEDED')) {
      return 'bg-blue-50 text-blue-700 border-blue-200';
    }
    return 'bg-slate-100 text-slate-700 border-slate-200';
  };

  return (
    <div className="space-y-5 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-2 border-b border-slate-200/80">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Audit Trail</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Cryptographic SHA-256 tamper-evident record of state changes, agent invocations, and approval decisions.
          </p>
        </div>

        <button
          onClick={onRefresh}
          disabled={isLoading}
          className="px-3 py-1.5 rounded-md bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-medium shadow-2xs transition-colors flex items-center space-x-1.5 self-start sm:self-auto"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Refresh Stream</span>
        </button>
      </div>

      {/* Filter & Search Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-2.5 rounded-lg border border-slate-200 shadow-2xs">
        <div className="relative w-full sm:w-80">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
          <input
            type="text"
            placeholder="Search by action, actor, resource ID or hash..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-slate-50 border border-slate-200 rounded-md pl-8 pr-3 py-1.5 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:border-blue-500 focus:bg-white"
          />
        </div>

        <div className="text-xs text-slate-500 font-medium">
          Showing <strong>{filteredLogs.length}</strong> of {logs.length} events
        </div>
      </div>

      {/* Audit Table */}
      <div className="bg-white border border-slate-200 rounded-lg shadow-2xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50/70 text-slate-500 text-[11px] font-semibold uppercase tracking-wider">
                <th className="py-2.5 px-4">Timestamp</th>
                <th className="py-2.5 px-4">Action</th>
                <th className="py-2.5 px-4">Actor</th>
                <th className="py-2.5 px-4">Target Resource</th>
                <th className="py-2.5 px-4">SHA-256 Provenance Hash</th>
                <th className="py-2.5 px-4 text-right">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {filteredLogs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-12 text-slate-500">
                    No audit records matched the filter criteria.
                  </td>
                </tr>
              ) : (
                filteredLogs.map((log) => (
                  <tr
                    key={log.id}
                    onClick={() => setSelectedRecord(log)}
                    className="hover:bg-slate-50/80 transition-colors cursor-pointer"
                  >
                    <td className="py-3 px-4 whitespace-nowrap text-slate-500 text-[11px]">
                      <div className="font-mono text-slate-800 font-medium">
                        {new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                      </div>
                      <div className="text-[10px] text-slate-400">
                        {new Date(log.timestamp).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })}
                      </div>
                    </td>

                    <td className="py-3 px-4">
                      <span className={`inline-block px-2 py-0.5 rounded-xs text-[10px] font-semibold border ${getActionBadge(log.action)}`}>
                        {log.action}
                      </span>
                    </td>

                    <td className="py-3 px-4 font-mono text-slate-800 text-[11px]">
                      {log.actor_id}
                    </td>

                    <td className="py-3 px-4">
                      <div className="font-semibold text-slate-900 text-xs">{log.resource_type}</div>
                      <div className="font-mono text-[10px] text-slate-400 truncate max-w-[140px]">
                        {log.resource_id}
                      </div>
                    </td>

                    <td className="py-3 px-4 font-mono text-[10px] text-slate-500">
                      <span className="bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200 text-slate-700">
                        sha256:{log.metadata_hash.slice(0, 12)}...
                      </span>
                    </td>

                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedRecord(log);
                        }}
                        className="text-xs text-blue-600 hover:text-blue-700 font-semibold"
                      >
                        Inspect →
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Audit Event JSON Inspector Modal */}
      {selectedRecord && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-slate-200 rounded-lg max-w-xl w-full p-5 shadow-xl space-y-4 animate-in fade-in">
            <div className="flex items-center justify-between border-b border-slate-200 pb-3">
              <div>
                <div className="flex items-center space-x-2">
                  <span className="font-mono font-bold text-xs text-slate-900">{selectedRecord.id}</span>
                  <span className={`px-2 py-0.5 rounded-xs text-[10px] font-semibold border ${getActionBadge(selectedRecord.action)}`}>
                    {selectedRecord.action}
                  </span>
                </div>
                <div className="text-[11px] text-slate-400 mt-0.5">
                  Tenant: <span className="font-mono text-slate-600">{selectedRecord.tenant_id}</span>
                </div>
              </div>

              <button
                onClick={() => setSelectedRecord(null)}
                className="text-slate-400 hover:text-slate-700"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Cryptographic Hash Card */}
            <div className="bg-slate-50 p-3 rounded-md border border-slate-200/80 space-y-1 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-slate-500 text-[11px] font-semibold">Cryptographic Metadata Hash (SHA-256)</span>
                <button
                  onClick={() => handleCopyHash(selectedRecord.metadata_hash)}
                  className="text-[11px] text-blue-600 hover:text-blue-700 flex items-center space-x-1"
                >
                  {copiedHash ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                  <span>{copiedHash ? 'Copied' : 'Copy'}</span>
                </button>
              </div>
              <div className="font-mono text-[10px] text-slate-800 break-all bg-white p-2 rounded border border-slate-200">
                {selectedRecord.metadata_hash}
              </div>
            </div>

            {/* Event Details Payload */}
            <div className="space-y-1.5">
              <div className="text-slate-700 text-xs font-semibold">Structured Audit Payload</div>
              <pre className="bg-slate-900 text-slate-100 p-3 rounded-md text-[11px] font-mono overflow-x-auto max-h-64">
                {JSON.stringify(selectedRecord.details, null, 2)}
              </pre>
            </div>

            <div className="flex justify-end pt-2 border-t border-slate-100">
              <button
                onClick={() => setSelectedRecord(null)}
                className="px-3.5 py-1.5 rounded-md bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold shadow-xs"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
