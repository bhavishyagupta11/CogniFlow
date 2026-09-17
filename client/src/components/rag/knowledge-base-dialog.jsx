import { useState, useEffect, useRef, useCallback } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "sonner";
import { UploadCloud, Trash2, FileText, Loader2, CheckCircle2, AlertCircle, RefreshCw } from "lucide-react";
import { useAuthStore } from "@/store/use-auth-store";
export function KnowledgeBaseDialog({ open, onOpenChange, onDocumentsChanged }) {
    const [documents, setDocuments] = useState([]);
    const [isDragging, setIsDragging] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const authAccessKey = useAuthStore((s) => s.accessKey);
    const [accessKey, setAccessKey] = useState(authAccessKey);
    const fileInputRef = useRef(null);
    const fetchDocuments = useCallback(async () => {
        try {
            const res = await fetch("/api/documents");
            if (res.ok) {
                const data = await res.json();
                setDocuments(data);
                if (onDocumentsChanged) {
                    onDocumentsChanged();
                }
            }
        }
        catch (e) {
            console.error("Failed to fetch documents", e);
        }
    }, [onDocumentsChanged]);
    useEffect(() => {
        if (open) {
            // eslint-disable-next-line react-hooks/set-state-in-effect
            fetchDocuments();
        }
    }, [open, fetchDocuments]);
    // Polling for processing documents
    useEffect(() => {
        if (!open)
            return;
        const hasProcessing = documents.some(d => !["completed", "failed"].includes(d.processingStatus));
        if (!hasProcessing)
            return;
        const interval = setInterval(fetchDocuments, 2000);
        return () => clearInterval(interval);
    }, [documents, open, fetchDocuments]);
    const handleDragOver = (e) => {
        e.preventDefault();
        setIsDragging(true);
    };
    const handleDragLeave = (e) => {
        e.preventDefault();
        setIsDragging(false);
    };
    const handleDrop = async (e) => {
        e.preventDefault();
        setIsDragging(false);
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            await handleFiles(Array.from(e.dataTransfer.files));
        }
    };
    const handleFileInput = async (e) => {
        if (e.target.files && e.target.files.length > 0) {
            await handleFiles(Array.from(e.target.files));
        }
        if (fileInputRef.current)
            fileInputRef.current.value = "";
    };
    const getOrPromptKey = () => {
        if (accessKey)
            return accessKey;
        const key = window.prompt("This action requires an access key. Please enter it:");
        if (key)
            setAccessKey(key);
        return key;
    };
    const handleFiles = async (files) => {
        const key = getOrPromptKey();
        if (!key)
            return;
        setIsUploading(true);
        try {
            const formData = new FormData();
            files.forEach(f => formData.append("file", f));
            const res = await fetch("/api/documents", {
                method: "POST",
                headers: { "x-access-key": key },
                body: formData
            });
            if (res.status === 401)
                setAccessKey("");
            const data = await res.json();
            if (!res.ok) {
                toast.error(data.error?.message || "Upload failed");
            }
            else {
                data.results.forEach((result) => {
                    if (result.status === 409) {
                        toast.error(result.error.message);
                    }
                    else if (result.status === 201) {
                        toast.success(`${result.document.originalFilename} uploaded.`);
                    }
                    else if (result.error) {
                        toast.error(result.error.message);
                    }
                });
            }
            await fetchDocuments();
        }
        catch (err) {
            toast.error(err.message || "Upload failed due to network error.");
        }
        finally {
            setIsUploading(false);
        }
    };
    const handleDelete = async (id) => {
        const key = getOrPromptKey();
        if (!key)
            return;
        if (!confirm("Are you sure you want to delete this document? It will be removed from the vector store."))
            return;
        try {
            const res = await fetch(`/api/documents/${id}`, {
                method: "DELETE",
                headers: { "x-access-key": key }
            });
            if (res.status === 401)
                setAccessKey("");
            if (!res.ok) {
                const data = await res.json();
                toast.error(data.error?.message || "Failed to delete document.");
                return;
            }
            toast.success("Document deleted.");
            await fetchDocuments();
        }
        catch (err) {
            toast.error(err.message || "Failed to delete document.");
        }
    };
    const getStatusIcon = (status) => {
        switch (status) {
            case "completed": return <CheckCircle2 className="h-3.5 w-3.5 text-[var(--accent-emerald)]"/>;
            case "failed": return <AlertCircle className="h-3.5 w-3.5 text-rose-400"/>;
            default: return <Loader2 className="h-3.5 w-3.5 animate-spin text-[var(--accent-amber)]"/>;
        }
    };
    const getStatusText = (status) => {
        switch (status) {
            case "queued": return "QUEUED";
            case "uploading": return "UPLOADING";
            case "extracting": return "EXTRACTING";
            case "chunking": return "CHUNKING";
            case "embedding": return "EMBEDDING";
            case "indexing": return "INDEXING";
            case "completed": return "READY";
            case "failed": return "FAILED";
        }
    };
    return (<Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="rounded-[4px] border border-[var(--panel-border)] bg-[var(--panel-bg)] text-[var(--text-primary)] max-w-4xl max-h-[85vh] flex flex-col shadow-2xl">
        <DialogHeader className="border-b border-[var(--panel-border)] pb-3">
          <DialogTitle className="font-mono text-sm font-bold uppercase tracking-wider text-[var(--text-primary)]">KNOWLEDGE_BASE_INGESTION</DialogTitle>
          <DialogDescription className="font-mono text-xs text-[var(--text-muted)]">
            Upload documents to expand the retrieval index. Supported formats: PDF, DOCX, TXT, MD.
          </DialogDescription>
        </DialogHeader>
        
        <div className={`mt-4 flex-shrink-0 flex flex-col items-center justify-center p-6 border-2 border-dashed rounded-[4px] transition-colors ${isDragging ? "border-[var(--accent-amber)] bg-[var(--accent-amber)]/10" : "border-[var(--panel-border)] bg-[var(--panel-inner)] hover:border-[var(--accent-amber)]/60"}`} onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop}>
          <UploadCloud className="h-8 w-8 text-[var(--accent-amber)] mb-2"/>
          <p className="font-mono text-xs font-bold uppercase tracking-wider text-[var(--text-primary)] mb-1">DRAG & DROP FILES HERE</p>
          <p className="font-mono text-[10px] text-[var(--text-muted)] mb-3">MAXIMUM FILE SIZE: 25MB</p>
          <input type="file" ref={fileInputRef} className="hidden" multiple accept=".pdf,.docx,.txt,.md" onChange={handleFileInput}/>
          <Button onClick={() => fileInputRef.current?.click()} disabled={isUploading} size="sm" className="rounded-[2px] font-mono text-xs bg-[var(--accent-amber)] text-black font-bold uppercase hover:bg-[var(--accent-amber-light)] cursor-pointer">
            {isUploading ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5"/> : null}
            BROWSE FILES
          </Button>
        </div>

        <div className="flex items-center justify-between mt-4 mb-2">
          <h3 className="font-mono text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">INDEXED DOCUMENTS</h3>
          <Button variant="ghost" size="sm" onClick={fetchDocuments} className="rounded-[2px] font-mono text-xs text-[var(--text-muted)] hover:text-[var(--accent-amber)] hover:bg-[var(--accent-amber)]/10">
            <RefreshCw className="h-3.5 w-3.5 mr-1"/>
            REFRESH
          </Button>
        </div>

        <div className="flex-1 border border-[var(--panel-border)] rounded-[4px] min-h-[200px] overflow-auto bg-[var(--panel-inner)]">
          <Table>
            <TableHeader className="bg-[var(--panel-bg)] sticky top-0 border-b border-[var(--panel-border)]">
              <TableRow className="text-[10px] font-mono uppercase tracking-wider text-[var(--text-muted)]">
                <TableHead>FILE NAME</TableHead>
                <TableHead>SIZE</TableHead>
                <TableHead>DATE</TableHead>
                <TableHead className="min-w-[150px]">STATUS</TableHead>
                <TableHead className="text-right">ACTIONS</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {documents.length === 0 ? (<TableRow>
                  <TableCell colSpan={5} className="text-center h-24 font-mono text-xs text-[var(--text-muted)]">
                    NO DOCUMENTS UPLOADED YET.
                  </TableCell>
                </TableRow>) : (documents.map((doc) => (<TableRow key={doc.id} className="font-mono text-xs border-b border-[var(--panel-border)] hover:bg-[var(--panel-bg)] transition-colors">
                    <TableCell className="font-medium flex items-center gap-2">
                      <FileText className="h-3.5 w-3.5 text-[var(--accent-amber)] flex-shrink-0"/>
                      <span className="truncate text-[var(--text-primary)]">{doc.originalFilename}</span>
                    </TableCell>
                    <TableCell className="text-[var(--text-secondary)]">{(doc.size / 1024 / 1024).toFixed(2)} MB</TableCell>
                    <TableCell className="text-[var(--text-muted)]">{new Date(doc.uploadedAt).toLocaleDateString()}</TableCell>
                    <TableCell>
                      <div className="flex flex-col gap-1">
                        <div className="flex items-center gap-1.5 text-xs">
                          {getStatusIcon(doc.processingStatus)}
                          <span className={doc.processingStatus === "failed" ? "text-rose-400" : "text-[var(--text-secondary)]"}>
                            {getStatusText(doc.processingStatus)}
                          </span>
                        </div>
                        {doc.processingStatus === "failed" && doc.errorMessage && (<div className="text-[10px] text-rose-400 max-w-[200px] truncate" title={doc.errorMessage}>
                            {doc.errorMessage}
                          </div>)}
                        {!["completed", "failed", "queued"].includes(doc.processingStatus) && (<Progress value={undefined} className="h-1 w-full mt-1 bg-[var(--panel-border)]"/>)}
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm" className="h-7 px-2 text-rose-400 hover:text-rose-300 hover:bg-rose-950/40 rounded-[2px]" onClick={() => handleDelete(doc.id)}>
                        <Trash2 className="h-3.5 w-3.5"/>
                      </Button>
                    </TableCell>
                  </TableRow>)))}
            </TableBody>
          </Table>
        </div>
      </DialogContent>
    </Dialog>);
}
