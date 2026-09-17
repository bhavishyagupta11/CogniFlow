"use client";
import React, { useState, useEffect, memo } from "react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { ChevronRight, Loader2, Code2, Terminal, Database, Sliders, FileText, ShieldCheck, Layers, Cpu, Check, Minus, AlertTriangle, Clock } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";

const STAGE_NUMBERS = {
  router: "01",
  retriever: "02",
  reranker: "03",
  generator: "04",
  verifier: "05",
  critic: "05",
  analyzer: "04",
  citations: "04",
  coordinator: "00",
  loader: "02",
  mapper: "03",
  reducer: "04"
};

const AGENT_LABELS = {
  router: "ROUTER",
  retriever: "RETRIEVER",
  reranker: "RERANKER",
  generator: "FINAL GENERATOR",
  verifier: "VERIFIER",
  critic: "CRITIC",
  analyzer: "ANALYZER",
  citations: "CITATIONS",
  coordinator: "COORDINATOR",
  loader: "PAGE_LOADER",
  mapper: "MAPPER",
  reducer: "REDUCER"
};

function formatMs(ms) {
  if (typeof ms !== "number" || isNaN(ms) || ms < 0) return "0.00s";
  return `${(ms / 1000).toFixed(2)}s`;
}

function StatusBadge({ status, durationMs, liveElapsedMs }) {
  const normStatus = (status || "").toLowerCase();
  if (normStatus === "queued") {
    return (
      <span className="flex items-center gap-1 text-[10px] font-mono text-[var(--text-muted)] font-semibold">
        <Clock className="h-3 w-3 shrink-0" />
        <span>QUEUED</span>
      </span>
    );
  }
  if (normStatus === "running") {
    return (
      <span data-testid="running-stage-badge" className="flex items-center gap-1 text-[10px] font-mono text-[#f97316] font-bold">
        <Loader2 className="h-3 w-3 animate-spin shrink-0" />
        <span>RUNNING {formatMs(liveElapsedMs)}</span>
      </span>
    );
  }
  if (normStatus === "skipped") {
    return (
      <span className="flex items-center gap-1 text-[10px] font-mono text-[var(--text-muted)]">
        <Minus className="h-3 w-3 shrink-0" />
        <span>SKIPPED</span>
      </span>
    );
  }
  if (normStatus === "error" || normStatus === "failed") {
    return (
      <span className="flex items-center gap-1 text-[10px] font-mono text-rose-500 font-bold">
        <AlertTriangle className="h-3 w-3 shrink-0" />
        <span>FAILED</span>
      </span>
    );
  }
  return (
    <span className="flex items-center gap-1 text-[10px] font-mono text-emerald-600 font-semibold">
      <Check className="h-3 w-3 shrink-0 text-emerald-600" />
      <span>COMPLETED {formatMs(durationMs)}</span>
    </span>
  );
}

