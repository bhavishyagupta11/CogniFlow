import * as React from "react";
import { cn } from "@/lib/utils";
function Input({ className, type, ...props }) {
    return (<input type={type} data-slot="input" className={cn("file:text-foreground placeholder:text-[var(--text-muted)] selection:bg-[var(--accent-amber)]/20 selection:text-[var(--accent-amber)] bg-[var(--panel-inner)] border border-[var(--panel-border)] text-[var(--text-primary)] flex h-8 w-full min-w-0 rounded-[4px] px-2.5 py-1 text-xs shadow-none transition-colors outline-none file:inline-flex file:h-6 file:border-0 file:bg-transparent file:text-xs file:font-medium disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50", "focus-visible:border-[var(--border-focus)] focus-visible:ring-2 focus-visible:ring-[var(--accent-amber-glow)]", "aria-invalid:ring-destructive/20 aria-invalid:border-destructive", className)} {...props}/>);
}
export { Input };
