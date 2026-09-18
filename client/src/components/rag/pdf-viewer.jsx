"use client";
import React, { useState, useCallback, useRef, useEffect } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import { Loader2, ChevronLeft, ChevronRight, ZoomIn, ZoomOut, Maximize2, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/store/use-auth-store";
import { resolveApiUrl } from "@/api/client";

if (typeof window !== "undefined") {
  pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
}

export function PdfViewer({ documentId, initialPage = 1 }) {
  const { token, sessionId } = useAuthStore();
  const [numPages, setNumPages] = useState();
  const [pageNumber, setPageNumber] = useState(initialPage);
  const [loadError, setLoadError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [pdfBlobUrl, setPdfBlobUrl] = useState(null);
  const [zoomScale, setZoomScale] = useState(1.0);
  const [zoomMode, setZoomMode] = useState("fit-width"); // "fit-width", "fit-page", "custom"
  const [pageDimensions, setPageDimensions] = useState({ width: 600, height: 800 });
  const [containerDimensions, setContainerDimensions] = useState({ width: 0, height: 0 });

  const viewportRef = useRef(null);

  // Explicit frontend fetch with auth headers, status mapping, and %PDF- header byte validation
  useEffect(() => {
    let active = true;
    let currentBlobUrl = null;

    async function fetchPdfDocument() {
      if (!documentId) {
        setIsLoading(false);
        setPdfBlobUrl(null);
        return;
      }

      setIsLoading(true);
      setLoadError(null);

      try {
        const params = new URLSearchParams();
        if (token) {
          params.set("token", token);
        } else if (sessionId) {
          params.set("session_id", sessionId);
        }
        const queryString = params.toString();
        const url = resolveApiUrl(`/api/documents/${documentId}/raw${queryString ? `?${queryString}` : ""}`);

        const headers = {
          "Cache-Control": "no-cache",
          "Pragma": "no-cache",
        };
        if (token) headers["Authorization"] = `Bearer ${token}`;
        if (sessionId) headers["x-session-id"] = sessionId;

        const res = await fetch(url, { headers, cache: "no-store" });

        if (!res.ok) {
          if (res.status === 401) {
            throw new Error("Authentication required (401). Please log in to view this document.");
          }
          if (res.status === 403) {
            throw new Error("Access denied (403). You do not have permission to view this document.");
          }
          if (res.status === 404) {
            throw new Error("Document not found (404). This file does not exist or has been removed.");
          }
          let detail = "";
          try {
            const errJson = await res.json();
            detail = errJson.detail || errJson.error || "";
          } catch {
            // ignore non-json error bodies
          }
          throw new Error(`Failed to load document (${res.status} ${res.statusText})${detail ? `: ${detail}` : ""}`);
        }

        const contentType = res.headers.get("content-type") || "";
        const arrayBuffer = await res.arrayBuffer();

        if (arrayBuffer.byteLength < 5) {
          throw new Error("Invalid document: File is empty or truncated.");
        }

        // Validate %PDF- header magic bytes: 0x25, 0x50, 0x44, 0x46, 0x2D
        const header = new Uint8Array(arrayBuffer, 0, 5);
        const isPdfMagic =
          header[0] === 0x25 && // %
          header[1] === 0x50 && // P
          header[2] === 0x44 && // D
          header[3] === 0x46 && // F
          header[4] === 0x2D;   // -

        if (!isPdfMagic) {
          // Check if payload is actually a JSON error or plain text
          try {
            const decoder = new TextDecoder("utf-8");
            const textPreview = decoder.decode(arrayBuffer.slice(0, 200));
            if (textPreview.trim().startsWith("{")) {
              const errObj = JSON.parse(textPreview);
              if (errObj.detail) {
                throw new Error(`Server error: ${errObj.detail}`);
              }
            }
          } catch (e) {
            if (e.message.startsWith("Server error:")) throw e;
          }
          throw new Error(
            `Invalid PDF format: File header does not start with '%PDF-'. Content-Type: ${contentType || "unknown"}`
          );
        }

        if (!active) return;

        const blob = new Blob([arrayBuffer], { type: "application/pdf" });
        currentBlobUrl = URL.createObjectURL(blob);
        setPdfBlobUrl(currentBlobUrl);
      } catch (err) {
        if (!active) return;
        console.error("PDF viewer loading error:", err);
        setLoadError(err.message || "Failed to load PDF");
      } finally {
        if (active) {
          setIsLoading(false);
        }
      }
    }

    fetchPdfDocument();

    return () => {
      active = false;
      if (currentBlobUrl) {
        URL.revokeObjectURL(currentBlobUrl);
      }
    };
  }, [documentId, token, sessionId]);

  // Responsive container observer
  useEffect(() => {
    const el = viewportRef.current;
    if (!el) return;

    const updateDimensions = () => {
      const rect = el.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        setContainerDimensions({
          width: Math.floor(rect.width),
          height: Math.floor(rect.height),
        });
      }
    };

    updateDimensions();

    const observer = new ResizeObserver(() => {
      updateDimensions();
    });
    observer.observe(el);

    return () => observer.disconnect();
  }, []);

  const onDocumentLoadSuccess = useCallback(
    ({ numPages }) => {
      setNumPages(numPages);
      setLoadError(null);
      if (initialPage > numPages) {
        setPageNumber(numPages);
      }
    },
    [initialPage]
  );

  const onDocumentLoadError = useCallback((error) => {
    console.error("PDF parsing error:", error);
    setLoadError(error.message || "Failed to render PDF pages");
  }, []);

  const onPageLoadSuccess = useCallback((page) => {
    const { width, height } = page;
    setPageDimensions({ width, height });
  }, []);

  // Calculate target page display width based on mode and container size
  const calculatedWidth = React.useMemo(() => {
    const availWidth = Math.max(containerDimensions.width - 48, 280);
    const availHeight = Math.max(containerDimensions.height - 48, 300);

    if (zoomMode === "fit-page" && pageDimensions.height > 0) {
      const widthByHeight = (availHeight / pageDimensions.height) * pageDimensions.width;
      return Math.min(availWidth, widthByHeight);
    }

    if (zoomMode === "fit-width") {
      // Fit to container width while preventing excessive stretch
      return Math.min(availWidth, pageDimensions.width * 1.5);
    }

    // Custom zoom
    return Math.round(availWidth * zoomScale);
  }, [containerDimensions, pageDimensions, zoomMode, zoomScale]);

  const handleZoomIn = () => {
    setZoomMode("custom");
    setZoomScale((prev) => Math.min(prev + 0.2, 2.5));
  };

  const handleZoomOut = () => {
    setZoomMode("custom");
    setZoomScale((prev) => Math.max(prev - 0.2, 0.4));
  };

  const handleFitWidth = () => {
    setZoomMode("fit-width");
    setZoomScale(1.0);
  };

  const handleFitPage = () => {
    setZoomMode("fit-page");
    setZoomScale(1.0);
  };

  const handleResetZoom = () => {
    setZoomMode("fit-width");
    setZoomScale(1.0);
  };

  return (
    <div
      data-testid="pdf-viewer-container"
      className="flex flex-col h-full w-full bg-[var(--bg-page)] select-none font-mono"
    >
      {/* Sticky Fixed Engineering Toolbar */}
      <div className="h-11 border-b border-[var(--panel-border)] bg-[var(--panel-inner)] px-4 flex items-center justify-between shrink-0 z-20 gap-2 flex-wrap text-xs">
        {/* Pagination Controls */}
        <div className="flex items-center gap-1.5">
          <Button
            variant="outline"
            size="sm"
            data-testid="pdf-prev-page"
            disabled={pageNumber <= 1}
            onClick={() => setPageNumber((p) => Math.max(1, p - 1))}
            aria-label="Previous page"
            className="h-7 px-2.5 text-[11px] font-mono rounded-[2px] border-[var(--panel-border)] hover:bg-[var(--panel-bg)] cursor-pointer"
          >
            <ChevronLeft className="h-3.5 w-3.5 mr-0.5" />
            PREV
          </Button>

          <span
            className="text-[11px] font-mono font-semibold px-2 text-[#f97316] select-none whitespace-nowrap"
            aria-live="polite"
          >
            PAGE {pageNumber} / {numPages || "--"}
          </span>

          <Button
            variant="outline"
            size="sm"
            data-testid="pdf-next-page"
            disabled={numPages === undefined || pageNumber >= numPages}
            onClick={() => setPageNumber((p) => Math.min(numPages || p, p + 1))}
            aria-label="Next page"
            className="h-7 px-2.5 text-[11px] font-mono rounded-[2px] border-[var(--panel-border)] hover:bg-[var(--panel-bg)] cursor-pointer"
          >
            NEXT
            <ChevronRight className="h-3.5 w-3.5 ml-0.5" />
          </Button>
        </div>

        {/* Zoom Controls */}
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleZoomOut}
            className="h-7 w-7 p-0 rounded-[2px] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--panel-bg)] border border-[var(--panel-border)] cursor-pointer"
            title="Zoom Out (-20%)"
            aria-label="Zoom out"
          >
            <ZoomOut className="h-3.5 w-3.5" />
          </Button>

          <Button
            variant="ghost"
            size="sm"
            onClick={handleZoomIn}
            className="h-7 w-7 p-0 rounded-[2px] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--panel-bg)] border border-[var(--panel-border)] cursor-pointer"
            title="Zoom In (+20%)"
            aria-label="Zoom in"
          >
            <ZoomIn className="h-3.5 w-3.5" />
          </Button>

          <div className="h-4 w-[1px] bg-[var(--panel-border)] mx-1" />

          <Button
            variant={zoomMode === "fit-width" ? "secondary" : "ghost"}
            size="sm"
            onClick={handleFitWidth}
            className={`h-7 px-2 text-[10px] font-mono rounded-[2px] border border-[var(--panel-border)] cursor-pointer ${
              zoomMode === "fit-width" ? "bg-[#f97316]/15 text-[#f97316] font-bold" : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"
            }`}
            title="Fit to available container width"
          >
            FIT WIDTH
          </Button>

          <Button
            variant={zoomMode === "fit-page" ? "secondary" : "ghost"}
            size="sm"
            onClick={handleFitPage}
            className={`h-7 px-2 text-[10px] font-mono rounded-[2px] border border-[var(--panel-border)] cursor-pointer ${
              zoomMode === "fit-page" ? "bg-[#f97316]/15 text-[#f97316] font-bold" : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"
            }`}
            title="Fit entire page in viewport"
          >
            FIT PAGE
          </Button>

          <Button
            variant="ghost"
            size="sm"
            onClick={handleResetZoom}
            className="h-7 px-1.5 text-[10px] font-mono text-[var(--text-muted)] hover:text-[var(--text-primary)] rounded-[2px] border border-[var(--panel-border)] cursor-pointer"
            title="Reset scale"
          >
            <RotateCcw className="h-3 w-3 mr-1" />
            100%
          </Button>
        </div>
      </div>

      {/* Viewport Area with Centered PDF Page */}
      <div
        ref={viewportRef}
        className="flex-1 min-h-0 w-full overflow-auto p-4 flex flex-col items-center justify-start relative bg-[var(--bg-page)]"
      >
        {isLoading ? (
          <div className="flex items-center justify-center p-16 text-[var(--text-muted)] font-mono text-xs my-auto">
            <Loader2 className="h-5 w-5 animate-spin mr-2 text-[#f97316]" /> LOADING DOCUMENT…
          </div>
        ) : loadError ? (
          <div className="p-8 my-auto text-center bg-[var(--panel-inner)] border border-rose-800/60 rounded-[3px] max-w-md">
            <p className="text-rose-400 font-mono text-xs uppercase font-bold">Failed to load PDF</p>
            <p className="text-xs text-[var(--text-muted)] mt-1 font-mono">{loadError}</p>
            <p className="text-[11px] text-[var(--text-muted)] mt-2">
              Please check your access permissions or ensure the document exists.
            </p>
          </div>
        ) : pdfBlobUrl ? (
          <div className="my-auto py-2 flex flex-col items-center justify-center min-w-full">
            <div
              className="shadow-md border border-[var(--panel-border)] bg-white rounded-[2px] transition-all duration-150 relative mx-auto"
              style={{
                width: calculatedWidth > 0 ? `${calculatedWidth}px` : "auto",
                maxWidth: zoomMode === "fit-width" ? "100%" : "none",
              }}
            >
              <Document
                file={pdfBlobUrl}
                onLoadSuccess={onDocumentLoadSuccess}
                onLoadError={onDocumentLoadError}
                loading={
                  <div className="flex items-center justify-center p-16 text-[var(--text-muted)] font-mono text-xs">
                    <Loader2 className="h-5 w-5 animate-spin mr-2 text-[#f97316]" /> PARSING PDF PAGES…
                  </div>
                }
              >
                <Page
                  pageNumber={pageNumber}
                  renderTextLayer={true}
                  renderAnnotationLayer={true}
                  width={calculatedWidth > 0 ? calculatedWidth : 600}
                  onLoadSuccess={onPageLoadSuccess}
                  className="mx-auto"
                />
              </Document>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

