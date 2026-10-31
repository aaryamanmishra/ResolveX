import React, { useState, useEffect } from 'react';
import { apiClient } from '../api';
import { Case, EvidenceAsset, EvidenceClaim, VerificationState } from '../types/contracts';
import {
  UploadCloud,
  CheckCircle2,
  AlertTriangle,
  FileText,
  ShieldCheck,
  Check,
  FileCheck2,
  Lock,
  Download,
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
  const [downloadUrl, setDownloadUrl] = useState<string>('');
  const [claims, setClaims] = useState<EvidenceClaim[]>([]);
  const [uploadSuccess, setUploadSuccess] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [editingClaimId, setEditingClaimId] = useState<string | null>(null);
  const [correctedValue, setCorrectedValue] = useState<string>('');

  // Auto-fetch existing evidence assets and claims when selected case changes
  useEffect(() => {
    if (selectedCaseId) {
      apiClient
        .getEvidenceForCase(selectedCaseId)
        .then((evList) => {
          if (evList && evList.length > 0) {
            setActiveAsset(evList[0].asset);
            setDownloadUrl(evList[0].download_url);
            setClaims(evList[0].claims);
          } else {
            setActiveAsset(null);
            setDownloadUrl('');
            setClaims([]);
          }
        })
        .catch(() => {
          setActiveAsset(null);
          setDownloadUrl('');
          setClaims([]);
        });
    }
  }, [selectedCaseId]);

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
      setDownloadUrl(res.download_url);
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
    valueOverride?: string
  ) => {
    if (!activeAsset) return;
    try {
      await onConfirmClaim(activeAsset.id, claimId, decision, valueOverride);
      setClaims((prev) =>
        prev.map((c) =>
          c.id === claimId
            ? {
                ...c,
                verification_state: decision,
                candidate_value: valueOverride || c.candidate_value,
              }
            : c
        )
      );
      setEditingClaimId(null);
      setCorrectedValue('');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMessage(msg);
    }
  };

  const getVerificationBadge = (state: VerificationState) => {
    switch (state) {
      case 'USER_CONFIRMED':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200';
      case 'PROVIDER_MATCHED':
        return 'bg-blue-50 text-blue-700 border-blue-200';
      case 'REJECTED':
        return 'bg-rose-50 text-rose-700 border-rose-200';
      case 'UNVERIFIED':
      default:
        return 'bg-amber-50 text-amber-700 border-amber-200';
    }
  };

  return (
    <div className="space-y-5 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-2 border-b border-slate-200/80">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">Multimodal Evidence</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Secure document intake, optical character extraction, and user field-level verification.
          </p>
        </div>

        {/* Semantic Boundary Banner */}
        <div className="px-3 py-1.5 rounded-md bg-slate-100 text-slate-600 border border-slate-200 text-[11px] flex items-center space-x-1.5 max-w-md">
          <Lock className="w-3.5 h-3.5 text-slate-500 shrink-0" />
          <span>
            <strong>Semantic Boundary:</strong> Uploaded evidence generates unverified claims and cannot overwrite provider truth.
          </span>
        </div>
      </div>

      {/* Main Grid: Upload Console (Left) + Document & Claims Review (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Left Column: Upload Console (5 cols) */}
        <div className="lg:col-span-5 bg-white border border-slate-200 rounded-lg shadow-2xs p-5 space-y-4">
          <div className="border-b border-slate-100 pb-2">
            <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-1.5">
              <UploadCloud className="w-4 h-4 text-blue-600" />
              <span>Intake New Document</span>
            </h2>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Attach receipt image, bank statement PDF, or audio note to an investigation.
            </p>
          </div>

          {/* Case Selector */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Associated Case
            </label>
            <select
              value={selectedCaseId}
              onChange={(e) => setSelectedCaseId(e.target.value)}
              className="w-full bg-slate-50 border border-slate-200 rounded-md px-3 py-2 text-xs text-slate-900 focus:outline-none focus:border-blue-500"
            >
              {cases.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.id} — {c.title.length > 40 ? `${c.title.slice(0, 40)}...` : c.title}
                </option>
              ))}
            </select>
          </div>

          {/* Document Source Type */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Document Format / Type
            </label>
            <select
              value={sourceType}
              onChange={(e) => setSourceType(e.target.value)}
              className="w-full bg-slate-50 border border-slate-200 rounded-md px-3 py-2 text-xs text-slate-900 focus:outline-none focus:border-blue-500"
            >
              <option value="RECEIPT_IMAGE">Payer UPI Receipt / Screenshot (PNG, JPG)</option>
              <option value="BANK_STATEMENT_PDF">Official Bank Statement (PDF)</option>
              <option value="CUSTOMER_VOICE_NOTE">Customer Support Voice Note (WAV, MP3)</option>
            </select>
          </div>

          {/* File Selector Dropzone */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Document File
            </label>
            <div className="border-2 border-dashed border-slate-200 hover:border-slate-300 rounded-lg p-5 text-center bg-slate-50/50 transition-colors">
              <input
                type="file"
                id="evidence-file"
                onChange={handleFileChange}
                accept="image/png,image/jpeg,application/pdf,audio/wav,audio/mpeg"
                className="hidden"
              />
              <label htmlFor="evidence-file" className="cursor-pointer space-y-2 block">
                <FileText className="w-8 h-8 text-slate-400 mx-auto" />
                <div className="text-xs text-slate-700 font-medium">
                  {currentFile ? (
                    <span className="font-semibold text-blue-600">{currentFile.name} ({(currentFile.size / 1024).toFixed(1)} KB)</span>
                  ) : (
                    <span>Click to choose file or drag and drop</span>
                  )}
                </div>
                <div className="text-[10px] text-slate-400">
                  PNG, JPG, PDF, or WAV/MP3 up to 10 MB. Scanned with ClamAV on intake.
                </div>
              </label>
            </div>
          </div>

          {/* Consent Checkbox */}
          <div className="bg-slate-50 border border-slate-200/80 rounded-md p-3 text-xs flex items-start space-x-2">
            <input
              type="checkbox"
              id="consent-check"
              checked={consentGranted}
              onChange={(e) => setConsentGranted(e.target.checked)}
              className="mt-0.5 rounded text-blue-600 focus:ring-0 cursor-pointer"
            />
            <label htmlFor="consent-check" className="text-slate-600 text-[11px] leading-relaxed cursor-pointer">
              <strong>User Consent Granted:</strong> Authorize automated extraction with redacting of PII before multimodal parsing.
            </label>
          </div>

          {errorMessage && (
            <div className="p-2.5 rounded-md bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center space-x-1.5">
              <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {uploadSuccess && (
            <div className="p-2.5 rounded-md bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs flex items-center space-x-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
              <span>Document processed and candidate claims extracted successfully!</span>
            </div>
          )}

          <button
            onClick={handleUpload}
            disabled={!currentFile || isLoading}
            className="w-full py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs rounded-md shadow-xs transition-colors disabled:opacity-50"
          >
            {isLoading ? 'Processing & Extracting...' : 'Upload & Process Document'}
          </button>
        </div>

        {/* Right Column: Document Details & Extracted Claims Verification (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          {activeAsset ? (
            <div className="bg-white border border-slate-200 rounded-lg shadow-2xs overflow-hidden space-y-4 p-5">
              {/* Document Header & Metadata */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-200">
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="font-mono text-xs font-bold text-slate-900">{activeAsset.id}</span>
                    <span className="text-[10px] px-1.5 py-0.2 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded font-semibold flex items-center gap-1">
                      <ShieldCheck className="w-3 h-3" />
                      <span>{activeAsset.scan_status} SCAN</span>
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-500 font-mono mt-0.5">
                    Storage: {activeAsset.storage_key}
                  </div>
                </div>

                {downloadUrl && (
                  <a
                    href={downloadUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-blue-600 hover:text-blue-700 font-semibold flex items-center space-x-1 border border-slate-200 rounded px-2.5 py-1 bg-white hover:bg-slate-50"
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span>Download File</span>
                  </a>
                )}
              </div>

              {/* SHA-256 Hash & Format Card */}
              <div className="bg-slate-50 rounded-md p-3 border border-slate-200/80 text-xs space-y-1">
                <div className="flex items-center justify-between text-slate-600">
                  <span>MIME Type: <strong className="text-slate-800">{activeAsset.mime_type}</strong></span>
                  <span>File Size: <strong className="text-slate-800">{(activeAsset.file_size_bytes / 1024).toFixed(1)} KB</strong></span>
                </div>
                <div className="text-[11px] text-slate-500 truncate font-mono">
                  SHA-256: {activeAsset.content_hash}
                </div>
              </div>

              {/* Extracted Candidate Claims Table */}
              <div className="space-y-3 pt-1">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                      Extracted Candidate Claims ({claims.length})
                    </h3>
                    <p className="text-[11px] text-slate-500">
                      Field-level claims produced by Gemma/Gemini. Verify or correct each field before attaching to case findings.
                    </p>
                  </div>
                </div>

                {claims.length === 0 ? (
                  <div className="p-6 text-center text-xs text-slate-500 bg-slate-50 rounded border border-slate-200">
                    No structured claims extracted from this asset.
                  </div>
                ) : (
                  <div className="divide-y divide-slate-100 border border-slate-200 rounded-lg overflow-hidden">
                    {claims.map((claim) => {
                      const isEditing = editingClaimId === claim.id;

                      return (
                        <div key={claim.id} className="p-3.5 bg-white space-y-2 text-xs">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center space-x-2">
                              <span className="font-mono text-xs font-bold text-slate-800">
                                {claim.field_name}
                              </span>
                              <span className={`text-[10px] px-1.5 py-0.2 rounded-xs font-semibold border ${getVerificationBadge(claim.verification_state)}`}>
                                {claim.verification_state}
                              </span>
                            </div>
                            <span className="text-[11px] text-emerald-700 font-semibold">
                              {(claim.confidence * 100).toFixed(0)}% OCR confidence
                            </span>
                          </div>

                          {/* Candidate Value / Edit Input */}
                          <div className="flex items-center justify-between gap-3 bg-slate-50 p-2.5 rounded border border-slate-200/60">
                            {isEditing ? (
                              <input
                                type="text"
                                value={correctedValue}
                                onChange={(e) => setCorrectedValue(e.target.value)}
                                className="bg-white border border-blue-500 rounded px-2 py-1 text-xs text-slate-900 font-mono w-full"
                              />
                            ) : (
                              <div>
                                <span className="text-slate-500 text-[11px] block">Candidate Value</span>
                                <span className="font-mono font-bold text-slate-900 text-sm">
                                  {claim.field_name === 'amount_minor'
                                    ? `₹${(Number(claim.candidate_value) / 100).toFixed(2)} (${claim.candidate_value} paise)`
                                    : claim.candidate_value}
                                </span>
                              </div>
                            )}

                            {/* Location Box citation */}
                            {claim.source_location && (
                              <div className="text-[10px] font-mono text-slate-400 text-right shrink-0">
                                page {String(claim.source_location.page || '1')}
                                {claim.source_location.box_2d ? ` • box [${String(claim.source_location.box_2d)}]` : ''}
                              </div>
                            )}
                          </div>

                          {/* User Verification Action Buttons */}
                          <div className="flex items-center justify-end space-x-2 pt-1">
                            {isEditing ? (
                              <>
                                <button
                                  onClick={() => setEditingClaimId(null)}
                                  className="px-2.5 py-1 text-[11px] text-slate-500 hover:text-slate-800"
                                >
                                  Cancel
                                </button>
                                <button
                                  onClick={() => handleClaimDecision(claim.id, 'USER_CONFIRMED', correctedValue)}
                                  className="px-3 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-[11px] font-semibold"
                                >
                                  Save & Confirm
                                </button>
                              </>
                            ) : (
                              <>
                                <button
                                  onClick={() => {
                                    setEditingClaimId(claim.id);
                                    setCorrectedValue(claim.candidate_value);
                                  }}
                                  className="px-2.5 py-1 border border-slate-200 hover:bg-slate-50 rounded text-[11px] text-slate-600 font-medium"
                                >
                                  Correct Value
                                </button>
                                <button
                                  onClick={() => handleClaimDecision(claim.id, 'REJECTED')}
                                  className="px-2.5 py-1 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded text-[11px] font-semibold"
                                >
                                  Reject
                                </button>
                                <button
                                  onClick={() => handleClaimDecision(claim.id, 'USER_CONFIRMED')}
                                  className="px-3 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-[11px] font-semibold flex items-center space-x-1"
                                >
                                  <Check className="w-3 h-3" />
                                  <span>Confirm Claim</span>
                                </button>
                              </>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="bg-white border border-slate-200 rounded-lg p-12 text-center text-slate-400 text-xs shadow-2xs space-y-1">
              <FileCheck2 className="w-8 h-8 text-slate-300 mx-auto mb-1" />
              <p className="font-semibold text-slate-700">No document selected</p>
              <p className="text-[11px] text-slate-400">
                Select a case on the left to review its attached evidence, or upload a new file.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
