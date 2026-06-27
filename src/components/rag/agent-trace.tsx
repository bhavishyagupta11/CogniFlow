"use client";

import { AgentStep, AgentName } from "@/lib/agents/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Router,
  Search,
  ListOrdered,
  PenLine,
  ShieldCheck,
  Workflow,
  ChevronRight,
  CheckCircle2,
  AlertCircle,
  Loader2,
} from "lucide-react";
import { useState } from "react";

const AGENT_META: Record<
  AgentName,
  { icon: React.ComponentType<{ className?: string }>; color: string; label: string }
> = {
  router: { icon: Router, color: "text-emerald-600", label: "Router" },
  retriever: { icon: Search, color: "text-amber-600", label: "Retriever" },
  reranker: { icon: ListOrdered, color: "text-violet-600", label: "Reranker" },
  analyzer: { icon: PenLine, color: "text-rose-600", label: "Analyzer" },
  critic: { icon: ShieldCheck, color: "text-sky-600", label: "Critic" },
  coordinator: { icon: Workflow, color: "text-slate-600", label: "Coordinator" },
};

function StatusIcon({ status }: { status: AgentStep["status"] }) {
  if (status === "running")
    return <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />;
  if (status === "error")
    return <AlertCircle className="h-3.5 w-3.5 text-destructive" />;
  return <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />;
}

