import * as React from "react";
import { cn } from "@/lib/utils";
function Textarea({ className, ...props }) {
    return (<textarea data-slot="textarea" className={cn("border border-[var(--panel-border)] bg-[var(--panel-inner)] text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus-visible:border-[var(--border-focus)] focus-visible:ring-2 focus-visible:ring-[var(--accent-amber-glow)] aria-invalid:ring-destructive/20 aria-invalid:border-destructive flex field-sizing-content min-h-16 w-full rounded-[4px] px-3 py-2 text-xs shadow-none transition-colors outline-none disabled:cursor-not-allowed disabled:opacity-50", className)} {...props}/>);
}
export { Textarea };
