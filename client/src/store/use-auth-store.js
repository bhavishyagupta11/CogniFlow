import { create } from "zustand";
import { persist } from "zustand/middleware";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/+$/, "");

function resolveUrl(path) {
  if (!API_BASE_URL || /^https?:\/\//i.test(path)) {
    return path;
  }
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

function getStoredSessionId() {
  try {
    if (typeof window !== "undefined") {
      const urlParams = new URLSearchParams(window.location.search);
      const urlSession = urlParams.get("session_id") || urlParams.get("sessionId") || urlParams.get("guest_session_id");
      if (urlSession) {
        sessionStorage.setItem("cogniflow_guest_session_id", urlSession);
        return urlSession;
      }
    }
    return sessionStorage.getItem("cogniflow_guest_session_id") || null;
  } catch {
    return null;
  }
}

function setStoredSessionId(id) {
  try {
    if (id) {
      sessionStorage.setItem("cogniflow_guest_session_id", id);
    } else {
      sessionStorage.removeItem("cogniflow_guest_session_id");
    }
  } catch {
    // Ignore storage quota errors
  }
}

export const useAuthStore = create()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      isAuthenticated: false,
      userId: null,
      sessionId: getStoredSessionId(),

      setSessionId: (sessionId) => {
        setStoredSessionId(sessionId);
        set({ sessionId });
      },

      initGuestSession: async () => {
        try {
          const currentSessionId = get().sessionId || getStoredSessionId();
          const headers = currentSessionId ? { "x-session-id": currentSessionId } : {};
          const res = await fetch(resolveUrl("/api/auth/guest-session"), { headers });
          if (res.ok) {
            const data = await res.json();
            if (data.sessionId) {
              get().setSessionId(data.sessionId);
              return data.sessionId;
            }
          }
        } catch {
          // Network errors fallback gracefully
        }
        return null;
      },

      migrateGuestSession: async () => {
        const { token, sessionId } = get();
        if (!token || !sessionId) return null;
        try {
          const res = await fetch(resolveUrl("/api/auth/migrate-guest-session"), {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
              "x-session-id": sessionId,
            },
            body: JSON.stringify({ session_id: sessionId }),
          });
          if (res.ok) {
            const data = await res.json();
            return data;
          }
        } catch {
          // Failure will preserve guest session for retry
        }
        return null;
      },

      login: async (email, password) => {
        const res = await fetch(resolveUrl("/api/auth/login"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.detail || "Authentication failed. Please check credentials.");
        }
        set({
          token: data.token,
          user: data.user,
          userId: data.user.id,
          isAuthenticated: true,
        });

        // Migrate guest session if one was active
        await get().migrateGuestSession();
        return data.user;
      },

      register: async (name, email, password, confirmPassword) => {
        const res = await fetch(resolveUrl("/api/auth/register"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name,
            email,
            password,
            confirm_password: confirmPassword,
          }),
        });
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.detail || "Registration failed.");
        }
        set({
          token: data.token,
          user: data.user,
          userId: data.user.id,
          isAuthenticated: true,
        });

        // Migrate guest session if one was active
        await get().migrateGuestSession();
        return data.user;
      },

      logout: async () => {
        try {
          await fetch(resolveUrl("/api/auth/logout"), { method: "POST" });
        } catch {
          // Ignore network errors on logout
        }
        setStoredSessionId(null);
        set({
          token: null,
          user: null,
          isAuthenticated: false,
          userId: null,
          sessionId: null,
        });
        // Request a fresh server-issued guest session for future unauthenticated use
        get().initGuestSession();
      },

      checkAuth: async () => {
        const token = get().token;
        if (!token) {
          // Ensure a guest session is initialized
          if (!get().sessionId) {
            get().initGuestSession();
          }
          return null;
        }
        try {
          const res = await fetch(resolveUrl("/api/auth/me"), {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (res.ok) {
            const data = await res.json();
            set({
              user: data.user,
              userId: data.user.id,
              isAuthenticated: true,
            });
            return data.user;
          } else {
            // Token expired or invalid
            set({ token: null, user: null, isAuthenticated: false, userId: null });
            get().initGuestSession();
            return null;
          }
        } catch {
          return null;
        }
      },

      clearAuth: () => {
        get().logout();
      },
    }),
    {
      name: "cogniflow-auth-store",
      partialize: (state) => ({
        token: state.token,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
        userId: state.userId,
      }),
    }
  )
);
