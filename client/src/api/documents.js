import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./client";
export const DOCUMENTS_QUERY_KEY = ["documents"];
export async function fetchDocuments() {
    const res = await apiFetch("/api/documents");
    if (!res.ok) {
        throw new Error(`Failed to fetch documents: ${res.statusText}`);
    }
    return res.json();
}
export async function uploadDocument(file, key) {
    const formData = new FormData();
    formData.append("file", file);
    const headers = {};
    if (key) {
        headers["x-access-key"] = key;
    }
    const res = await apiFetch("/api/documents", {
        method: "POST",
        headers,
        body: formData,
    });
    if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        const msg = errorData.error?.message || errorData.error || errorData.detail || `Upload failed with status ${res.status}`;
        throw new Error(msg);
    }
    const data = await res.json();
    return data.document || data;
}
export async function deleteDocument(id, key) {
    const headers = {};
    if (key) {
        headers["x-access-key"] = key;
    }
    const res = await apiFetch(`/api/documents/${id}`, {
        method: "DELETE",
        headers,
    });
    if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        const msg = errorData.error?.message || errorData.error || errorData.detail || `Deletion failed with status ${res.status}`;
        throw new Error(msg);
    }
    return res.json();
}
export function useDocumentsQuery() {
    return useQuery({
        queryKey: DOCUMENTS_QUERY_KEY,
        queryFn: fetchDocuments,
        refetchInterval: (query) => {
            // Auto-poll every 2s if any document is processing
            const docs = query.state.data;
            if (Array.isArray(docs) && docs.some((d) => !["completed", "failed"].includes(d.processingStatus))) {
                return 2000;
            }
            return false;
        },
    });
}
export function useUploadDocumentMutation() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ file, key }) => uploadDocument(file, key),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: DOCUMENTS_QUERY_KEY });
        },
    });
}
export function useDeleteDocumentMutation() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ id, key }) => deleteDocument(id, key),
        onSuccess: (_data, variables) => {
            queryClient.setQueryData(DOCUMENTS_QUERY_KEY, (old = []) => {
                if (!Array.isArray(old)) return [];
                return old.filter((d) => d.id !== variables.id && d.document_id !== variables.id);
            });
            queryClient.invalidateQueries({ queryKey: DOCUMENTS_QUERY_KEY });
        },
    });
}

export async function reindexDocument(id, key) {
    const headers = {};
    if (key) {
        headers["x-access-key"] = key;
    }
    const res = await apiFetch(`/api/documents/${id}/reindex`, {
        method: "POST",
        headers,
    });
    if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        const msg = errorData.error?.message || errorData.error || errorData.detail || `Re-indexing failed with status ${res.status}`;
        throw new Error(msg);
    }
    return res.json();
}

export function useReindexDocumentMutation() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ id, key }) => reindexDocument(id, key),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: DOCUMENTS_QUERY_KEY });
        },
    });
}

