import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva } from "class-variance-authority";
import { cn } from "@/lib/utils";
const buttonVariants = cva("inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[4px] text-xs font-medium transition-all active:translate-y-[1px] disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-3.5 shrink-0 [&_svg]:shrink-0 outline-none focus-visible:border-[var(--border-focus)] focus-visible:ring-2 focus-visible:ring-[var(--accent-amber-glow)] aria-invalid:ring-destructive/20 aria-invalid:border-destructive", {
    variants: {
        variant: {
            default: "bg-[var(--accent-amber)] text-black font-semibold shadow-xs hover:bg-[var(--accent-amber-hover)] hover:shadow-[0_0_10px_rgba(245,158,11,0.25)]",
            destructive: "bg-rose-950/50 border border-rose-800 text-rose-300 shadow-xs hover:bg-rose-900/60 hover:border-rose-600 focus-visible:ring-rose-500/30",
            outline: "border border-[var(--panel-border)] bg-[var(--panel-inner)] text-[var(--text-primary)] shadow-xs hover:border-[var(--accent-amber)] hover:text-[var(--text-primary)] hover:shadow-[0_0_10px_rgba(245,158,11,0.18)]",
            secondary: "bg-[var(--panel-inner)] border border-[var(--panel-border)] text-[var(--text-secondary)] shadow-xs hover:text-[var(--text-primary)] hover:border-zinc-600",
            ghost: "text-[var(--text-secondary)] hover:bg-[var(--panel-inner)] hover:text-[var(--text-primary)]",
            link: "text-[var(--accent-amber)] underline-offset-4 hover:underline",
        },
        size: {
            default: "h-8 px-3 py-1.5 has-[>svg]:px-2.5",
            sm: "h-7 rounded-[4px] gap-1 px-2.5 has-[>svg]:px-2 text-[11px]",
            lg: "h-9 rounded-[4px] px-4 has-[>svg]:px-3 text-sm",
            icon: "size-8",
        },
    },
    defaultVariants: {
        variant: "default",
        size: "default",
    },
});
function Button({ className, variant, size, asChild = false, ...props }) {
    const Comp = asChild ? Slot : "button";
    return (<Comp data-slot="button" className={cn(buttonVariants({ variant, size, className }))} {...props}/>);
}
export { Button, buttonVariants };
