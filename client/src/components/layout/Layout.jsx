import React, { useState } from "react";
import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { ArchitectureDialog } from "@/components/rag/architecture-dialog";
import { DocumentViewer } from "@/components/rag/document-viewer";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { useUIStore } from "@/store/use-ui-store";
import { Menu } from "lucide-react";

export function Layout() {
  const { archOpen, setArchOpen, activeDocument, setActiveDocument, pdfSource, setPdfSource } = useUIStore();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  return (
    <div className="flex h-screen w-screen bg-[var(--bg-page)] text-[var(--text-primary)] overflow-hidden font-mono">
      {/* Mobile backdrop */}
      {isMobileOpen && (
        <div
          onClick={() => setIsMobileOpen(false)}
          className="fixed inset-0 bg-black/40 z-30 md:hidden backdrop-blur-xs"
          aria-hidden="true"
        />
      )}

      {/* Navigation Sidebar */}
      <Sidebar
        isCollapsed={isCollapsed}
        setIsCollapsed={setIsCollapsed}
        isMobileOpen={isMobileOpen}
        setIsMobileOpen={setIsMobileOpen}
      />

      {/* Main Workspace Area */}
      <div className="flex-1 min-w-0 h-full flex flex-col overflow-hidden relative">
        {/* Mobile Header Toggle */}
        <header className="md:hidden h-10 border-b border-[var(--panel-border)] bg-[var(--panel-bg)] px-3 flex items-center justify-between shrink-0 z-20">
          <button
            onClick={() => setIsMobileOpen(true)}
            className="p-1 rounded-[2px] border border-[var(--panel-border)] text-[var(--text-muted)] hover:text-[var(--text-primary)]"
            aria-label="Open sidebar menu"
          >
            <Menu className="h-4 w-4" />
          </button>
          <div className="flex items-center gap-1.5 font-mono text-xs font-bold uppercase tracking-wider">
            <span className="h-3.5 w-3.5 rounded-[2px] bg-[#f97316] text-white flex items-center justify-center text-[9px]">■</span>
            <span>COGNIFLOW</span>
          </div>
          <div className="w-6" />
        </header>

        {/* Content Viewport */}
        <main className="flex-1 min-h-0 flex flex-col overflow-hidden relative cogniflow-grid">
          <Outlet />
        </main>
      </div>

      {/* Global Architecture Dialog */}
      <ArchitectureDialog open={archOpen} onOpenChange={setArchOpen} />

      {/* Global Document Viewer Modal */}
      {(() => {
        const currentDoc = activeDocument || pdfSource;
        const handleCloseDoc = () => {
          if (setActiveDocument) setActiveDocument(null);
          if (setPdfSource) setPdfSource(null);
        };
        return (
          <Dialog open={!!currentDoc} onOpenChange={(open) => !open && handleCloseDoc()}>
            <DialogContent className="max-w-4xl h-[90vh] p-0 overflow-hidden flex flex-col rounded-[3px] border border-[var(--panel-border)] bg-[var(--panel-bg)]">
              <DialogTitle className="sr-only">Document Viewer</DialogTitle>
              <div className="flex-1 min-h-0 relative">
                {currentDoc && (
                  <DocumentViewer
                    document={currentDoc}
                    onClose={handleCloseDoc}
                    initialPage={currentDoc.pageNumber || 1}
                    initialSection={currentDoc.section || ""}
                  />
                )}
              </div>
            </DialogContent>
          </Dialog>
        );
      })()}
    </div>
  );
}
