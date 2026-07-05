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
import { randomUUID } from "crypto";
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
import { logger } from "../logger";
import { BaseApplicationError } from "../errors";

const MAX_ITERATIONS = 2;
const TOP_K = 5;

function makeStepId(prefix: string, i: number): string {
  return `${prefix}-${Date.now()}-${i}`;
}

export async function runMultiAgentPipeline(
  question: string,
): Promise<AgentRunResult> {
  const runStart = Date.now();
  const requestId = randomUUID();
  logger.info("Starting Multi-Agent Pipeline", { requestId, question });

  const steps: AgentStep[] = [];
  let stepCounter = 0;
  const nextId = (prefix: string) => makeStepId(prefix, ++stepCounter);

  // Helper to construct error response state
  const buildErrorResult = (err: BaseApplicationError, fallbackAnswer: string): AgentRunResult => {
    const errorStep: CoordinatorStep = {
      id: nextId("coordinator"),
      agent: "coordinator",
      label: "Pipeline aborted due to infrastructure failure",
      startedAt: runStart,
      finishedAt: Date.now(),
      durationMs: Date.now() - runStart,
      status: "error",
      error: err.developerMessage,
      input: { question },
      output: { flow: [], totalIterations: 0, finalVerdict: "aborted" }
    };
    steps.push(errorStep);
    
    return {
      question,
      answer: fallbackAnswer,
      sources: [],
      steps,
      totalDurationMs: Date.now() - runStart,
      error: {
        code: err.code,
        type: err.type,
        userMessage: err.userMessage,
        developerMessage: err.developerMessage,
        retryable: err.retryable
      }
    };
  };

  // ─── 1. Router ────────────────────────────────────────────────────────
  const routerResult = await runRouterAgent(question, nextId("router"), requestId);
  if (!routerResult.success) {
    logger.error("Pipeline failed at Router", routerResult.error, { requestId });
    return buildErrorResult(routerResult.error, routerResult.error.userMessage);
  }
  const routerStep = routerResult.data;
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
      answer: "Hi! Ask me about transformers, BERT, GPT-3, RAG, chain-of-thought, ReAct, Constitutional AI, or LangGraph and I'll route it through the full multi-agent pipeline.",
      sources: [],
      steps,
      totalDurationMs: Date.now() - runStart,
    };
  }

  // ─── 2. Retriever ────────────────────────────────────────────────────
  const retrieverResult = await runRetrieverAgent(
    rewrittenQuery,
    TOP_K,
    nextId("retriever"),
    requestId
  );
  if (!retrieverResult.success) {
    logger.error("Pipeline failed at Retriever", retrieverResult.error, { requestId });
    return buildErrorResult(retrieverResult.error, retrieverResult.error.userMessage);
  }
  const retrieverStep = retrieverResult.data;
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
      answer: "I couldn't find any relevant passages in my knowledge base for that question.",
      sources: [],
      steps,
      totalDurationMs: Date.now() - runStart,
    };
  }

  // ─── 3. Reranker ─────────────────────────────────────────────────────
  const rerankerResult = await runRerankerAgent(
    rewrittenQuery,
    candidateIds,
    nextId("reranker"),
    requestId
  );
  if (!rerankerResult.success) {
    logger.error("Pipeline failed at Reranker", rerankerResult.error, { requestId });
    return buildErrorResult(rerankerResult.error, rerankerResult.error.userMessage);
  }
  const rerankerStep = rerankerResult.data;
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
  let finalAnswer = "";
  let finalVerdict = "unknown";
  
  while (iteration < MAX_ITERATIONS) {
    iteration++;
    const analyzerResult = await runAnalyzerAgent({
      question,
      queryType,
      chunks: finalChunks,
      iteration,
      revisionNotes: iteration > 1 && steps.length > 0 ? (steps[steps.length - 1].output as any).revisionNotes : undefined,
      stepId: nextId("analyzer"),
      requestId
    });

    if (!analyzerResult.success) {
      logger.error(`Pipeline failed at Analyzer (iteration ${iteration})`, analyzerResult.error, { requestId });
      return buildErrorResult(analyzerResult.error, analyzerResult.error.userMessage);
    }

    const analyzerStep = analyzerResult.data;
    steps.push(analyzerStep);
    finalAnswer = analyzerStep.output.answer;

    const criticResult = await runCriticAgent({
      question,
      answer: finalAnswer,
      chunks: finalChunks,
      stepId: nextId("critic"),
      requestId
    });

    if (!criticResult.success) {
      logger.error(`Pipeline failed at Critic (iteration ${iteration})`, criticResult.error, { requestId });
      return buildErrorResult(criticResult.error, criticResult.error.userMessage);
    }

    const criticStep = criticResult.data;
    steps.push(criticStep);
    finalVerdict = criticStep.output.verdict;

    if (finalVerdict === "faithful") {
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
      finalVerdict,
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

  logger.info("Multi-Agent Pipeline completed successfully", { requestId, durationMs: Date.now() - runStart });

  return {
    question,
    answer: finalAnswer,
    sources,
    steps,
    totalDurationMs: Date.now() - runStart,
  };
}
