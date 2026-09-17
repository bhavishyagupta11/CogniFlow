import React, { useState } from "react";
import {
  Workflow,
  Zap,
  Brain,
  Bot,
  FileText,
  Server,
  Layers,
  ArrowDown,
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
  Database,
  Radio,
  Clock,
  Sparkles,
  GitFork,
  FileSearch,
} from "lucide-react";

export function ArchitecturePage() {
  const [activeFlowMode, setActiveFlowMode] = useState("adaptive_rag");
  const [activeTab, setActiveTab] = useState("execution"); // 'execution' | 'ingestion' | 'provider' | 'citations' | 'streaming'

  return (
    <div className="flex-1 flex flex-col min-w-0 h-full overflow-y-auto bg-[var(--bg-page)] text-[var(--text-primary)] font-mono p-4 sm:p-6 lg:p-8 select-none">
      <div className="max-w-7xl w-full mx-auto space-y-8">
        {/* Header Banner */}
        <div className="border border-[var(--panel-border)] bg-[var(--panel-bg)] rounded-[3px] p-5 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <div className="h-6 w-6 rounded-[2px] bg-[#f97316] text-white flex items-center justify-center font-bold text-xs">
                ■
              </div>
              <h1 className="text-base sm:text-lg font-bold uppercase tracking-wider text-[var(--text-primary)]">
                COGNIFLOW ARCHITECTURE SPECIFICATION
              </h1>
            </div>
            <p className="text-xs text-[var(--text-secondary)] font-sans leading-relaxed">
              Adaptive Hybrid Text-RAG: Use the minimum computation required to produce a correct, grounded answer.
            </p>
          </div>

          {/* Tab Navigation */}
          <div className="flex items-center gap-1.5 flex-wrap">
            {[
              { id: "execution", label: "QUERY EXECUTION", icon: Workflow },
              { id: "ingestion", label: "SEMANTIC INGESTION", icon: FileText },
              { id: "provider", label: "PROVIDER HIERARCHY", icon: Server },
              { id: "citations", label: "CITATION PROVENANCE", icon: ShieldCheck },
              { id: "streaming", label: "STREAMING & SCROLL", icon: Radio },
            ].map((tab) => {
              const Icon = tab.icon;
              const isSelected = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-[2px] text-[11px] font-mono font-bold tracking-wider uppercase transition-all cursor-pointer border ${
                    isSelected
                      ? "border-[#f97316] bg-[#f97316] text-white shadow-xs"
                      : "border-[var(--panel-border)] bg-[var(--panel-inner)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--border-focus)]"
                  }`}
                >
                  <Icon className="h-3.5 w-3.5" />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* TAB 1: PRIMARY QUERY EXECUTION FLOW */}
        {activeTab === "execution" && (
          <div className="space-y-6">
            {/* Interactive Mode Highlight Switcher */}
            <div className="border border-[var(--panel-border)] bg-[var(--panel-bg)] rounded-[3px] p-4 space-y-3">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <span className="text-xs font-bold uppercase tracking-wider text-[#f97316]">
                  SELECT ACTIVE EXECUTION PATH TO TRACE FLOW:
                </span>
                <span className="text-[10px] text-[var(--text-muted)]">
                  Highlighted components indicate active pipeline execution
                </span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {[
                  { id: "fast", label: "1. FAST", sub: "Sub-3s, 1 Gen Call, No Critic", icon: Zap },
                  { id: "adaptive_rag", label: "2. ADAPTIVE RAG", sub: "Simple / Moderate / Complex", icon: Workflow },
                  { id: "deep_research", label: "3. DEEP RESEARCH", sub: "Planner + Parallel Workers", icon: Brain },
                  { id: "general_chat", label: "4. GENERAL CHAT", sub: "Zero Retrieval, Zero Citations", icon: Bot },
                ].map((mode) => {
                  const Icon = mode.icon;
                  const isSelected = activeFlowMode === mode.id;
                  return (
                    <button
                      key={mode.id}
                      onClick={() => setActiveFlowMode(mode.id)}
                      className={`p-3 rounded-[3px] border text-left transition-all cursor-pointer ${
                        isSelected
                          ? "border-[#f97316] bg-[#fff7ed] dark:bg-[#f97316]/15 shadow-xs"
                          : "border-[var(--panel-border)] bg-[var(--panel-inner)] hover:border-[var(--border-focus)]"
                      }`}
                    >
                      <div className="flex items-center gap-1.5">
                        <Icon className={`h-4 w-4 ${isSelected ? "text-[#f97316]" : "text-[var(--text-muted)]"}`} />
                        <span className={`text-xs font-bold tracking-wider ${isSelected ? "text-[#f97316]" : "text-[var(--text-primary)]"}`}>
                          {mode.label}
                        </span>
                      </div>
                      <p className="text-[10px] text-[var(--text-secondary)] mt-1 font-sans">
                        {mode.sub}
                      </p>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Visual Arrow-Driven Flowchart */}
            <div className="border border-[var(--panel-border)] bg-[var(--panel-bg)] rounded-[3px] p-6 shadow-xs overflow-x-auto space-y-6">
              <div className="min-w-[760px] space-y-6">
                {/* 1. Request Ingestion */}
                <div className="flex flex-col items-center">
                  <div className="px-6 py-2.5 rounded-[3px] border border-[var(--panel-border)] bg-[var(--panel-inner)] text-center shadow-xs">
                    <span className="text-xs font-bold uppercase text-[var(--text-primary)]">USER QUERY & EXPLICIT MODE</span>
                    <span className="block text-[10px] text-[var(--text-muted)]">User selected: {activeFlowMode.toUpperCase()}</span>
                  </div>
                  <ArrowDown className="h-5 w-5 text-[var(--text-muted)] my-1 animate-pulse" />
                  <div className="px-6 py-2.5 rounded-[3px] border border-[#f97316] bg-[#f97316]/10 text-center shadow-xs">
                    <span className="text-xs font-bold uppercase text-[#f97316]">ADAPTIVE ROUTER & TARGETING CONTROLLER</span>
                    <span className="block text-[10px] text-[var(--text-secondary)]">0ms deterministic policy · Evaluates query linguistics & document scope</span>
                  </div>
                  <ArrowDown className="h-5 w-5 text-[var(--text-muted)] my-1" />
                </div>

                {/* 2. Branch Execution Paths */}
                <div className="grid grid-cols-4 gap-4">
                  {/* PATH 1: FAST */}
                  <div className={`p-3.5 rounded-[3px] border space-y-3 ${
                    activeFlowMode === "fast"
                      ? "border-[#f97316] bg-[#fff7ed] dark:bg-[#f97316]/15 shadow-md"
                      : "border-[var(--panel-border)] bg-[var(--panel-inner)] opacity-40"
                  }`}>
                    <div className="flex items-center gap-1.5 text-xs font-bold uppercase text-amber-600">
                      <Zap className="h-3.5 w-3.5" />
                      <span>FAST PATH</span>
                    </div>
                    <div className="space-y-1 text-[11px] text-[var(--text-secondary)] font-mono">
                      <div className="p-1.5 border border-[var(--panel-border)] bg-[var(--panel-bg)] rounded-[2px]">1. Fast Retrieval (k=5)</div>
                      <div className="p-1.5 border border-[var(--panel-border)] bg-[var(--panel-bg)] rounded-[2px]">2. Conditional Light Rerank</div>
                      <div className="p-1.5 border border-[var(--panel-border)] bg-[var(--panel-bg)] rounded-[2px]">3. Single Generation Call</div>
                      <div className="p-1.5 border border-[var(--panel-border)] bg-[var(--panel-bg)] rounded-[2px]">4. Deterministic Citations</div>
                    </div>
                    <div className="text-[10px] text-[var(--text-muted)] pt-1 border-t border-[var(--panel-border)]">
                      Target: 2–5s latency
                    </div>
                  </div>

                  {/* PATH 2: ADAPTIVE RAG (DEFAULT) */}
                  <div className={`p-3.5 rounded-[3px] border space-y-3 ${
                    activeFlowMode === "adaptive_rag"
                      ? "border-[#f97316] bg-[#fff7ed] dark:bg-[#f97316]/15 shadow-md"
                      : "border-[var(--panel-border)] bg-[var(--panel-inner)] opacity-40"
                  }`}>
                    <div className="flex items-center gap-1.5 text-xs font-bold uppercase text-[#f97316]">
                      <Workflow className="h-3.5 w-3.5" />
                      <span>ADAPTIVE RAG</span>
                    </div>
                    <div className="space-y-1 text-[11px] text-[var(--text-secondary)] font-mono">
                      <div className="p-1.5 border border-[var(--panel-border)] bg-[var(--panel-bg)] rounded-[2px]">1. Candidate Retrieval (k=6)</div>
                      <div className="p-1.5 border border-[var(--panel-border)] bg-[var(--panel-bg)] rounded-[2px]">2. Score Distribution Analysis</div>
                      <div className="p-1.5 border border-[#f97316]/50 bg-[#f97316]/10 rounded-[2px] text-[#f97316] font-bold">
                        → Simple / Moderate / Complex
                      </div>
                      <div className="p-1.5 border border-[var(--panel-border)] bg-[var(--panel-bg)] rounded-[2px]">3. Conditional Reranking</div>
                      <div className="p-1.5 border border-[var(--panel-border)] bg-[var(--panel-bg)] rounded-[2px]">4. Grounded Synthesis</div>
                    </div>
                    <div className="text-[10px] text-[var(--text-muted)] pt-1 border-t border-[var(--panel-border)]">
                      Target: 3–7s latency
                    </div>
                  </div>

                  {/* PATH 3: DEEP RESEARCH */}
                  <div className={`p-3.5 rounded-[3px] border space-y-3 ${
                    activeFlowMode === "deep_research"
                      ? "border-[#f97316] bg-[#fff7ed] dark:bg-[#f97316]/15 shadow-md"
                      : "border-[var(--panel-border)] bg-[var(--panel-inner)] opacity-40"
                  }`}>
                    <div className="flex items-center gap-1.5 text-xs font-bold uppercase text-rose-500">
                      <Brain className="h-3.5 w-3.5" />
                      <span>DEEP RESEARCH</span>
                    </div>
                    <div className="space-y-1 text-[11px] text-[var(--text-secondary)] font-mono">
                      <div className="p-1.5 border border-[var(--panel-border)] bg-[var(--panel-bg)] rounded-[2px]">1. Research Planner Decomp</div>
                      <div className="p-1.5 border border-[var(--panel-border)] bg-[var(--panel-bg)] rounded-[2px]">2. Parallel Retrieval Workers</div>
                      <div className="p-1.5 border border-[var(--panel-border)] bg-[var(--panel-bg)] rounded-[2px]">3. Evidence Merge & RRF</div>
                      <div className="p-1.5 border border-[var(--panel-border)] bg-[var(--panel-bg)] rounded-[2px]">4. Deep Synthesis</div>
                      <div className="p-1.5 border border-[var(--panel-border)] bg-[var(--panel-bg)] rounded-[2px]">5. Claim Verifier (max 1 iter)</div>
                    </div>
                    <div className="text-[10px] text-[var(--text-muted)] pt-1 border-t border-[var(--panel-border)]">
                      Target: 5–10s latency
                    </div>
                  </div>

                  {/* PATH 4: GENERAL CHAT */}
                  <div className={`p-3.5 rounded-[3px] border space-y-3 ${
                    activeFlowMode === "general_chat"
                      ? "border-[#f97316] bg-[#fff7ed] dark:bg-[#f97316]/15 shadow-md"
                      : "border-[var(--panel-border)] bg-[var(--panel-inner)] opacity-40"
                  }`}>
                    <div className="flex items-center gap-1.5 text-xs font-bold uppercase text-blue-500">
                      <Bot className="h-3.5 w-3.5" />
                      <span>GENERAL CHAT</span>
                    </div>
                    <div className="space-y-1 text-[11px] text-[var(--text-secondary)] font-mono">
                      <div className="p-1.5 border border-[var(--panel-border)] bg-[var(--panel-bg)] rounded-[2px] text-emerald-600 font-bold">
                        Bypasses RAG Engine
                      </div>
                      <div className="p-1.5 border border-[var(--panel-border)] bg-[var(--panel-bg)] rounded-[2px]">1. Direct Provider Stream</div>
                      <div className="p-1.5 border border-[var(--panel-border)] bg-[var(--panel-bg)] rounded-[2px]">2. Zero Document Retrieval</div>
                      <div className="p-1.5 border border-[var(--panel-border)] bg-[var(--panel-bg)] rounded-[2px]">3. Zero Citations / Source Cards</div>
                    </div>
                    <div className="text-[10px] text-[var(--text-muted)] pt-1 border-t border-[var(--panel-border)]">
                      Clean conversation mode
                    </div>
                  </div>
                </div>

                {/* Detailed Hybrid Text-RAG Flowchart (Specification Section 32 & 60) */}
                <div className="border border-[var(--panel-border)] bg-[var(--panel-inner)] rounded-[3px] p-5 space-y-4">
                  <div className="flex items-center justify-between border-b border-[var(--panel-border)] pb-2">
                    <span className="text-xs font-bold font-mono text-[#f97316] uppercase tracking-wider">
                      PRIMARY ADAPTIVE HYBRID TEXT-RAG RETRIEVAL & FUSION ENGINE
                    </span>
                    <span className="text-[10px] font-mono text-[var(--text-muted)]">
                      Reciprocal Rank Fusion · MMR Diversity · Empirical Gate
                    </span>
                  </div>

                  {/* Flowchart Diagram */}
                  <div className="flex flex-col items-center space-y-2 text-center text-xs font-mono">
                    <div className="px-5 py-2 rounded-[2px] border border-[var(--panel-border)] bg-[var(--panel-bg)] font-bold text-[var(--text-primary)] shadow-xs">
                      USER QUERY
                    </div>
                    <ArrowDown className="h-4 w-4 text-[var(--text-muted)]" />

                    <div className="px-5 py-2 rounded-[2px] border border-[#f97316] bg-[#f97316]/10 font-bold text-[#f97316] shadow-xs">
                      QUERY ROUTER & COMPLEXITY ESTIMATOR
                    </div>
                    <ArrowDown className="h-4 w-4 text-[var(--text-muted)]" />

                    {/* Dual Parallel Search */}
                    <div className="grid grid-cols-2 gap-4 w-full max-w-xl">
                      <div className="p-3 rounded-[2px] border border-blue-500/50 bg-blue-500/10 text-center">
                        <span className="font-bold text-blue-700 dark:text-blue-300 block">LEXICAL SEARCH</span>
                        <span className="text-[10px] text-[var(--text-secondary)]">Sparse TF-IDF Cosine Similarity</span>
                      </div>
                      <div className="p-3 rounded-[2px] border border-purple-500/50 bg-purple-500/10 text-center">
                        <span className="font-bold text-purple-700 dark:text-purple-300 block">SEMANTIC SEARCH</span>
                        <span className="text-[10px] text-[var(--text-secondary)]">LSA Dense TruncatedSVD Concept Vectors</span>
                      </div>
                    </div>
                    <ArrowDown className="h-4 w-4 text-[var(--text-muted)]" />

                    <div className="px-5 py-2 rounded-[2px] border border-emerald-500/50 bg-emerald-500/10 font-bold text-emerald-700 dark:text-emerald-300 shadow-xs w-full max-w-xl">
                      RECIPROCAL RANK FUSION (RRF k=60)
                      <span className="block text-[10px] font-normal text-[var(--text-secondary)]">
                        Unifies uncalibrated lexical and latent semantic score distributions
                      </span>
                    </div>
                    <ArrowDown className="h-4 w-4 text-[var(--text-muted)]" />

                    <div className="px-5 py-2 rounded-[2px] border border-[var(--panel-border)] bg-[var(--panel-bg)] font-bold text-[var(--text-primary)] shadow-xs w-full max-w-xl">
                      MMR DIVERSITY CONTROLLER (λ=0.7)
                      <span className="block text-[10px] font-normal text-[var(--text-secondary)]">
                        Detects pairwise passage redundancy (threshold &gt; 0.82) to prevent near-duplicate chunks
                      </span>
                    </div>
                    <ArrowDown className="h-4 w-4 text-[var(--text-muted)]" />

                    <div className="px-5 py-2 rounded-[2px] border border-amber-500/50 bg-amber-500/10 font-bold text-amber-700 dark:text-amber-300 shadow-xs w-full max-w-xl">
                      CONDITIONAL RERANKER (EMPIRICAL THRESHOLD: 0.58)
                      <span className="block text-[10px] font-normal text-[var(--text-secondary)]">
                        Skipped for high-confidence decisive retrieval; executes when candidate scores are ambiguous
                      </span>
                    </div>
                    <ArrowDown className="h-4 w-4 text-[var(--text-muted)]" />

                    <div className="px-5 py-2 rounded-[2px] border border-[var(--panel-border)] bg-[var(--panel-bg)] font-bold text-[var(--text-primary)] shadow-xs w-full max-w-xl">
                      CONTEXT BUDGET SELECTION
                      <span className="block text-[10px] font-normal text-[var(--text-secondary)]">
                        Formats top diverse evidence chunks into [E1], [E2] blocks with full provenance
                      </span>
                    </div>
                    <ArrowDown className="h-4 w-4 text-[var(--text-muted)]" />

                    <div className="px-5 py-2 rounded-[2px] border border-[#f97316] bg-[#f97316]/10 font-bold text-[#f97316] shadow-xs w-full max-w-xl">
                      GROUNDED GENERATION (OFFICIAL GOOGLE-GENAI SDK)
                      <span className="block text-[10px] font-normal text-[var(--text-secondary)]">
                        Single-pass streaming prompt instructing model to cite [E1], [E2] strictly from evidence
                      </span>
                    </div>
                    <ArrowDown className="h-4 w-4 text-[var(--text-muted)]" />

                    <div className="px-5 py-2 rounded-[2px] border border-teal-500/50 bg-teal-500/10 font-bold text-teal-700 dark:text-teal-300 shadow-xs w-full max-w-xl">
                      DETERMINISTIC CITATION PROVENANCE & SELECTIVE VERIFICATION
                      <span className="block text-[10px] font-normal text-[var(--text-secondary)]">
                        Maps claims to exact chunk_id, document_name, and page ranges · Zero invented citations
                      </span>
                    </div>
                  </div>
                </div>

                {/* 3. Output Stage */}
                <div className="flex flex-col items-center pt-2">
                  <div className="w-full max-w-xl p-3.5 rounded-[3px] border border-[var(--panel-border)] bg-[var(--panel-inner)] text-center space-y-1 shadow-xs">
                    <span className="text-xs font-bold uppercase text-[var(--text-primary)]">
                      REAL-TIME SSE STREAMING & SCROLL CONTROLLER
                    </span>
                    <p className="text-[10px] text-[var(--text-secondary)] font-sans">
                      Streams tokens immediately · Near-bottom auto-follow · User scroll-up leaves stream uninterrupted
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: SEMANTIC INGESTION FLOW */}
        {activeTab === "ingestion" && (
          <div className="space-y-6">
            <div className="border border-[var(--panel-border)] bg-[var(--panel-bg)] rounded-[3px] p-6 shadow-xs space-y-6">
              <div>
                <h2 className="text-sm font-bold uppercase tracking-wider text-[#f97316]">
                  DOCUMENT INGESTION & STRUCTURE-AWARE SEMANTIC CHUNKING FLOW
                </h2>
                <p className="text-xs text-[var(--text-secondary)] font-sans mt-1">
                  Replaces fixed 600-character chunking with structural segmentation preserving section boundaries, headings, and exact page numbers.
                </p>
              </div>

              {/* 6-Stage Ingestion Pipeline Flow */}
              <div className="grid grid-cols-1 md:grid-cols-6 gap-2 items-center text-center">
                <div className="p-3 border border-[var(--panel-border)] bg-[var(--panel-inner)] rounded-[3px]">
                  <FileText className="h-5 w-5 text-[#f97316] mx-auto mb-1" />
                  <div className="text-[11px] font-bold">1. UPLOAD</div>
                  <div className="text-[9px] text-[var(--text-muted)]">PDF / TXT / MD</div>
                </div>

                <div className="p-3 border border-[var(--panel-border)] bg-[var(--panel-inner)] rounded-[3px]">
                  <Layers className="h-5 w-5 text-amber-500 mx-auto mb-1" />
                  <div className="text-[11px] font-bold">2. PARSING</div>
                  <div className="text-[9px] text-[var(--text-muted)]">PyMuPDF (fitz)</div>
                </div>

                <div className="p-3 border border-[var(--panel-border)] bg-[var(--panel-inner)] rounded-[3px]">
                  <FileSearch className="h-5 w-5 text-blue-500 mx-auto mb-1" />
                  <div className="text-[11px] font-bold">3. STRUCTURE</div>
                  <div className="text-[9px] text-[var(--text-muted)]">Headings & Lists</div>
                </div>

                <div className="p-3 border border-[#f97316] bg-[#f97316]/10 rounded-[3px]">
                  <FileSearch className="h-5 w-5 text-[#f97316] mx-auto mb-1" />
                  <div className="text-[11px] font-bold text-[#f97316]">4. SEMANTIC CHUNKING</div>
                  <div className="text-[9px] text-[var(--text-secondary)]">Bonds headers & text</div>
                </div>

                <div className="p-3 border border-purple-500/50 bg-purple-500/10 rounded-[3px]">
                  <ShieldCheck className="h-5 w-5 text-purple-600 mx-auto mb-1" />
                  <div className="text-[11px] font-bold text-purple-700 dark:text-purple-300">5. PROVENANCE</div>
                  <div className="text-[9px] text-[var(--text-secondary)]">doc_id, page_start/end</div>
                </div>

                <div className="p-3 border border-emerald-500/50 bg-emerald-500/10 rounded-[3px]">
                  <Database className="h-5 w-5 text-emerald-600 mx-auto mb-1" />
                  <div className="text-[11px] font-bold text-emerald-700 dark:text-emerald-300">6. INDEXING</div>
                  <div className="text-[9px] text-[var(--text-secondary)]">TF-IDF + LSA SVD</div>
                </div>
              </div>

              {/* Dual Path Output: Searchable Vector Store + Background Summary Precomputation */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-[var(--panel-border)]">
                <div className="p-4 rounded-[3px] border border-[var(--panel-border)] bg-[var(--panel-inner)] space-y-2">
                  <div className="flex items-center gap-2 text-xs font-bold uppercase text-[var(--text-primary)]">
                    <Database className="h-4 w-4 text-emerald-600" />
                    <span>Searchable Hybrid Vector Store</span>
                  </div>
                  <p className="text-xs text-[var(--text-secondary)] font-sans leading-relaxed">
                    Indexed chunks retain complete provenance: chunk_id, document_id, section, subsection, page_start, page_end, and text. Ready for sub-millisecond hybrid query retrieval.
                  </p>
                </div>

                <div className="p-4 rounded-[3px] border border-[#f97316] bg-[#fff7ed] dark:bg-[#f97316]/15 space-y-2">
                  <div className="flex items-center gap-2 text-xs font-bold uppercase text-[#f97316]">
                    <Clock className="h-4 w-4" />
                    <span>Background Summary Precomputation</span>
                  </div>
                  <p className="text-xs text-[var(--text-secondary)] font-sans leading-relaxed">
                    Upon document upload, background task partitions batches, generates chapter summaries, and populates the Summary Cache. When a user requests a summary, it resolves in &lt; 50ms from cache without blocking.
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: PROVIDER HIERARCHY */}
        {activeTab === "provider" && (
          <div className="space-y-6">
            <div className="border border-[var(--panel-border)] bg-[var(--panel-bg)] rounded-[3px] p-6 shadow-xs space-y-6">
              <div>
                <h2 className="text-sm font-bold uppercase tracking-wider text-[#f97316]">
                  LLM PROVIDER ABSTRACTION & FALLBACK CHAIN
                </h2>
                <p className="text-xs text-[var(--text-secondary)] font-sans mt-1">
                  CogniFlow implements an authoritative provider hierarchy with automatic failover and honest telemetry. Zero fake/heuristic generation.
                </p>
              </div>

              {/* Provider Chain Cards */}
              <div className="space-y-3 max-w-2xl mx-auto">
                {/* 1. Primary Remote Provider */}
                <div className="p-4 rounded-[3px] border border-emerald-500/50 bg-emerald-500/10 flex items-center justify-between">
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold uppercase text-emerald-700 dark:text-emerald-400">1. PRIMARY REMOTE PROVIDER</span>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 rounded-[2px]">PREFERRED</span>
                    </div>
                    <div className="text-xs font-mono text-[var(--text-primary)]">Google Gemini (official google-genai SDK)</div>
                    <div className="text-[10px] text-[var(--text-muted)]">Model: gemini-2.5-flash / gemini-3.6-flash</div>
                  </div>
                  <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                </div>

                <div className="flex justify-center"><ArrowDown className="h-4 w-4 text-[var(--text-muted)]" /></div>

                {/* 2. Secondary Remote Provider */}
                <div className="p-4 rounded-[3px] border border-blue-500/50 bg-blue-500/10 flex items-center justify-between">
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold uppercase text-blue-700 dark:text-blue-400">2. SECONDARY REMOTE PROVIDER</span>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 bg-blue-500/20 text-blue-700 dark:text-blue-300 rounded-[2px]">REMOTE FALLBACK</span>
                    </div>
                    <div className="text-xs font-mono text-[var(--text-primary)]">OpenAI-Compatible Remote (OpenRouter)</div>
                    <div className="text-[10px] text-[var(--text-muted)]">Model: google/gemini-2.5-flash via OpenRouter API</div>
                  </div>
                  <Server className="h-5 w-5 text-blue-600" />
                </div>

                <div className="flex justify-center"><ArrowDown className="h-4 w-4 text-[var(--text-muted)]" /></div>

                {/* 3. Tertiary Local Provider */}
                <div className="p-4 rounded-[3px] border border-amber-500/50 bg-amber-500/10 flex items-center justify-between">
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold uppercase text-amber-700 dark:text-amber-400">3. LOCAL FALLBACK PROVIDER</span>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 bg-amber-500/20 text-amber-700 dark:text-amber-300 rounded-[2px]">OFFLINE FALLBACK</span>
                    </div>
                    <div className="text-xs font-mono text-[var(--text-primary)]">Ollama Local Instance (localhost:11434)</div>
                    <div className="text-[10px] text-[var(--text-muted)]">Model: llama3.2:1b</div>
                  </div>
                  <Server className="h-5 w-5 text-amber-600" />
                </div>

                <div className="flex justify-center"><ArrowDown className="h-4 w-4 text-[var(--text-muted)]" /></div>

                {/* 4. Controlled Failure */}
                <div className="p-4 rounded-[3px] border border-rose-500/50 bg-rose-500/10 flex items-center justify-between">
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold uppercase text-rose-700 dark:text-rose-400">4. CONTROLLED PROVIDER FAILURE</span>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 bg-rose-500/20 text-rose-700 dark:text-rose-300 rounded-[2px]">ZERO FABRICATION</span>
                    </div>
                    <div className="text-xs font-mono text-[var(--text-primary)]">Explicit actionable infrastructure notification</div>
                    <div className="text-[10px] text-[var(--text-muted)]">Never fabricates answers or pretends an offline LLM succeeded</div>
                  </div>
                  <ShieldCheck className="h-5 w-5 text-rose-600" />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 4: CITATION PROVENANCE FLOW */}
        {activeTab === "citations" && (
          <div className="space-y-6">
            <div className="border border-[var(--panel-border)] bg-[var(--panel-bg)] rounded-[3px] p-6 shadow-xs space-y-6">
              <div>
                <h2 className="text-sm font-bold uppercase tracking-wider text-[#f97316]">
                  DETERMINISTIC CITATION PROVENANCE PIPELINE
                </h2>
                <p className="text-xs text-[var(--text-secondary)] font-sans mt-1">
                  How citations are generated, bounded, and verified without allowing the LLM to invent page numbers or references.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-5 gap-3 items-center text-center">
                <div className="p-3 border border-[var(--panel-border)] bg-[var(--panel-inner)] rounded-[3px]">
                  <span className="text-xs font-bold">1. Answer Claim</span>
                  <span className="block text-[9px] text-[var(--text-muted)] mt-1">Extracted factual statement</span>
                </div>
                <ArrowRight className="hidden md:block h-4 w-4 text-[var(--text-muted)] mx-auto" />

                <div className="p-3 border border-[var(--panel-border)] bg-[var(--panel-inner)] rounded-[3px]">
                  <span className="text-xs font-bold">2. Evidence ID</span>
                  <span className="block text-[9px] text-[var(--text-muted)] mt-1">Bounded marker [E1], [E2]</span>
                </div>
                <ArrowRight className="hidden md:block h-4 w-4 text-[var(--text-muted)] mx-auto" />

                <div className="p-3 border border-[#f97316] bg-[#f97316]/10 rounded-[3px]">
                  <span className="text-xs font-bold text-[#f97316]">3. Retrieved Chunk</span>
                  <span className="block text-[9px] text-[var(--text-secondary)] mt-1">chunk_id, excerpt</span>
                </div>
                <ArrowRight className="hidden md:block h-4 w-4 text-[var(--text-muted)] mx-auto" />

                <div className="p-3 border border-[var(--panel-border)] bg-[var(--panel-inner)] rounded-[3px]">
                  <span className="text-xs font-bold">4. Document Metadata</span>
                  <span className="block text-[9px] text-[var(--text-muted)] mt-1">doc_id, page_start, page_end</span>
                </div>
                <ArrowRight className="hidden md:block h-4 w-4 text-[var(--text-muted)] mx-auto" />

                <div className="p-3 border border-emerald-500/50 bg-emerald-500/10 rounded-[3px]">
                  <span className="text-xs font-bold text-emerald-700 dark:text-emerald-300">5. Source Citation</span>
                  <span className="block text-[9px] text-[var(--text-secondary)] mt-1">[E1] Data Structures.pdf — p. 42</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 5: STREAMING & SCROLL STATE MACHINE */}
        {activeTab === "streaming" && (
          <div className="space-y-6">
            <div className="border border-[var(--panel-border)] bg-[var(--panel-bg)] rounded-[3px] p-6 shadow-xs space-y-6">
              <div>
                <h2 className="text-sm font-bold uppercase tracking-wider text-[#f97316]">
                  STREAMING & SCROLL CONTROLLER STATE MACHINE
                </h2>
                <p className="text-xs text-[var(--text-secondary)] font-sans mt-1">
                  Fixes the scrolling bug by decoupling token reception from scroll position.
                </p>
              </div>

              {/* Streaming Event Protocol Flow */}
              <div className="p-4 rounded-[3px] border border-[var(--panel-border)] bg-[var(--panel-inner)] space-y-2">
                <span className="text-xs font-bold uppercase text-[#f97316]">SSE Event Lifecycle</span>
                <div className="flex flex-wrap items-center gap-2 text-[10px] font-mono">
                  <span className="px-2 py-1 bg-[var(--panel-bg)] border border-[var(--panel-border)] rounded-[2px]">request_started</span>
                  <span>→</span>
                  <span className="px-2 py-1 bg-[var(--panel-bg)] border border-[var(--panel-border)] rounded-[2px]">retrieval_started</span>
                  <span>→</span>
                  <span className="px-2 py-1 bg-[var(--panel-bg)] border border-[var(--panel-border)] rounded-[2px]">retrieval_completed</span>
                  <span>→</span>
                  <span className="px-2 py-1 bg-[var(--panel-bg)] border border-[var(--panel-border)] rounded-[2px]">generation_started</span>
                  <span>→</span>
                  <span className="px-2 py-1 bg-[#f97316]/20 border border-[#f97316] text-[#f97316] rounded-[2px]">text_delta (tokens)</span>
                  <span>→</span>
                  <span className="px-2 py-1 bg-[var(--panel-bg)] border border-[var(--panel-border)] rounded-[2px]">citation_event</span>
                  <span>→</span>
                  <span className="px-2 py-1 bg-emerald-500/20 border border-emerald-500 text-emerald-700 dark:text-emerald-300 rounded-[2px]">pipeline_complete</span>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-4 rounded-[3px] border border-emerald-500/40 bg-emerald-500/10 space-y-2">
                  <div className="flex items-center gap-2 text-xs font-bold uppercase text-emerald-700 dark:text-emerald-400">
                    <CheckCircle2 className="h-4 w-4" />
                    <span>State: Near Bottom (distance &lt; 120px)</span>
                  </div>
                  <ul className="text-xs text-[var(--text-secondary)] font-sans space-y-1 list-disc pl-4">
                    <li><strong className="font-mono text-[var(--text-primary)]">autoFollow = true</strong></li>
                    <li>As new tokens arrive via SSE, view smoothly auto-scrolls to newest text.</li>
                    <li>Message maintains stable ID (no remounting or jumping).</li>
                  </ul>
                </div>

                <div className="p-4 rounded-[3px] border border-amber-500/40 bg-amber-500/10 space-y-2">
                  <div className="flex items-center gap-2 text-xs font-bold uppercase text-amber-700 dark:text-amber-400">
                    <ArrowDown className="h-4 w-4" />
                    <span>State: User Scrolled Up</span>
                  </div>
                  <ul className="text-xs text-[var(--text-secondary)] font-sans space-y-1 list-disc pl-4">
                    <li><strong className="font-mono text-[var(--text-primary)]">autoFollow = false</strong></li>
                    <li>Streaming continues in background without forcing scroll down.</li>
                    <li>User can read previous answers with rock-solid stability.</li>
                    <li>Floating <strong>"Jump to latest"</strong> button appears. Clicking it scrolls to bottom and resumes auto-follow.</li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
