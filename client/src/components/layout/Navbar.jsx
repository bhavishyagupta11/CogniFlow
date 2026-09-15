import { NavLink } from "react-router-dom";
import { Sparkles, MessageSquare, Files, BarChart3, Settings, Workflow, Github, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useUIStore } from "@/store/use-ui-store";
import { useAuthStore } from "@/store/use-auth-store";
export function Navbar() {
    const setArchOpen = useUIStore((s) => s.setArchOpen);
    const { userId, accessKey } = useAuthStore();
    return (<header className="h-[52px] border-b border-[var(--panel-border)] bg-[var(--panel-bg)] sticky top-0 z-20 flex items-center">
      <div className="w-full flex items-center justify-between px-4">
        {/* Brand & Terminal Title */}
        <div className="flex items-center gap-5">
          <NavLink to="/" className="flex items-center gap-2.5 group">
            <div className="flex h-7 w-7 items-center justify-center rounded-[4px] bg-[var(--panel-inner)] border border-[var(--panel-border)] text-[var(--accent-amber)] group-hover:border-[var(--accent-amber)] transition-colors">
              <Sparkles className="h-4 w-4"/>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-sm font-bold tracking-tight text-[var(--text-primary)] font-mono uppercase">CogniFlow</h1>
                <span className="text-[10px] py-0 px-1 font-mono uppercase font-bold text-[var(--accent-amber)] bg-[var(--accent-amber-glow)] border border-[var(--accent-amber)]/40 rounded-[2px]">
                  TERMINAL
                </span>
              </div>
            </div>
          </NavLink>

          {/* Navigation tabs */}
          <nav className="hidden md:flex items-center gap-1 pl-4 border-l border-[var(--panel-border)]">
            <NavLink to="/" className={({ isActive }) => `flex items-center gap-1.5 px-2.5 py-1 rounded-[4px] font-mono text-[11px] uppercase tracking-wider transition-colors ${isActive
            ? "bg-[var(--accent-amber-glow)] text-[var(--accent-amber)] border border-[var(--accent-amber)]/40 font-semibold"
            : "text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--panel-inner)] border border-transparent"}`}>
              <MessageSquare className="h-3.5 w-3.5"/>
              Chat
            </NavLink>
            <NavLink to="/documents" className={({ isActive }) => `flex items-center gap-1.5 px-2.5 py-1 rounded-[4px] font-mono text-[11px] uppercase tracking-wider transition-colors ${isActive
            ? "bg-[var(--accent-amber-glow)] text-[var(--accent-amber)] border border-[var(--accent-amber)]/40 font-semibold"
            : "text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--panel-inner)] border border-transparent"}`}>
              <Files className="h-3.5 w-3.5"/>
              Documents
            </NavLink>
            <NavLink to="/eval" className={({ isActive }) => `flex items-center gap-1.5 px-2.5 py-1 rounded-[4px] font-mono text-[11px] uppercase tracking-wider transition-colors ${isActive
            ? "bg-[var(--accent-amber-glow)] text-[var(--accent-amber)] border border-[var(--accent-amber)]/40 font-semibold"
            : "text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--panel-inner)] border border-transparent"}`}>
              <BarChart3 className="h-3.5 w-3.5"/>
              Evaluation
            </NavLink>
            <NavLink to="/settings" className={({ isActive }) => `flex items-center gap-1.5 px-2.5 py-1 rounded-[4px] font-mono text-[11px] uppercase tracking-wider transition-colors ${isActive
            ? "bg-[var(--accent-amber-glow)] text-[var(--accent-amber)] border border-[var(--accent-amber)]/40 font-semibold"
            : "text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--panel-inner)] border border-transparent"}`}>
              <Settings className="h-3.5 w-3.5"/>
              Settings
            </NavLink>
          </nav>
        </div>

        {/* Right HUD telemetry & action controls */}
        <div className="flex items-center gap-2">
          {/* Tenant indicator */}
          <NavLink to="/settings" className="hidden sm:flex items-center gap-1.5 px-2 py-0.5 rounded-[2px] bg-[var(--panel-inner)] border border-[var(--panel-border)] text-[11px] font-mono text-[var(--text-secondary)] hover:border-[var(--accent-amber)] transition-colors">
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-400"/>
            <span className="font-mono text-[10px]">{userId.slice(0, 12)}</span>
            {accessKey ? (<span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(16,185,129,0.6)]" title="Access key active"/>) : (<span className="inline-block w-1.5 h-1.5 rounded-full bg-amber-400" title="Public tenant"/>)}
          </NavLink>

          <Button variant="outline" size="sm" onClick={() => setArchOpen(true)} aria-label="View Architecture Diagram" data-testid="nav-architecture-button" className="h-7 text-xs font-mono">
            <Workflow className="h-3.5 w-3.5 sm:mr-1.5"/>
            <span className="hidden sm:inline">Architecture</span>
          </Button>

          <a href="https://github.com/bhavishyagupta11/CogniFlow" target="_blank" rel="noreferrer" className="inline-flex" aria-label="GitHub Repository">
            <Button variant="ghost" size="sm" aria-label="GitHub Repository" className="h-7 w-7 p-0">
              <Github className="h-3.5 w-3.5"/>
            </Button>
          </a>
        </div>
      </div>
    </header>);
}
