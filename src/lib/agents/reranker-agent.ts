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
import { z } from "zod";
import { chatJson } from "../llm";
import { getVectorStore } from "../rag/vector-store";
import { RerankerStep } from "./types";
import { Result, success, failure } from "../result";
import { logger } from "../logger";
import { ParsingError, BaseApplicationError } from "../errors";

const LlmRerankerResponseSchema = z.object({
  items: z.array(z.object({
    chunkId: z.string(),
    llmScore: z.number().min(0).max(10),
    rationale: z.string()
  }))
});

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
    { "chunkId": "...", "llmScore": 8.5, "rationale": "..." }
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
  requestId: string
): Promise<Result<RerankerStep>> {
  const startedAt = Date.now();
  logger.info("Starting Reranker Agent", { requestId, agent: "reranker", stepId, candidateCount: candidateChunkIds.length });

  const store = await getVectorStore();
  const allChunks = store.getChunks();
  const candidateChunks = allChunks.filter((c) =>
    candidateChunkIds.includes(c.id),
  );

  if (candidateChunks.length === 0) {
    const finishedAt = Date.now();
    logger.info("Reranker Agent fast-path completed (no candidates)", { requestId, agent: "reranker", durationMs: finishedAt - startedAt });
    return success({
      id: stepId,
      agent: "reranker",
      label: "Reranking candidates (LLM cross-encoder)",
      startedAt,
      finishedAt,
      durationMs: finishedAt - startedAt,
      status: "completed",
      input: { query, numCandidates: 0 },
      output: { reranked: [] },
    });
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
    const rawOutput = await chatJson<unknown>(
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
      requestId,
      "reranker"
    );

    const parseResult = LlmRerankerResponseSchema.safeParse(rawOutput);
    if (!parseResult.success) {
      const errorMsg = parseResult.error.errors.map(e => `${e.path.join(".")}: ${e.message}`).join(", ");
      logger.warn("Reranker validation failed", { requestId, agent: "reranker", errors: errorMsg });
      throw new ParsingError("RERANKER_SCHEMA_MISMATCH", `Reranker output violated schema: ${errorMsg}`, { requestId, agent: "reranker" });
    }

    const response = parseResult.data;

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

    const finishedAt = Date.now();
    logger.info("Reranker Agent completed successfully", { 
      requestId, agent: "reranker", durationMs: finishedAt - startedAt, rerankedCount: reranked.length 
    });

    return success({
      id: stepId,
      agent: "reranker",
      label: "Reranking candidates (LLM cross-encoder)",
      startedAt,
      finishedAt,
      durationMs: finishedAt - startedAt,
      status: "completed",
      input: { query, numCandidates: candidateChunks.length },
      output: { reranked },
    });
  } catch (e: any) {
    if (e instanceof BaseApplicationError) {
      return failure(e);
    }
    return failure(
      new ParsingError("RERANKER_UNEXPECTED_ERROR", e?.message ?? "Unknown reranker error", { requestId, agent: "reranker" }, e)
    );
  }
}
