import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva } from "class-variance-authority";
import { cn } from "@/lib/utils";
const badgeVariants = cva("inline-flex items-center justify-center rounded-[2px] border px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider w-fit whitespace-nowrap shrink-0 [&>svg]:size-3 gap-1 [&>svg]:pointer-events-none focus-visible:border-[var(--border-focus)] focus-visible:ring-2 focus-visible:ring-[var(--accent-amber-glow)] transition-colors overflow-hidden", {
    variants: {
        variant: {
            default: "border-[var(--accent-amber)]/50 bg-[var(--accent-amber-glow)] text-[var(--accent-amber)]",
            secondary: "border-[var(--panel-border)] bg-[var(--panel-inner)] text-[var(--text-secondary)]",
            destructive: "border-rose-800/80 bg-rose-950/40 text-rose-300",
            outline: "border-[var(--panel-border)] text-[var(--text-secondary)] bg-transparent",
        },
    },
    defaultVariants: {
        variant: "default",
    },
});
function Badge({ className, variant, asChild = false, ...props }) {
    const Comp = asChild ? Slot : "span";
    return (<Comp data-slot="badge" className={cn(badgeVariants({ variant }), className)} {...props}/>);
}
export { Badge, badgeVariants };
