/**
 * Multi-Agent System — Type Definitions
 *
 * These types are shared between the agent runtime (server) and the UI
 * (client) so the agent trace panel can render each step uniformly.
 */

import { z } from "zod";

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

// --- ZOD SCHEMAS FOR RUNTIME VALIDATION ---

export const RouterOutputSchema = z.object({
  queryType: z.enum(["factual", "comparison", "synthesis", "procedural"]),
  rewrittenQuery: z.string().min(1),
  intentSummary: z.string(),
  needsRetrieval: z.boolean(),
});
export type RouterOutput = z.infer<typeof RouterOutputSchema>;

export const RerankerOutputSchema = z.object({
  reranked: z.array(z.object({
    chunkId: z.string(),
    documentTitle: z.string(),
    originalRank: z.number().int().min(1),
    newRank: z.number().int().min(1),
    llmScore: z.number().min(0).max(10),
    rationale: z.string(),
  }))
});
export type RerankerOutput = z.infer<typeof RerankerOutputSchema>;

export const CriticOutputSchema = z.object({
  verdict: z.enum(["faithful", "needs_revision"]),
  faithfulnessScore: z.number().min(0).max(100),
  issues: z.array(z.string()),
  revisionNotes: z.string().optional(),
});
export type CriticOutput = z.infer<typeof CriticOutputSchema>;

// --- STEP INTERFACES ---

export interface RouterStep extends AgentStepBase {
  agent: "router";
  input: { question: string };
  output: RouterOutput;
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
  output: RerankerOutput;
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
  output: CriticOutput;
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
  error?: {
    code: string;
    type: string;
    userMessage: string;
    developerMessage: string;
    retryable: boolean;
    provider?: string;
    requestId?: string;
    traceId?: string;
    timestamp?: string;
    stack?: string;
  };
}
