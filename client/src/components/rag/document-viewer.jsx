"use client";
import React, { useState, useEffect, useMemo } from "react";
import {
  FileText,
  Loader2,
  AlertCircle,
  Copy,
  Check,
  Download,
  ExternalLink,
  Layers,
  BookOpen,
  X
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/store/use-auth-store";
import { resolveApiUrl } from "@/api/client";
import { PdfViewer } from "./pdf-viewer";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Helper: Determine viewer type from MIME or filename extension
export function detectDocumentType(doc) {
  if (!doc) return "pdf";
  const mime = (doc.mimeType || doc.mime_type || "").toLowerCase();
  const name = (doc.originalFilename || doc.original_filename || doc.filename || doc.source || "").toLowerCase();

  if (mime === "application/pdf" || name.endsWith(".pdf")) return "pdf";
  if (mime.includes("wordprocessingml") || mime.includes("officedocument") || name.endsWith(".docx")) return "docx";
  if (mime.includes("markdown") || name.endsWith(".md") || name.endsWith(".markdown")) return "md";
  if (mime.startsWith("text/") || name.endsWith(".txt") || name.endsWith(".log") || name.endsWith(".json")) return "txt";

  return "pdf";
}

// ── In-App Text Viewer ──────────────────────────────────────────────
export function TextViewer({ documentId, filename }) {
  const { token, sessionId } = useAuthStore();
  const [content, setContent] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let active = true;
    async function fetchText() {
      if (!documentId) return;
      setIsLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams();
        if (token) params.set("token", token);
        else if (sessionId) params.set("session_id", sessionId);
        const q = params.toString();

        const url = resolveApiUrl(`/api/documents/${documentId}/raw${q ? `?${q}` : ""}`);
        const headers = {};
        if (token) headers["Authorization"] = `Bearer ${token}`;
        if (sessionId) headers["x-session-id"] = sessionId;

        const res = await fetch(url, { headers, cache: "no-store" });
        if (!res.ok) {
          throw new Error(`Failed to load text content (${res.status} ${res.statusText})`);
        }
        const text = await res.text();
        if (active) setContent(text);
      } catch (err) {
        if (active) setError(err.message || "Failed to load document text.");
      } finally {
        if (active) setIsLoading(false);
      }
    }
    fetchText();
    return () => { active = false; };
  }, [documentId, token, sessionId]);

  const handleCopy = () => {
    if (!content) return;
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (isLoading) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-8 font-mono text-xs text-[var(--text-muted)]">
        <Loader2 className="h-6 w-6 animate-spin text-[var(--accent-amber)] mb-2" />
        <span>Loading text content...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-8 font-mono text-xs text-rose-500 text-center">
        <AlertCircle className="h-6 w-6 mb-2 text-rose-500" />
        <span className="font-bold">Error Opening Document</span>
        <span className="text-[11px] text-[var(--text-muted)] mt-1 max-w-md">{error}</span>
      </div>
    );
  }

  const lines = content.split("\n");

  return (
    <div className="flex flex-col h-full bg-[var(--panel-bg)] text-[var(--text-primary)]">
      <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--panel-border)] bg-[var(--panel-inner)] shrink-0">
        <div className="flex items-center gap-2 font-mono text-xs text-[var(--text-muted)]">
          <span>{lines.length} lines</span>
          <span>·</span>
          <span>{content.length.toLocaleString()} characters</span>
        </div>
        <Button
          size="sm"
          variant="outline"
          className="h-7 px-2.5 font-mono text-xs border-[var(--panel-border)] hover:bg-[var(--panel-bg)] text-[var(--text-primary)]"
          onClick={handleCopy}
        >
          {copied ? (
            <>
              <Check className="h-3.5 w-3.5 mr-1.5 text-emerald-500" />
              COPIED
            </>
          ) : (
            <>
              <Copy className="h-3.5 w-3.5 mr-1.5" />
              COPY TEXT
            </>
          )}
        </Button>
      </div>

      <div className="flex-1 overflow-auto p-4 font-mono text-xs leading-relaxed select-text">
        <pre className="whitespace-pre-wrap break-words font-mono text-xs text-[var(--text-primary)]">
          {content}
        </pre>
      </div>
    </div>
  );
}

