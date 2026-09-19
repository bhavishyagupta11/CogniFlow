"use client";
import { Card, CardContent } from "@/components/ui/card";
import { FileText, Quote, ChevronRight, ChevronDown, ExternalLink, ShieldAlert, Layers } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
export function SourcesPanel({ sources, onOpenPdf, }) {
    const [expanded, setExpanded] = useState(null);
    if (!sources || sources.length === 0)
        return null;
    return (<div className="mt-3 space-y-2 min-w-0 w-full" data-testid="sources-panel-container">
      {/* Panel Header */}
      <div className="flex items-center justify-between gap-2 flex-wrap min-w-0">
        <div className="flex items-center gap-2 text-[11px] font-mono font-bold uppercase tracking-wider text-[var(--text-muted)] min-w-0">
          <Quote className="h-3.5 w-3.5 text-[var(--accent-amber)] shrink-0"/>
          <span className="truncate">Retrieved Evidence ({sources.length} sources)</span>
        </div>

        {/* Safeguards status */}
        <span className="text-[10px] font-mono text-[var(--text-muted)] shrink-0">
          Heuristic safeguards applied
        </span>
      </div>

      {/* Sources Grid */}
      <div className="grid gap-2 grid-cols-1 md:grid-cols-2 min-w-0 w-full">
        {sources.map((s, i) => {
            const isOpen = expanded === s.chunkId;
            const hasParent = Boolean(s.parentChunkId && s.parentContent);
            const sectionTitle = s.heading || s.section || s.chapter;
            return (<Card key={s.chunkId || i} data-testid={`source-card-${i + 1}`} className={`overflow-hidden min-w-0 w-full border-l-2 rounded-[4px] border border-[var(--panel-border)] bg-[var(--panel-bg)] transition-all cursor-pointer select-none focus:outline-hidden focus-visible:border-[var(--border-focus)] focus-visible:ring-2 focus-visible:ring-[var(--accent-amber-glow)] ${isOpen
                    ? "border-l-[#f97316] shadow-[0_0_12px_rgba(249,115,22,0.12)]"
                    : "border-l-[#f97316]/60 hover:border-l-[#f97316] hover:border-[var(--panel-border)]"}`} onClick={() => setExpanded(isOpen ? null : s.chunkId)} onKeyDown={(e) => {
                    if (e.target !== e.currentTarget)
                        return;
                    if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setExpanded(isOpen ? null : s.chunkId);
                    }
                }} tabIndex={0} role="button" aria-expanded={isOpen} aria-label={`Source citation ${i + 1}: ${s.documentTitle}`}>
              <CardContent className="p-3 space-y-2 min-w-0 overflow-hidden">
                {/* Header Row */}
                <div className="flex items-start justify-between gap-2 min-w-0">
                  <div className="flex items-center gap-2 min-w-0 flex-1">
                    <span className="font-mono text-[10px] font-bold text-[#f97316] shrink-0">
                      [{s.badge || `SRC-0${i + 1}`}]
                    </span>
                    <FileText className="h-3.5 w-3.5 text-[var(--text-muted)] shrink-0"/>
                    <span className="text-xs font-semibold truncate text-[var(--text-primary)] min-w-0" title={s.documentTitle}>
                      {s.documentTitle}
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5 shrink-0 flex-wrap justify-end">
                    <span className="text-[10px] font-mono text-emerald-600 font-semibold uppercase shrink-0">
                      Verified
                    </span>
                    {typeof s.llmScore === "number" && !isNaN(s.llmScore) && (<span className="font-mono text-[10px] text-[var(--text-muted)] shrink-0">
                        LLM {s.llmScore.toFixed(1)}/10
                      </span>)}
                    {isOpen ? (<ChevronDown className="h-3.5 w-3.5 text-[var(--text-muted)] shrink-0"/>) : (<ChevronRight className="h-3.5 w-3.5 text-[var(--text-muted)] shrink-0"/>)}
                  </div>
                </div>

                {/* Metadata Row */}
                <div className="text-[10px] text-[var(--text-muted)] flex flex-wrap gap-x-2 gap-y-0.5 items-center font-mono min-w-0">
                  {sectionTitle && (<span className="text-[var(--text-secondary)] truncate max-w-[160px] sm:max-w-[200px] min-w-0">
                      {sectionTitle}
                    </span>)}
                  {s.pageRange ? (
                    <span className="shrink-0">· Pages {s.pageRange}</span>
                  ) : (s.page_start || (s.pageNumber && (s.format === "pdf" || (s.documentTitle || s.originalFilename || "").toLowerCase().endsWith(".pdf")))) ? (
                    <span className="shrink-0">· P.{s.page_start || s.pageNumber}</span>
                  ) : s.source_location && !s.source_location.startsWith("p.") ? (
                    <span className="shrink-0">· {s.source_location}</span>
                  ) : null}
                  {s.batchId && <span className="shrink-0">· {s.batchId}</span>}
                  {hasParent && <span className="text-emerald-600 shrink-0">· Parent</span>}
                </div>

                {/* Claims Supported Excerpt if open */}
                {isOpen && Array.isArray(s.claimsSupported) && s.claimsSupported.length > 0 && (
                  <div className="p-2 border border-[var(--panel-border)] bg-[var(--panel-inner)] rounded-[2px] space-y-1 min-w-0 overflow-hidden">
                    <span className="text-[9px] font-mono font-bold uppercase tracking-wider text-[var(--accent-emerald)] block shrink-0">
                      Claims Supported:
                    </span>
                    <ul className="list-disc list-inside space-y-0.5 text-[10px] text-[var(--text-secondary)] pl-1 min-w-0">
                      {s.claimsSupported.map((c, ci) => (
                        <li key={ci} className="leading-tight truncate min-w-0" title={c}>{c}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Primary Retrieved Content */}
                <div className={`text-[11px] text-[var(--text-secondary)] leading-relaxed prose prose-sm prose-invert prose-p:my-0 prose-p:leading-relaxed prose-headings:my-1 max-w-none break-words overflow-hidden min-w-0 ${isOpen ? "" : "line-clamp-3"}`}>
                  <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                    {s.quoteOrEvidence || s.chunkContent}
                  </ReactMarkdown>
                </div>

                {/* Parent Context Expansion Excerpt (if attached) */}
                {isOpen && hasParent && s.parentContent && (<div className="mt-2 pt-2 border-t border-dashed border-[var(--panel-border)] space-y-1 bg-[var(--panel-inner)] p-2 rounded-[2px] min-w-0 overflow-hidden">
                    <div className="flex items-center gap-1 text-[10px] font-mono font-semibold uppercase text-emerald-400 min-w-0">
                      <Layers className="h-3 w-3 text-emerald-400 shrink-0"/>
                      <span className="truncate min-w-0">Parent Context ({s.heading || s.section || "Surrounding Section"})</span>
                    </div>
                    <p className="text-[10px] text-[var(--text-muted)] italic leading-relaxed whitespace-pre-wrap font-sans break-words min-w-0">
                      {s.parentContent}
                    </p>
                  </div>)}

                {/* Footer Controls */}
                <div className="flex items-center justify-between text-[10px] font-mono text-[var(--text-muted)] pt-1.5 border-t border-[var(--panel-border)] flex-wrap gap-1 min-w-0">
                  <span className="truncate min-w-0">
                    {isOpen ? "COLLAPSE" : "EXPAND"} · CHUNK #{s.chunkIndex}
                  </span>
                  {s.documentId?.startsWith?.("doc-") ? (
                    <span className="text-[9px] text-[var(--text-muted)] uppercase shrink-0">BUNDLED PAPER</span>
                  ) : onOpenPdf && isOpen ? (
                    <Button variant="ghost" size="sm" data-testid={`open-pdf-source-${i + 1}`} className="h-5 px-1.5 text-[10px] font-mono text-[var(--accent-amber)] hover:text-[var(--accent-amber-hover)] shrink-0" onClick={(e) => {
                        e.stopPropagation();
                        onOpenPdf(s);
                    }}>
                      OPEN PDF <ExternalLink className="h-2.5 w-2.5 ml-1"/>
                    </Button>
                  ) : null}
                </div>
              </CardContent>
            </Card>);
        })}
      </div>
    </div>);
}
