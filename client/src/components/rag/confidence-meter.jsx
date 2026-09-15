"use client";
import { useState } from "react";
import { classifyConfidence } from "@/lib/types";
import { ShieldCheck, HelpCircle, ChevronDown, ChevronRight, Activity } from "lucide-react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger, } from "@/components/ui/tooltip";
export function ConfidenceMeter({ confidence, className }) {
    const [showBreakdown, setShowBreakdown] = useState(false);
    if (!confidence) {
        return null;
    }
    // Composite score is the primary metric
    const scoreValue = confidence.compositeScore ?? confidence.score;
    const display = classifyConfidence(scoreValue);
    return (<div data-testid="confidence-meter" className={`rounded-[4px] border border-[var(--panel-border)] bg-[var(--panel-bg)] p-3 text-xs space-y-2 shadow-none ${className ?? ""}`}>
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-1.5">
          <ShieldCheck className={`h-4 w-4 ${display.colorClass}`}/>
          <span className="font-mono text-[11px] font-bold uppercase tracking-wider text-[var(--text-primary)]">
            Retrieval Evidence Match
          </span>
          <TooltipProvider delayDuration={150}>
            <Tooltip>
              <TooltipTrigger asChild>
                <button type="button" className="text-[var(--text-muted)] hover:text-[var(--text-primary)] cursor-help p-0.5 rounded-[2px] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[var(--accent-amber-glow)]" aria-label="Evidence match score explanation">
                  <HelpCircle className="h-3.5 w-3.5"/>
                </button>
              </TooltipTrigger>
              <TooltipContent side="top" className="max-w-xs text-xs p-2.5 space-y-1 rounded-[4px] bg-[var(--panel-inner)] border border-[var(--panel-border)] text-[var(--text-primary)]">
                <p className="font-semibold font-mono text-[10px] uppercase">Evidence Retrieval Alignment</p>
                <p className="text-[var(--text-secondary)] text-[11px] leading-relaxed">
                  {display.disclaimer || "This metric measures lexical and semantic alignment between your query and retrieved document passages. It is not a model truthfulness or accuracy rating."}
                </p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>

        <div className="flex items-center gap-2">
          <span className={`font-mono text-[10px] font-bold uppercase px-2 py-0.5 rounded-[2px] border ${display.bgClass} ${display.colorClass} ${display.borderClass}`}>
            {display.tier} Match ({display.percentage}%)
          </span>

          <button type="button" data-testid="confidence-components-toggle" onClick={() => setShowBreakdown((prev) => !prev)} className="text-[10px] font-mono uppercase tracking-wider text-[var(--text-muted)] hover:text-[var(--text-primary)] flex items-center gap-0.5 px-1.5 py-0.5 rounded-[2px] hover:bg-[var(--panel-inner)] transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[var(--accent-amber-glow)] cursor-pointer" aria-expanded={showBreakdown}>
            <span>Telemetry</span>
            {showBreakdown ? (<ChevronDown className="h-3 w-3"/>) : (<ChevronRight className="h-3 w-3"/>)}
          </button>
        </div>
      </div>

      {/* Expandable Component Breakdown */}
      {showBreakdown && (<div className="pt-2 border-t border-[var(--panel-border)] mt-1.5 space-y-2 animate-in fade-in-50 duration-150">
          <div className="text-[10px] font-mono uppercase font-semibold text-[var(--text-muted)] flex items-center gap-1">
            <Activity className="h-3 w-3 text-[var(--accent-amber)]"/>
            <span>Score Components (Score-Space Calibrated)</span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
            <div className="rounded-[2px] border border-[var(--panel-border)] bg-[var(--panel-inner)] p-1.5">
              <span className="text-[9px] font-mono uppercase text-[var(--text-muted)] block">Top Similarity</span>
              <span className="font-mono font-medium text-[var(--accent-amber)]">
                {typeof confidence.topScore === "number" ? confidence.topScore.toFixed(3) : "N/A"}
              </span>
            </div>

            <div className="rounded-[2px] border border-[var(--panel-border)] bg-[var(--panel-inner)] p-1.5">
              <span className="text-[9px] font-mono uppercase text-[var(--text-muted)] block">Query Coverage</span>
              <span className="font-mono font-medium text-emerald-400">
                {typeof confidence.evidenceCoverage === "number"
                ? `${Math.round(confidence.evidenceCoverage * 100)}%`
                : "N/A"}
              </span>
            </div>

            <div className="rounded-[2px] border border-[var(--panel-border)] bg-[var(--panel-inner)] p-1.5">
              <span className="text-[9px] font-mono uppercase text-[var(--text-muted)] block">Source Diversity</span>
              <span className="font-mono font-medium text-[var(--text-primary)]">
                {typeof confidence.sourceDiversity === "number"
                ? `${Math.round(confidence.sourceDiversity * 100)}%`
                : "N/A"}
              </span>
            </div>

            <div className="rounded-[2px] border border-[var(--panel-border)] bg-[var(--panel-inner)] p-1.5">
              <span className="text-[9px] font-mono uppercase text-[var(--text-muted)] block">Score Gap</span>
              <span className="font-mono font-medium text-[var(--text-primary)]">
                {typeof confidence.scoreGap === "number" ? confidence.scoreGap.toFixed(3) : "N/A"}
              </span>
            </div>
          </div>

          {confidence.reason && (<p className="text-[10px] font-mono text-[var(--text-muted)] leading-tight">
              Note: {confidence.reason}
            </p>)}
        </div>)}
    </div>);
}