// ── In-App Markdown Viewer ──────────────────────────────────────────
export function MarkdownViewer({ documentId, filename }) {
  const { token, sessionId } = useAuthStore();
  const [content, setContent] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let active = true;
    async function fetchMarkdown() {
      if (!documentId) return;
      setIsLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams();
        if (token) params.set("token", token);
        else if (sessionId) params.set("session_id", sessionId);
        const q = params.toString();

        const url = resolveApiUrl(`/api/documents/${documentId}/raw${q ? `?${q}` : ""}`);
        const headers = {};
        if (token) headers["Authorization"] = `Bearer ${token}`;
        if (sessionId) headers["x-session-id"] = sessionId;

        const res = await fetch(url, { headers, cache: "no-store" });
        if (!res.ok) {
          throw new Error(`Failed to load markdown content (${res.status} ${res.statusText})`);
        }
        const text = await res.text();
        if (active) setContent(text);
      } catch (err) {
        if (active) setError(err.message || "Failed to load markdown content.");
      } finally {
        if (active) setIsLoading(false);
      }
    }
    fetchMarkdown();
    return () => { active = false; };
  }, [documentId, token, sessionId]);

  if (isLoading) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-8 font-mono text-xs text-[var(--text-muted)]">
        <Loader2 className="h-6 w-6 animate-spin text-[var(--accent-amber)] mb-2" />
        <span>Rendering Markdown document...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-8 font-mono text-xs text-rose-500 text-center">
        <AlertCircle className="h-6 w-6 mb-2 text-rose-500" />
        <span className="font-bold">Error Opening Markdown</span>
        <span className="text-[11px] text-[var(--text-muted)] mt-1 max-w-md">{error}</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-[var(--panel-bg)] text-[var(--text-primary)] overflow-auto p-6">
      <div className="max-w-3xl mx-auto w-full prose prose-invert prose-headings:font-mono prose-headings:text-[var(--text-primary)] prose-p:text-[var(--text-secondary)] prose-pre:bg-[var(--panel-inner)] prose-pre:border prose-pre:border-[var(--panel-border)]">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {content}
        </ReactMarkdown>
      </div>
    </div>
  );
}

