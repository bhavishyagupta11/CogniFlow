import React, { useState } from "react";
import { NavLink, useNavigate, useLocation } from "react-router-dom";
import {
  Plus,
  Search,
  ChevronLeft,
  ChevronRight,
  Sun,
  Moon,
  LogOut,
  LogIn,
  Files,
  BarChart3,
  Workflow,
  Settings,
  Brain,
  BarChart2,
  Globe,
  GitBranch,
  Zap,
  Trash2,
  ShieldCheck,
  Menu,
} from "lucide-react";
import { useChatStore } from "@/store/use-chat-store";
import { useAuthStore } from "@/store/use-auth-store";
import { useUIStore } from "@/store/use-ui-store";

const MODE_ICONS = {
  deep_research: { icon: Brain, color: "text-rose-500" },
  quant_data: { icon: BarChart2, color: "text-amber-500" },
  live_web: { icon: Globe, color: "text-cyan-500" },
  github_scout: { icon: GitBranch, color: "text-orange-500" },
  fast_chat: { icon: Zap, color: "text-yellow-500" },
};

export function Sidebar({ isCollapsed, setIsCollapsed, isMobileOpen, setIsMobileOpen }) {
  const navigate = useNavigate();
  const location = useLocation();
  const {
    missions,
    activeMissionId,
    loading,
    createNewMission,
    loadMission,
    deleteMission,
  } = useChatStore();
  const { user, isAuthenticated, logout } = useAuthStore();
  const { setArchOpen } = useUIStore();

  const [searchQuery, setSearchQuery] = useState("");
  const [theme, setTheme] = useState(() => {
    // Read from localStorage (single source of truth, synced with index.html inline script).
    // Falls back to reading the DOM class (in case localStorage is blocked).
    try {
      return localStorage.getItem("cogniflow-theme") || "dark";
    } catch {
      return document.documentElement.classList.contains("dark") ? "dark" : "light";
    }
  });

  const toggleTheme = () => {
    const nextTheme = theme === "light" ? "dark" : "light";
    setTheme(nextTheme);
    try {
      localStorage.setItem("cogniflow-theme", nextTheme);
    } catch { /* localStorage blocked — fail silently */ }
    if (nextTheme === "dark") {
      document.documentElement.classList.add("dark");
      document.documentElement.setAttribute("data-theme", "dark");
    } else {
      document.documentElement.classList.remove("dark");
      document.documentElement.setAttribute("data-theme", "light");
    }
  };


  const handleNewMission = () => {
    createNewMission();
    if (location.pathname !== "/") {
      navigate("/");
    }
    if (setIsMobileOpen) setIsMobileOpen(false);
  };

  const handleSelectMission = (id) => {
    loadMission(id);
    if (location.pathname !== "/") {
      navigate("/");
    }
    if (setIsMobileOpen) setIsMobileOpen(false);
  };

  const handleLogout = async () => {
    await logout();
    useChatStore.getState().clearUserChatState();
    navigate("/auth");
    if (setIsMobileOpen) setIsMobileOpen(false);
  };

  // Filter missions
  const filteredMissions = (missions || []).filter((m) =>
    (m.title || "").toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Friendly operator display name
  const displayName = user?.name || user?.email?.split("@")[0] || "Guest";
  const operatorInitial = displayName.charAt(0).toUpperCase();

  return (
    <aside
      className={`fixed md:relative z-40 h-full flex flex-col shrink-0 bg-[var(--panel-bg)] border-r border-[var(--panel-border)] font-mono transition-all duration-200 select-none ${
        isCollapsed ? "w-[52px]" : "w-[216px]"
      } ${
        isMobileOpen
          ? "translate-x-0"
          : "-translate-x-full md:translate-x-0"
      }`}
      style={{ minWidth: isCollapsed ? "52px" : "216px" }}
      aria-label="Sidebar Navigation"
    >
      {/* Top Header / Branding */}
      <div className="h-14 border-b border-[var(--panel-border)] px-3 flex items-center justify-between shrink-0">
        {!isCollapsed ? (
          <div className="flex items-center gap-2.5 min-w-0">
            {/* Orange Square Block Icon */}
            <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-[2px] bg-[#f97316] text-white font-mono font-black text-xs shadow-xs">
              ■
            </div>
            <div className="min-w-0 leading-tight">
              <div className="font-mono text-xs font-bold tracking-wider text-[var(--text-primary)] uppercase truncate">
                COGNIFLOW
              </div>
              <div className="text-[8px] font-mono tracking-widest text-[var(--text-muted)] font-semibold uppercase">
                ADAPTIVE RAG
              </div>
            </div>
          </div>
        ) : (
          <div className="w-full flex justify-center">
            <div className="flex h-7 w-7 items-center justify-center rounded-[2px] bg-[#f97316] text-white font-mono font-black text-xs">
              ■
            </div>
          </div>
        )}

        {/* Collapse Toggle Button */}
        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className="hidden md:flex h-5 w-5 items-center justify-center rounded-[2px] border border-[var(--panel-border)] text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:border-[var(--border-focus)] transition-colors cursor-pointer text-xs"
          title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {isCollapsed ? (
            <ChevronRight className="h-3 w-3" />
          ) : (
            <ChevronLeft className="h-3 w-3" />
          )}
        </button>

        {/* Mobile close button */}
        <button
          onClick={() => setIsMobileOpen(false)}
          className="md:hidden flex h-5 w-5 items-center justify-center rounded-[2px] border border-[var(--panel-border)] text-[var(--text-muted)]"
          aria-label="Close sidebar"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Main Sidebar Body */}
      <div className="flex-1 min-h-0 flex flex-col overflow-hidden px-2.5 py-3 space-y-3">
        {/* + NEW MISSION Button */}
        <div>
          <button
            onClick={handleNewMission}
            className={`w-full flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-[2px] border border-[var(--panel-border)] bg-[var(--panel-bg)] hover:bg-[var(--panel-inner)] hover:border-[var(--border-focus)] text-[var(--text-primary)] font-mono text-[11px] font-bold uppercase tracking-wider transition-all cursor-pointer shadow-xs active:translate-y-[1px] ${
              isCollapsed ? "h-9 w-full p-0" : ""
            }`}
            title="Start new mission"
            aria-label="New Mission"
          >
            <Plus className="h-3.5 w-3.5 shrink-0 text-[#f97316]" />
            {!isCollapsed && <span>+ NEW MISSION</span>}
          </button>
        </div>

        {/* Search Field */}
        {!isCollapsed && (
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-[9px] font-mono uppercase tracking-wider text-[var(--text-muted)] font-bold">
              <span>RECENT MISSIONS</span>
              <span className="text-[10px] text-[var(--text-muted)] font-normal font-mono">
                ({filteredMissions.length})
              </span>
            </div>
            <div className="relative flex items-center">
              <Search className="absolute left-2 h-3 w-3 text-[var(--text-muted)] pointer-events-none" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search missions & dossiers…"
                className="w-full h-6.5 pl-6.5 pr-2 rounded-[2px] border border-[var(--panel-border)] bg-[var(--panel-inner)] text-[10px] font-mono text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-hidden focus:border-[var(--border-focus)] transition-colors"
                aria-label="Search missions"
              />
            </div>
          </div>
        )}

        {/* Mission List */}
        {!isCollapsed && (
          <div className="flex-1 min-h-0 overflow-y-auto space-y-0.5 pr-0.5">
            {filteredMissions.length === 0 ? (
              <div className="py-4 text-center text-[10px] text-[var(--text-muted)] font-mono">
                {searchQuery ? "No missions found" : "No recent missions"}
              </div>
            ) : (
              filteredMissions.map((mission) => {
                const iconMeta = MODE_ICONS[mission.mode] || MODE_ICONS.deep_research;
                const Icon = iconMeta.icon;
                const isActive = activeMissionId === mission.id && location.pathname === "/";

                return (
                  <div
                    key={mission.id}
                    onClick={() => handleSelectMission(mission.id)}
                    className={`group relative flex items-start gap-2 px-2 py-1.5 rounded-[2px] cursor-pointer transition-all ${
                      isActive
                        ? "bg-[#f97316]/10 border-l-2 border-[#f97316] text-[var(--text-primary)] font-semibold"
                        : "text-[var(--text-secondary)] hover:bg-[var(--panel-inner)] hover:text-[var(--text-primary)]"
                    }`}
                  >
                    <Icon className={`h-3 w-3 shrink-0 mt-0.5 ${iconMeta.color}`} />
                    <div className="flex-1 min-w-0">
                      <div className="text-[11px] font-mono truncate leading-tight">
                        {mission.title || "Untitled Mission"}
                      </div>
                      <div className="text-[9px] font-mono text-[var(--text-muted)] mt-0.5">
                        {mission.createdAt || "TODAY"}
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteMission(mission.id);
                      }}
                      className="opacity-0 group-hover:opacity-100 p-0.5 hover:text-rose-500 transition-opacity"
                      title="Delete mission"
                      aria-label="Delete mission"
                    >
                      <Trash2 className="h-2.5 w-2.5" />
                    </button>
                  </div>
                );
              })
            )}
          </div>
        )}

        {/* Collapsed spacer */}
        {isCollapsed && <div className="flex-1" />}

        {/* Navigation Quick Links */}
        <div className="border-t border-[var(--panel-border)] pt-2 space-y-1 shrink-0">
          <NavLink
            to="/documents"
            className={({ isActive }) =>
              `flex items-center gap-2 px-2 py-1 rounded-[2px] text-[10px] font-mono uppercase tracking-wider transition-colors ${
                isActive
                  ? "bg-[#f97316]/15 text-[#f97316] font-bold border border-[#f97316]/40"
                  : "text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--panel-inner)]"
              } ${isCollapsed ? "justify-center p-1.5" : ""}`
            }
            title="Corpus & Documents"
            aria-label="Documents"
          >
            <Files className="h-3 w-3 shrink-0 text-[#f97316]" />
            {!isCollapsed && <span>DOCUMENTS CORPUS</span>}
          </NavLink>

          <NavLink
            to="/eval"
            className={({ isActive }) =>
              `flex items-center gap-2 px-2 py-1 rounded-[2px] text-[10px] font-mono uppercase tracking-wider transition-colors ${
                isActive
                  ? "bg-[#f97316]/15 text-[#f97316] font-bold border border-[#f97316]/40"
                  : "text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--panel-inner)]"
              } ${isCollapsed ? "justify-center p-1.5" : ""}`
            }
            title="Evaluation & Benchmarks"
            aria-label="Evaluation"
          >
            <BarChart3 className="h-3 w-3 shrink-0 text-cyan-600" />
            {!isCollapsed && <span>EVALUATION</span>}
          </NavLink>

          <NavLink
            to="/auth"
            className={({ isActive }) =>
              `flex items-center gap-2 px-2 py-1 rounded-[2px] text-[10px] font-mono uppercase tracking-wider transition-colors ${
                isActive
                  ? "bg-[#f97316]/15 text-[#f97316] font-bold border border-[#f97316]/40"
                  : "text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--panel-inner)]"
              } ${isCollapsed ? "justify-center p-1.5" : ""}`
            }
            title="Account & Authentication"
            aria-label="Account Settings"
          >
            <ShieldCheck className="h-3 w-3 shrink-0 text-amber-500" />
            {!isCollapsed && <span>ACCOUNT / AUTH</span>}
          </NavLink>

          <NavLink
            to="/architecture"
            onClick={() => setIsMobileOpen && setIsMobileOpen(false)}
            className={({ isActive }) =>
              `w-full flex items-center gap-2 px-2 py-1 rounded-[2px] text-[10px] font-mono uppercase tracking-wider transition-colors cursor-pointer ${
                isActive
                  ? "bg-[#f97316]/10 text-[#f97316] font-bold border border-[#f97316]/30"
                  : "text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--panel-inner)]"
              } ${isCollapsed ? "justify-center p-1.5" : ""}`
            }
            title="System Architecture Telemetry"
            aria-label="Architecture"
          >
            <Workflow className="h-3 w-3 shrink-0 text-indigo-500" />
            {!isCollapsed && <span>ARCHITECTURE</span>}
          </NavLink>
        </div>
      </div>

      {/* Bottom Operator Section */}
      <div className="border-t border-[var(--panel-border)] p-2.5 bg-[var(--panel-bg)] space-y-2 shrink-0">
        {/* Operator Profile Card */}
        <div
          className={`flex items-center justify-between rounded-[2px] border border-[var(--panel-border)] bg-[var(--panel-inner)] p-1.5 ${
            isCollapsed ? "justify-center p-1" : ""
          }`}
        >
          <div className="flex items-center gap-2 min-w-0">
            {/* Avatar Block */}
            <div className="flex h-5.5 w-5.5 shrink-0 items-center justify-center rounded-[2px] bg-[#f97316] text-white font-mono font-bold text-[10px]">
              {operatorInitial}
            </div>
            {!isCollapsed && (
              <div className="min-w-0 leading-none">
                <div className="font-mono text-[11px] font-bold text-[var(--text-primary)] truncate">
                  {displayName}
                </div>
                <div className="text-[8px] font-mono uppercase text-[var(--text-muted)] tracking-wider mt-0.5">
                  {isAuthenticated ? "AUTHENTICATED" : "GUEST"}
                </div>
              </div>
            )}
          </div>
          {!isCollapsed && (
            isAuthenticated ? (
              <button
                onClick={handleLogout}
                className="text-[var(--text-muted)] hover:text-rose-500 p-0.5 transition-colors cursor-pointer"
                title="Log out"
                aria-label="Log out of session"
              >
                <LogOut className="h-3 w-3" />
              </button>
            ) : (
              <button
                onClick={() => navigate("/auth")}
                className="text-[var(--text-muted)] hover:text-[#f97316] p-0.5 transition-colors cursor-pointer"
                title="Sign In"
                aria-label="Sign In"
              >
                <LogIn className="h-3 w-3" />
              </button>
            )
          )}
        </div>

        {/* Stark Light / Dark Theme Button */}
        {!isCollapsed ? (
          <button
            onClick={toggleTheme}
            className="w-full flex items-center justify-center gap-1.5 py-1 px-2 rounded-[2px] border border-[var(--panel-border)] bg-[var(--panel-bg)] hover:bg-[var(--panel-inner)] text-[10px] font-mono uppercase tracking-wider text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors cursor-pointer"
            aria-label="Toggle Theme"
          >
            {theme === "light" ? (
              <>
                <Sun className="h-3 w-3 text-amber-500" />
                <span>STARK LIGHT</span>
              </>
            ) : (
              <>
                <Moon className="h-3 w-3 text-cyan-400" />
                <span>TERMINAL DARK</span>
              </>
            )}
          </button>
        ) : (
          <button
            onClick={toggleTheme}
            className="w-full flex justify-center py-1 rounded-[2px] border border-[var(--panel-border)] text-[var(--text-muted)] hover:text-[var(--text-primary)]"
            title="Toggle theme"
            aria-label="Toggle theme"
          >
            {theme === "light" ? (
              <Sun className="h-3.5 w-3.5 text-amber-500" />
            ) : (
              <Moon className="h-3.5 w-3.5 text-cyan-400" />
            )}
          </button>
        )}

        {/* System Status Metadata */}
        {!isCollapsed ? (
          <div className="flex items-center justify-center gap-1.5 py-1 font-mono text-[10px] uppercase tracking-wider font-medium text-[var(--text-muted)]">
            {loading ? (
              <>
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-[#f97316] animate-pulse" />
                <span className="text-[#f97316]">Processing · Streaming</span>
              </>
            ) : (
              <>
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-500" />
                <span>Idle · Ready</span>
              </>
            )}
          </div>
        ) : (
          <div className="flex justify-center py-1" title={loading ? "STREAMING" : "READY"}>
            <span
              className={`inline-block h-2 w-2 rounded-full ${
                loading ? "bg-[#f97316] animate-pulse" : "bg-emerald-500"
              }`}
            />
          </div>
        )}
      </div>
    </aside>
  );
}