function formatMs(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function StepCard({ step }: { step: AgentStep }) {
  const [open, setOpen] = useState(false);
  const meta = AGENT_META[step.agent];
  const Icon = meta.icon;

  return (
    <Collapsible
      open={open}
      onOpenChange={setOpen}
      className="rounded-lg border bg-card shadow-sm"
    >
      <CollapsibleTrigger className="flex w-full items-center gap-3 p-3 text-left hover:bg-accent/40 transition-colors">
        <div className={`flex h-8 w-8 items-center justify-center rounded-md bg-muted ${meta.color}`}>
          <Icon className="h-4 w-4" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {meta.label}
            </span>
            <StatusIcon status={step.status} />
          </div>
          <p className="text-sm font-medium truncate">{step.label}</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Badge variant="outline" className="font-mono">
            {formatMs(step.durationMs)}
          </Badge>
          <ChevronRight
            className={`h-4 w-4 transition-transform ${open ? "rotate-90" : ""}`}
          />
        </div>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="border-t px-3 py-3 text-xs space-y-3 bg-muted/30">
          <StepDetails step={step} />
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}

function StepDetails({ step }: { step: AgentStep }) {
  switch (step.agent) {
    case "router":
      return (
        <div className="space-y-2">
          <DetailRow label="Question" value={step.input.question} />
          <DetailRow label="Intent" value={step.output.intentSummary} />
          <DetailRow label="Query Type" value={step.output.queryType} />
          <DetailRow
            label="Rewritten Query"
            value={step.output.rewrittenQuery}
            mono
          />
          <DetailRow
            label="Needs Retrieval"
            value={step.output.needsRetrieval ? "Yes" : "No"}
          />
        </div>
      );
    case "retriever":
      return (
        <div className="space-y-2">
          <DetailRow label="Query" value={step.input.query} mono />
          <DetailRow label="k" value={String(step.input.k)} />
          <DetailRow
            label="Corpus Stats"
            value={`${step.output.stats.numChunks} chunks · ${step.output.stats.vocabSize} vocab terms`}
          />
          <div className="space-y-1">
            <div className="text-[10px] font-semibold uppercase text-muted-foreground">
              Candidates ({step.output.candidates.length})
            </div>
            {step.output.candidates.map((c, i) => (
              <div
                key={c.chunkId}
                className="rounded border bg-card p-2 space-y-1"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] text-muted-foreground">
                    #{i + 1} · {c.chunkId}
                  </span>
                  <Badge variant="secondary" className="font-mono text-[10px]">
                    {c.score.toFixed(3)}
                  </Badge>
                </div>
                <div className="text-[11px] font-medium">{c.documentTitle}</div>
                <p className="text-[11px] text-muted-foreground line-clamp-2">
                  {c.preview}
                </p>
              </div>
            ))}
          </div>
        </div>
      );
    case "reranker":
      return (
        <div className="space-y-2">
          <DetailRow
            label="Candidates Re-scored"
            value={String(step.input.numCandidates)}
          />
          <div className="space-y-1">
            <div className="text-[10px] font-semibold uppercase text-muted-foreground">
              LLM Reranking
            </div>
            {step.output.reranked.map((r) => (
              <div
                key={r.chunkId}
                className="rounded border bg-card p-2 space-y-1"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] text-muted-foreground">
                    rank {r.originalRank} → {r.newRank}
                  </span>
                  <Badge
                    variant={r.llmScore >= 7 ? "default" : "secondary"}
                    className="font-mono text-[10px]"
                  >
                    {r.llmScore.toFixed(1)}/10
                  </Badge>
                </div>
                <div className="text-[11px] font-medium">{r.documentTitle}</div>
                <p className="text-[11px] text-muted-foreground italic">
                  {r.rationale}
                </p>
              </div>
            ))}
          </div>
        </div>
      );
    case "analyzer":
      return (
        <div className="space-y-2">
          <DetailRow label="Iteration" value={String(step.input.iteration)} />
          <DetailRow
            label="Sources Used"
            value={String(step.input.numSources)}
          />
          <DetailRow
            label="Citations"
            value={`${step.output.citationsUsed} unique`}
          />
          <div>
            <div className="text-[10px] font-semibold uppercase text-muted-foreground mb-1">
              Answer
            </div>
            <div className="rounded border bg-card p-2 text-[11px] whitespace-pre-wrap max-h-48 overflow-y-auto">
              {step.output.answer}
            </div>
          </div>
        </div>
      );
    case "critic":
      return (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <Badge
              variant={
                step.output.verdict === "faithful" ? "default" : "destructive"
              }
            >
              {step.output.verdict}
            </Badge>
            <Badge variant="outline" className="font-mono">
              {step.output.faithfulnessScore}/100
            </Badge>
          </div>
          {step.output.issues.length > 0 && (
            <div>
              <div className="text-[10px] font-semibold uppercase text-muted-foreground mb-1">
                Issues
              </div>
              <ul className="list-disc pl-4 space-y-0.5 text-[11px]">
                {step.output.issues.map((issue, i) => (
                  <li key={i}>{issue}</li>
                ))}
              </ul>
            </div>
          )}
          {step.output.revisionNotes && (
            <div>
              <div className="text-[10px] font-semibold uppercase text-muted-foreground mb-1">
                Revision Notes
              </div>
              <p className="text-[11px] italic text-muted-foreground">
                {step.output.revisionNotes}
              </p>
            </div>
          )}
        </div>
      );
    case "coordinator":
      return (
        <div className="space-y-2">
          <DetailRow
            label="Pipeline Flow"
            value={step.output.flow.join(" → ")}
          />
          <DetailRow
            label="Total Iterations"
            value={String(step.output.totalIterations)}
          />
          <DetailRow label="Final Verdict" value={step.output.finalVerdict} />
        </div>
      );
  }
}

function DetailRow({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      <span className={`text-[11px] ${mono ? "font-mono" : ""}`}>{value}</span>
    </div>
  );
}

export function AgentTrace({ steps }: { steps: AgentStep[] }) {
  if (steps.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-center">
        <div className="space-y-2">
          <Workflow className="mx-auto h-10 w-10 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">
            The agent trace will appear here once you ask a question.
          </p>
          <p className="text-xs text-muted-foreground/70">
            Each step shows input, output, timing, and the LLM&apos;s reasoning.
          </p>
        </div>
      </div>
    );
  }

  return (
    <ScrollArea className="h-full">
      <div className="space-y-2 p-3">
        {steps.map((step) => (
          <StepCard key={step.id} step={step} />
        ))}
      </div>
    </ScrollArea>
  );
}