const StepCard = memo(function StepCard({ step, index, devMode }) {
  const [open, setOpen] = useState(false);
  const [liveElapsed, setLiveElapsed] = useState(0);

  const normStatus = (step.status || "").toLowerCase();
  const isRunning = normStatus === "running";
  const isQueued = normStatus === "queued";
  const isSkipped = normStatus === "skipped";
  const isError = normStatus === "error" || normStatus === "failed";

  const stageNum = STAGE_NUMBERS[step.agent] || String(index + 1).padStart(2, "0");
  const stageName = step.agent === "generator" ? "FINAL GENERATOR" : (AGENT_LABELS[step.agent] || (step.agent ? step.agent.toUpperCase() : "STAGE"));

  // Live timer for currently running step
  useEffect(() => {
    let interval;
    if (isRunning && step.startedAt) {
      interval = setInterval(() => {
        setLiveElapsed(Math.max(0, Date.now() - step.startedAt));
      }, 100);
    } else {
      setLiveElapsed(0);
    }
    return () => clearInterval(interval);
  }, [isRunning, step.startedAt]);

  // Derive compact technical summary line
  let subtitle = "";
  if (isSkipped) {
    subtitle = step.input?.skipReason || step.input?.reason || "Skipped by pipeline policy";
  } else if (step.agent === "retriever" && step.output) {
    const count = step.output.count ?? step.output.candidates?.length ?? 0;
    const mmr = step.output.mmrUsed ? " · MMR applied" : "";
    subtitle = `${count} candidates${mmr} · hybrid / RRF`;
  } else if (step.agent === "reranker" && step.output) {
    const topScore = typeof step.output.topScore === "number" ? `top score ${step.output.topScore.toFixed(3)}` : "re-scored";
    subtitle = `NumPy scored · ${topScore}`;
  } else if (step.agent === "generator" && step.output) {
    const cites = step.output.citationsUsed !== undefined ? `${step.output.citationsUsed} citations` : "";
    subtitle = cites ? `Evidence grounded · ${cites}` : "Grounded generation";
  } else if (step.agent === "verifier" && step.output) {
    const verdict = step.output.verdict || "verified";
    const faith = step.output.faithfulness !== undefined ? ` · ${step.output.faithfulness}/100` : "";
    subtitle = `${verdict}${faith}`;
  } else if (step.label) {
    subtitle = step.label;
  }

  return (
    <Collapsible
      open={open}
      onOpenChange={setOpen}
      className={`rounded-[2px] border font-mono transition-colors ${
        isRunning
          ? "border-[#f97316] bg-[#f97316]/5"
          : isQueued
          ? "border-[var(--panel-border)]/40 bg-[var(--panel-inner)]/20 opacity-60"
          : isSkipped
          ? "border-[var(--panel-border)]/50 bg-[var(--panel-inner)]/30 opacity-75"
          : isError
          ? "border-rose-800/80 bg-rose-950/20"
          : "border-[var(--panel-border)] bg-[var(--panel-inner)]"
      }`}
    >
      <CollapsibleTrigger className="flex w-full items-center justify-between p-2.5 text-left hover:bg-[var(--panel-bg)] transition-colors cursor-pointer outline-none">
        <div className="flex items-center gap-2.5 min-w-0 flex-1">
          {/* Numbered Square Marker */}
          <span className="flex h-5 w-7 items-center justify-center rounded-[2px] bg-[var(--panel-bg)] border border-[var(--panel-border)] text-[9px] font-mono font-bold text-[var(--text-secondary)] shrink-0">
            [{stageNum}]
          </span>

          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-2 pr-2">
              <span className="text-[11px] font-mono font-bold uppercase tracking-wider text-[var(--text-primary)]">
                {stageName}
              </span>
              <StatusBadge
                status={step.status}
                durationMs={step.durationMs}
                liveElapsedMs={liveElapsed}
              />
            </div>
            {subtitle && (
              <p className="text-[10px] font-mono text-[var(--text-muted)] truncate mt-0.5">
                {subtitle}
              </p>
            )}
          </div>
        </div>

        <ChevronRight
          className={`h-3.5 w-3.5 transition-transform text-[var(--text-muted)] shrink-0 ml-1 ${
            open ? "rotate-90" : ""
          }`}
        />
      </CollapsibleTrigger>

      <CollapsibleContent>
        <div className="border-t border-[var(--panel-border)] px-3 py-2.5 text-xs font-mono space-y-2 bg-[var(--panel-bg)]">
          <StepDetails step={step} devMode={devMode} />
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
});

function StepDetails({ step, devMode }) {
  const normStatus = (step.status || "").toLowerCase();
  if (normStatus === "queued") {
    return <div className="text-[10px] font-mono text-[var(--text-muted)]">Stage queued in execution pipeline...</div>;
  }
  if (normStatus === "running") {
    return <div className="text-[10px] font-mono text-[#f97316] animate-pulse">Stage currently executing...</div>;
  }
  if (normStatus === "skipped") {
    return (
      <div className="text-[10px] font-mono text-[var(--text-muted)]">
        Stage bypassed: {step.input?.skipReason || step.input?.reason || "Pipeline decision"}
      </div>
    );
  }
  if (step.status === "error" || !step.output) {
    return <div className="text-[10px] font-mono text-rose-400">{step.error || "Step failed before producing output."}</div>;
  }

  switch (step.agent) {
    case "router":
      return (
        <div className="space-y-1.5 font-mono">
          <DetailRow label="Question" value={step.input?.question || ""} />
          <DetailRow label="Mode" value={step.input?.mode || "adaptive_rag"} />
          <DetailRow label="Complexity" value={step.output?.complexity || "standard"} />
          {step.output?.target && <DetailRow label="Target Document" value={step.output.target} />}
        </div>
      );
    case "retriever": {
      const candidates = Array.isArray(step.output?.candidates) ? step.output.candidates : [];
      const numChunks = step.output?.count ?? candidates.length;
      return (
        <div className="space-y-2 font-mono">
          <DetailRow label="Chunks Retrieved" value={String(numChunks)} />
          <DetailRow label="Diversity MMR" value={step.output?.mmrUsed ? "Applied (lambda=0.7)" : "Skipped"} />
          {candidates.length > 0 && (
            <div className="space-y-1 pt-1">
              <div className="text-[9px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                Candidate Evidence Chunks ({candidates.length})
              </div>
              {candidates.map((c, i) => {
                const scoreDisplay = typeof c?.score === "number" ? c.score.toFixed(3) : "0.000";
                return (
                  <div key={c?.chunkId || i} className="rounded-[2px] border border-[var(--panel-border)] bg-[var(--panel-inner)] p-1.5 text-[10px] space-y-0.5">
                    <div className="flex items-center justify-between text-[var(--text-muted)]">
                      <span>#{i + 1} · {c?.chunkId || `chunk-${i + 1}`}</span>
                      <span>Score {scoreDisplay}</span>
                    </div>
                    <div className="text-[var(--text-primary)] font-medium truncate">{c?.documentTitle || "Evidence Document"}</div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      );
    }
    case "reranker": {
      return (
        <div className="space-y-1.5 font-mono">
          <DetailRow label="Candidate Count" value={String(step.input?.candidateCount || 0)} />
          <DetailRow label="Top Score" value={typeof step.output?.topScore === "number" ? step.output.topScore.toFixed(3) : "N/A"} />
        </div>
      );
    }
    case "generator":
      return (
        <div className="space-y-2 font-mono">
          <DetailRow label="Citations Used" value={`${step.output?.citationsUsed ?? 0} unique`} />
          {step.output?.answer && (
            <div>
              <div className="text-[9px] font-bold uppercase tracking-wider text-[var(--text-muted)] mb-1">
                Generated Answer Preview
              </div>
              <div className="rounded-[2px] border border-[var(--panel-border)] bg-[var(--panel-inner)] p-2 text-[10.5px] leading-relaxed max-h-36 overflow-y-auto whitespace-pre-wrap">
                {step.output.answer}
              </div>
            </div>
          )}
        </div>
      );
    case "verifier":
    case "critic": {
      const verdict = step.output?.verdict || "verified";
      const faith = step.output?.faithfulness ?? step.output?.faithfulnessScore ?? 95;
      return (
        <div className="space-y-1.5 font-mono">
          <DetailRow label="Verdict" value={verdict} />
          <DetailRow label="Faithfulness" value={`${faith}/100`} />
        </div>
      );
    }
    default: {
      const entries = Object.entries(step.output || {});
      return (
        <div className="space-y-1 font-mono">
          {entries.map(([k, v]) => (
            <DetailRow key={k} label={k} value={typeof v === "object" ? JSON.stringify(v) : String(v)} />
          ))}
        </div>
      );
    }
  }
}

function DetailRow({ label, value, mono }) {
  return (
    <div className="flex flex-col gap-0.5 font-mono">
      <span className="text-[9px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
        {label}
      </span>
      <span className="text-[10.5px] text-[var(--text-secondary)] break-words">{value}</span>
    </div>
  );
}

export function AgentTrace({ steps = [], isLoading = false }) {
  const [devMode, setDevMode] = useState(false);

  if (steps.length === 0 && !isLoading) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-center font-mono">
        <div className="space-y-2">
          <Terminal className="mx-auto h-7 w-7 text-[var(--text-muted)] opacity-40" />
          <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
            Awaiting Pipeline Execution
          </p>
          <p className="text-[10px] text-[var(--text-muted)]/80 max-w-xs">
            Live router, retriever, reranker, generator, and verifier traces will stream here.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full relative bg-[var(--panel-bg)] font-mono">
      {/* Console Header Bar */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--panel-border)] bg-[var(--panel-inner)] shrink-0">
        <span className="text-[10px] font-mono uppercase tracking-wider text-[var(--text-muted)] font-bold">
          EXECUTION CONSOLE ({steps.length} STAGES)
        </span>
        <div className="flex items-center space-x-2">
          <Switch id="dev-mode" checked={devMode} onCheckedChange={setDevMode} />
          <Label htmlFor="dev-mode" className="text-[10px] font-mono text-[var(--text-muted)] flex items-center cursor-pointer">
            <Code2 className="w-3 h-3 mr-1 text-[#f97316]" /> DEV
          </Label>
        </div>
      </div>

      {/* Steps List */}
      <div className="flex-1 min-h-0 overflow-y-auto space-y-2 p-3">
        {steps.map((step, idx) => (
          <StepCard key={step.id || idx} step={step} index={idx} devMode={devMode} />
        ))}
      </div>
    </div>
  );
}
