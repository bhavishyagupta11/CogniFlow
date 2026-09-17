import { create } from "zustand";
import { persist } from "zustand/middleware";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/+$/, "");

function resolveUrl(path) {
  if (!API_BASE_URL || /^https?:\/\//i.test(path)) {
    return path;
  }
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

export const useAuthStore = create()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      isAuthenticated: false,
      userId: "dev-user",
      accessKey: "rc3-eval-key",

      setAccessKey: (accessKey) => set({ accessKey }),

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
        return data.user;
      },

      logout: async () => {
        try {
          await fetch(resolveUrl("/api/auth/logout"), { method: "POST" });
        } catch {
          // Ignore network errors on logout
        }
        set({
          token: null,
          user: null,
          isAuthenticated: false,
          userId: "dev-user",
        });
      },

      checkAuth: async () => {
        const token = get().token;
        if (!token) return null;
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
            set({ token: null, user: null, isAuthenticated: false, userId: "dev-user" });
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
        accessKey: state.accessKey,
      }),
    }
  )
);
