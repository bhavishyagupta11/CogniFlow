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
import { Result, success, failure } from "../result";
import { RetrieverError } from "../errors";

export async function runRetrieverAgent(
  query: string,
  k: number,
  stepId: string,
  requestId: string
): Promise<Result<RetrieverStep>> {
  const startedAt = Date.now();
  
  try {
    const store = await getVectorStore();
    const stats = store.getStats();

    const scored = store.searchWithMMR(query, k, 0.7);
    
    if (scored.length === 0) {
      throw new RetrieverError("NO_RESULTS", "Vector search returned no results.", { requestId, agent: "retriever" });
    }

    const output = {
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

    const finishedAt = Date.now();
    return success({
      id: stepId,
      agent: "retriever",
      label: `Retrieving top-${k} chunks (TF-IDF + MMR)`,
      startedAt,
      finishedAt,
      durationMs: finishedAt - startedAt,
      status: "completed",
      input: { query, k },
      output,
    });
  } catch (e: any) {
    const finishedAt = Date.now();
    
    // If it's already a RetrieverError, pass it through. Otherwise wrap it.
    const err = e instanceof RetrieverError ? e : new RetrieverError("RETRIEVER_FAILED", e?.message ?? "Unknown retriever error", { requestId, agent: "retriever" }, e);
    
    return failure(err, {
      id: stepId,
      agent: "retriever",
      label: `Retrieving top-${k} chunks (TF-IDF + MMR)`,
      startedAt,
      finishedAt,
      durationMs: finishedAt - startedAt,
      status: "error",
      error: err.developerMessage,
      input: { query, k },
      output: { candidates: [], stats: { vocabSize: 0, numChunks: 0 } },
    });
  }
}
