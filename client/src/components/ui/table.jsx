"use client";
import * as React from "react";
import { cn } from "@/lib/utils";
function Table({ className, ...props }) {
    return (<div data-slot="table-container" className="relative w-full overflow-x-auto rounded-[4px] border border-[var(--panel-border)] bg-[var(--panel-bg)]">
      <table data-slot="table" className={cn("w-full caption-bottom text-xs", className)} {...props}/>
    </div>);
}
function TableHeader({ className, ...props }) {
    return (<thead data-slot="table-header" className={cn("[&_tr]:border-b [&_tr]:border-[var(--panel-border)] bg-[var(--panel-inner)]", className)} {...props}/>);
}
function TableBody({ className, ...props }) {
    return (<tbody data-slot="table-body" className={cn("[&_tr:last-child]:border-0", className)} {...props}/>);
}
function TableFooter({ className, ...props }) {
    return (<tfoot data-slot="table-footer" className={cn("bg-[var(--panel-inner)] border-t border-[var(--panel-border)] font-medium [&>tr]:last:border-b-0 text-[var(--text-muted)]", className)} {...props}/>);
}
function TableRow({ className, ...props }) {
    return (<tr data-slot="table-row" className={cn("hover:bg-[var(--panel-inner)] border-b border-[var(--panel-border)] transition-colors data-[state=selected]:bg-[var(--accent-amber-glow)]", className)} {...props}/>);
}
function TableHead({ className, ...props }) {
    return (<th data-slot="table-head" className={cn("text-[var(--text-muted)] h-8 px-3 text-left align-middle font-mono text-[11px] font-semibold uppercase tracking-wider whitespace-nowrap [&:has([role=checkbox])]:pr-0 [&>[role=checkbox]]:translate-y-[2px]", className)} {...props}/>);
}
function TableCell({ className, ...props }) {
    return (<td data-slot="table-cell" className={cn("px-3 py-2 align-middle text-xs whitespace-nowrap text-[var(--text-primary)] [&:has([role=checkbox])]:pr-0 [&>[role=checkbox]]:translate-y-[2px]", className)} {...props}/>);
}
function TableCaption({ className, ...props }) {
    return (<caption data-slot="table-caption" className={cn("text-muted-foreground mt-4 text-sm", className)} {...props}/>);
}
export { Table, TableHeader, TableBody, TableFooter, TableHead, TableRow, TableCell, TableCaption, };
