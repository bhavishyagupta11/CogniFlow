import React, { useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { UploadCloud, FileText, Trash2, Loader2, CheckCircle2, AlertCircle, RefreshCw, ExternalLink, HardDrive, Layers, Clock, Info, ShieldCheck, Database, Paperclip, Check } from "lucide-react";
import { toast } from "sonner";
import { useAuthStore } from "@/store/use-auth-store";
import { useUIStore } from "@/store/use-ui-store";
import { useChatStore } from "@/store/use-chat-store";
import { useDocumentsQuery, useUploadDocumentMutation, useDeleteDocumentMutation, useReindexDocumentMutation } from "@/api/documents";
import { PdfPasswordDialog } from "@/components/documents/PdfPasswordDialog";

export function DocumentsPage() {
    const [isDragging, setIsDragging] = useState(false);
    const [selectedDoc, setSelectedDoc] = useState(null);
    const [docToDelete, setDocToDelete] = useState(null);
    const fileInputRef = useRef(null);
    const { setPdfSource, setActiveDocument } = useUIStore();
    const { attachSource, detachSource, attachedSources = [] } = useChatStore();
    const { data: documents = [], isLoading, isError, error, refetch, isFetching } = useDocumentsQuery();
    const uploadMutation = useUploadDocumentMutation();
    const deleteMutation = useDeleteDocumentMutation();
    const reindexMutation = useReindexDocumentMutation();
    const [reindexingId, setReindexingId] = useState(null);

    // Password-protected PDF state
    const [pendingEncryptedFile, setPendingEncryptedFile] = useState(null);
    const [isPasswordModalOpen, setIsPasswordModalOpen] = useState(false);
    const [pdfPasswordError, setPdfPasswordError] = useState("");
    const [isDecrypting, setIsDecrypting] = useState(false);

    const completedDocs = documents.filter((d) => d.processingStatus === "completed" || d.indexStatus === "indexed");
    const totalChunks = completedDocs.reduce((acc, d) => acc + (d.chunkCount || 0), 0);
    const processingCount = documents.filter((d) => !["completed", "failed", "indexed"].includes(d.processingStatus)).length;

    const handleFiles = async (files) => {
        if (files.length === 0 || uploadMutation.isPending) return;
        for (const file of files) {
            const toastId = toast.loading(`Uploading & extracting ${file.name}...`);
            try {
                await uploadMutation.mutateAsync({ file });
                toast.success("Indexed and ready for retrieval.", { id: toastId });
                refetch();
            }
            catch (err) {
                if (err.code === "PASSWORD_REQUIRED" || err.code === "INCORRECT_PASSWORD") {
                    toast.dismiss(toastId);
                    setPendingEncryptedFile(file);
                    setPdfPasswordError(err.code === "INCORRECT_PASSWORD" ? "Incorrect PDF password. Please try again." : "");
                    setIsPasswordModalOpen(true);
                } else {
                    toast.error(err.message || `Failed to upload ${file.name}`, { id: toastId });
                }
            }
        }
    };

    const handlePasswordSubmit = async (password) => {
        if (!pendingEncryptedFile) return;
        setIsDecrypting(true);
        setPdfPasswordError("");
        const toastId = toast.loading(`Decrypting & extracting ${pendingEncryptedFile.name}...`);
        try {
            await uploadMutation.mutateAsync({ file: pendingEncryptedFile, password });
            toast.success("Decrypted and indexed successfully.", { id: toastId });
            setIsPasswordModalOpen(false);
            setPendingEncryptedFile(null);
            refetch();
        } catch (err) {
            toast.dismiss(toastId);
            if (err.code === "INCORRECT_PASSWORD" || err.code === "PASSWORD_REQUIRED") {
                setPdfPasswordError("Incorrect PDF password. Please try again.");
            } else {
                setPdfPasswordError(err.message || "Failed to decrypt and process PDF.");
            }
        } finally {
            setIsDecrypting(false);
        }
    };

    const handleReindex = async (doc) => {
        const toastId = toast.loading(`Re-indexing ${doc.originalFilename}...`);
        setReindexingId(doc.id);
        try {
            await reindexMutation.mutateAsync({ id: doc.id });
            toast.success("Indexed and ready for retrieval.", { id: toastId });
            refetch();
        }
        catch (err) {
            toast.error(err.message || "Re-indexing failed", { id: toastId });
        }
        finally {
            setReindexingId(null);
        }
    };

    const handleDelete = (doc) => {
        setDocToDelete(doc);
    };

    const confirmDelete = async () => {
        if (!docToDelete) return;
        const target = docToDelete;
        const toastId = toast.loading(`Deleting ${target.originalFilename}...`);
        try {
            await deleteMutation.mutateAsync({ id: target.id });
            if (selectedDoc?.id === target.id) setSelectedDoc(null);
            setDocToDelete(null);
            toast.success(`${target.originalFilename} deleted and removed from index`, { id: toastId });
            refetch();
        }
        catch (err) {
            toast.error(err.message || "Deletion failed", { id: toastId });
        }
    };

    const getStatusBadge = (status, error) => {
        if (status === "completed" || status === "indexed") {
            return (
                <span className="font-mono text-xs text-[var(--accent-emerald)] font-medium uppercase">
                    Ready
                </span>
            );
        }
        if (status === "extracted") {
            return (
                <span className="font-mono text-xs text-[var(--accent-cyan)] font-medium uppercase">
                    Extracted
                </span>
            );
        }
        if (status === "ocr_required" || (error && error.toLowerCase().includes("ocr"))) {
            return (
                <span className="font-mono text-xs text-amber-500 font-medium uppercase">
                    OCR Required
                </span>
            );
        }
        if (status === "failed") {
            return (
                <span className="font-mono text-xs text-rose-500 font-medium uppercase">
                    Failed
                </span>
            );
        }
        return (
            <span className="font-mono text-xs text-[var(--accent-amber)] font-medium uppercase flex items-center gap-1">
                <Loader2 className="h-3 w-3 animate-spin"/>
                {status || "Processing"}
            </span>
        );
    };

    const getIndexBadge = (status, processingStatus) => {
        if (status === "indexed" || processingStatus === "completed") {
            return (
                <span className="font-mono text-xs text-[var(--accent-cyan)] font-medium uppercase">
                    Indexed
                </span>
            );
        }
        return (
            <span className="font-mono text-xs text-[var(--text-muted)] font-medium uppercase">
                Not Indexed
            </span>
        );
    };

    const getFormatBadge = (doc) => {
        const mime = (doc.mimeType || doc.mime_type || "").toLowerCase();
        const name = (doc.originalFilename || doc.original_filename || "").toLowerCase();
        if (mime === "application/pdf" || name.endsWith(".pdf")) {
            return <span className="px-1.5 py-0.5 rounded-[2px] bg-rose-500/10 text-rose-500 border border-rose-500/20 font-mono text-[9px] font-bold">PDF</span>;
        }
        if (mime.includes("wordprocessingml") || mime.includes("officedocument") || name.endsWith(".docx")) {
            return <span className="px-1.5 py-0.5 rounded-[2px] bg-blue-500/10 text-blue-500 border border-blue-500/20 font-mono text-[9px] font-bold">DOCX</span>;
        }
        if (mime.includes("markdown") || name.endsWith(".md") || name.endsWith(".markdown")) {
            return <span className="px-1.5 py-0.5 rounded-[2px] bg-purple-500/10 text-purple-500 border border-purple-500/20 font-mono text-[9px] font-bold">MD</span>;
        }
        return <span className="px-1.5 py-0.5 rounded-[2px] bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 font-mono text-[9px] font-bold">TXT</span>;
    };
    return (<div className="flex-1 overflow-y-auto p-6 max-w-6xl mx-auto w-full space-y-6">
      {/* Top summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="rounded-[4px] border border-[var(--panel-border)] bg-[var(--panel-bg)] shadow-xs">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="h-9 w-9 rounded-[2px] border border-[var(--accent-amber)]/30 bg-[var(--accent-amber)]/10 text-[var(--accent-amber)] flex items-center justify-center">
              <HardDrive className="h-4 w-4"/>
            </div>
            <div>
              <div className="font-mono text-2xl font-bold text-[var(--text-primary)]">{documents.length}</div>
              <div className="font-mono text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Indexed Documents</div>
            </div>
          </CardContent>
        </Card>

        <Card className="rounded-[4px] border border-[var(--panel-border)] bg-[var(--panel-bg)] shadow-xs">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="h-9 w-9 rounded-[2px] border border-emerald-500/30 bg-emerald-500/10 text-[var(--accent-emerald)] flex items-center justify-center">
              <Layers className="h-4 w-4"/>
            </div>
            <div>
              <div className="font-mono text-2xl font-bold text-[var(--accent-emerald)]">{totalChunks}</div>
              <div className="font-mono text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Indexed Text Chunks</div>
            </div>
          </CardContent>
        </Card>

        <Card className="rounded-[4px] border border-[var(--panel-border)] bg-[var(--panel-bg)] shadow-xs">
          <CardContent className="p-4 flex items-center gap-4">
            <div className="h-9 w-9 rounded-[2px] border border-cyan-500/30 bg-cyan-500/10 text-[var(--accent-cyan)] flex items-center justify-center">
              <Clock className="h-4 w-4"/>
            </div>
            <div>
              <div className="font-mono text-2xl font-bold text-[var(--accent-cyan)]">{processingCount}</div>
              <div className="font-mono text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Active Ingestion Queue</div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Upload Drop Zone */}
      <Card className="rounded-[4px] border border-[var(--panel-border)] bg-[var(--panel-bg)] shadow-xs">
        <CardContent className="p-6">
          <div onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
        }} onDragLeave={() => setIsDragging(false)} onDrop={(e) => {
            e.preventDefault();
            setIsDragging(false);
            if (e.dataTransfer.files) {
                handleFiles(Array.from(e.dataTransfer.files));
            }
        }} className={`flex flex-col items-center justify-center py-8 rounded-[4px] border-2 border-dashed transition-all ${isDragging
            ? "border-[var(--accent-amber)] bg-[var(--accent-amber)]/10"
            : "border-[var(--panel-border)] bg-[var(--panel-inner)] hover:border-[var(--accent-amber)]/60"}`}>
            <UploadCloud className="h-9 w-9 text-[var(--accent-amber)] mb-3"/>
            <p className="font-mono text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
              DROP RESEARCH PAPERS OR DOCUMENT SOURCES HERE
            </p>
            <p className="font-mono text-[10px] text-[var(--text-muted)] mt-1 mb-4">
              SUPPORTED FORMATS: PDF, DOCX, TXT, MD (UP TO 50MB)
            </p>

            <input type="file" ref={fileInputRef} className="hidden" multiple accept=".pdf,.docx,.txt,.md" onChange={(e) => {
            if (e.target.files) {
                handleFiles(Array.from(e.target.files));
            }
            if (fileInputRef.current)
                fileInputRef.current.value = "";
        }}/>

            <Button variant="outline" size="sm" className="rounded-[2px] font-mono text-xs border-[var(--panel-border)] bg-[var(--panel-bg)] text-[var(--text-primary)] hover:border-[var(--accent-amber)] hover:text-[var(--accent-amber)] cursor-pointer" onClick={() => fileInputRef.current?.click()} disabled={uploadMutation.isPending}>
              {uploadMutation.isPending ? (<Loader2 className="h-4 w-4 mr-2 animate-spin"/>) : (<FileText className="h-4 w-4 mr-2"/>)}
              SELECT FILES
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Document Table */}
      <Card className="rounded-[4px] border border-[var(--panel-border)] bg-[var(--panel-bg)] shadow-xs">
        <CardHeader className="flex flex-row items-center justify-between pb-3 border-b border-[var(--panel-border)]">
          <div>
            <CardTitle className="font-mono text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">CORPUS_DOCUMENTS</CardTitle>
            <CardDescription className="font-mono text-[11px] text-[var(--text-muted)]">
              Indexed knowledge base units available to the RAG retrieval pipeline.
            </CardDescription>
          </div>
          <Button variant="ghost" size="sm" onClick={() => refetch()} disabled={isFetching} aria-label="Refresh documents list" className="rounded-[2px] text-[var(--text-muted)] hover:text-[var(--accent-amber)] hover:bg-[var(--accent-amber)]/10">
            <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin text-[var(--accent-amber)]" : ""}`}/>
          </Button>
        </CardHeader>

        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="text-[10px] font-mono uppercase tracking-wider text-[var(--text-muted)] border-b border-[var(--panel-border)] bg-[var(--panel-inner)]">
                <TableHead>FILENAME</TableHead>
                <TableHead>STATUS</TableHead>
                <TableHead>INDEX STATUS</TableHead>
                <TableHead>CHUNKS</TableHead>
                <TableHead>PAGES</TableHead>
                <TableHead>SIZE</TableHead>
                <TableHead>UPLOADED</TableHead>
                <TableHead className="text-right">ACTIONS</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                <TableRow>
                  <TableCell colSpan={8} className="text-center py-8 font-mono text-xs text-[var(--text-muted)]">
                    <Loader2 className="h-5 w-5 animate-spin mx-auto mb-2 text-[var(--accent-amber)]"/>
                    LOADING_DOCUMENTS...
                  </TableCell>
                </TableRow>
              ) : isError ? (
                <TableRow>
                  <TableCell colSpan={8} className="py-8">
                    <div className="flex flex-col items-center gap-3 font-mono text-xs text-center">
                      <AlertCircle className="h-6 w-6 text-rose-500" />
                      <span className="font-bold text-rose-500 uppercase tracking-wider">API Error — Cannot Load Documents</span>
                      <span className="text-[var(--text-muted)] max-w-md">
                        {error?.name === "ApiConfigError"
                          ? "Backend URL not configured. Set VITE_API_BASE_URL in Vercel environment variables."
                          : (error?.message || "Unknown error fetching documents.")}
                      </span>
                      <button
                        onClick={() => refetch()}
                        className="mt-1 px-3 py-1.5 border border-rose-500/40 text-rose-500 rounded-[2px] hover:bg-rose-500/10 transition-colors text-[10px] font-mono uppercase tracking-wider"
                      >
                        RETRY
                      </button>
                    </div>
                  </TableCell>
                </TableRow>
              ) : documents.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} className="text-center py-8 font-mono text-xs text-[var(--text-muted)]">
                    NO DOCUMENTS UPLOADED YET. UPLOAD A PDF OR TEXT DOCUMENT TO BEGIN RETRIEVAL.
                  </TableCell>
                </TableRow>
              ) : (
                documents.map((doc) => (
                  <TableRow key={doc.id} className="text-xs font-mono border-b border-[var(--panel-border)] hover:bg-[var(--panel-inner)] transition-colors">
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-2 cursor-pointer group" onClick={() => setSelectedDoc(doc)}>
                        <FileText className="h-4 w-4 text-[var(--accent-amber)] shrink-0"/>
                        <span className="truncate max-w-[200px] text-[var(--text-primary)] group-hover:text-[var(--accent-amber)] transition-colors" title={doc.originalFilename}>
                          {doc.originalFilename}
                        </span>
                        {getFormatBadge(doc)}
                      </div>
                    </TableCell>
                    <TableCell>{getStatusBadge(doc.processingStatus)}</TableCell>
                    <TableCell>{getIndexBadge(doc.indexStatus, doc.processingStatus)}</TableCell>
                    <TableCell className="font-mono text-[var(--text-secondary)]">{doc.chunkCount || 0}</TableCell>
                    <TableCell className="font-mono text-[var(--text-secondary)]">{doc.pageCount ? `${doc.pageCount} pgs` : "—"}</TableCell>
                    <TableCell className="text-[var(--text-muted)]">
                      {(doc.size / 1024).toFixed(1)} KB
                    </TableCell>
                    <TableCell className="text-[var(--text-muted)]">
                      {new Date(doc.uploadedAt).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="text-right space-x-1">
                      {(() => {
                        const isAttached = attachedSources.some(
                          (s) => (s.id || s.document_id || s.documentId) === doc.id
                        );
                        return (
                          <Button
                            variant="ghost"
                            size="sm"
                            className={`h-7 px-2 rounded-[2px] transition-colors ${
                              isAttached
                                ? "text-emerald-500 bg-emerald-500/10 hover:bg-emerald-500/20"
                                : "text-[var(--text-muted)] hover:text-[#f97316] hover:bg-[#f97316]/10"
                            }`}
                            onClick={() => {
                              if (isAttached) {
                                detachSource(doc.id);
                                toast.info(`Removed "${doc.originalFilename}" from chat sources.`);
                              } else {
                                attachSource(doc);
                                toast.success(`Attached "${doc.originalFilename}" to current chat.`);
                              }
                            }}
                            title={isAttached ? "Attached to current chat (click to detach)" : "Attach to current chat"}
                          >
                            {isAttached ? (
                              <Check className="h-3.5 w-3.5 text-emerald-500" />
                            ) : (
                              <Paperclip className="h-3.5 w-3.5" />
                            )}
                          </Button>
                        );
                      })()}
                      <Button variant="ghost" size="sm" className="h-7 px-2 text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--panel-bg)] rounded-[2px]" onClick={() => setSelectedDoc(doc)} title="Document Details">
                        <Info className="h-3.5 w-3.5"/>
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 px-2 text-[var(--accent-amber)] hover:text-[var(--accent-amber-light)] hover:bg-[var(--accent-amber)]/10 rounded-[2px]"
                        onClick={() => {
                          const docPayload = {
                            id: doc.id,
                            documentId: doc.id,
                            documentTitle: doc.originalFilename,
                            originalFilename: doc.originalFilename,
                            mimeType: doc.mimeType,
                            pageNumber: 1,
                            source: doc.originalFilename,
                          };
                          if (setActiveDocument) setActiveDocument(docPayload);
                          else setPdfSource(docPayload);
                        }}
                        title={`View ${doc.originalFilename}`}
                      >
                        <ExternalLink className="h-3.5 w-3.5"/>
                      </Button>
                      <Button variant="ghost" size="sm" className="h-7 px-2 text-[var(--accent-cyan)] hover:text-[var(--accent-cyan-light)] hover:bg-cyan-500/10 rounded-[2px]" onClick={() => handleReindex(doc)} disabled={reindexingId === doc.id} title="Re-index Document">
                        <RefreshCw className={`h-3.5 w-3.5 ${reindexingId === doc.id ? "animate-spin text-[var(--accent-cyan)]" : ""}`}/>
                      </Button>
                      <Button variant="ghost" size="sm" className="h-7 px-2 text-rose-600 dark:text-rose-400 hover:text-rose-700 dark:hover:text-rose-300 hover:bg-rose-500/10 rounded-[2px]" onClick={() => handleDelete(doc)} title="Delete Document">
                        <Trash2 className="h-3.5 w-3.5"/>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Document Details Dialog */}
      <Dialog open={!!selectedDoc} onOpenChange={(open) => !open && setSelectedDoc(null)}>
        <DialogContent className="max-w-md border-[var(--panel-border)] bg-[var(--panel-bg)]">
          <DialogHeader>
            <DialogTitle className="font-mono text-sm font-bold uppercase tracking-wider text-[var(--text-primary)] flex items-center gap-2">
              <FileText className="h-4 w-4 text-[var(--accent-amber)]"/>
              DOCUMENT_METADATA_HUD
            </DialogTitle>
            <DialogDescription className="font-mono text-xs text-[var(--text-muted)] truncate">
              {selectedDoc?.originalFilename}
            </DialogDescription>
          </DialogHeader>

          {selectedDoc && (
            <div className="space-y-3 py-2 font-mono text-xs border-y border-[var(--panel-border)]">
              <div className="flex justify-between">
                <span className="text-[var(--text-muted)]">DOCUMENT ID:</span>
                <span className="text-[var(--text-primary)] select-all">{selectedDoc.id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--text-muted)]">OWNER / TENANT:</span>
                <span className="text-[var(--accent-amber)]">{selectedDoc.ownerId || selectedDoc.owner_id || "dev-user"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--text-muted)]">INGESTION STATUS:</span>
                <span>{getStatusBadge(selectedDoc.processingStatus)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--text-muted)]">INDEX STATUS:</span>
                <span>{getIndexBadge(selectedDoc.indexStatus, selectedDoc.processingStatus)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--text-muted)]">SEARCHABLE IN PIPELINE:</span>
                <span className="text-emerald-500 font-bold flex items-center gap-1">
                  <ShieldCheck className="h-3.5 w-3.5"/>
                  YES (HOT IN-MEMORY VECTOR STORE)
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--text-muted)]">PAGES EXTRACTED:</span>
                <span className="text-[var(--text-primary)]">
                  {selectedDoc.pageCount && (selectedDoc.mimeType === "application/pdf" || (selectedDoc.originalFilename || "").toLowerCase().endsWith(".pdf"))
                    ? `${selectedDoc.pageCount} pages`
                    : "N/A (Structured Document)"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--text-muted)]">TEXT CHUNKS:</span>
                <span className="text-[var(--text-primary)]">{selectedDoc.chunkCount || 0} indexed chunks</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--text-muted)]">FILE SIZE:</span>
                <span className="text-[var(--text-primary)]">{(selectedDoc.size / 1024).toFixed(1)} KB</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--text-muted)]">UPLOADED AT:</span>
                <span className="text-[var(--text-primary)]">{new Date(selectedDoc.uploadedAt).toLocaleString()}</span>
              </div>
            </div>
          )}

          <DialogFooter className="flex justify-between sm:justify-between w-full">
            {selectedDoc && (() => {
              const isAttached = attachedSources.some(
                (s) => (s.id || s.document_id || s.documentId) === selectedDoc.id
              );
              return (
                <Button
                  size="sm"
                  variant="outline"
                  className={`font-mono text-xs mr-2 ${
                    isAttached
                      ? "border-emerald-500/40 text-emerald-500 hover:bg-emerald-500/10"
                      : "border-[#f97316]/40 text-[#f97316] hover:bg-[#f97316]/10"
                  }`}
                  onClick={() => {
                    if (isAttached) {
                      detachSource(selectedDoc.id);
                      toast.info(`Removed "${selectedDoc.originalFilename}" from chat sources.`);
                    } else {
                      attachSource(selectedDoc);
                      toast.success(`Attached "${selectedDoc.originalFilename}" to current chat.`);
                    }
                  }}
                >
                  <Paperclip className="h-3.5 w-3.5 mr-1" />
                  {isAttached ? "DETACH FROM CHAT" : "ATTACH TO CHAT"}
                </Button>
              );
            })()}
            {selectedDoc && (
              <Button size="sm" variant="outline" className="font-mono text-xs border-[var(--accent-amber)]/40 text-[var(--accent-amber)] hover:bg-[var(--accent-amber)]/10" onClick={() => {
                const docPayload = {
                  id: selectedDoc.id,
                  documentId: selectedDoc.id,
                  documentTitle: selectedDoc.originalFilename,
                  originalFilename: selectedDoc.originalFilename,
                  mimeType: selectedDoc.mimeType,
                  chunkId: "",
                  authors: "",
                  year: 2026,
                  source: selectedDoc.originalFilename,
                  chunkIndex: 0,
                  chunkContent: "",
                  score: 1,
                  pageNumber: 1,
                };
                if (setActiveDocument) setActiveDocument(docPayload);
                else setPdfSource(docPayload);
                setSelectedDoc(null);
              }}>
                <ExternalLink className="h-3.5 w-3.5 mr-1"/>
                OPEN VIEWER
              </Button>
            )}
            {selectedDoc && (
              <Button size="sm" variant="outline" className="font-mono text-xs border-cyan-500/40 text-[var(--accent-cyan)] hover:bg-cyan-500/10 mr-2" onClick={() => handleReindex(selectedDoc)} disabled={reindexingId === selectedDoc.id}>
                <RefreshCw className={`h-3.5 w-3.5 mr-1 ${reindexingId === selectedDoc.id ? "animate-spin" : ""}`}/>
                RE-INDEX
              </Button>
            )}
            {selectedDoc && (
              <Button size="sm" variant="outline" className="font-mono text-xs border-rose-500/40 text-rose-500 hover:bg-rose-500/10 mr-2" onClick={() => {
                const toDel = selectedDoc;
                setSelectedDoc(null);
                setDocToDelete(toDel);
              }}>
                <Trash2 className="h-3.5 w-3.5 mr-1"/>
                DELETE
              </Button>
            )}
            <Button size="sm" variant="secondary" className="font-mono text-xs ml-auto" onClick={() => setSelectedDoc(null)}>
              CLOSE
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!docToDelete} onOpenChange={(open) => !open && setDocToDelete(null)}>
        <DialogContent className="max-w-md border-[var(--panel-border)] bg-[var(--panel-bg)]">
          <DialogHeader>
            <DialogTitle className="font-mono text-sm font-bold uppercase tracking-wider text-rose-500 flex items-center gap-2">
              <Trash2 className="h-4 w-4 text-rose-500"/>
              CONFIRM_DOCUMENT_DELETION
            </DialogTitle>
            <DialogDescription className="font-mono text-xs text-[var(--text-muted)] truncate">
              {docToDelete?.originalFilename}
            </DialogDescription>
          </DialogHeader>

          <div className="py-3 font-mono text-xs text-[var(--text-secondary)] space-y-2 border-y border-[var(--panel-border)]">
            <p>
              Are you sure you want to delete <span className="text-[var(--text-primary)] font-bold">"{docToDelete?.originalFilename}"</span>?
            </p>
            <p className="text-[11px] text-[var(--text-muted)]">
              This will permanently remove the document file from disk storage, purge all {docToDelete?.chunkCount || 0} text chunks from the active vector index, and invalidate any cached summaries.
            </p>
          </div>

          <DialogFooter className="flex justify-end gap-2 w-full pt-2">
            <Button
              size="sm"
              variant="secondary"
              className="font-mono text-xs"
              onClick={() => setDocToDelete(null)}
              disabled={deleteMutation.isPending}
            >
              CANCEL
            </Button>
            <Button
              size="sm"
              variant="destructive"
              className="font-mono text-xs bg-rose-600 hover:bg-rose-700 text-white flex items-center gap-1.5"
              onClick={confirmDelete}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin"/>
                  DELETING...
                </>
              ) : (
                <>
                  <Trash2 className="h-3.5 w-3.5"/>
                  DELETE DOCUMENT
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Contextual Password Dialog for Encrypted PDFs */}
      <PdfPasswordDialog
        isOpen={isPasswordModalOpen}
        file={pendingEncryptedFile}
        errorMessage={pdfPasswordError}
        isProcessing={isDecrypting}
        onSubmit={handlePasswordSubmit}
        onCancel={() => {
          setIsPasswordModalOpen(false);
          setPendingEncryptedFile(null);
          setPdfPasswordError("");
        }}
      />
    </div>
  );
}
