"use client";
import * as React from "react";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import { cn } from "@/lib/utils";
function Tabs({ className, ...props }) {
    return (<TabsPrimitive.Root data-slot="tabs" className={cn("flex flex-col gap-2", className)} {...props}/>);
}
function TabsList({ className, ...props }) {
    return (<TabsPrimitive.List data-slot="tabs-list" className={cn("bg-[var(--panel-inner)] border border-[var(--panel-border)] text-[var(--text-muted)] inline-flex h-8 w-fit items-center justify-center rounded-[4px] p-0.5", className)} {...props}/>);
}
function TabsTrigger({ className, ...props }) {
    return (<TabsPrimitive.Trigger data-slot="tabs-trigger" className={cn("data-[state=active]:bg-[var(--accent-amber-glow)] data-[state=active]:text-[var(--accent-amber)] data-[state=active]:border-[var(--accent-amber)]/40 text-[var(--text-muted)] hover:text-[var(--text-primary)] inline-flex h-[calc(100%-2px)] flex-1 items-center justify-center gap-1.5 rounded-[2px] border border-transparent px-2.5 py-0.5 font-mono text-[11px] font-medium uppercase tracking-wider whitespace-nowrap transition-colors outline-none disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-3.5", className)} {...props}/>);
}
function TabsContent({ className, ...props }) {
    return (<TabsPrimitive.Content data-slot="tabs-content" className={cn("flex-1 outline-none", className)} {...props}/>);
}
export { Tabs, TabsList, TabsTrigger, TabsContent };
