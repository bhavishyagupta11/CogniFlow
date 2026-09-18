import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import {
  apiListConversations,
  apiGetConversation,
  apiDeleteConversation,
  apiCreateConversation,
  apiGetConversationSources,
  apiAttachConversationSource,
  apiDetachConversationSource,
} from "@/api/chat";
import { useAuthStore } from "./use-auth-store";

function formatMissionDate() {
  const d = new Date();
  const months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];
  return `${months[d.getMonth()]} ${d.getDate()}`;
}

export const useChatStore = create()(
  persist(
    (set, get) => ({
      messages: [],
      input: "",
      loading: false,
      activeMode: "adaptive_rag", // 'fast' | 'adaptive_rag' | 'deep_research' | 'general_chat'
      activeMissionId: null,
      missions: [], // Array of { id, title, mode, createdAt, messages, lastMessagePreview }
      attachedSources: [], // Documents explicitly attached to this chat session

      setInput: (input) => set({ input }),
      setLoading: (loading) => set({ loading }),
      setActiveMode: (mode) => set({ activeMode: mode }),
      setAttachedSources: (sources) => set({ attachedSources: Array.isArray(sources) ? sources : [] }),

      fetchAttachedSources: async (convId) => {
        if (!convId) return;
        try {
          const res = await apiGetConversationSources(convId);
          if (res.ok && Array.isArray(res.sources)) {
            set({ attachedSources: res.sources });
          }
        } catch {
          // ignore
        }
      },

      attachSource: async (doc) => {
        if (!doc) return;
        const docId = doc.id || doc.document_id || doc.documentId;
        const current = get().attachedSources;
        if (current.some((d) => (d.id || d.document_id || d.documentId) === docId)) {
          return;
        }
        const updated = [...current, doc];
        set({ attachedSources: updated });

        const activeMissionId = get().activeMissionId;
        if (activeMissionId) {
          try {
            await apiAttachConversationSource(activeMissionId, docId);
          } catch (e) {
            console.error("Failed to persist attached source:", e);
          }
        }
      },

      detachSource: async (docId) => {
        const current = get().attachedSources;
        const updated = current.filter((d) => (d.id || d.document_id || d.documentId) !== docId);
        set({ attachedSources: updated });

        const activeMissionId = get().activeMissionId;
        if (activeMissionId) {
          try {
            await apiDetachConversationSource(activeMissionId, docId);
          } catch (e) {
            console.error("Failed to detach source on server:", e);
          }
        }
      },

      // Fetch user's or guest's conversations from server
      fetchUserConversations: async (autoRestoreLatest = true) => {
        try {
          const res = await apiListConversations();
          if (res.ok && Array.isArray(res.conversations)) {
            const formatted = res.conversations.map((c) => ({
              id: c.id,
              title: c.title,
              mode: c.mode,
              createdAt: c.createdAt ? new Date(c.createdAt).toLocaleDateString("en-US", { month: "short", day: "numeric" }).toUpperCase() : formatMissionDate(),
              updatedAt: c.updatedAt,
              messageCount: c.messageCount,
              lastMessagePreview: c.lastMessagePreview,
            }));
            set({ missions: formatted });

            // Restore the most recent conversation if none active or if auto-restore requested
            if (autoRestoreLatest && formatted.length > 0 && !get().activeMissionId) {
              await get().loadMission(formatted[0].id);
            }
          }
        } catch {
          // If network error, retain local state
        }
      },

      setMessages: (updater) => {
        const nextMessages = typeof updater === "function" ? updater(get().messages) : updater;
        const activeMissionId = get().activeMissionId;
        let missions = get().missions;

        if (activeMissionId) {
          missions = missions.map((m) =>
            m.id === activeMissionId ? { ...m, messages: nextMessages } : m
          );
        } else if (nextMessages.length > 0) {
          const firstUserMsg = nextMessages.find((m) => m.role === "user");
          const newId = `mission-${Date.now()}`;
          const newMission = {
            id: newId,
            title: firstUserMsg?.content?.slice(0, 45) || "New Mission",
            mode: get().activeMode,
            createdAt: formatMissionDate(),
            messages: nextMessages,
          };
          missions = [newMission, ...missions];
          set({ activeMissionId: newId, missions, messages: nextMessages });
          return;
        }

        set({ messages: nextMessages, missions });
      },

      addMessage: (msg) => {
        get().setMessages((prev) => [...prev, msg]);
      },

      createNewMission: () => {
        set({
          messages: [],
          input: "",
          loading: false,
          activeMissionId: null,
          attachedSources: [],
        });
      },

      loadMission: async (missionId) => {
        const { isAuthenticated } = useAuthStore.getState();
        if (missionId) {
          get().fetchAttachedSources(missionId);
        }
        if (isAuthenticated) {
          try {
            const res = await apiGetConversation(missionId);
            if (res.ok && res.conversation) {
              set({
                activeMissionId: res.conversation.id,
                messages: res.conversation.messages || [],
                activeMode: res.conversation.mode || "adaptive_rag",
                input: "",
                loading: false,
              });
              return;
            }
          } catch {
            // Fallback to local cache if offline
          }
        }

        const mission = get().missions.find((m) => m.id === missionId);
        if (mission) {
          set({
            activeMissionId: mission.id,
            messages: mission.messages || [],
            activeMode: mission.mode || "adaptive_rag",
            input: "",
            loading: false,
          });
        }
      },

      deleteMission: async (missionId) => {
        const { isAuthenticated } = useAuthStore.getState();
        if (isAuthenticated) {
          try {
            await apiDeleteConversation(missionId);
          } catch {
            // Ignore if already deleted on server
          }
        }
        set((state) => ({
          missions: state.missions.filter((m) => m.id !== missionId),
          ...(state.activeMissionId === missionId
            ? { activeMissionId: null, messages: [], input: "", attachedSources: [] }
            : {}),
        }));
      },

      clearUserChatState: () => {
        set({
          missions: [],
          messages: [],
          input: "",
          loading: false,
          activeMissionId: null,
          attachedSources: [],
        });
      },

      clearMessages: () => {
        set({ messages: [], input: "", loading: false, activeMissionId: null, attachedSources: [] });
      },
    }),
    {
      name: "cogniflow-missions-store",
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({
        missions: state.missions,
        activeMissionId: state.activeMissionId,
        messages: state.messages,
        activeMode: state.activeMode,
        attachedSources: state.attachedSources,
      }),
    }
  )
);
