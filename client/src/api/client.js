import { useAuthStore } from "../store/use-auth-store";

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/+$/, "");

// Warn loudly in development when VITE_API_BASE_URL is not set.
// In production this causes Vercel's SPA catch-all to intercept every /api/*
// request and silently return index.html (text/html) instead of JSON.
if (import.meta.env.DEV && !API_BASE_URL) {
    console.warn(
        "[CogniFlow] VITE_API_BASE_URL is not set.\n" +
        "API requests will use relative URLs — this only works in development via the Vite proxy.\n" +
        "In production (Vercel) you MUST set VITE_API_BASE_URL to your Render backend URL."
    );
}

/** Thrown when the backend returns text/html instead of JSON (Vercel SPA catch-all misconfiguration). */
export class ApiConfigError extends Error {
    constructor(message = "Backend API URL not configured. Set VITE_API_BASE_URL to your Render backend URL.") {
        super(message);
        this.name = "ApiConfigError";
        this.code = "API_NOT_CONFIGURED";
    }
}

export function resolveApiUrl(path) {
    if (!API_BASE_URL || /^https?:\/\//i.test(path)) {
        return path;
    }
    return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

/**
 * Guards a Response object against the Vercel SPA misconfiguration scenario:
 * when VITE_API_BASE_URL is missing, /api/* requests hit the Vercel catch-all
 * rewrite and return index.html (200 text/html).  Calling .json() on that
 * produces a cryptic "Unexpected token '<'" SyntaxError.  This guard detects
 * the condition early and throws a descriptive ApiConfigError instead.
 */
export function assertJsonResponse(res) {
    const ct = res.headers.get("Content-Type") || "";
    if (ct.includes("text/html")) {
        throw new ApiConfigError();
    }
}

export async function apiFetch(path, options = {}) {
    const { token, sessionId } = useAuthStore.getState();
    const headers = new Headers(options.headers || {});

    if (token && !headers.has("Authorization")) {
        headers.set("Authorization", `Bearer ${token}`);
    } else if (sessionId && !headers.has("x-session-id")) {
        headers.set("x-session-id", sessionId);
    }

    const res = await fetch(resolveApiUrl(path), {
        ...options,
        headers,
    });

    // Automatically recover from expired/invalid tokens by switching to guest session
    if (res.status === 401 && token) {
        useAuthStore.getState().logout();
    }

    // Capture server-issued guest session ID if unauthenticated
    const serverSessionId = res.headers.get("X-Session-ID");
    if (serverSessionId && !token && serverSessionId !== sessionId) {
        useAuthStore.getState().setSessionId(serverSessionId);
    }

    return res;
}

