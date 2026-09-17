"use client";
import { getArchetypeMeta } from "@/lib/types";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger, } from "@/components/ui/tooltip";
export function QueryArchetypeBadge({ archetype, className }) {
    const meta = getArchetypeMeta(archetype);
    return (<TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className={`inline-flex items-center gap-1.5 cursor-help ${className ?? ""}`}>
            <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-[var(--accent-amber)]">
              {meta.label}
            </span>
            <span className="text-[10px] font-mono text-[var(--text-muted)] hidden sm:inline">
              (CLASSIFIED)
            </span>
          </div>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-xs text-xs p-2 rounded-[4px] bg-[var(--panel-inner)] border border-[var(--panel-border)] text-[var(--text-primary)]">
          <p className="font-semibold font-mono text-[10px] uppercase text-[var(--accent-amber)]">{meta.label} Query</p>
          <p className="text-[var(--text-secondary)] text-[11px] mt-0.5 leading-relaxed">{meta.description}</p>
          <p className="text-[10px] font-mono text-[var(--text-muted)] mt-1 border-t border-[var(--panel-border)] pt-1">
            Classified via deterministic keyword heuristics and intent matching.
          </p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>);
}
