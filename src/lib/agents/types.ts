/**
 * Multi-Agent System — Type Definitions
 *
 * These types are shared between the agent runtime (server) and the UI
 * (client) so the agent trace panel can render each step uniformly.
 */

export type AgentName =
  | "router"
  | "retriever"
  | "reranker"
  | "analyzer"
  | "critic"
  | "coordinator";

export interface AgentStepBase {
  /** Stable id for the step (used as React key) */
  id: string;
  /** Which agent produced this step */
  agent: AgentName;
  /** Human-readable label, e.g. "Routing question…" */
  label: string;
  /** When the agent started, ms since epoch */
  startedAt: number;
  /** When the agent finished, ms since epoch */
  finishedAt: number;
  /** Wall-clock duration in ms */
  durationMs: number;
  /** Status flag */
  status: "running" | "completed" | "error";
  /** Optional error message */
  error?: string;
}

export interface RouterStep extends AgentStepBase {
  agent: "router";
  input: { question: string };
  output: {
    queryType: "factual" | "comparison" | "synthesis" | "procedural";
    rewrittenQuery: string;
    intentSummary: string;
    needsRetrieval: boolean;
  };
}

export interface RetrieverStep extends AgentStepBase {
  agent: "retriever";
  input: { query: string; k: number };
  output: {
    candidates: {
      chunkId: string;
      documentTitle: string;
      score: number;
      preview: string;
    }[];
    stats: { vocabSize: number; numChunks: number };
  };
}

export interface RerankerStep extends AgentStepBase {
  agent: "reranker";
  input: { query: string; numCandidates: number };
  output: {
    reranked: {
      chunkId: string;
      documentTitle: string;
      originalRank: number;
      newRank: number;
      llmScore: number;
      rationale: string;
    }[];
  };
}

export interface AnalyzerStep extends AgentStepBase {
  agent: "analyzer";
  input: { query: string; numSources: number; iteration: number };
  output: {
    answer: string;
    citationsUsed: number;
  };
}

export interface CriticStep extends AgentStepBase {
  agent: "critic";
  input: { answerLength: number; numSources: number };
  output: {
    verdict: "faithful" | "needs_revision";
    faithfulnessScore: number;
    issues: string[];
    revisionNotes?: string;
  };
}

export interface CoordinatorStep extends AgentStepBase {
  agent: "coordinator";
  input: { question: string };
  output: {
    flow: string[];
    totalIterations: number;
    finalVerdict: string;
  };
}

export type AgentStep =
  | RouterStep
  | RetrieverStep
  | RerankerStep
  | AnalyzerStep
  | CriticStep
  | CoordinatorStep;

/** A retrieved chunk with its final rank + score, used by the UI. */
export interface CitedSource {
  chunkId: string;
  documentId: string;
  documentTitle: string;
  authors: string;
  year: number;
  source: string;
  chunkIndex: number;
  chunkContent: string;
  score: number;
  llmScore?: number;
}

/** The full result returned by the multi-agent coordinator. */
export interface AgentRunResult {
  question: string;
  answer: string;
  sources: CitedSource[];
  steps: AgentStep[];
  totalDurationMs: number;
}
