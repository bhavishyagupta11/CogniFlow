import { apiFetch } from "./client";
import { safeParseSSEEvent } from "../lib/types";
export async function streamChatQuery({ question, onEvent, signal, mode }) {
    const res = await apiFetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, mode }),
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
