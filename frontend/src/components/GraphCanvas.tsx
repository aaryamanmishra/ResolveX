import React, { useState } from 'react';
import { GraphNeighborhoodResponse, GraphNode, FraudEvaluationResponse } from '../api';
import {
  Network,
  Search,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Smartphone,
  CreditCard,
  User,
  ShoppingBag,
  Hash,
} from 'lucide-react';

interface GraphCanvasProps {
  neighborhood: GraphNeighborhoodResponse | null;
  fraudEval: FraudEvaluationResponse | null;
  onSearchNeighborhood: (entityToken: string, depth?: number) => Promise<void>;
  onEvaluateFraud: (caseId: string) => Promise<void>;
  isLoading: boolean;
}

export const GraphCanvas: React.FC<GraphCanvasProps> = ({
  neighborhood,
  fraudEval,
  onSearchNeighborhood,
  isLoading,
}) => {
  const [searchToken, setSearchToken] = useState('cust_tok_synth_001');
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchToken.trim()) return;
    await onSearchNeighborhood(searchToken.trim(), 2);
  };

  const getNodeColor = (label: string) => {
    switch (label) {
      case 'CustomerToken':
        return '#0284c7'; // sky-600
      case 'DeviceToken':
        return '#e11d48'; // rose-600
      case 'PaymentInstrumentToken':
        return '#d97706'; // amber-600
      case 'Payment':
        return '#10b981'; // emerald-500
      case 'Merchant':
        return '#8b5cf6'; // purple-500
      default:
        return '#64748b'; // slate-500
    }
  };

  const getNodeIcon = (label: string) => {
    switch (label) {
      case 'CustomerToken':
        return <User className="w-4 h-4 text-sky-400" />;
      case 'DeviceToken':
        return <Smartphone className="w-4 h-4 text-rose-400" />;
      case 'PaymentInstrumentToken':
        return <CreditCard className="w-4 h-4 text-amber-400" />;
      case 'Payment':
        return <Hash className="w-4 h-4 text-emerald-400" />;
      case 'Merchant':
        return <ShoppingBag className="w-4 h-4 text-purple-400" />;
      default:
        return <Network className="w-4 h-4 text-slate-400" />;
    }
  };

  // Compute circular or grid layout coordinates for vertices
  const nodes = neighborhood?.vertices || [];
  const edges = neighborhood?.edges || [];

  const width = 640;
  const height = 400;
  const centerX = width / 2;
  const centerY = height / 2;
  const radius = Math.min(centerX, centerY) - 70;

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

  return (
    <div className="space-y-6">
      {/* Header & Traversal Controller */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 sm:p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-white flex items-center gap-2">
            <Network className="w-4 h-4 text-rose-400" />
            <span>Tokenized Graph Investigation Canvas (Apache AGE / In-Memory Adapter)</span>
          </h2>
          <p className="text-xs text-slate-400">
            Traverse tenant-scoped relationships across HMAC-tokenized customers, devices, and payment instruments.
          </p>
        </div>

        {/* Search Token Input */}
        <form onSubmit={handleSearch} className="flex items-center space-x-2 w-full sm:w-auto">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2.5" />
            <input
              type="text"
              placeholder="Enter entity token..."
              value={searchToken}
              onChange={(e) => setSearchToken(e.target.value)}
              className="bg-slate-950 border border-slate-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-rose-500 w-56 font-mono"
            />
          </div>
          <button
            type="submit"
            disabled={isLoading}
            className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold flex items-center space-x-1 transition shadow-lg shadow-rose-600/20"
          >
            {isLoading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <span>Traverse</span>}
          </button>
        </form>
      </div>

      {/* Main Graph Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Interactive SVG Graph Canvas */}
        <div className="lg:col-span-8 bg-slate-950 border border-slate-800 rounded-2xl p-4 flex flex-col items-center justify-center min-h-[460px] relative overflow-hidden shadow-inner">
          <div className="absolute top-3 left-4 text-xs text-slate-500 flex items-center space-x-4">
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-sky-500" /> Customer
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-rose-500" /> Device
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-500" /> Instrument
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" /> Payment
            </span>
          </div>

          <div className="absolute top-3 right-4 text-[11px] text-slate-400 font-mono">
            Nodes: {nodes.length} | Edges: {edges.length}
          </div>

          {nodes.length === 0 ? (
            <div className="text-center text-slate-500 text-xs py-16">
              <Network className="w-8 h-8 mx-auto mb-2 text-slate-700 animate-pulse" />
              <span>No graph vertices loaded. Enter a token above or run the Track 2 demo.</span>
            </div>
          ) : (
            <svg width={width} height={height} className="max-w-full">
              {/* Directed Edges */}
              {edges.map((e) => {
                const src = nodePositions[e.source_id];
                const tgt = nodePositions[e.target_id];
                if (!src || !tgt) return null;
                return (
                  <g key={e.id}>
                    <line
                      x1={src.x}
                      y1={src.y}
                      x2={tgt.x}
                      y2={tgt.y}
                      stroke="#334155"
                      strokeWidth={1.5}
                      strokeDasharray={e.inferred ? '4 2' : undefined}
                    />
                  </g>
                );
              })}

              {/* Vertices */}
              {nodes.map((n) => {
                const pos = nodePositions[n.id] || { x: centerX, y: centerY };
                const isSelected = selectedNode?.id === n.id;
                const color = getNodeColor(n.label);
                return (
                  <g
                    key={n.id}
                    className="cursor-pointer transition-transform duration-150 hover:scale-110"
                    onClick={() => setSelectedNode(n)}
                  >
                    <circle
                      cx={pos.x}
                      cy={pos.y}
                      r={isSelected ? 22 : 18}
                      fill={color}
                      fillOpacity={0.85}
                      stroke={isSelected ? '#ffffff' : '#0f172a'}
                      strokeWidth={isSelected ? 3 : 2}
                    />
                    <text
                      x={pos.x}
                      y={pos.y + 32}
                      textAnchor="middle"
                      fill="#94a3b8"
                      fontSize="9"
                      fontFamily="monospace"
                    >
                      {n.id.length > 12 ? `${n.id.substring(0, 10)}...` : n.id}
                    </text>
                  </g>
                );
              })}
            </svg>
          )}
        </div>

        {/* Right: Inspector & Deterministic Indicators Panel */}
        <div className="lg:col-span-4 space-y-4">
          {/* Node Inspector */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 text-xs space-y-3">
            <h3 className="font-bold text-white uppercase tracking-wider text-[11px] flex items-center gap-1.5">
              <span>Vertex Inspector</span>
            </h3>

            {selectedNode ? (
              <div className="space-y-2">
                <div className="flex items-center space-x-2 bg-slate-950 p-2.5 rounded-lg border border-slate-800">
                  {getNodeIcon(selectedNode.label)}
                  <div>
                    <div className="font-bold text-white">{selectedNode.label}</div>
                    <div className="font-mono text-[10px] text-slate-400 break-all">{selectedNode.id}</div>
                  </div>
                </div>

                <div className="bg-slate-950/50 p-2.5 rounded-lg border border-slate-800 text-[11px] space-y-1">
                  <span className="text-slate-500 font-semibold block">HMAC Tokenization:</span>
                  <span className="text-emerald-400 font-mono">Tenant-Keyed SHA-256 HMAC (No PII stored)</span>
                </div>
              </div>
            ) : (
              <p className="text-slate-500 text-[11px]">Click any node on the graph canvas to inspect its properties and linkages.</p>
            )}
          </div>

          {/* Deterministic Indicators Panel */}
          {fraudEval ? (
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 text-xs space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="font-bold text-white uppercase tracking-wider text-[11px] flex items-center gap-1.5">
                  <ShieldAlert className="w-4 h-4 text-rose-400" />
                  <span>Deterministic Fraud Indicators</span>
                </h3>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${
                    fraudEval.severity === 'CRITICAL' || fraudEval.severity === 'HIGH'
                      ? 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                      : fraudEval.severity === 'MEDIUM'
                      ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                      : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                  }`}
                >
                  {fraudEval.severity}
                </span>
              </div>

              <p className="text-slate-300 leading-relaxed text-[11px]">{fraudEval.summary}</p>

              {fraudEval.reason_codes.length > 0 && (
                <div className="space-y-1">
                  <span className="text-slate-500 font-semibold text-[10px] uppercase">Reason Codes:</span>
                  <div className="flex flex-wrap gap-1">
                    {fraudEval.reason_codes.map((code) => (
                      <span key={code} className="px-1.5 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20 text-[10px] font-mono font-bold">
                        {code}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Benign Household Filter Badge */}
              <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800 flex items-center justify-between text-[11px]">
                <span className="text-slate-400">Benign Household Filter:</span>
                <span className="text-emerald-400 font-semibold flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5" /> Active (≤2 users)
                </span>
              </div>
            </div>
          ) : (
            <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-4 text-xs text-slate-500 text-center py-6">
              Deterministic fraud indicators will appear when investigating a fraud case.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
