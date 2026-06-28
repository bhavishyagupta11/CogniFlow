/**
 * Coordinator — Multi-Agent Orchestration
 *
 * Implements the agent graph:
 *
 *   Router → Retriever → Reranker → Analyzer ⇄ Critic
 *                                    ↑            │
 *                                    └─ revision ─┘  (max 2 iterations)
 *
 * The Coordinator is the "state machine" that decides which agent runs next,
 * passes state between them, and terminates the run when the Critic is
 * satisfied (or when we've hit the iteration cap).
 *
 * This pattern mirrors LangGraph's StateGraph with a cyclic edge for the
 * Analyzer ⇄ Critic refinement loop — a great interview talking point.
 */

import "server-only";
import { getVectorStore } from "../rag/vector-store";
import { Chunk } from "../rag/chunker";
import { KNOWLEDGE_BASE } from "../rag/documents";
import { runRouterAgent } from "./router-agent";
import { runRetrieverAgent } from "./retriever-agent";
import { runRerankerAgent } from "./reranker-agent";
import { runAnalyzerAgent } from "./analyzer-agent";
import { runCriticAgent } from "./critic-agent";
import {
  AgentRunResult,
  AgentStep,
  CitedSource,
  CoordinatorStep,
} from "./types";

const MAX_ITERATIONS = 2;
const TOP_K = 5;

function makeStepId(prefix: string, i: number): string {
  return `${prefix}-${Date.now()}-${i}`;
}

export async function runMultiAgentPipeline(
  question: string,
): Promise<AgentRunResult> {
  const runStart = Date.now();
  const steps: AgentStep[] = [];
  let stepCounter = 0;
  const nextId = (prefix: string) => makeStepId(prefix, ++stepCounter);

  // ─── 1. Router ────────────────────────────────────────────────────────
  const routerStep = await runRouterAgent(question, nextId("router"));
  steps.push(routerStep);
  const { rewrittenQuery, queryType, needsRetrieval } = routerStep.output;

  if (!needsRetrieval) {
    // Trivial question — skip the rest of the pipeline
    const coordinatorStep: CoordinatorStep = {
      id: nextId("coordinator"),
      agent: "coordinator",
      label: "Routing decision: skip retrieval",
      startedAt: runStart,
      finishedAt: Date.now(),
      durationMs: Date.now() - runStart,
      status: "completed",
      input: { question },
      output: {
        flow: ["router"],
        totalIterations: 0,
        finalVerdict: "skipped",
      },
    };
    steps.push(coordinatorStep);
    return {
      question,
      answer:
        "Hi! Ask me about transformers, BERT, GPT-3, RAG, chain-of-thought, ReAct, Constitutional AI, or LangGraph and I'll route it through the full multi-agent pipeline.",
      sources: [],
      steps,
      totalDurationMs: Date.now() - runStart,
    };
  }

  // ─── 2. Retriever ────────────────────────────────────────────────────
  const retrieverStep = await runRetrieverAgent(
    rewrittenQuery,
    TOP_K,
    nextId("retriever"),
  );
  steps.push(retrieverStep);
  const candidateIds = retrieverStep.output.candidates.map((c) => c.chunkId);

  if (candidateIds.length === 0) {
    const coordinatorStep: CoordinatorStep = {
      id: nextId("coordinator"),
      agent: "coordinator",
      label: "No candidates found — terminating",
      startedAt: runStart,
      finishedAt: Date.now(),
      durationMs: Date.now() - runStart,
      status: "completed",
      input: { question },
      output: {
        flow: ["router", "retriever"],
        totalIterations: 0,
        finalVerdict: "no_candidates",
      },
    };
    steps.push(coordinatorStep);
    return {
      question,
      answer:
        "I couldn't find any relevant passages in my knowledge base for that question. Try asking about transformers, BERT, GPT-3, RAG, chain-of-thought prompting, ReAct, Constitutional AI, or LangGraph.",
      sources: [],
      steps,
      totalDurationMs: Date.now() - runStart,
    };
  }

  // ─── 3. Reranker ─────────────────────────────────────────────────────
  const rerankerStep = await runRerankerAgent(
    rewrittenQuery,
    candidateIds,
    nextId("reranker"),
  );
  steps.push(rerankerStep);

  // Pick the top-N reranked chunks (cap at 4 to keep the prompt manageable)
  const TOP_N = Math.min(4, rerankerStep.output.reranked.length);
  const finalChunkIds = rerankerStep.output.reranked
    .slice(0, TOP_N)
    .map((r) => r.chunkId);

  const store = await getVectorStore();
  const allChunks = store.getChunks();
  const finalChunks: Chunk[] = finalChunkIds
    .map((id) => allChunks.find((c) => c.id === id))
    .filter((c): c is Chunk => c !== undefined);

  // Attach LLM reranker scores for the UI
  const llmScoreById = new Map(
    rerankerStep.output.reranked.map((r) => [r.chunkId, r.llmScore]),
  );

  // ─── 4. Analyzer ⇄ Critic loop ──────────────────────────────────────
  let iteration = 0;
  let analyzerStep;
  let criticStep;
  let finalAnswer = "";

  while (iteration < MAX_ITERATIONS) {
    iteration++;
    analyzerStep = await runAnalyzerAgent({
      question,
      queryType,
      chunks: finalChunks,
      iteration,
      revisionNotes:
        iteration > 1 ? criticStep?.output.revisionNotes : undefined,
      stepId: nextId("analyzer"),
    });
    steps.push(analyzerStep);
    finalAnswer = analyzerStep.output.answer;

    criticStep = await runCriticAgent({
      question,
      answer: finalAnswer,
      chunks: finalChunks,
      stepId: nextId("critic"),
    });
    steps.push(criticStep);

    if (criticStep.output.verdict === "faithful") {
      break;
    }
    // Otherwise: loop back to Analyzer with revision notes
  }

  // ─── 5. Coordinator summary ─────────────────────────────────────────
  const coordinatorStep: CoordinatorStep = {
    id: nextId("coordinator"),
    agent: "coordinator",
    label: "Pipeline complete",
    startedAt: runStart,
    finishedAt: Date.now(),
    durationMs: Date.now() - runStart,
    status: "completed",
    input: { question },
    output: {
      flow: ["router", "retriever", "reranker", "analyzer", "critic"],
      totalIterations: iteration,
      finalVerdict: criticStep?.output.verdict ?? "unknown",
    },
  };
  steps.push(coordinatorStep);

  // Build the cited-sources list in the order the analyzer received them
  const sources: CitedSource[] = finalChunks.map((c, i) => {
    // Look up the document metadata from the knowledge base
    const doc = KNOWLEDGE_BASE.find((d) => d.id === c.documentId);
    return {
      chunkId: c.id,
      documentId: c.documentId,
      documentTitle: c.documentTitle,
      authors: doc?.authors ?? "Unknown",
      year: doc?.year ?? 0,
      source: doc?.source ?? "",
      chunkIndex: c.index,
      chunkContent: c.content,
      score: 0,
      llmScore: llmScoreById.get(c.id),
    };
  });
  void sources; // avoid unused warning in some toolchains

  return {
    question,
    answer: finalAnswer,
    sources,
    steps,
    totalDurationMs: Date.now() - runStart,
  };
}
