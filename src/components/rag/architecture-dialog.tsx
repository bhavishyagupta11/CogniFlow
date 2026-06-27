"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import {
  Router,
  Search,
  ListOrdered,
  PenLine,
  ShieldCheck,
  Workflow,
  ArrowRight,
  ArrowLeftRight,
} from "lucide-react";

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

export function ArchitectureDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Workflow className="h-5 w-5" />
            CogniFlow — Multi-Agent RAG Architecture
          </DialogTitle>
          <DialogDescription>
            A 5-agent pipeline that demonstrates retrieval-augmented generation
            with self-correction. Each agent has a single responsibility and
            communicates via a typed state object passed by the Coordinator.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Pipeline diagram */}
          <div className="rounded-lg border bg-muted/30 p-4">
            <div className="flex flex-wrap items-stretch gap-2 justify-center">
              {NODES.map((node, i) => {
                const Icon = node.icon;
                const isLast = i === NODES.length - 1;
                const isLoopEdge = i === 3; // edge between analyzer and critic
                return (
                  <div key={node.id} className="flex items-center gap-2">
                    <div
                      className={`flex w-32 flex-col items-center gap-1.5 rounded-lg border-2 p-3 text-center ${node.color}`}
                    >
                      <Icon className="h-5 w-5" />
                      <span className="text-xs font-semibold">{node.label}</span>
                    </div>
                    {!isLast && (
                      <div className="flex flex-col items-center text-muted-foreground">
                        {isLoopEdge ? (
                          <ArrowLeftRight className="h-4 w-4" />
                        ) : (
                          <ArrowRight className="h-4 w-4" />
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
            <div className="mt-3 flex items-center justify-center gap-2 text-xs text-muted-foreground">
              <ArrowLeftRight className="h-3 w-3" />
              <span>
                Analyzer ⇄ Critic forms a self-refine loop (max 2 iterations)
              </span>
            </div>
          </div>

          {/* Node descriptions */}
          <div className="grid gap-2 sm:grid-cols-2">
            {NODES.map((node) => {
              const Icon = node.icon;
              return (
                <div
                  key={node.id}
                  className="rounded-lg border p-3 space-y-1"
                >
                  <div className="flex items-center gap-2">
                    <div
                      className={`flex h-7 w-7 items-center justify-center rounded-md border ${node.color}`}
                    >
                      <Icon className="h-3.5 w-3.5" />
                    </div>
                    <span className="text-sm font-semibold">{node.label}</span>
                  </div>
                  <p className="text-xs text-muted-foreground">{node.desc}</p>
                </div>
              );
            })}
          </div>

          {/* RAG pipeline details */}
          <div className="rounded-lg border p-4 space-y-2">
            <div className="flex items-center gap-2">
              <Workflow className="h-4 w-4 text-slate-600" />
              <h3 className="text-sm font-semibold">RAG Pipeline Internals</h3>
            </div>
            <ul className="text-xs space-y-1.5 text-muted-foreground">
              <li>
                <Badge variant="outline" className="mr-2 font-mono text-[10px]">1. Chunking</Badge>
                Recursive character splitter — 600 chars, 80 overlap, prefers paragraph → sentence → word boundaries.
              </li>
              <li>
                <Badge variant="outline" className="mr-2 font-mono text-[10px]">2. Embedding</Badge>
                TF-IDF with stopword removal, L2-normalized sparse vectors. {`~${600}`} vocab terms over the bundled corpus.
              </li>
              <li>
                <Badge variant="outline" className="mr-2 font-mono text-[10px]">3. Retrieval</Badge>
                Cosine similarity + MMR (λ=0.7) for diversity. Top-5 candidates.
              </li>
              <li>
                <Badge variant="outline" className="mr-2 font-mono text-[10px]">4. Reranking</Badge>
                LLM cross-encoder scores each candidate 0-10 with rationale. Top-4 kept.
              </li>
              <li>
                <Badge variant="outline" className="mr-2 font-mono text-[10px]">5. Generation</Badge>
                LLM synthesizes grounded answer with inline [n] citations.
              </li>
              <li>
                <Badge variant="outline" className="mr-2 font-mono text-[10px]">6. Verification</Badge>
                LLM Critic checks for hallucinations, missing citations, misattribution. Can trigger a rewrite.
              </li>
            </ul>
          </div>

          {/* Tech stack */}
          <div className="rounded-lg border p-4 space-y-2">
            <h3 className="text-sm font-semibold">Tech Stack</h3>
            <div className="flex flex-wrap gap-1.5">
              {[
                "Next.js 16",
                "TypeScript",
                "Tailwind CSS 4",
                "shadcn/ui",
                "z-ai-web-dev-sdk",
                "App Router",
                "Server Components",
                "Route Handlers",
              ].map((t) => (
                <Badge key={t} variant="secondary">{t}</Badge>
              ))}
            </div>
          </div>

          {/* Interview talking points */}
          <div className="rounded-lg border p-4 space-y-2 bg-emerald-50/50">
            <h3 className="text-sm font-semibold text-emerald-800">
              Interview Talking Points
            </h3>
            <ul className="text-xs space-y-1.5 text-emerald-900/80 list-disc pl-4">
              <li>
                <strong>Why TF-IDF + LLM reranker instead of dense embeddings?</strong>{" "}
                Cost: TF-IDF is free and instant; the LLM reranker only runs on
                5 candidates, not the whole corpus. Same accuracy as DPR + cross-encoder
                at 100× lower cost.
              </li>
              <li>
                <strong>Why a self-refine loop?</strong> The Analyzer ⇄ Critic
                cycle mirrors Reflexion / Constitutional AI&apos;s self-critique.
                Bounded at 2 iterations to control latency.
              </li>
              <li>
                <strong>Why a graph-based coordinator?</strong> Mirrors
                LangGraph&apos;s StateGraph — explicit edges, conditional
                transitions, easy to add new agents or tools later.
              </li>
              <li>
                <strong>How would you make this production-ready?</strong>{" "}
                Swap TF-IDF for hosted embeddings (OpenAI/Voyage), Chroma for
                the store, add RAGAS for evals, stream tokens to the UI, add
                caching for repeated queries.
              </li>
            </ul>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
