"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { AgentTrace } from "@/components/rag/agent-trace";
import { SourcesPanel } from "@/components/rag/sources-panel";
import { ArchitectureDialog } from "@/components/rag/architecture-dialog";
import { KnowledgeBaseDialog } from "@/components/rag/knowledge-base-dialog";
import { AgentRunResult } from "@/lib/agents/types";
import { KNOWLEDGE_BASE } from "@/lib/rag/documents";
import { toast } from "sonner";
import {
  Send,
  Sparkles,
  Workflow,
  Clock,
  User,
  Bot,
  Github,
  BookOpen,
  Loader2,
  Square,
} from "lucide-react";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: AgentRunResult["sources"];
  steps?: AgentRunResult["steps"];
  totalDurationMs?: number;
  error?: boolean;
}

const SAMPLE_PROMPTS = [
  "How does attention work in transformers?",
  "Compare BERT and GPT-3 in terms of architecture and use cases.",
  "What are the advantages of RAG over fine-tuning?",
  "Explain the ReAct pattern and when it outperforms chain-of-thought.",
  "How does Constitutional AI differ from RLHF?",
  "What is LangGraph and when would you use it?",
];

export default function HomePage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [archOpen, setArchOpen] = useState(false);
  const [kbOpen, setKbOpen] = useState(false);
  const [uploadedCount, setUploadedCount] = useState(0);
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const fetchDocCount = useCallback(async () => {
    try {
      const res = await fetch("/api/documents");
      if (res.ok) {
        const data = await res.json();
        const completed = data.filter((d: any) => d.processingStatus === "completed").length;
        setUploadedCount(completed);
      }
    } catch (e) {}
  }, []);

  useEffect(() => {
    fetchDocCount();
  }, [fetchDocCount]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  async function handleSubmit(prompt?: string) {
    const question = (prompt ?? input).trim();
    if (!question || loading) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setLoading(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
        signal: controller.signal,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: "Request failed" }));
        throw new Error(err.error ?? `HTTP ${res.status}`);
      }

      const result: AgentRunResult = await res.json();
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: result.answer,
          sources: result.sources,
          steps: result.steps,
          totalDurationMs: result.totalDurationMs,
        },
      ]);
    } catch (e: any) {
      if (e.name === "AbortError") {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: "_(request cancelled)_",
            error: true,
          },
        ]);
      } else {
        toast.error(e?.message ?? "Pipeline failed");
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: `Sorry, something went wrong: ${e?.message ?? "unknown error"}`,
            error: true,
          },
        ]);
      }
    } finally {
      setLoading(false);
      abortRef.current = null;
    }
  }

  function handleCancel() {
    abortRef.current?.abort();
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }

  // Find the latest assistant message that has steps for the right-panel
  const latestSteps =
    [...messages].reverse().find((m) => m.role === "assistant" && m.steps)
      ?.steps ?? [];
  const latestTotalMs =
    [...messages].reverse().find((m) => m.role === "assistant" && m.steps)
      ?.totalDurationMs ?? 0;

  return (
    <div className="flex h-screen flex-col bg-gradient-to-br from-slate-50 via-white to-violet-50/30">
      {/* Header */}
      <header className="border-b bg-white/80 backdrop-blur-md sticky top-0 z-10">
        <div className="mx-auto flex max-w-[1600px] items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-violet-600 to-rose-500 text-white shadow-sm">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight">
                CogniFlow
              </h1>
              <p className="text-[11px] text-muted-foreground -mt-0.5">
                RAG + Multi-Agent Research Assistant
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setKbOpen(true)}
            >
              <BookOpen className="h-4 w-4 mr-1.5" />
              Knowledge Base
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setArchOpen(true)}
            >
              <Workflow className="h-4 w-4 mr-1.5" />
              Architecture
            </Button>
            <a
              href="https://github.com/your-username/cogniflow"
              target="_blank"
              rel="noreferrer"
              className="inline-flex"
            >
              <Button variant="ghost" size="sm">
                <Github className="h-4 w-4" />
              </Button>
            </a>
          </div>
        </div>
      </header>

      {/* Main layout */}
      <div className="flex flex-1 min-h-0 mx-auto max-w-[1600px] w-full">
        {/* Chat column */}
        <main className="flex-1 flex flex-col min-w-0 border-r">
          {/* Messages */}
          <ScrollArea className="flex-1" ref={scrollRef as any}>
            <div className="mx-auto max-w-3xl px-4 py-6 space-y-6">
              {messages.length === 0 && (
                <WelcomeScreen onPickPrompt={(p) => handleSubmit(p)} uploadedCount={uploadedCount} />
              )}

              {messages.map((msg, i) => (
                <MessageBubble key={i} message={msg} />
              ))}

              {loading && <LoadingIndicator />}
            </div>
          </ScrollArea>

          {/* Sample prompts */}
          {messages.length === 0 && (
            <div className="border-t bg-white/60 backdrop-blur px-4 py-3">
              <div className="mx-auto max-w-3xl">
                <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground mb-2">
                  Try one of these
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {SAMPLE_PROMPTS.map((p) => (
                    <button
                      key={p}
                      onClick={() => handleSubmit(p)}
                      disabled={loading}
                      className="rounded-full border bg-white px-3 py-1 text-xs text-foreground/80 hover:border-violet-300 hover:bg-violet-50 hover:text-violet-700 transition-colors disabled:opacity-50"
                    >
                      {p}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Composer */}
          <div className="border-t bg-white p-4">
            <div className="mx-auto max-w-3xl">
              <div className="relative rounded-xl border bg-white shadow-sm focus-within:ring-2 focus-within:ring-violet-400/40 focus-within:border-violet-400 transition">
                <Textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask about transformers, BERT, GPT-3, RAG, ReAct, Constitutional AI, LangGraph…"
                  disabled={loading}
                  className="min-h-[56px] max-h-[200px] resize-none border-0 bg-transparent pr-24 focus-visible:ring-0 focus-visible:ring-offset-0 text-sm"
                  rows={2}
                />
                <div className="absolute bottom-2 right-2 flex items-center gap-2">
                  <span className="text-[10px] text-muted-foreground hidden sm:inline">
                    Enter to send · Shift+Enter for newline
                  </span>
                  {loading ? (
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={handleCancel}
                    >
                      <Square className="h-3.5 w-3.5 mr-1" />
                      Cancel
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      onClick={() => handleSubmit()}
                      disabled={!input.trim()}
                    >
                      <Send className="h-3.5 w-3.5 mr-1" />
                      Send
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </div>
        </main>

        {/* Agent trace column */}
        <aside className="hidden lg:flex w-[400px] xl:w-[440px] flex-col bg-slate-50/50">
          <div className="border-b px-4 py-3 flex items-center justify-between bg-white/60 backdrop-blur">
            <div className="flex items-center gap-2">
              <Workflow className="h-4 w-4 text-muted-foreground" />
              <h2 className="text-sm font-semibold">Agent Trace</h2>
            </div>
            {latestTotalMs > 0 && (
              <Badge variant="outline" className="font-mono text-[10px]">
                <Clock className="h-3 w-3 mr-1" />
                {(latestTotalMs / 1000).toFixed(2)}s total
              </Badge>
            )}
          </div>
          <div className="flex-1 min-h-0">
            <AgentTrace steps={loading ? [] : latestSteps} />
          </div>
        </aside>
      </div>

      <ArchitectureDialog open={archOpen} onOpenChange={setArchOpen} />
      <KnowledgeBaseDialog open={kbOpen} onOpenChange={setKbOpen} onDocumentsChanged={fetchDocCount} />
    </div>
  );
}

function WelcomeScreen({ onPickPrompt, uploadedCount }: { onPickPrompt: (p: string) => void, uploadedCount: number }) {
  const totalPapers = KNOWLEDGE_BASE.length + uploadedCount;
  return (
    <Card className="border-2 border-dashed bg-gradient-to-br from-violet-50/50 to-rose-50/30 p-8 space-y-4">
      <div className="flex items-center gap-3">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-violet-600 to-rose-500 text-white shadow-md">
          <Sparkles className="h-6 w-6" />
        </div>
        <div>
          <h2 className="text-xl font-bold">CogniFlow</h2>
          <p className="text-sm text-muted-foreground">
            A RAG + Multi-Agent Research Assistant
          </p>
        </div>
      </div>

      <p className="text-sm leading-relaxed text-foreground/80">
        Ask any question about influential AI/ML papers — the system routes your
        question through a 5-agent pipeline: <strong>Router</strong> (query
        understanding) → <strong>Retriever</strong> (TF-IDF + MMR) →{" "}
        <strong>Reranker</strong> (LLM cross-encoder) →{" "}
        <strong>Analyzer</strong> (grounded synthesis) →{" "}
        <strong>Critic</strong> (hallucination check, with self-refine loop).
      </p>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
        <div className="rounded-md border bg-white p-2">
          <div className="font-semibold text-emerald-700">{totalPapers} papers</div>
          <div className="text-muted-foreground">Bundled knowledge base</div>
        </div>
        <div className="rounded-md border bg-white p-2">
          <div className="font-semibold text-amber-700">TF-IDF + MMR</div>
          <div className="text-muted-foreground">Retrieval strategy</div>
        </div>
        <div className="rounded-md border bg-white p-2">
          <div className="font-semibold text-violet-700">5 agents</div>
          <div className="text-muted-foreground">Coordinated pipeline</div>
        </div>
      </div>

      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <BookOpen className="h-3.5 w-3.5" />
        Click <Workflow className="h-3.5 w-3.5 inline" /> Architecture in the
        header to see the full diagram.
      </div>
    </Card>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className="flex gap-3">
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-md ${
          isUser
            ? "bg-slate-200 text-slate-700"
            : message.error
              ? "bg-rose-100 text-rose-700"
              : "bg-gradient-to-br from-violet-600 to-rose-500 text-white"
        }`}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>
      <div className="flex-1 min-w-0 space-y-1">
        <div className="text-xs font-semibold text-muted-foreground">
          {isUser ? "You" : "CogniFlow"}
          {!isUser && message.totalDurationMs !== undefined && (
            <span className="ml-2 font-mono text-[10px] text-muted-foreground/70">
              {(message.totalDurationMs / 1000).toFixed(2)}s ·{" "}
              {message.steps?.length ?? 0} agent steps
            </span>
          )}
        </div>
        <div
          className={`prose prose-sm max-w-none rounded-lg px-3 py-2 ${
            isUser
              ? "bg-slate-100"
              : message.error
                ? "bg-rose-50 border border-rose-200"
                : "bg-white border"
          }`}
        >
          <div className="text-sm leading-relaxed whitespace-pre-wrap">
            {message.content}
          </div>
        </div>
        {!isUser && message.sources && message.sources.length > 0 && (
          <SourcesPanel sources={message.sources} />
        )}
      </div>
    </div>
  );
}

function LoadingIndicator() {
  return (
    <div className="flex gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-gradient-to-br from-violet-600 to-rose-500 text-white">
        <Loader2 className="h-4 w-4 animate-spin" />
      </div>
      <div className="flex-1 space-y-2">
        <div className="text-xs font-semibold text-muted-foreground">
          CogniFlow
        </div>
        <div className="rounded-lg border bg-white px-3 py-2 text-sm text-muted-foreground space-y-1">
          <div className="flex items-center gap-2">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            <span>Agents are working… check the trace panel →</span>
          </div>
          <p className="text-[11px] text-muted-foreground/70">
            The pipeline runs 5 LLM calls in sequence; expect 8-15 seconds.
          </p>
        </div>
      </div>
    </div>
  );
}
