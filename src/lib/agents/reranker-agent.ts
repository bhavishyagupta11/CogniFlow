/**
 * Reranker Agent (LLM-as-judge cross-encoder)
 *
 * The retriever returns candidates ranked by lexical similarity. That ranking
 * can be wrong — e.g., a chunk may share many keywords with the query but not
 * actually answer it. This agent asks the LLM to score each candidate's
 * relevance to the query on a 0-10 scale and re-sorts accordingly.
 *
 * This mirrors the well-known "cross-encoder reranking" pattern used in
 * production RAG systems (Cohere Rerank, BGE Reranker, etc.) and is a great
 * interview talking point — it shows you understand why a two-stage retrieve-
 * then-rerank pipeline beats single-stage retrieval.
 */

import "server-only";
import { chatJson } from "../llm";
import { getVectorStore } from "../rag/vector-store";
import { RerankerStep } from "./types";

interface RerankerResponseItem {
  chunkId: string;
  llmScore: number;
  rationale: string;
}

interface RerankerResponse {
  items: RerankerResponseItem[];
}

const SYSTEM_PROMPT = `You are the Reranker agent in a multi-agent research assistant.
You will receive a query and a list of candidate text chunks (with their chunkId).
For EACH chunk, score how relevant it is to the query on a 0-10 scale where:
  - 10: directly answers the query
  - 7-9: substantially relevant
  - 4-6: partially relevant
  - 1-3: tangentially related
  - 0: not relevant at all

Also provide a one-sentence rationale for each score.

Return JSON ONLY with this exact schema:
{
  "items": [
    { "chunkId": "...", "llmScore": 8.5, "rationale": "..." },
    ...
  ]
}

Rules:
- Score every chunk you were given
- DO NOT include markdown code fences, just emit raw JSON
- Be strict: a chunk that merely shares keywords but doesn't answer the question should score low`;

export async function runRerankerAgent(
  query: string,
  candidateChunkIds: string[],
  stepId: string,
): Promise<RerankerStep> {
  const startedAt = Date.now();
  let status: RerankerStep["status"] = "running";
  let error: string | undefined;

  const store = await getVectorStore();
  const allChunks = store.getChunks();
  const candidateChunks = allChunks.filter((c) =>
    candidateChunkIds.includes(c.id),
  );

  let output: RerankerStep["output"];

  if (candidateChunks.length === 0) {
    output = { reranked: [] };
    status = "completed";
    const finishedAt = Date.now();
    return {
      id: stepId,
      agent: "reranker",
      label: "Reranking candidates (LLM cross-encoder)",
      startedAt,
      finishedAt,
      durationMs: finishedAt - startedAt,
      status,
      input: { query, numCandidates: 0 },
      output,
    };
  }

  // Build a compact representation of each candidate for the LLM
  const candidatesPayload = candidateChunks.map((c, i) => ({
    chunkId: c.id,
    documentTitle: c.documentTitle,
    text:
      c.content.slice(0, 400).replace(/\s+/g, " ").trim() +
      (c.content.length > 400 ? "…" : ""),
    originalRank: i + 1,
  }));

  try {
    const response = await chatJson<RerankerResponse>(
      [
        { role: "system", content: SYSTEM_PROMPT },
        {
          role: "user",
          content: `Query: "${query}"\n\nCandidates:\n${JSON.stringify(
            candidatesPayload,
            null,
            2,
          )}`,
        },
      ],
      { temperature: 0, maxTokens: 800 },
    );

    // Merge LLM scores with the original candidate metadata and re-sort
    const scoreById = new Map(
      (response.items ?? []).map((it) => [it.chunkId, it]),
    );
    const reranked = candidateChunks
      .map((chunk, i) => {
        const scored = scoreById.get(chunk.id);
        return {
          chunkId: chunk.id,
          documentTitle: chunk.documentTitle,
          originalRank: i + 1,
          newRank: 0, // filled in below
          llmScore: scored?.llmScore ?? 0,
          rationale: scored?.rationale ?? "No rationale returned",
        };
      })
      .sort((a, b) => b.llmScore - a.llmScore)
      .map((item, i) => ({ ...item, newRank: i + 1 }));

    output = { reranked };
    status = "completed";
  } catch (e: any) {
    // Fallback: keep original ordering, assign neutral scores
    output = {
      reranked: candidateChunks.map((chunk, i) => ({
        chunkId: chunk.id,
        documentTitle: chunk.documentTitle,
        originalRank: i + 1,
        newRank: i + 1,
        llmScore: 5,
        rationale: "Reranker fallback: LLM call failed, keeping original order.",
      })),
    };
    status = "error";
    error = e?.message ?? "Unknown reranker error";
  }

  const finishedAt = Date.now();
  return {
    id: stepId,
    agent: "reranker",
    label: "Reranking candidates (LLM cross-encoder)",
    startedAt,
    finishedAt,
    durationMs: finishedAt - startedAt,
    status,
    error,
    input: { query, numCandidates: candidateChunks.length },
    output,
  };
}
