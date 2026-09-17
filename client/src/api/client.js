import { useAuthStore } from "../store/use-auth-store";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/+$/, "");

function resolveApiUrl(path) {
    if (!API_BASE_URL || /^https?:\/\//i.test(path)) {
        return path;
    }
    return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

export async function apiFetch(path, options = {}) {
    const { token, userId, accessKey } = useAuthStore.getState();
    const headers = new Headers(options.headers || {});
    if (token && !headers.has("Authorization")) {
        headers.set("Authorization", `Bearer ${token}`);
    }
    if (userId && !headers.has("x-user-id")) {
        headers.set("x-user-id", userId);
    }
    if (accessKey && !headers.has("x-access-key")) {
        headers.set("x-access-key", accessKey);
    }
    return fetch(resolveApiUrl(path), {
        ...options,
        headers,
    });
}
