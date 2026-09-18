import { apiFetch } from "./client";
import { safeParseSSEEvent } from "../lib/types";

export async function streamChatQuery({ question, onEvent, signal, mode, conversationId, sourceDocumentIds }) {
    const res = await apiFetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            question,
            mode,
            conversation_id: conversationId,
            conversationId: conversationId,
            source_document_ids: sourceDocumentIds,
            sourceDocumentIds: sourceDocumentIds,
        }),
        signal,
    });
    if (!res.ok) {
        if (res.status === 402) {
            throw new Error("HTTP 402: Insufficient quota or billing limit reached");
        }
        if (res.status === 429) {
            throw new Error("HTTP 429: Rate limit exceeded. Automatic retry was attempted.");
        }
        throw new Error(`HTTP ${res.status}: Failed to execute chat query`);
    }
    const reader = res.body?.getReader();
    if (!reader) {
        throw new Error("No readable stream received from server");
    }
    const decoder = new TextDecoder();
    let buffer = "";
    try {
        while (true) {
            const { done, value } = await reader.read();
            if (done)
                break;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop() || "";
            for (const line of lines) {
                const trimmed = line.trim();
                if (!trimmed || !trimmed.startsWith("data: "))
                    continue;
                const event = safeParseSSEEvent(trimmed);
                if (event) {
                    onEvent(event);
                }
            }
        }
        if (buffer.trim().startsWith("data: ")) {
            const event = safeParseSSEEvent(buffer.trim());
            if (event) {
                onEvent(event);
            }
        }
    }
    finally {
        reader.releaseLock();
    }
}

export async function apiListConversations() {
    const res = await apiFetch("/api/chats");
    if (!res.ok) {
        throw new Error(`Failed to load conversations (${res.status})`);
    }
    return res.json();
}

export async function apiCreateConversation(data = {}) {
    const res = await apiFetch("/api/chats", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });
    if (!res.ok) {
        throw new Error(`Failed to create conversation (${res.status})`);
    }
    return res.json();
}

export async function apiGetConversation(convId) {
    const res = await apiFetch(`/api/chats/${convId}`);
    if (!res.ok) {
        throw new Error(`Failed to get conversation (${res.status})`);
    }
    return res.json();
}

export async function apiDeleteConversation(convId) {
    const res = await apiFetch(`/api/chats/${convId}`, {
        method: "DELETE",
    });
    if (!res.ok) {
        throw new Error(`Failed to delete conversation (${res.status})`);
    }
    return res.json();
}

export async function apiSaveMessage(convId, { role, content, metadata }) {
    const res = await apiFetch(`/api/chats/${convId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role, content, metadata }),
    });
    if (!res.ok) {
        throw new Error(`Failed to save message (${res.status})`);
    }
    return res.json();
}

export async function apiGetConversationSources(convId) {
    const res = await apiFetch(`/api/chats/${convId}/sources`);
    if (!res.ok) {
        throw new Error(`Failed to get conversation sources (${res.status})`);
    }
    return res.json();
}

export async function apiAttachConversationSource(convId, documentId) {
    const res = await apiFetch(`/api/chats/${convId}/sources`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ document_id: documentId, documentId }),
    });
    if (!res.ok) {
        throw new Error(`Failed to attach conversation source (${res.status})`);
    }
    return res.json();
}

export async function apiDetachConversationSource(convId, documentId) {
    const res = await apiFetch(`/api/chats/${convId}/sources/${documentId}`, {
        method: "DELETE",
    });
    if (!res.ok) {
        throw new Error(`Failed to detach conversation source (${res.status})`);
    }
    return res.json();
}

