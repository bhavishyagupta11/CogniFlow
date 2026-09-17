"use client";
import { ShieldAlert } from "lucide-react";
export function SecurityDisclaimer({ compact = false, className }) {
    if (compact) {
        return (<div className={`flex items-center gap-1.5 font-mono text-[10px] text-[var(--text-muted)] ${className ?? ""}`}>
        <ShieldAlert className="h-3 w-3 text-[var(--accent-amber)] shrink-0"/>
        <span>UNTRUSTED EVIDENCE · HEURISTIC SAFEGUARDS APPLIED</span>
      </div>);
    }
    return (<div className={`rounded-[4px] border border-[var(--panel-border)] bg-[var(--panel-inner)] p-2.5 text-[11px] text-[var(--text-secondary)] space-y-1.5 ${className ?? ""}`}>
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-1.5 font-mono text-xs uppercase font-bold text-[var(--accent-amber)]">
          <ShieldAlert className="h-3.5 w-3.5 text-[var(--accent-amber)]"/>
          <span>Evidence Security & System Boundaries</span>
        </div>
        <div className="flex flex-wrap gap-1 font-mono">
          <span className="text-[9px] uppercase px-1.5 py-0.2 rounded-[2px] bg-[var(--panel-bg)] border border-[var(--panel-border)] text-[var(--text-muted)]">
            TF-IDF Retrieval
          </span>
          <span className="text-[9px] uppercase px-1.5 py-0.2 rounded-[2px] bg-[var(--panel-bg)] border border-[var(--panel-border)] text-[var(--text-muted)]">
            Heuristic Safeguards
          </span>
          <span className="text-[9px] uppercase px-1.5 py-0.2 rounded-[2px] bg-[var(--panel-bg)] border border-[var(--panel-border)] text-[var(--text-muted)]">
            Local Evaluation
          </span>
        </div>
      </div>
      <p className="text-[10px] text-[var(--text-muted)] leading-relaxed font-sans">
        Retrieved content is untrusted evidence and may contain inaccurate or adversarial instructions. CogniFlow employs CDATA isolation and directive neutralization, but does not provide formal proof against all adversarial jailbreaks.
      </p>
    </div>);
}
