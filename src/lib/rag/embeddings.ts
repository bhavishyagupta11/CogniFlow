/**
 * TF-IDF Embedder — Lightweight lexical embedder
 *
 * Why TF-IDF instead of OpenAI embeddings?
 * 1. Zero external API dependency → the demo works offline.
 * 2. Deterministic → easier to debug and test.
 * 3. Fast → microseconds per query, not network round-trips.
 * 4. Honest interview talking point: tradeoffs between lexical (TF-IDF, BM25)
 *    and semantic (dense embedding) retrieval. We pair TF-IDF retrieval with
 *    an LLM reranker downstream to recover semantic matching where it matters.
 *
 * The embedder is fit lazily on the corpus on first use, then cached for the
 * lifetime of the process.
 */

const STOPWORDS = new Set([
  "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
  "have", "in", "is", "it", "its", "of", "on", "or", "that", "the", "to",
  "was", "were", "will", "with", "this", "these", "those", "i", "you",
  "he", "she", "we", "they", "but", "not", "or", "if", "then", "than",
  "so", "such", "no", "nor", "only", "own", "same", "too", "very", "can",
  "just", "should", "now", "do", "does", "did", "doing", "would", "could",
  "may", "might", "must", "shall", "about", "above", "after", "again",
  "against", "all", "any", "because", "before", "below", "between", "down",
  "during", "few", "further", "how", "more", "most", "other", "out", "over",
  "the", "there", "under", "up", "what", "when", "where", "which", "while",
  "who", "whom", "why",
]);

const TOKEN_RE = /[a-z0-9]+/g;

export function tokenize(text: string): string[] {
  const tokens = (text.toLowerCase().match(TOKEN_RE) ?? []).filter(
    (t) => t.length > 1 && !STOPWORDS.has(t),
  );
  return tokens;
}

export interface VocabularyEntry {
  /** The term */
  term: string;
  /** Index in the embedding vector */
  idx: number;
  /** Number of documents containing this term */
  df: number;
  /** Inverse document frequency = ln((1 + N) / (1 + df)) + 1 */
  idf: number;
}

export class TfidfEmbedder {
  private vocab = new Map<string, VocabularyEntry>();
  private dims = 0;
  private numDocs = 0;
  private fitted = false;

  fit(documents: string[]): this {
    this.vocab.clear();
    this.dims = 0;
    this.numDocs = documents.length;

    // Build vocab + DF
    const df = new Map<string, number>();
    for (const doc of documents) {
      const tokens = new Set(tokenize(doc));
      for (const t of tokens) {
        df.set(t, (df.get(t) ?? 0) + 1);
      }
    }

    // Sort terms for deterministic ordering
    const sortedTerms = [...df.entries()].sort(([a], [b]) => a.localeCompare(b));
    for (const [term, count] of sortedTerms) {
      const idf = Math.log((1 + this.numDocs) / (1 + count)) + 1;
      this.vocab.set(term, { term, idx: this.dims++, df: count, idf });
    }

    this.fitted = true;
    return this;
  }

  get dimensions(): number {
    return this.dims;
  }

  /** Embed a single piece of text as a sparse TF-IDF vector. */
  embed(text: string): Map<number, number> {
    if (!this.fitted) {
      throw new Error("Embedder not fitted. Call .fit() first.");
    }
    const tokens = tokenize(text);
    if (tokens.length === 0) return new Map();

    // Term frequencies
    const tf = new Map<string, number>();
    for (const t of tokens) tf.set(t, (tf.get(t) ?? 0) + 1);

    // Build sparse TF-IDF vector
    const vec = new Map<number, number>();
    const totalTokens = tokens.length;
    for (const [term, count] of tf) {
      const entry = this.vocab.get(term);
      if (!entry) continue;
      const tfVal = count / totalTokens;
      const tfidf = tfVal * entry.idf;
      if (tfidf > 0) vec.set(entry.idx, tfidf);
    }

    // L2-normalize so cosine similarity reduces to a dot product.
    let norm = 0;
    for (const v of vec.values()) norm += v * v;
    norm = Math.sqrt(norm) || 1;
    for (const [k, v] of vec) vec.set(k, v / norm);

    return vec;
  }

  /** Get vocabulary info (useful for debugging / interviews). */
  getVocabularyStats(): {
    size: number;
    numDocs: number;
    topTerms: { term: string; df: number; idf: number }[];
  } {
    const entries = [...this.vocab.values()].sort((a, b) => b.df - a.df);
    return {
      size: this.dims,
      numDocs: this.numDocs,
      topTerms: entries.slice(0, 10).map((e) => ({
        term: e.term,
        df: e.df,
        idf: Number(e.idf.toFixed(3)),
      })),
    };
  }
}

/** Cosine similarity between two sparse vectors (already L2-normalized → dot product). */
export function cosineSimilarity(a: Map<number, number>, b: Map<number, number>): number {
  // Iterate the smaller vector for efficiency
  if (a.size > b.size) return cosineSimilarity(b, a);
  let dot = 0;
  for (const [k, v] of a) {
    const w = b.get(k);
    if (w !== undefined) dot += v * w;
  }
  return dot;
}
