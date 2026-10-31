import React, { useState } from 'react';
import { Case, EvidenceAsset, EvidenceClaim, VerificationState } from '../types/contracts';
import {
  UploadCloud,
  ShieldCheck,
  Check,
  X,
  Hash,
  Sparkles,
  Lock,
} from 'lucide-react';

interface EvidenceTabProps {
  cases: Case[];
  onUploadEvidence: (
    caseId: string,
    file: File,
    sourceType: string,
    consentGranted: boolean
  ) => Promise<{ asset: EvidenceAsset; download_url: string; claims: EvidenceClaim[] }>;
  onConfirmClaim: (
    evidenceId: string,
    claimId: string,
    decision: VerificationState,
    confirmedValue?: string
  ) => Promise<void>;
  isLoading: boolean;
}

export const EvidenceTab: React.FC<EvidenceTabProps> = ({
  cases,
  onUploadEvidence,
  onConfirmClaim,
  isLoading,
}) => {
  const [selectedCaseId, setSelectedCaseId] = useState(cases[0]?.id || '');
  const [sourceType, setSourceType] = useState('RECEIPT_IMAGE');
  const [consentGranted, setConsentGranted] = useState(true);
  const [currentFile, setCurrentFile] = useState<File | null>(null);

  const [activeAsset, setActiveAsset] = useState<EvidenceAsset | null>(null);
  const [claims, setClaims] = useState<EvidenceClaim[]>([]);
  const [uploadSuccess, setUploadSuccess] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setCurrentFile(e.target.files[0]);
      setUploadSuccess(false);
      setErrorMessage('');
    }
  };

  const handleUpload = async () => {
    if (!currentFile || !selectedCaseId) {
      setErrorMessage('Please select a case and choose an evidence file.');
      return;
    }
    setErrorMessage('');
    try {
      const res = await onUploadEvidence(selectedCaseId, currentFile, sourceType, consentGranted);
      setActiveAsset(res.asset);
      setClaims(res.claims);
      setUploadSuccess(true);
      setCurrentFile(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMessage(msg);
    }
  };

  const handleClaimDecision = async (
    claimId: string,
    decision: VerificationState,
    confirmedValue?: string
  ) => {
    if (!activeAsset) return;
    try {
      await onConfirmClaim(activeAsset.id, claimId, decision, confirmedValue);
      setClaims((prev) =>
        prev.map((c) =>
          c.id === claimId
            ? { ...c, verification_state: decision, candidate_value: confirmedValue || c.candidate_value }
            : c
        )
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMessage(msg);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header & Controls */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 sm:p-5">
        <h2 className="text-sm font-semibold text-white flex items-center gap-2 mb-1">
          <UploadCloud className="w-4 h-4 text-emerald-400" />
          <span>Multimodal Evidence Intake & User Field Confirmation</span>
        </h2>
        <p className="text-xs text-slate-400">
          Upload payment receipts, bank statements (PDF), or voice notes. Magic bytes are validated, malware scanned,
          and candidate fields extracted with 2D coordinates for interactive confirmation.
        </p>

        {/* Form Controls */}
        <div className="mt-4 grid grid-cols-1 md:grid-cols-4 gap-3">
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Target Case</label>
            <select
              value={selectedCaseId}
              onChange={(e) => setSelectedCaseId(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-emerald-500"
            >
              {cases.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.id} - {c.title.substring(0, 24)}...
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Evidence Type</label>
            <select
              value={sourceType}
              onChange={(e) => setSourceType(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-emerald-500"
            >
              <option value="RECEIPT_IMAGE">Receipt Image (PNG/JPEG)</option>
              <option value="PDF_STATEMENT">Bank Statement (PDF)</option>
              <option value="VOICE_NOTE">Voice Note (Audio OGG/MP3)</option>
            </select>
          </div>

          <div className="md:col-span-2 flex flex-col justify-end">
            <div className="flex items-center space-x-2">
              <input
                type="file"
                id="file-upload"
                onChange={handleFileChange}
                className="hidden"
                accept={
                  sourceType === 'PDF_STATEMENT'
                    ? 'application/pdf'
                    : sourceType === 'VOICE_NOTE'
                    ? 'audio/*'
                    : 'image/*'
                }
              />
              <label
                htmlFor="file-upload"
                className="flex-1 text-center px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 border border-slate-700 cursor-pointer truncate transition"
              >
                {currentFile ? currentFile.name : 'Choose File...'}
              </label>

              <button
                onClick={handleUpload}
                disabled={!currentFile || isLoading}
                className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-lg shadow-emerald-600/20 disabled:opacity-50 transition"
              >
                {isLoading ? 'Scanning...' : 'Upload & Extract'}
              </button>
            </div>
          </div>
        </div>

        {/* Consent & Privacy Gate */}
        <div className="mt-3 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs">
          <label className="flex items-center space-x-2 cursor-pointer text-slate-300">
            <input
              type="checkbox"
              checked={consentGranted}
              onChange={(e) => setConsentGranted(e.target.checked)}
              className="rounded bg-slate-950 border-slate-700 text-emerald-500 focus:ring-0"
            />
            <span>
              Explicit Consent: Allow external Gemini API fallback with identifier redaction (PRD §13.2)
            </span>
          </label>
          <span className="text-[11px] text-slate-500 flex items-center gap-1">
            <Lock className="w-3 h-3 text-emerald-400" /> Private Spaces Storage
          </span>
        </div>

        {uploadSuccess && (
          <div className="mt-3 p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-400">
            Evidence uploaded successfully and claims extracted.
          </div>
        )}

        {errorMessage && (
          <div className="mt-3 p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/20 text-xs text-rose-400">
            {errorMessage}
          </div>
        )}
      </div>

      {/* Extracted Evidence Details & User Confirmation */}
      {activeAsset && (
        <div className="bg-slate-900/70 border border-slate-800 rounded-2xl p-5 space-y-4">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 pb-3 border-b border-slate-800">
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-mono text-xs font-bold text-emerald-400">{activeAsset.id}</span>
                <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px] font-bold flex items-center gap-1">
                  <ShieldCheck className="w-3 h-3" /> {activeAsset.scan_status}
                </span>
                <span className="text-slate-400 text-xs">{activeAsset.mime_type}</span>
              </div>
              <div className="text-[11px] font-mono text-slate-500 mt-1 flex items-center gap-1">
                <Hash className="w-3 h-3" /> Content Hash: {activeAsset.content_hash}
              </div>
            </div>

            <div className="text-right text-[11px] text-slate-400">
              Retention: 90 days (until {new Date(activeAsset.retention_until).toLocaleDateString()})
            </div>
          </div>

          {/* Extracted Candidate Claims */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-sky-400" />
                <span>Extracted Candidate Claims ({claims.length})</span>
              </h3>
              <p className="text-[11px] text-slate-400">
                Candidate claims do NOT overwrite provider payment truth. Confirm values below.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {claims.map((claim) => (
                <div
                  key={claim.id}
                  className="bg-slate-950/80 border border-slate-800 rounded-xl p-3.5 text-xs space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-sky-400 text-[11px] uppercase">
                      {claim.field_name}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${
                        claim.verification_state === 'USER_CONFIRMED'
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                          : claim.verification_state === 'REJECTED'
                          ? 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                          : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                      }`}
                    >
                      {claim.verification_state}
                    </span>
                  </div>

                  <div className="font-mono text-sm text-white font-semibold break-all bg-slate-900 p-2 rounded border border-slate-800">
                    {claim.candidate_value}
                  </div>

                  {/* Location Provenance */}
                  <div className="text-[11px] text-slate-400 flex items-center justify-between pt-1">
                    <span>Confidence: {(claim.confidence * 100).toFixed(0)}%</span>
                    {claim.source_location && (
                      <span className="font-mono text-[10px] text-slate-500">
                        {claim.source_location.box_2d
                          ? `Box: [${(claim.source_location.box_2d as number[]).join(', ')}]`
                          : claim.source_location.audio_start_sec !== undefined
                          ? `Audio: ${claim.source_location.audio_start_sec}s - ${claim.source_location.audio_end_sec}s`
                          : claim.source_location.page
                          ? `Page ${claim.source_location.page}, Line ${claim.source_location.line || 1}`
                          : ''}
                      </span>
                    )}
                  </div>

                  {/* User Confirmation Buttons */}
                  {claim.verification_state === 'UNVERIFIED' && (
                    <div className="pt-2 flex items-center justify-end space-x-2 border-t border-slate-800/80">
                      <button
                        onClick={() => handleClaimDecision(claim.id, 'REJECTED')}
                        className="px-2.5 py-1 rounded bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/20 text-[11px] font-medium flex items-center space-x-1"
                      >
                        <X className="w-3 h-3" />
                        <span>Reject</span>
                      </button>
                      <button
                        onClick={() => handleClaimDecision(claim.id, 'USER_CONFIRMED')}
                        className="px-3 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] font-semibold flex items-center space-x-1 shadow shadow-emerald-600/30"
                      >
                        <Check className="w-3 h-3" />
                        <span>Confirm Value</span>
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
