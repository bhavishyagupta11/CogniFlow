"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { toast } from "sonner";
import { UploadCloud, Trash2, FileText, Loader2, CheckCircle2, AlertCircle, RefreshCw } from "lucide-react";

interface ManifestEntry {
  id: string;
  filename: string;
  originalFilename: string;
  mimeType: string;
  size: number;
  uploadedAt: string;
  processingStatus: "queued" | "uploading" | "extracting" | "chunking" | "embedding" | "indexing" | "completed" | "failed";
  errorMessage: string | null;
  chunkCount: number;
}

export function KnowledgeBaseDialog({ open, onOpenChange, onDocumentsChanged }: { open: boolean, onOpenChange: (open: boolean) => void, onDocumentsChanged?: () => void }) {
  const [documents, setDocuments] = useState<ManifestEntry[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [accessKey, setAccessKey] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  
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
    } catch (e) {
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
    if (!open) return;
    
    const hasProcessing = documents.some(d => !["completed", "failed"].includes(d.processingStatus));
    if (!hasProcessing) return;

    const interval = setInterval(fetchDocuments, 2000);
    return () => clearInterval(interval);
  }, [documents, open, fetchDocuments]);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      await handleFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleFileInput = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      await handleFiles(Array.from(e.target.files));
    }
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const getOrPromptKey = () => {
    if (accessKey) return accessKey;
    const key = window.prompt("This action requires an access key. Please enter it:");
    if (key) setAccessKey(key);
    return key;
  };

  const handleFiles = async (files: File[]) => {
    const key = getOrPromptKey();
    if (!key) return;

    setIsUploading(true);
    try {
      const formData = new FormData();
      files.forEach(f => formData.append("file", f));
      
      const res = await fetch("/api/documents", {
        method: "POST",
        headers: { "x-access-key": key },
        body: formData
      });
      
      if (res.status === 401) setAccessKey("");
      
      const data = await res.json();
      
      if (!res.ok) {
        toast.error(data.error?.message || "Upload failed");
      } else {
        data.results.forEach((result: any) => {
          if (result.status === 409) {
            toast.error(result.error.message);
          } else if (result.status === 201) {
            toast.success(`${result.document.originalFilename} uploaded.`);
          } else if (result.error) {
            toast.error(result.error.message);
          }
        });
      }
      
      await fetchDocuments();
    } catch (err: any) {
      toast.error(err.message || "Upload failed due to network error.");
    } finally {
      setIsUploading(false);
    }
  };

  const handleDelete = async (id: string) => {
    const key = getOrPromptKey();
    if (!key) return;

    if (!confirm("Are you sure you want to delete this document? It will be removed from the vector store.")) return;
    try {
      const res = await fetch(`/api/documents/${id}`, { 
        method: "DELETE",
        headers: { "x-access-key": key }
      });
      
      if (res.status === 401) setAccessKey("");

      if (!res.ok) {
        const data = await res.json();
        toast.error(data.error?.message || "Failed to delete document.");
        return;
      }
      toast.success("Document deleted.");
      await fetchDocuments();
    } catch (err: any) {
      toast.error(err.message || "Failed to delete document.");
    }
  };

  const getStatusIcon = (status: ManifestEntry["processingStatus"]) => {
    switch (status) {
      case "completed": return <CheckCircle2 className="h-4 w-4 text-emerald-500" />;
      case "failed": return <AlertCircle className="h-4 w-4 text-rose-500" />;
      default: return <Loader2 className="h-4 w-4 animate-spin text-violet-500" />;
    }
  };

  const getStatusText = (status: ManifestEntry["processingStatus"]) => {
    switch (status) {
      case "queued": return "Queued";
      case "uploading": return "Uploading";
      case "extracting": return "Extracting Text";
      case "chunking": return "Chunking";
      case "embedding": return "Generating Embeddings";
      case "indexing": return "Updating Vector Store";
      case "completed": return "Ready";
      case "failed": return "Failed";
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Knowledge Base</DialogTitle>
          <DialogDescription>
            Upload documents to expand the AI's searchable knowledge. Supported formats: PDF, DOCX, TXT, MD.
          </DialogDescription>
        </DialogHeader>
        
        <div 
          className={`mt-4 flex-shrink-0 flex flex-col items-center justify-center p-8 border-2 border-dashed rounded-lg transition-colors ${
            isDragging ? "border-violet-500 bg-violet-50" : "border-slate-200 bg-slate-50/50"
          }`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          <UploadCloud className="h-10 w-10 text-slate-400 mb-4" />
          <p className="text-sm text-slate-600 mb-2">Drag and drop files here</p>
          <p className="text-xs text-slate-400 mb-4">Maximum file size: 25MB</p>
          <input 
            type="file" 
            ref={fileInputRef}
            className="hidden" 
            multiple 
            accept=".pdf,.docx,.txt,.md" 
            onChange={handleFileInput}
          />
          <Button onClick={() => fileInputRef.current?.click()} disabled={isUploading}>
            {isUploading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
            Browse Files
          </Button>
        </div>

        <div className="flex items-center justify-between mt-6 mb-2">
          <h3 className="text-sm font-semibold">Uploaded Documents</h3>
          <Button variant="ghost" size="sm" onClick={fetchDocuments}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        </div>

        <div className="flex-1 border rounded-md min-h-[200px] overflow-auto">
          <Table>
            <TableHeader className="bg-slate-50 sticky top-0">
              <TableRow>
                <TableHead>File Name</TableHead>
                <TableHead>Size</TableHead>
                <TableHead>Date</TableHead>
                <TableHead className="min-w-[150px]">Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {documents.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center h-24 text-muted-foreground">
                    No documents uploaded yet.
                  </TableCell>
                </TableRow>
              ) : (
                documents.map((doc) => (
                  <TableRow key={doc.id}>
                    <TableCell className="font-medium flex items-center gap-2">
                      <FileText className="h-4 w-4 text-slate-400 flex-shrink-0" />
                      <span className="truncate">{doc.originalFilename}</span>
                    </TableCell>
                    <TableCell>{(doc.size / 1024 / 1024).toFixed(2)} MB</TableCell>
                    <TableCell>{new Date(doc.uploadedAt).toLocaleDateString()}</TableCell>
                    <TableCell>
                      <div className="flex flex-col gap-1">
                        <div className="flex items-center gap-2 text-sm">
                          {getStatusIcon(doc.processingStatus)}
                          <span className={doc.processingStatus === "failed" ? "text-rose-600" : ""}>
                            {getStatusText(doc.processingStatus)}
                          </span>
                        </div>
                        {doc.processingStatus === "failed" && doc.errorMessage && (
                          <div className="text-[10px] text-rose-500 max-w-[200px] truncate" title={doc.errorMessage}>
                            {doc.errorMessage}
                          </div>
                        )}
                        {!["completed", "failed", "queued"].includes(doc.processingStatus) && (
                          <Progress value={undefined} className="h-1 w-full mt-1" />
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm" className="text-rose-500 hover:text-rose-700 hover:bg-rose-50" onClick={() => handleDelete(doc.id)}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </DialogContent>
    </Dialog>
  );
}
