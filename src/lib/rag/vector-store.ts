/**
 * In-memory Vector Store
 *
 * Stores chunks and their pre-computed embeddings. Provides similarity search
 * returning the top-k most similar chunks. The store is process-lifetime —
 * re-fits on first access from the bundled knowledge base.
 *
 * In production you'd swap this for Qdrant / Pinecone / pgvector. The interface
 * here (add/get/search) mirrors those stores so the swap is trivial.
 */

import { Chunk, chunkDocument } from "./chunker";
import { TfidfEmbedder, cosineSimilarity } from "./embeddings";
import { KNOWLEDGE_BASE, Document } from "./documents";

export interface ScoredChunk {
  chunk: Chunk;
  score: number;
}

export interface VectorDocument {
  id: string;
  title: string;
  authors: string;
  year: number;
  source: string;
}

class InMemoryVectorStore {
  private chunks: Chunk[] = [];
  private embeddings: Map<string, Map<number, number>> = new Map();
  private embedder: TfidfEmbedder = new TfidfEmbedder();
  private built = false;

  build(documents: { id: string; title: string; authors: string; year: number; source: string; content: string }[]) {
    // 1. Chunk each document
    const allChunks: Chunk[] = [];
    for (const doc of documents) {
      const chunks = this.splitIntoChunks(doc);
      allChunks.push(...chunks);
    }
    this.chunks = allChunks;

    // 2. Fit the embedder on the corpus
    this.embedder = new TfidfEmbedder().fit(allChunks.map((c) => c.content));

    // 3. Pre-compute embeddings for every chunk
    this.embeddings.clear();
    for (const chunk of allChunks) {
      this.embeddings.set(chunk.id, this.embedder.embed(chunk.content));
    }

    this.built = true;
    return this;
  }

  private splitIntoChunks(doc: { id: string; title: string; authors: string; year: number; source: string; content: string }): Chunk[] {
    // Prepend title to the content so the title tokens contribute to retrieval
    const enrichedContent = `${doc.title}\n\n${doc.content}`;
    return chunkDocument(doc.id, doc.title, enrichedContent, {
      chunkSize: 600,
      chunkOverlap: 80,
    });
  }

  isBuilt(): boolean {
    return this.built;
  }

  getStats() {
    return {
      numChunks: this.chunks.length,
      vocabSize: this.embedder.dimensions,
      ...this.embedder.getVocabularyStats(),
    };
  }

  getChunks(): Chunk[] {
    return this.chunks;
  }

  /**
   * Cosine-similarity search. Returns the top-k chunks most similar to the
   * query. Note: because we L2-normalize during embedding, cosine similarity
   * reduces to a plain dot product.
   */
  search(query: string, k: number = 5): ScoredChunk[] {
    if (!this.built) {
      throw new Error("Vector store not built. Call .build() first.");
    }
    const q = this.embedder.embed(query);
    if (q.size === 0) return [];

    const scored: ScoredChunk[] = [];
    for (const chunk of this.chunks) {
      const emb = this.embeddings.get(chunk.id);
      if (!emb) continue;
      const score = cosineSimilarity(q, emb);
      scored.push({ chunk, score });
    }
    scored.sort((a, b) => b.score - a.score);
    return scored.slice(0, k);
  }

  /**
   * Maximal Marginal Relevance (MMR) search.
   *
   * Returns a diverse set of k chunks that are both relevant to the query and
   * not too similar to each other. Useful when several chunks from the same
   * document would otherwise dominate the results.
   *
   * @param lambda Tradeoff between relevance (1.0) and diversity (0.0). 0.7 is a good default.
   */
  searchWithMMR(query: string, k: number = 5, lambda: number = 0.7): ScoredChunk[] {
    if (!this.built) {
      throw new Error("Vector store not built. Call .build() first.");
    }
    // Fetch a larger candidate pool first
    const candidates = this.search(query, Math.min(k * 4, this.chunks.length));
    if (candidates.length <= k) return candidates;

    const q = this.embedder.embed(query);
    const selected: ScoredChunk[] = [];
    const selectedIdx = new Set<number>();

    while (selected.length < k) {
      let best: { idx: number; score: number } | null = null;
      for (let i = 0; i < candidates.length; i++) {
        if (selectedIdx.has(i)) continue;
        const relevance = candidates[i].score;
        let maxSim = 0;
        for (const s of selected) {
          const a = this.embeddings.get(candidates[i].chunk.id)!;
          const b = this.embeddings.get(s.chunk.id)!;
          maxSim = Math.max(maxSim, cosineSimilarity(a, b));
        }
        const mmrScore = lambda * relevance - (1 - lambda) * maxSim;
        if (!best || mmrScore > best.score) {
          best = { idx: i, score: mmrScore };
        }
      }
      if (!best) break;
      selectedIdx.add(best.idx);
      selected.push({
        chunk: candidates[best.idx].chunk,
        score: candidates[best.idx].score,
      });
    }
    // Avoid unused-variable warning for q
    void q;
    return selected;
  }
}

import { extractText } from "../services/upload-service";
import { updateManifest } from "../services/manifest-service";

// Singleton — built lazily on first access from the bundled knowledge base.
let store: InMemoryVectorStore | null = null;

import fs from "fs";
import path from "path";

export async function getVectorStore(): Promise<InMemoryVectorStore> {
  if (store && store.isBuilt()) return store;
  store = new InMemoryVectorStore();
  
  const docs = [...KNOWLEDGE_BASE];

  try {
    const DATA_DIR = path.join(process.cwd(), "data");
    const MANIFEST_PATH = path.join(DATA_DIR, "manifest.json");
    const EXTRACTED_DIR = path.join(DATA_DIR, "extracted");
    
    if (fs.existsSync(MANIFEST_PATH)) {
      const data = fs.readFileSync(MANIFEST_PATH, "utf-8");
      const manifest = JSON.parse(data);
      const completedDocs = manifest.filter((m: any) => m.processingStatus === "completed");
      
      for (const entry of completedDocs) {
        const extPath = path.join(EXTRACTED_DIR, `${entry.id}.txt`);
        if (fs.existsSync(extPath)) {
          const content = fs.readFileSync(extPath, "utf-8");
          docs.push({
            id: entry.id,
            title: entry.originalFilename,
            authors: "Uploaded Document",
            year: new Date(entry.uploadedAt).getFullYear() || new Date().getFullYear(),
            source: "User Upload",
            content: content
          });
        } else {
          // Attempt recovery
          console.warn(`[VectorStore] Missing extracted text for ${entry.id}. Attempting recovery from source...`);
          try {
            const ext = path.extname(entry.filename);
            const content = await extractText(entry.id, ext);
            docs.push({
              id: entry.id,
              title: entry.originalFilename,
              authors: "Uploaded Document",
              year: new Date(entry.uploadedAt).getFullYear() || new Date().getFullYear(),
              source: "User Upload",
              content: content
            });
            console.log(`[VectorStore] Successfully recovered ${entry.id}`);
          } catch (recoveryErr: any) {
            console.error(`[VectorStore] Recovery failed for ${entry.id}: ${recoveryErr.message}`);
            await updateManifest(entries => {
              const mEntry = entries.find(e => e.id === entry.id);
              if (mEntry) {
                mEntry.processingStatus = "failed";
                mEntry.errorMessage = "Extracted text and source file both missing/unreadable on startup recovery";
              }
            });
          }
        }
      }
    }
  } catch (err) {
    console.error("[VectorStore] Failed to load persisted documents on startup", err);
  }

  store.build(docs);
  return store;
}

// Re-export for callers that need direct access to the documents
export { KNOWLEDGE_BASE, type Document };

