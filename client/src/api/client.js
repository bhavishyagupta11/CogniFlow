import { useAuthStore } from "../store/use-auth-store";

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/+$/, "");

export function resolveApiUrl(path) {
    if (!API_BASE_URL || /^https?:\/\//i.test(path)) {
        return path;
    }
    return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
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
