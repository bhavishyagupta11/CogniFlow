import React from "react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { ExternalLink, CheckCircle2, FileText } from "lucide-react";

export function CitationCard({ source, index, onOpenPdf }) {
  const sectionTitle = source.heading || source.section || source.chapter;
  const badgeLabel = source.badge || (typeof index === "string" ? index.replace(/^[\[\]]/g, "") : `E${index}`);

  // Calculate accurate page display using pageStart/pageEnd or pageNumber
  const pStart = source.pageStart || source.page_start || source.pageNumber || source.page_number;
  const pEnd = source.pageEnd || source.page_end || pStart;
  const pageDisplay = pStart && pEnd && pStart !== pEnd ? `Pages ${pStart}–${pEnd}` : pStart ? `Page ${pStart}` : null;

  // Retrieve the full, unclipped evidence text from provenance fields
  const evidenceText = (
    source.excerpt ||
    source.quoteOrEvidence ||
    source.chunkContent ||
    source.text ||
    source.content ||
    ""
  ).trim();

  // Document metadata
  const docTitle = source.documentTitle || source.documentName || source.originalFilename || source.filename || "Referenced Document";
  const chunkIdShort = source.chunkId || source.chunk_id ? String(source.chunkId || source.chunk_id).split("#").pop() : null;

  // Only display verified badge if genuinely validated by backend
  const isVerified = source.verified !== false;

  const handleOpenPdf = () => {
    if (!onOpenPdf) return;
    onOpenPdf({
      documentId: source.documentId || source.document_id,
      pageNumber: pStart || 1,
      pageStart: pStart || 1,
      pageEnd: pEnd || pStart || 1,
      documentTitle: docTitle,
      originalFilename: docTitle
    });
  };

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          data-testid={`citation-pill-${badgeLabel}`}
          className="inline-flex items-center justify-center text-[#f97316] hover:text-[#ea580c] hover:underline font-mono text-[11px] font-bold cursor-pointer align-baseline mx-0.5 outline-hidden transition-colors"
          aria-label={`View citation [${badgeLabel}]: ${docTitle}`}
        >
          <span>[{badgeLabel}]</span>
        </button>
      </PopoverTrigger>
      <PopoverContent
        data-testid="citation-popover"
        className="w-[min(26rem,calc(100vw-2rem))] max-w-[calc(100vw-2rem)] p-0 shadow-2xl border border-[var(--panel-border)] rounded-[4px] bg-[var(--panel-bg)] z-50 overflow-hidden min-w-0"
        align="start"
        sideOffset={6}
      >
        <div className="flex flex-col text-xs max-h-[85vh] min-w-0">
          {/* 1. Fixed Header */}
          <div className="shrink-0 border-b border-[var(--panel-border)] bg-[var(--panel-inner)] p-3 space-y-1.5 min-w-0">
            <div className="flex items-center justify-between gap-2 flex-wrap font-mono min-w-0">
              <span className="text-[11px] font-bold text-[#f97316] uppercase tracking-wider flex items-center gap-1.5 shrink-0">
                <FileText className="h-3 w-3" />
                SOURCE [{badgeLabel}]
              </span>
              {isVerified && (
                <span className="text-[10px] text-emerald-500 font-semibold uppercase flex items-center gap-1 shrink-0">
                  <CheckCircle2 className="h-3 w-3" />
                  VERIFIED GROUNDED
                </span>
              )}
            </div>

            {/* 2. Metadata */}
            <h4 className="text-xs font-semibold text-[var(--text-primary)] break-words line-clamp-2 min-w-0" title={docTitle}>
              {docTitle}
            </h4>

            <div className="flex items-center gap-2 text-[10px] text-[var(--text-muted)] flex-wrap font-mono min-w-0">
              {sectionTitle && (
                <span className="font-medium text-[var(--text-secondary)] truncate max-w-[190px] min-w-0">
                  {sectionTitle}
                </span>
              )}
              {pageDisplay && <span className="text-[var(--accent-cyan)] font-bold shrink-0">· {pageDisplay}</span>}
              {chunkIdShort && <span className="shrink-0">· Chunk: {chunkIdShort}</span>}
            </div>
          </div>

          {/* 3. Independently Scrollable Evidence Viewport */}
          <div className="flex-1 p-3 bg-[var(--panel-bg)] space-y-1.5 overflow-hidden flex flex-col min-h-0 min-w-0">
            <span className="text-[9px] font-mono uppercase tracking-wider text-[var(--text-muted)] block shrink-0 font-semibold">
              SOURCE EVIDENCE QUOTE:
            </span>
            <div
              data-testid="citation-passage-snippet"
              className="max-h-56 overflow-y-auto pr-2 rounded-[2px] bg-[var(--panel-inner)] border border-[var(--panel-border)] p-2.5 text-[11px] text-[var(--text-primary)] font-sans leading-relaxed break-words select-text min-w-0"
              tabIndex={0}
              role="region"
              aria-label={`Evidence passage for citation [${badgeLabel}]`}
            >
              {evidenceText ? (
                <span className="italic whitespace-pre-wrap break-words">"{evidenceText}"</span>
              ) : (
                <span className="text-[var(--text-muted)] italic">No source passage text available.</span>
              )}
            </div>
          </div>

          {/* 4. Fixed Footer */}
          <div className="shrink-0 flex items-center justify-between border-t border-[var(--panel-border)] bg-[var(--panel-inner)] px-3 py-2 gap-2 min-w-0 flex-wrap">
            <div className="flex items-center gap-1.5 font-mono text-[10px] text-[var(--text-muted)]">
              {typeof source.score === "number" && !isNaN(source.score) && (
                <span className="font-semibold text-[var(--text-secondary)]">
                  Score {source.score.toFixed(2)}
                </span>
              )}
              {source.claimType && (
                <span>· {source.claimType}</span>
              )}
            </div>

            {onOpenPdf && (source.documentId || source.document_id) ? (
              <Button
                variant="ghost"
                size="sm"
                data-testid="citation-open-pdf"
                aria-label={`Open document at ${pageDisplay || "page 1"}`}
                className="h-6 text-[10px] font-mono text-[#f97316] hover:text-[#ea580c] px-2 hover:bg-[#f97316]/10"
                onClick={handleOpenPdf}
              >
                OPEN PDF <ExternalLink className="ml-1 h-2.5 w-2.5" />
              </Button>
            ) : null}
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
