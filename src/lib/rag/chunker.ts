/**
 * Text Chunker — Recursive Character Splitter
 *
 * Splits documents into smaller chunks for retrieval. Mirrors the behavior of
 * LangChain's RecursiveCharacterTextSplitter: try to split on paragraph breaks
 * first, then sentences, then words, then characters — always preferring the
 * largest semantic boundary that fits within the target chunk size.
 */

export interface Chunk {
  id: string;
  documentId: string;
  documentTitle: string;
  content: string;
  /** 1-indexed position of this chunk within its source document */
  index: number;
  /** Character offset of the start of this chunk in the source document */
  startOffset: number;
}

export interface ChunkerOptions {
  /** Target size of each chunk in characters */
  chunkSize?: number;
  /** Overlap between adjacent chunks in characters */
  chunkOverlap?: number;
}

const DEFAULTS: Required<ChunkerOptions> = {
  chunkSize: 600,
  chunkOverlap: 80,
};

const SPLIT_BOUNDARIES = [
  /\n\n+/,
  /\n/,
  /\.(?=\s|$)/,
  /[,;:](?=\s|$)/,
  /\s+/,
  "",
];

function splitWithBoundary(text: string, boundary: RegExp): string[] {
  if (boundary.source === "") {
    return text.split("");
  }
  const parts = text.split(boundary);
  // Preserve the delimiter where possible by re-attaching it.
  // For sentences / commas / etc. we want to keep the punctuation.
  const result: string[] = [];
  const matches = text.matchAll(new RegExp(boundary.source, "g"));
  let i = 0;
  for (const part of parts) {
    result.push(part);
    const m = matches.next();
    if (!m.done && i < parts.length - 1) {
      result[result.length - 1] += m.value[0];
    }
    i++;
  }
  return result.filter((p) => p.length > 0);
}

function joinToSize(
  pieces: string[],
  maxSize: number,
  overlap: number,
): { chunks: string[]; offsets: number[] } {
  const chunks: string[] = [];
  const offsets: number[] = [];
  let current = "";
  let currentStart = 0;
  let cursor = 0;

  for (const piece of pieces) {
    const pieceStart = cursor;
    cursor += piece.length;

    if (current.length + piece.length <= maxSize) {
      if (current.length === 0) currentStart = pieceStart;
      current += piece;
    } else {
      // Flush current
      if (current.length > 0) {
        chunks.push(current);
        offsets.push(currentStart);
      }
      // Start a new chunk with overlap from the tail of the previous one
      let overlapText = "";
      if (overlap > 0 && chunks.length > 0) {
        overlapText = chunks[chunks.length - 1].slice(-overlap);
      }
      current = overlapText + piece;
      currentStart = pieceStart - overlapText.length;
    }
  }
  if (current.length > 0) {
    chunks.push(current);
    offsets.push(currentStart);
  }
  return { chunks, offsets };
}

/**
 * Recursively split a text into chunks that fit within chunkSize.
 * Tries the largest semantic boundary first, falls back to smaller ones.
 */
function recursiveSplit(
  text: string,
  chunkSize: number,
  chunkOverlap: number,
  boundaryIdx = 0,
): { chunks: string[]; offsets: number[] } {
  if (text.length <= chunkSize) {
    return { chunks: [text], offsets: [0] };
  }

  const boundary = SPLIT_BOUNDARIES[boundaryIdx];
  if (!boundary) {
    // Last resort: hard character split.
    const { chunks, offsets } = joinToSize(
      text.match(/[\s\S]{1,1}/g) ?? [],
      chunkSize,
      chunkOverlap,
    );
    return { chunks, offsets };
  }

  const pieces = splitWithBoundary(text, boundary);
  // First pass: try to join pieces directly into chunks of chunkSize.
  const { chunks, offsets } = joinToSize(pieces, chunkSize, chunkOverlap);

  // Any chunk still bigger than chunkSize must be recursively split with the
  // next smaller boundary.
  const finalChunks: string[] = [];
  const finalOffsets: number[] = [];
  for (let i = 0; i < chunks.length; i++) {
    if (chunks[i].length > chunkSize) {
      const sub = recursiveSplit(
        chunks[i],
        chunkSize,
        chunkOverlap,
        boundaryIdx + 1,
      );
      for (let j = 0; j < sub.chunks.length; j++) {
        finalChunks.push(sub.chunks[j]);
        finalOffsets.push((offsets[i] ?? 0) + (sub.offsets[j] ?? 0));
      }
    } else {
      finalChunks.push(chunks[i]);
      finalOffsets.push(offsets[i] ?? 0);
    }
  }
  return { chunks: finalChunks, offsets: finalOffsets };
}

export function chunkDocument(
  documentId: string,
  documentTitle: string,
  content: string,
  options: ChunkerOptions = {},
): Chunk[] {
  const { chunkSize, chunkOverlap } = { ...DEFAULTS, ...options };
  const { chunks, offsets } = recursiveSplit(content, chunkSize, chunkOverlap);
  return chunks.map((content, i) => ({
    id: `${documentId}#chunk-${i + 1}`,
    documentId,
    documentTitle,
    content: content.trim(),
    index: i + 1,
    startOffset: offsets[i] ?? 0,
  }));
}
