import React from "react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { FileText, ExternalLink, Layers, ShieldCheck, CheckCircle2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export function CitationCard({ source, index, onOpenPdf }) {
    const sectionTitle = source.heading || source.section || source.chapter;
    const hasParent = Boolean(source.parentChunkId && source.parentContent);
    const badgeLabel = source.badge || index;
    const pageDisplay = source.pageRange ? `Pages ${source.pageRange}` : source.pageNumber ? `Page ${source.pageNumber}` : null;
    const evidenceText = source.quoteOrEvidence || source.chunkContent || "";

    return (
      <Popover>
        <PopoverTrigger asChild>
          <button
            type="button"
            data-testid={`citation-pill-${badgeLabel}`}
            className="inline-flex items-center justify-center rounded-[2px] bg-[var(--panel-inner)] hover:bg-[var(--panel-bg)] text-[var(--accent-amber)] font-mono text-[10px] font-bold px-1.5 py-0.5 transition-colors cursor-pointer align-baseline mx-0.5 border border-[var(--panel-border)] hover:border-[var(--accent-amber)] hover:shadow-[0_0_8px_rgba(245,158,11,0.25)] focus-visible:ring-2 focus-visible:ring-[var(--accent-amber-glow)] outline-hidden"
            aria-label={`View citation [${badgeLabel}]: ${source.documentTitle}`}
          >
            <FileText className="h-2.5 w-2.5 mr-0.5 text-[var(--accent-amber)]" />
            <span>[{badgeLabel}]</span>
          </button>
        </PopoverTrigger>
        <PopoverContent
          data-testid="citation-popover"
          className="w-[min(23rem,calc(100vw-2rem))] max-w-[calc(100vw-2rem)] p-0 shadow-[var(--shadow-matrix)] border border-[var(--panel-border)] rounded-[4px] bg-[var(--panel-bg)]"
          align="start"
        >
          <div className="flex flex-col text-xs">
            {/* Header */}
            <div className="border-b border-[var(--panel-border)] bg-[var(--panel-inner)] p-3 space-y-1.5">
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <span className="font-mono text-[10px] font-bold text-[var(--accent-amber)] bg-[var(--accent-amber-glow)] px-1.5 py-0.5 rounded-[2px] border border-[var(--accent-amber)]/40">
                  SOURCE [{badgeLabel}]
                </span>
                <Badge
                  variant="outline"
                  className="text-[9px] px-1.5 py-0 bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 flex items-center gap-1 font-mono"
                >
                  <ShieldCheck className="h-3 w-3" />
                  <span>VERIFIED GROUNDED</span>
                </Badge>
              </div>

              <h4 className="text-xs font-semibold text-[var(--text-primary)] truncate" title={source.documentTitle}>
                {source.documentTitle}
              </h4>

              <div className="flex items-center gap-2 text-[10px] text-[var(--text-muted)] flex-wrap font-mono">
                {sectionTitle && (
                  <span className="font-medium text-[var(--text-secondary)] truncate max-w-[190px]">
                    {sectionTitle}
                  </span>
                )}
                {pageDisplay && <span className="text-[var(--accent-cyan)]">· {pageDisplay}</span>}
              </div>

              {(source.chunkId || source.batchId) && (
                <div className="flex items-center gap-2 text-[9px] text-[var(--text-muted)] font-mono">
                  {source.chunkId && <span>Chunk: {source.chunkId.split("#").pop()}</span>}
                  {source.batchId && <span>· Batch: {source.batchId}</span>}
                </div>
              )}
            </div>

            {/* Claims Supported (Section 15.5) */}
            {Array.isArray(source.claimsSupported) && source.claimsSupported.length > 0 && (
              <div className="p-2.5 border-b border-[var(--panel-border)] bg-[var(--panel-inner)]/50 space-y-1">
                <span className="text-[9px] font-mono font-bold uppercase tracking-wider text-[var(--accent-emerald)] flex items-center gap-1">
                  <CheckCircle2 className="h-3 w-3" />
                  <span>Claims Supported:</span>
                </span>
                <ul className="list-disc list-inside space-y-0.5 text-[10px] text-[var(--text-secondary)] pl-1">
                  {source.claimsSupported.map((c, ci) => (
                    <li key={ci} className="leading-tight truncate" title={c}>{c}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Quote / Evidence Excerpt */}
            <div className="p-3 text-[11px] text-[var(--text-secondary)] leading-relaxed bg-[var(--panel-bg)] space-y-1">
              <span className="text-[9px] font-mono uppercase tracking-wider text-[var(--text-muted)] block">
                Source Evidence Quote:
              </span>
              <div
                data-testid="citation-passage-snippet"
                className="line-clamp-4 italic bg-[var(--panel-inner)] p-2 rounded-[2px] border border-[var(--panel-border)] text-[var(--text-primary)] break-words font-sans text-[10.5px]"
              >
                "{evidenceText}"
              </div>
            </div>

            {/* Footer Metadata & Open PDF Action */}
            <div className="flex items-center justify-between border-t border-[var(--panel-border)] bg-[var(--panel-inner)] p-2 gap-2">
              <div className="flex gap-1.5 flex-wrap">
                {typeof source.score === "number" && !isNaN(source.score) && (
                  <span className="text-[9px] font-mono bg-[var(--panel-bg)] text-[var(--text-secondary)] border border-[var(--panel-border)] px-1.5 py-0.5 rounded-[2px]">
                    Match: {(source.score * 100).toFixed(0)}%
                  </span>
                )}
                {source.claimType && (
                  <span className="text-[9px] font-mono bg-[var(--accent-cyan)]/10 text-[var(--accent-cyan)] border border-[var(--accent-cyan)]/30 px-1.5 py-0.5 rounded-[2px]">
                    {source.claimType}
                  </span>
                )}
              </div>

              {source.documentId?.startsWith("doc-") ? (
                <span className="text-[9px] font-mono text-[var(--text-muted)] uppercase tracking-wider px-1">
                  Bundled
                </span>
              ) : onOpenPdf ? (
                <Button
                  variant="ghost"
                  size="sm"
                  data-testid="citation-open-pdf"
                  aria-label={`View citation in document: ${source.documentTitle}`}
                  className="h-6 text-[10px] font-mono text-[var(--accent-amber)] hover:text-[var(--accent-amber-hover)] px-1.5"
                  onClick={() => onOpenPdf(source)}
                >
                  Open PDF <ExternalLink className="ml-1 h-2.5 w-2.5" />
                </Button>
              ) : null}
            </div>
          </div>
        </PopoverContent>
      </Popover>
    );
}
