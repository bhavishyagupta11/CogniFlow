"use client";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, } from "@/components/ui/dialog";
import { Router, Search, ListOrdered, PenLine, ShieldCheck, Workflow, ArrowRight, ArrowLeftRight, } from "lucide-react";
const NODES = [
    {
        id: "router",
        icon: Router,
        label: "Router",
        color: "bg-emerald-100 text-emerald-700 border-emerald-300",
        desc: "Analyzes the question, classifies intent, and rewrites the query for retrieval.",
    },
    {
        id: "retriever",
        icon: Search,
        label: "Retriever",
        color: "bg-amber-100 text-amber-700 border-amber-300",
        desc: "TF-IDF vector search with MMR diversity reranking. Returns top-k candidate chunks.",
    },
    {
        id: "reranker",
        icon: ListOrdered,
        label: "Reranker",
        color: "bg-violet-100 text-violet-700 border-violet-300",
        desc: "LLM-as-judge cross-encoder. Scores each candidate 0-10 on actual relevance.",
    },
    {
        id: "analyzer",
        icon: PenLine,
        label: "Analyzer",
        color: "bg-rose-100 text-rose-700 border-rose-300",
        desc: "Synthesizes a grounded answer with inline citations [1], [2], ...",
    },
    {
        id: "critic",
        icon: ShieldCheck,
        label: "Critic",
        color: "bg-sky-100 text-sky-700 border-sky-300",
        desc: "Verifies the answer against sources. Flags hallucinations. Can request a revision.",
    },
];
export function ArchitectureDialog({ open, onOpenChange, }) {
    return (<Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto rounded-[4px] border border-[var(--panel-border)] bg-[var(--panel-bg)] text-[var(--text-primary)] shadow-[var(--shadow-matrix)]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-sm font-mono uppercase font-bold text-[var(--accent-amber)]">
            <Workflow className="h-4 w-4 text-[var(--accent-amber)]"/>
            CogniFlow — Multi-Agent RAG Architecture
          </DialogTitle>
          <DialogDescription className="text-xs text-[var(--text-muted)] font-mono">
            5-agent self-correcting RAG pipeline orchestrated via Coordinator state transitions.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Pipeline diagram */}
          <div className="rounded-[4px] border border-[var(--panel-border)] bg-[var(--panel-inner)] p-3">
            <div className="flex flex-wrap items-stretch gap-2 justify-center">
              {NODES.map((node, i) => {
            const Icon = node.icon;
            const isLast = i === NODES.length - 1;
            const isLoopEdge = i === 3; // edge between analyzer and critic
            return (<div key={node.id} className="flex items-center gap-2">
                    <div className="flex w-28 flex-col items-center gap-1 rounded-[4px] border border-[var(--panel-border)] bg-[var(--panel-bg)] p-2.5 text-center">
                      <Icon className="h-4 w-4 text-[var(--accent-amber)]"/>
                      <span className="text-[11px] font-mono font-bold uppercase text-[var(--text-primary)]">{node.label}</span>
                    </div>
                    {!isLast && (<div className="flex flex-col items-center text-[var(--text-muted)]">
                        {isLoopEdge ? (<ArrowLeftRight className="h-3.5 w-3.5 text-[var(--accent-amber)]"/>) : (<ArrowRight className="h-3.5 w-3.5"/>)}
                      </div>)}
                  </div>);
        })}
            </div>
            <div className="mt-2.5 flex items-center justify-center gap-1.5 text-[10px] font-mono uppercase text-[var(--text-muted)]">
              <ArrowLeftRight className="h-3 w-3 text-[var(--accent-amber)]"/>
              <span>
                Analyzer ⇄ Critic self-refine loop (max 2 iterations)
              </span>
            </div>
          </div>

          {/* Node descriptions */}
          <div className="grid gap-2 sm:grid-cols-2">
            {NODES.map((node) => {
            const Icon = node.icon;
            return (<div key={node.id} className="rounded-[4px] border border-[var(--panel-border)] bg-[var(--panel-inner)] p-2.5 space-y-1">
                  <div className="flex items-center gap-2">
                    <div className="flex h-6 w-6 items-center justify-center rounded-[2px] border border-[var(--panel-border)] bg-[var(--panel-bg)] text-[var(--accent-amber)]">
                      <Icon className="h-3 w-3"/>
                    </div>
                    <span className="text-xs font-mono uppercase font-bold text-[var(--text-primary)]">{node.label}</span>
                  </div>
                  <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed">{node.desc}</p>
                </div>);
        })}
          </div>

          {/* RAG pipeline details */}
          <div className="rounded-[4px] border border-[var(--panel-border)] bg-[var(--panel-inner)] p-3 space-y-2">
            <div className="flex items-center gap-2">
              <Workflow className="h-3.5 w-3.5 text-[var(--accent-amber)]"/>
              <h3 className="text-xs font-mono font-bold uppercase text-[var(--text-primary)]">RAG Pipeline Internals</h3>
            </div>
            <ul className="text-[11px] space-y-1.5 text-[var(--text-secondary)] font-sans">
              <li>
                <span className="font-mono text-[9px] uppercase px-1.5 py-0.2 rounded-[2px] bg-[var(--panel-bg)] border border-[var(--panel-border)] text-[var(--accent-amber)] mr-2">1. Chunking</span>
                Recursive character splitter — 600 chars, 80 overlap, prefers paragraph → sentence → word boundaries.
              </li>
              <li>
                <span className="font-mono text-[9px] uppercase px-1.5 py-0.2 rounded-[2px] bg-[var(--panel-bg)] border border-[var(--panel-border)] text-[var(--accent-amber)] mr-2">2. Embedding</span>
                TF-IDF with stopword removal, L2-normalized sparse vectors. ~600 vocab terms over the bundled corpus.
              </li>
              <li>
                <span className="font-mono text-[9px] uppercase px-1.5 py-0.2 rounded-[2px] bg-[var(--panel-bg)] border border-[var(--panel-border)] text-[var(--accent-amber)] mr-2">3. Retrieval</span>
                Cosine similarity + MMR (λ=0.7) for diversity. Top-5 candidates.
              </li>
              <li>
                <span className="font-mono text-[9px] uppercase px-1.5 py-0.2 rounded-[2px] bg-[var(--panel-bg)] border border-[var(--panel-border)] text-[var(--accent-amber)] mr-2">4. Reranking</span>
                LLM cross-encoder scores each candidate 0-10 with rationale. Top-4 kept.
              </li>
              <li>
                <span className="font-mono text-[9px] uppercase px-1.5 py-0.2 rounded-[2px] bg-[var(--panel-bg)] border border-[var(--panel-border)] text-[var(--accent-amber)] mr-2">5. Generation</span>
                LLM synthesizes grounded answer with inline [n] citations.
              </li>
              <li>
                <span className="font-mono text-[9px] uppercase px-1.5 py-0.2 rounded-[2px] bg-[var(--panel-bg)] border border-[var(--panel-border)] text-[var(--accent-amber)] mr-2">6. Verification</span>
                LLM Critic checks for hallucinations, missing citations, misattribution. Can trigger a rewrite.
              </li>
            </ul>
          </div>

          {/* Tech stack */}
          <div className="rounded-[4px] border border-[var(--panel-border)] bg-[var(--panel-inner)] p-3 space-y-2">
            <h3 className="text-xs font-mono font-bold uppercase text-[var(--text-primary)]">Tech Stack</h3>
            <div className="flex flex-wrap gap-1.5 font-mono">
              {[
            "React 19",
            "Vite",
            "TypeScript",
            "Tailwind CSS 4",
            "TanStack Query",
            "Zustand",
            "React Router",
            "Lucide Icons",
        ].map((t) => (<span key={t} className="text-[10px] uppercase px-1.5 py-0.5 rounded-[2px] bg-[var(--panel-bg)] border border-[var(--panel-border)] text-[var(--text-secondary)]">
                  {t}
                </span>))}
            </div>
          </div>

          {/* Architectural Notes */}
          <div className="rounded-[4px] border border-emerald-800/80 bg-emerald-950/20 p-3 space-y-2">
            <h3 className="text-xs font-mono font-bold uppercase text-emerald-400">
              System Architecture & Design Notes
            </h3>
            <ul className="text-[11px] space-y-1.5 text-emerald-300/90 list-disc pl-4 font-sans">
              <li>
                <strong>Why TF-IDF + LLM reranker instead of dense embeddings?</strong>{" "}
                Cost: TF-IDF is deterministic and instant; the cross-encoder only evaluates candidate chunks.
              </li>
              <li>
                <strong>Why a self-refine loop?</strong> The Analyzer ⇄ Critic
                cycle mirrors Reflexion / Constitutional AI self-critique bounded at 2 iterations to control latency.
              </li>
              <li>
                <strong>Why a graph-based coordinator?</strong> Mirrors
                LangGraph StateGraph explicit edges and conditional transitions for multi-agent handoffs.
              </li>
            </ul>
          </div>
        </div>
      </DialogContent>
    </Dialog>);
}
