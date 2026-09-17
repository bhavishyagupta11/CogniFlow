"use client";
import { useState } from "react";
import { QueryArchetypeBadge } from "./query-archetype-badge";
import { Collapsible, CollapsibleContent, CollapsibleTrigger, } from "@/components/ui/collapsible";
import { Compass, ChevronDown, ChevronRight, GitFork, Code2, } from "lucide-react";
export function RetrievalPlanVisualizer({ plan, trace, subqueries, sources, originalQuery, rewrittenQuery: propRewrittenQuery, candidateCount: propCandidateCount, className, }) {
    const [open, setOpen] = useState(false);
    const [techDetailsOpen, setTechDetailsOpen] = useState(false);
    // If neither plan nor trace exists, nothing to visualize
    if (!plan && !trace) {
        return null;
    }
    const queryType = trace?.queryType || plan?.queryType || "unknown";
    const rewrittenQuery = propRewrittenQuery || trace?.rewrittenQuery;
    const initialTopK = trace?.initialTopK ?? plan?.initialTopK ?? 5;
    const finalTopK = trace?.finalTopK ?? initialTopK;
    const candidateCount = propCandidateCount ?? trace?.candidateCount;
    const acceptedChunkCount = trace?.acceptedChunkCount ?? sources?.length;
    const expansionRounds = trace?.expansionRounds ?? 0;
    // Transformation calculations
    const earlyStopped = expansionRounds < 2 &&
        trace?.retrievalConfidence?.sufficient &&
        (trace?.retrievalConfidence?.topScore ?? 0) >= 0.30;
    const filteredCount = typeof candidateCount === "number" && typeof acceptedChunkCount === "number"
        ? Math.max(0, candidateCount - acceptedChunkCount)
        : undefined;
    const parentExpandedCount = sources?.filter((s) => Boolean(s.parentChunkId && s.parentContent)).length ?? 0;
    const effectiveSubqueries = subqueries && subqueries.length > 0
        ? subqueries
        : trace?.subqueries?.map((q, i) => ({ id: `sub-${i + 1}`, query: q, purpose: "Decomposed lookup" }));
    return (<Collapsible open={open} onOpenChange={setOpen} className={`rounded-[4px] border border-[var(--panel-border)] bg-[var(--panel-bg)] text-xs shadow-none transition-colors ${className ?? ""}`}>
      <CollapsibleTrigger asChild>
        <button type="button" data-testid="retrieval-plan-toggle" className="flex w-full items-center justify-between p-2.5 hover:bg-[var(--panel-inner)] transition-colors text-left rounded-[4px] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[var(--accent-amber-glow)] cursor-pointer" aria-expanded={open}>
          <div className="flex items-center gap-2 flex-wrap min-w-0">
            <Compass className="h-4 w-4 text-[var(--accent-amber)] shrink-0"/>
            <span className="font-mono text-[11px] font-bold uppercase tracking-wider text-[var(--text-primary)]">
              Retrieval Strategy & Execution Plan
            </span>
            <QueryArchetypeBadge archetype={queryType}/>
          </div>

          <div className="flex items-center gap-2 text-[var(--text-muted)] shrink-0 font-mono">
            <span className="text-[10px] text-[var(--accent-amber)] font-bold">
              {queryType === "document_summary" ? "FULL DOCUMENT (ALL PAGES)" : `TOP-K: ${initialTopK}${finalTopK !== initialTopK ? ` → ${finalTopK}` : ""}`}
            </span>
            {open ? <ChevronDown className="h-4 w-4"/> : <ChevronRight className="h-4 w-4"/>}
          </div>
        </button>
      </CollapsibleTrigger>

      <CollapsibleContent>
        <div className="border-t border-[var(--panel-border)] px-3 py-3 space-y-3 bg-[var(--panel-inner)]">
          {/* Main Grid of Retrieval Controls */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {/* 1. Query Type & Strategy */}
            <div className="rounded-[2px] border border-[var(--panel-border)] bg-[var(--panel-bg)] p-2 space-y-1">
              <span className="text-[9px] font-mono font-semibold uppercase text-[var(--text-muted)] tracking-wider block">
                Query Type
              </span>
              <div className="flex items-center justify-between font-mono text-xs">
                <span className="text-[var(--text-primary)] uppercase">{queryType.replace("_", " ")}</span>
                <span className="text-[10px] text-[var(--text-muted)]">
                  {queryType === "document_summary" ? "Hierarchical" : "Heuristic"}
                </span>
              </div>
            </div>

            {/* 2. Retrieval Strategy */}
            <div className="rounded-[2px] border border-[var(--panel-border)] bg-[var(--panel-bg)] p-2 space-y-1">
              <span className="text-[9px] font-mono font-semibold uppercase text-[var(--text-muted)] tracking-wider block">
                Retrieval Strategy
              </span>
              <span className="font-mono text-xs text-[var(--accent-amber)] font-bold">
                {queryType === "document_summary" ? "Hierarchical Map-Reduce (All Pages)" : "Lexical TF-IDF Sparse Index"}
              </span>
            </div>

            {/* 3. Dynamic Top-K */}
            <div className="rounded-[2px] border border-[var(--panel-border)] bg-[var(--panel-bg)] p-2 space-y-1">
              <span className="text-[9px] font-mono font-semibold uppercase text-[var(--text-muted)] tracking-wider block">
                Dynamic Top-K
              </span>
              <span className="font-mono text-xs text-[var(--text-primary)]">
                {queryType === "document_summary"
                  ? "All 128 Pages (290 Chunks Contiguous)"
                  : `${initialTopK} initial ${finalTopK !== initialTopK ? `(expanded to ${finalTopK})` : "(unexpanded)"}`}
              </span>
            </div>

            {/* 4. Candidate Pool & Relevance Filtering */}
            <div className="rounded-[2px] border border-[var(--panel-border)] bg-[var(--panel-bg)] p-2 space-y-1">
              <span className="text-[9px] font-mono font-semibold uppercase text-[var(--text-muted)] tracking-wider block">
                Candidate Pool & Filtering
              </span>
              <span className="font-mono text-xs text-[var(--text-primary)]">
                {candidateCount !== undefined ? `${candidateCount} candidates` : "Active"}
                {filteredCount !== undefined && filteredCount > 0 ? ` · ${filteredCount} pruned below floor` : ""}
              </span>
            </div>

            {/* 5. Expansion Rounds & Early Stopping */}
            <div className="rounded-[2px] border border-[var(--panel-border)] bg-[var(--panel-bg)] p-2 space-y-1">
              <span className="text-[9px] font-mono font-semibold uppercase text-[var(--text-muted)] tracking-wider block">
                Expansion & Early Stopping
              </span>
              <span className="font-mono text-xs text-[var(--text-primary)] flex items-center gap-1">
                {expansionRounds === 0 ? "0 expansion rounds" : `${expansionRounds} rounds`}
                {earlyStopped && (<span className="text-[10px] text-emerald-600 font-semibold uppercase">
                    · Early Stopped
                  </span>)}
              </span>
            </div>

            {/* 6. Parent Context Expansion */}
            <div className="rounded-[2px] border border-[var(--panel-border)] bg-[var(--panel-bg)] p-2 space-y-1">
              <span className="text-[9px] font-mono font-semibold uppercase text-[var(--text-muted)] tracking-wider block">
                Parent Context Expansion
              </span>
              <span className="font-mono text-xs text-[var(--text-primary)]">
                {parentExpandedCount > 0
            ? `${parentExpandedCount} chunks expanded (<120 tokens)`
            : "Self-contained (no expansion needed)"}
              </span>
            </div>
          </div>

          {/* Rewritten Query Section */}
          {rewrittenQuery && rewrittenQuery !== originalQuery && (<div className="rounded-[2px] border border-[var(--panel-border)] bg-[var(--panel-bg)] p-2 space-y-1">
              <span className="text-[9px] font-mono font-semibold uppercase text-[var(--text-muted)] tracking-wider block">
                Rewritten Search Query (Keyword Optimization)
              </span>
              <p className="font-mono text-[11px] text-[var(--accent-amber)] bg-[var(--panel-inner)] p-1.5 rounded-[2px] border border-[var(--panel-border)]">
                {rewrittenQuery}
              </p>
            </div>)}

          {/* Decomposed Subqueries Section */}
          {effectiveSubqueries && effectiveSubqueries.length > 0 && (<div className="rounded-[2px] border border-[var(--panel-border)] bg-[var(--panel-bg)] p-2 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-[9px] font-mono font-semibold uppercase text-[var(--text-muted)] tracking-wider">
                  Decomposed Subqueries ({effectiveSubqueries.length})
                </span>
                <span className="text-[10px] font-mono text-[var(--text-muted)]">Multi-hop coverage</span>
              </div>
              <div className="space-y-1">
                {effectiveSubqueries.map((sub, idx) => (<div key={sub.id || idx} className="flex items-start gap-2 bg-[var(--panel-inner)] p-1.5 rounded-[2px] border border-[var(--panel-border)] text-[11px]">
                    <GitFork className="h-3.5 w-3.5 text-[var(--accent-amber)] mt-0.5 shrink-0"/>
                    <div className="min-w-0 flex-1 font-mono">
                      <span className="font-medium text-[var(--text-primary)]">{sub.query}</span>
                      {sub.purpose && (<span className="text-[10px] text-[var(--text-muted)] block">
                          Purpose: {sub.purpose}
                        </span>)}
                    </div>
                  </div>))}
              </div>
            </div>)}

          {/* Collapsible Technical Details */}
          <div className="pt-1">
            <button type="button" data-testid="tech-diagnostics-toggle" onClick={() => setTechDetailsOpen((prev) => !prev)} className="text-[10px] font-mono uppercase tracking-wider text-[var(--text-muted)] hover:text-[var(--text-primary)] flex items-center gap-1 font-medium transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[var(--accent-amber-glow)] rounded-[2px] px-1 cursor-pointer" aria-expanded={techDetailsOpen}>
              <Code2 className="h-3 w-3 text-[var(--accent-amber)]"/>
              <span>Technical Diagnostics</span>
              {techDetailsOpen ? <ChevronDown className="h-3 w-3"/> : <ChevronRight className="h-3 w-3"/>}
            </button>

            {techDetailsOpen && (<div className="mt-2 p-2 rounded-[2px] border border-[var(--panel-border)] bg-[var(--bg-page)] font-mono text-[10px] space-y-1 text-[var(--text-secondary)] animate-in fade-in-50 duration-100">
                {trace?.traceId && (<div>
                    <span className="text-[var(--text-muted)]">Trace ID: </span>
                    <span className="text-[var(--text-primary)]">{trace.traceId}</span>
                  </div>)}
                {trace?.latencyMs && (<div>
                    <span className="text-[var(--text-muted)]">Latency: </span>
                    <span>
                      Planning: {trace.latencyMs.planning ?? 0}ms · Retrieval: {trace.latencyMs.retrieval ?? 0}ms · Reranking: {trace.latencyMs.reranking ?? 0}ms · Total: {trace.latencyMs.total ?? 0}ms
                    </span>
                  </div>)}
                <div>
                  <span className="text-[var(--text-muted)]">Parameters: </span>
                  <span>
                    relevanceFloor=0.08, earlyStoppingTopScore=0.30, earlyStoppingCoverage=0.45, maxParentTokens=250
                  </span>
                </div>
              </div>)}
          </div>
        </div>
      </CollapsibleContent>
    </Collapsible>);
}