// ── In-App DOCX Structured Section Viewer ───────────────────────────
export function DocxViewer({ documentId, filename, initialSection }) {
  const { token, sessionId } = useAuthStore();
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let active = true;
    async function fetchDocxSections() {
      if (!documentId) return;
      setIsLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams();
        if (token) params.set("token", token);
        else if (sessionId) params.set("session_id", sessionId);
        const q = params.toString();

        const url = resolveApiUrl(`/api/documents/${documentId}/content${q ? `?${q}` : ""}`);
        const headers = {};
        if (token) headers["Authorization"] = `Bearer ${token}`;
        if (sessionId) headers["x-session-id"] = sessionId;

        const res = await fetch(url, { headers, cache: "no-store" });
        if (!res.ok) {
          throw new Error(`Failed to load DOCX structure (${res.status} ${res.statusText})`);
        }
        const json = await res.json();
        if (active) setData(json);
      } catch (err) {
        if (active) setError(err.message || "Failed to load DOCX content.");
      } finally {
        if (active) setIsLoading(false);
      }
    }
    fetchDocxSections();
    return () => { active = false; };
  }, [documentId, token, sessionId]);

  if (isLoading) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-8 font-mono text-xs text-[var(--text-muted)]">
        <Loader2 className="h-6 w-6 animate-spin text-[var(--accent-amber)] mb-2" />
        <span>Extracting and rendering Word document structure...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-8 font-mono text-xs text-rose-500 text-center">
        <AlertCircle className="h-6 w-6 mb-2 text-rose-500" />
        <span className="font-bold">Error Opening DOCX</span>
        <span className="text-[11px] text-[var(--text-muted)] mt-1 max-w-md">{error}</span>
      </div>
    );
  }

  const sections = data?.sections || [];

  return (
    <div className="flex flex-col h-full bg-[var(--panel-bg)] text-[var(--text-primary)]">
      <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--panel-border)] bg-[var(--panel-inner)] shrink-0 font-mono text-xs text-[var(--text-muted)]">
        <div className="flex items-center gap-2">
          <BookOpen className="h-3.5 w-3.5 text-[var(--accent-cyan)]" />
          <span>{sections.length} Logical Section(s)</span>
          <span>·</span>
          <span>Preserved Body Hierarchy</span>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6 space-y-6">
        {sections.length === 0 ? (
          <div className="p-8 text-center font-mono text-xs text-[var(--text-muted)]">
            No text content found in document.
          </div>
        ) : (
          sections.map((sec, idx) => (
            <div
              key={idx}
              id={`sec-${idx + 1}`}
              className="rounded-[3px] border border-[var(--panel-border)] bg-[var(--panel-inner)]/50 p-4 space-y-2.5 transition-all"
            >
              <div className="flex items-center justify-between border-b border-[var(--panel-border)]/60 pb-2">
                <span className="font-mono text-xs font-bold uppercase tracking-wider text-[var(--accent-amber)] flex items-center gap-2">
                  <Layers className="h-3.5 w-3.5" />
                  {sec.section || `Section ${idx + 1}`}
                </span>
                <span className="font-mono text-[10px] text-[var(--text-muted)]">
                  {sec.text ? `${sec.text.length} chars` : ""}
                </span>
              </div>
              <div className="font-mono text-xs text-[var(--text-secondary)] whitespace-pre-wrap leading-relaxed select-text">
                {sec.text}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ── Master Document Viewer Abstraction ──────────────────────────────
export function DocumentViewer({ document, onClose, initialPage = 1, initialSection = "" }) {
  if (!document) return null;

  const docType = detectDocumentType(document);
  const docId = document.documentId || document.document_id || document.id;
  const docTitle = document.originalFilename || document.original_filename || document.documentTitle || document.title || document.source || "Document";

  const getFormatBadge = () => {
    switch (docType) {
      case "pdf":
        return <span className="px-1.5 py-0.5 rounded-[2px] bg-rose-500/10 text-rose-500 border border-rose-500/20 font-mono text-[10px] font-bold">PDF</span>;
      case "docx":
        return <span className="px-1.5 py-0.5 rounded-[2px] bg-blue-500/10 text-blue-500 border border-blue-500/20 font-mono text-[10px] font-bold">DOCX</span>;
      case "md":
        return <span className="px-1.5 py-0.5 rounded-[2px] bg-purple-500/10 text-purple-500 border border-purple-500/20 font-mono text-[10px] font-bold">MD</span>;
      case "txt":
      default:
        return <span className="px-1.5 py-0.5 rounded-[2px] bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 font-mono text-[10px] font-bold">TXT</span>;
    }
  };

  return (
    <div className="flex flex-col h-full w-full bg-[var(--panel-bg)] select-none">
      {/* Top Universal Viewer Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-[var(--panel-border)] bg-[var(--panel-inner)] shrink-0">
        <div className="flex items-center gap-2.5 min-w-0">
          <FileText className="h-4 w-4 text-[var(--accent-amber)] shrink-0" />
          <span className="font-mono text-xs font-bold text-[var(--text-primary)] truncate max-w-sm sm:max-w-md">
            {docTitle}
          </span>
          {getFormatBadge()}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {onClose && (
            <Button
              size="sm"
              variant="ghost"
              className="h-7 w-7 p-0 text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--panel-bg)] rounded-[2px]"
              onClick={onClose}
              title="Close Viewer"
            >
              <X className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>

      {/* Render Format-Specific Viewer Component */}
      <div className="flex-1 min-h-0 relative overflow-hidden">
        {docType === "pdf" && (
          <PdfViewer documentId={docId} initialPage={initialPage || document.pageNumber || 1} />
        )}
        {docType === "docx" && (
          <DocxViewer documentId={docId} filename={docTitle} initialSection={initialSection} />
        )}
        {docType === "md" && (
          <MarkdownViewer documentId={docId} filename={docTitle} />
        )}
        {docType === "txt" && (
          <TextViewer documentId={docId} filename={docTitle} />
        )}
      </div>
    </div>
  );
}
