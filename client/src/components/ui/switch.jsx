"use client";
import * as React from "react";
import * as SwitchPrimitive from "@radix-ui/react-switch";
import { cn } from "@/lib/utils";
function Switch({ className, ...props }) {
    return (<SwitchPrimitive.Root data-slot="switch" className={cn("peer data-[state=checked]:bg-[var(--accent-amber)] data-[state=unchecked]:bg-[var(--panel-inner)] border border-[var(--panel-border)] focus-visible:border-[var(--border-focus)] focus-visible:ring-2 focus-visible:ring-[var(--accent-amber-glow)] inline-flex h-4 w-7 shrink-0 items-center rounded-[2px] shadow-none transition-colors outline-none disabled:cursor-not-allowed disabled:opacity-50", className)} {...props}>
      <SwitchPrimitive.Thumb data-slot="switch-thumb" className={cn("bg-[var(--text-primary)] data-[state=checked]:bg-black pointer-events-none block size-3 rounded-[1px] transition-transform data-[state=checked]:translate-x-3 data-[state=unchecked]:translate-x-0.5")}/>
    </SwitchPrimitive.Root>);
}
export { Switch };
