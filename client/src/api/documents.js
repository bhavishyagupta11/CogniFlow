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

export async function uploadDocument(file, options = {}) {
    const formData = new FormData();
    formData.append("file", file);

    const password = typeof options === "string" ? null : options?.password;
    if (password) {
        formData.append("password", password);
    }

    const res = await apiFetch("/api/documents", {
        method: "POST",
        body: formData,
    });

    if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        const msg = errorData.error?.message || errorData.error || errorData.detail || `Upload failed with status ${res.status}`;
        const err = new Error(msg);
        err.code = errorData.error?.code || "UPLOAD_ERROR";
        err.status = res.status;
        err.file = file;
        throw err;
    }

    const data = await res.json();
    return data.document || data;
}

export async function deleteDocument(id) {
    const res = await apiFetch(`/api/documents/${id}`, {
        method: "DELETE",
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
            const docs = query.state.data;
            if (Array.isArray(docs) && docs.some((d) => !["completed", "failed", "indexed"].includes(d.processingStatus))) {
                return 2000;
            }
            return false;
        },
    });
}

export function useUploadDocumentMutation() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ file, password }) => uploadDocument(file, { password }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: DOCUMENTS_QUERY_KEY });
        },
    });
}

export function useDeleteDocumentMutation() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: ({ id }) => deleteDocument(id),
        onSuccess: (_data, variables) => {
            queryClient.setQueryData(DOCUMENTS_QUERY_KEY, (old = []) => {
                if (!Array.isArray(old)) return [];
                return old.filter((d) => d.id !== variables.id && d.document_id !== variables.id);
            });
            queryClient.invalidateQueries({ queryKey: DOCUMENTS_QUERY_KEY });
        },
    });
}

export async function reindexDocument(id) {
    const res = await apiFetch(`/api/documents/${id}/reindex`, {
        method: "POST",
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
        mutationFn: ({ id }) => reindexDocument(id),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: DOCUMENTS_QUERY_KEY });
        },
    });
}
