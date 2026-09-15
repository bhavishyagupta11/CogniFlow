"use client";
import { AlertCircle, AlertTriangle, XCircle } from "lucide-react";

import { normalizeArray } from "../../lib/utils.js";
export { normalizeArray };

export function AnswerabilityBanner({ answerability, className }) {
    if (!answerability) {
        return null;
    }
    const { status, reason, missingInformation, conflictingChunkIds } = answerability;
    const safeMissingInfo = Array.isArray(normalizeArray(missingInformation)) ? normalizeArray(missingInformation) : [];
    const safeConflictingChunks = Array.isArray(normalizeArray(conflictingChunkIds)) ? normalizeArray(conflictingChunkIds) : [];

    switch (status) {
        case "partially_answerable":
            return (<div data-testid="answerability-banner" className={`rounded-[3px] border border-amber-500/40 bg-amber-500/10 p-3 text-xs space-y-1.5 text-[var(--text-secondary)] font-mono ${className ?? ""}`} role="status">
          <div className="flex items-center gap-2 font-bold text-amber-700 dark:text-amber-300 uppercase tracking-wider text-[11px]">
            <AlertTriangle className="h-3.5 w-3.5 text-[var(--accent-amber)] shrink-0"/>
            <span>PARTIALLY ANSWERABLE — INSUFFICIENT EVIDENCE FOR SOME CLAIMS</span>
          </div>
          {reason && (<p className="text-[11px] text-[var(--text-secondary)] leading-relaxed pl-5 font-mono">
              {reason}
            </p>)}
          {safeMissingInfo.length > 0 && (<div className="pl-5 flex flex-wrap gap-1.5 items-center pt-1">
              <span className="text-[10px] font-mono uppercase font-bold text-amber-700 dark:text-amber-400">MISSING TOPICS:</span>
              {safeMissingInfo.map((term, i) => (<span key={i} className="bg-amber-500/15 border border-amber-500/30 text-amber-800 dark:text-amber-300 font-mono text-[10px] px-1.5 py-0.5 rounded-[2px]">
                  {term}
                </span>))}
            </div>)}
        </div>);
        case "not_answerable":
            return (<div data-testid="answerability-banner" className={`rounded-[3px] border border-[var(--panel-border)] bg-[var(--panel-inner)] p-3 text-xs space-y-1.5 text-[var(--text-secondary)] font-mono ${className ?? ""}`} role="alert">
          <div className="flex items-center gap-2 font-bold text-[var(--text-primary)] uppercase tracking-wider text-[11px]">
            <XCircle className="h-3.5 w-3.5 text-[var(--accent-rose)] shrink-0"/>
            <span>NOT ANSWERABLE FROM RETRIEVED CORPUS</span>
          </div>
          <p className="text-[11px] text-[var(--text-muted)] leading-relaxed pl-5 font-mono">
            {reason || "The available documents do not provide sufficient evidence to answer this question. Early factual abstention was triggered to prevent hallucinated claims."}
          </p>
          {safeMissingInfo.length > 0 && !safeMissingInfo.includes(reason) && (
            <div className="pl-5 flex flex-wrap gap-1.5 items-center pt-1">
              <span className="text-[10px] font-mono uppercase font-bold text-[var(--accent-rose)]">UNAVAILABLE TOPICS:</span>
              {safeMissingInfo.map((term, i) => (
                <span key={i} className="bg-rose-500/15 border border-rose-500/30 text-rose-800 dark:text-rose-300 font-mono text-[10px] px-1.5 py-0.5 rounded-[2px]">
                  {term}
                </span>
              ))}
            </div>
          )}
        </div>);
        case "contradictory":
            return (<div data-testid="answerability-banner" className={`rounded-[3px] border border-rose-500/40 bg-rose-500/10 p-3 text-xs space-y-1.5 text-[var(--text-secondary)] font-mono ${className ?? ""}`} role="alert">
          <div className="flex items-center gap-2 font-bold text-rose-700 dark:text-rose-300 uppercase tracking-wider text-[11px]">
            <AlertCircle className="h-3.5 w-3.5 text-[var(--accent-rose)] shrink-0"/>
            <span>CONFLICTING EVIDENCE DETECTED ACROSS SOURCES</span>
          </div>
          <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed pl-5 font-mono">
            Heuristic contradiction detection found potentially conflicting evidence across retrieved passages: {reason}
          </p>
          {safeConflictingChunks.length > 0 && (<div className="pl-5 flex flex-wrap gap-1.5 items-center pt-1">
              <span className="text-[10px] font-mono uppercase font-bold text-rose-700 dark:text-rose-400">CONFLICTING CHUNKS:</span>
              {safeConflictingChunks.map((cid, i) => (<span key={i} className="font-mono text-[10px] px-1.5 py-0.5 rounded-[2px] bg-rose-500/15 text-rose-800 dark:text-rose-300 border border-rose-500/30">
                  {cid}
                </span>))}
            </div>)}
        </div>);
        case "fully_answerable":
        default:
            return null;
    }
}
