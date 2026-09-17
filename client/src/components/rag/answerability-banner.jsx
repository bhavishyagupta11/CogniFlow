"use client";

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
            return (
                <div data-testid="answerability-banner" className={`rounded-[3px] border border-amber-500/40 bg-amber-500/10 p-3 text-xs space-y-1.5 text-[var(--text-secondary)] font-mono ${className ?? ""}`} role="status">
                    <div className="font-bold text-amber-700 dark:text-amber-400 uppercase tracking-wider text-[11px]">
                        PARTIALLY ANSWERABLE — INSUFFICIENT EVIDENCE FOR SOME CLAIMS
                    </div>
                    {reason && (
                        <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed font-mono">
                            {reason}
                        </p>
                    )}
                    {safeMissingInfo.length > 0 && (
                        <div className="text-[11px] font-mono text-[var(--text-muted)] pt-0.5">
                            Missing: {safeMissingInfo.map(t => typeof t === 'object' ? JSON.stringify(t) : String(t)).join(" · ")}
                        </div>
                    )}
                </div>
            );
        case "not_answerable":
            return (
                <div data-testid="answerability-banner" className={`rounded-[3px] border border-[var(--panel-border)] bg-[var(--panel-inner)] p-3 text-xs space-y-1.5 text-[var(--text-secondary)] font-mono ${className ?? ""}`} role="alert">
                    <div className="font-bold text-[var(--text-primary)] uppercase tracking-wider text-[11px]">
                        NOT ANSWERABLE FROM RETRIEVED CORPUS
                    </div>
                    <p className="text-[11px] text-[var(--text-muted)] leading-relaxed font-mono">
                        {reason || "The available documents do not provide sufficient evidence to answer this question. Early factual abstention was triggered to prevent hallucinated claims."}
                    </p>
                    {safeMissingInfo.length > 0 && !safeMissingInfo.includes(reason) && (
                        <div className="text-[11px] font-mono text-[var(--text-muted)] pt-0.5">
                            Missing: {safeMissingInfo.map(t => typeof t === 'object' ? JSON.stringify(t) : String(t)).join(" · ")}
                        </div>
                    )}
                </div>
            );
        case "contradictory":
            return (
                <div data-testid="answerability-banner" className={`rounded-[3px] border border-rose-500/40 bg-rose-500/10 p-3 text-xs space-y-1.5 text-[var(--text-secondary)] font-mono ${className ?? ""}`} role="alert">
                    <div className="font-bold text-rose-700 dark:text-rose-400 uppercase tracking-wider text-[11px]">
                        CONFLICTING EVIDENCE DETECTED ACROSS SOURCES
                    </div>
                    <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed font-mono">
                        Heuristic contradiction detection found potentially conflicting evidence across retrieved passages: {reason}
                    </p>
                    {safeConflictingChunks.length > 0 && (
                        <div className="text-[11px] font-mono text-[var(--text-muted)] pt-0.5">
                            Conflicting: {safeConflictingChunks.map(c => typeof c === 'object' ? JSON.stringify(c) : String(c)).join(" · ")}
                        </div>
                    )}
                </div>
            );
        case "fully_answerable":
        default:
            return null;
    }
}
