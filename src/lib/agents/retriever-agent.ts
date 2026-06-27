/**
 * Retriever Agent
 *
 * Wraps the TF-IDF vector store. Given a (rewritten) query, returns the top-k
 * candidate chunks with similarity scores. Uses MMR for diversity so we don't
 * return 5 chunks from the same document.
 *
 * In a production system this is where you'd swap in DPR / ColBERT / a hosted
 * embedding endpoint. The agent boundary makes that swap transparent to the
 * rest of the pipeline.
 */

import "server-only";
import { getVectorStore } from "../rag/vector-store";
import { RetrieverStep } from "./types";

export async function runRetrieverAgent(
  query: string,
  k: number,
  stepId: string,
): Promise<RetrieverStep> {
  const startedAt = Date.now();
  let status: RetrieverStep["status"] = "running";
  let error: string | undefined;

  const store = getVectorStore();
  const stats = store.getStats();

  let output: RetrieverStep["output"];

  try {
    const scored = store.searchWithMMR(query, k, 0.7);
    output = {
      candidates: scored.map((s) => ({
        chunkId: s.chunk.id,
        documentTitle: s.chunk.documentTitle,
        score: Number(s.score.toFixed(4)),
        preview:
          s.chunk.content.slice(0, 160).replace(/\s+/g, " ").trim() +
          (s.chunk.content.length > 160 ? "…" : ""),
      })),
      stats: { vocabSize: stats.vocabSize, numChunks: stats.numChunks },
    };
    status = "completed";
  } catch (e: any) {
    output = { candidates: [], stats: { vocabSize: 0, numChunks: 0 } };
    status = "error";
    error = e?.message ?? "Unknown retriever error";
  }

  const finishedAt = Date.now();
  return {
    id: stepId,
    agent: "retriever",
    label: `Retrieving top-${k} chunks (TF-IDF + MMR)`,
    startedAt,
    finishedAt,
    durationMs: finishedAt - startedAt,
    status,
    error,
    input: { query, k },
    output,
  };
}
