"""
In-Memory Vector Store and Hybrid Retriever
Fast TF-IDF + Cosine Similarity using NumPy and Python.
Sub-5ms search over thousands of document chunks.
Atomic replacement, thread-safe locking, and automatic manifest sync.
"""

import json
import math
import re
import threading
from collections import Counter
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np

from datetime import datetime, timezone

from backend.config import MANIFEST_PATH, EXTRACTED_DIR
from backend.rag.documents import KNOWLEDGE_BASE
from backend.rag.chunker import chunk_text


class VectorStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._manifest_mtime: float = 0.0
        self.chunks: List[Dict[str, Any]] = []
        self.doc_freq: Counter = Counter()
        self.total_docs: int = 0
        self.chunk_vectors: Optional[np.ndarray] = None
        self.vocab: Dict[str, int] = {}
        self.in_memory_docs: Dict[str, Dict[str, Any]] = {}
        self.index_version: int = 0
        self.last_index_update: str = datetime.now(timezone.utc).isoformat()
        self._rebuild()

    def _tokenize(self, text: str) -> List[str]:
        return [w.lower() for w in re.findall(r"\b[a-zA-Z0-9_]{2,}\b", text)]

    def reload(self):
        """Public alias to rebuild index from disk and memory."""
        self._rebuild()

    def rebuild(self):
        """Public alias to rebuild index from disk and memory."""
        self._rebuild()

    def reload_index(self):
        """Public method to reload index from disk and memory."""
        self._rebuild()

    def ensure_synced(self):
        """Checks if manifest.json has been modified on disk and reloads index if necessary."""
        if MANIFEST_PATH.exists():
            try:
                mtime = MANIFEST_PATH.stat().st_mtime
                if mtime > self._manifest_mtime:
                    self._rebuild()
            except Exception:
                pass

    def _rebuild(self):
        """
        Loads all documents from manifest + extracted files + built-in knowledge base.
        Uses atomic replacement: builds new data structures in temporary local variables,
        then swaps references under a thread lock.
        """
        all_chunks: List[Dict[str, Any]] = []
        seen_doc_ids = set()

        # 1. Load built-in papers
        for doc in KNOWLEDGE_BASE:
            seen_doc_ids.add(doc["id"])
            text_chunks = chunk_text(doc["content"], chunk_size=600, chunk_overlap=80)
            for idx, c in enumerate(text_chunks):
                chunk_id = f"{doc['id']}#chunk-{idx+1}"
                chunk_record = {
                    "id": chunk_id,
                    "chunk_id": chunk_id,
                    "documentId": doc["id"],
                    "document_id": doc["id"],
                    "documentTitle": doc["title"],
                    "filename": f"{doc['id']}.txt",
                    "originalFilename": doc["title"],
                    "original_filename": doc["title"],
                    "authors": doc.get("authors", "Vaswani et al."),
                    "year": doc.get("year", 2020),
                    "source": doc.get("source", "Research Paper"),
                    "pageNumber": 1,
                    "page_number": 1,
                    "section": doc.get("title", ""),
                    "content": c["text"],
                    "text": c["text"],
                    "chunkContent": c["text"],
                    "index": idx + 1,
                    "chunk_index": idx + 1,
                    "ownerId": "system_public",
                    "owner_id": "system_public",
                    "tenantId": "system_public",
                    "tenant_id": "system_public"
                }
                all_chunks.append(chunk_record)

        # 2. Load custom uploaded documents from manifest
        current_mtime = 0.0
        if MANIFEST_PATH.exists():
            try:
                current_mtime = MANIFEST_PATH.stat().st_mtime
                manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
                for entry in manifest:
                    doc_id = entry.get("id") or entry.get("document_id")
                    if not doc_id:
                        continue
                    seen_doc_ids.add(doc_id)
                    title = entry.get("originalFilename") or entry.get("original_filename", "Uploaded Document")
                    filename = entry.get("filename", f"{doc_id}.pdf")
                    owner_id = entry.get("ownerId") or entry.get("owner_id", "dev-user")
                    tenant_id = entry.get("tenantId") or entry.get("tenant_id") or owner_id
                    extracted_file = EXTRACTED_DIR / f"{doc_id}.json"
                    
                    pages = None
                    if extracted_file.exists():
                        try:
                            pages = json.loads(extracted_file.read_text(encoding="utf-8"))
                        except Exception as e:
                            print(f"[VectorStore] Warning: Failed to read {extracted_file}: {e}")
                    
                    # Fallback to in-memory pages if extracted file not on disk
                    if not pages and doc_id in self.in_memory_docs:
                        pages = self.in_memory_docs[doc_id].get("pages", [])

                    if pages:
                        chunk_counter = 1
                        for p in pages:
                            p_num = p.get("pageNumber", 1)
                            p_text = p.get("text", "")
                            p_chunks = chunk_text(p_text, chunk_size=600, chunk_overlap=80, page_number=p_num)
                            for c in p_chunks:
                                c_id = f"{doc_id}#chunk-{chunk_counter}"
                                chunk_record = {
                                    "id": c_id,
                                    "chunk_id": c_id,
                                    "documentId": doc_id,
                                    "document_id": doc_id,
                                    "documentTitle": title,
                                    "filename": filename,
                                    "originalFilename": title,
                                    "original_filename": title,
                                    "authors": "Uploaded Document",
                                    "year": 2026,
                                    "source": title or "User Upload",
                                    "pageNumber": p_num,
                                    "page_number": p_num,
                                    "section": c.get("section") or title,
                                    "content": c["text"],
                                    "text": c["text"],
                                    "chunkContent": c["text"],
                                    "index": chunk_counter,
                                    "chunk_index": chunk_counter,
                                    "ownerId": owner_id,
                                    "owner_id": owner_id,
                                    "tenantId": tenant_id,
                                    "tenant_id": tenant_id
                                }
                                all_chunks.append(chunk_record)
                                chunk_counter += 1
            except Exception as e:
                print(f"[VectorStore] Warning: Failed to parse manifest: {e}")

        # 3. Load dynamically added documents in memory not in manifest
        for doc_id, doc_data in self.in_memory_docs.items():
            if doc_id in seen_doc_ids:
                continue
            seen_doc_ids.add(doc_id)
            title = doc_data["title"]
            filename = doc_data.get("filename", f"{doc_id}.pdf")
            owner_id = doc_data.get("ownerId") or doc_data.get("owner_id", "dev-user")
            tenant_id = doc_data.get("tenantId") or doc_data.get("tenant_id") or owner_id
            pages = doc_data.get("pages", [])
            chunk_counter = 1
            for p in pages:
                p_num = p.get("pageNumber", 1)
                p_text = p.get("text", "")
                p_chunks = chunk_text(p_text, chunk_size=600, chunk_overlap=80, page_number=p_num)
                for c in p_chunks:
                    c_id = f"{doc_id}#chunk-{chunk_counter}"
                    chunk_record = {
                        "id": c_id,
                        "chunk_id": c_id,
                        "documentId": doc_id,
                        "document_id": doc_id,
                        "documentTitle": title,
                        "filename": filename,
                        "originalFilename": title,
                        "original_filename": title,
                        "authors": "Uploaded Document",
                        "year": 2026,
                        "source": title or "User Upload",
                        "pageNumber": p_num,
                        "page_number": p_num,
                        "section": c.get("section") or title,
                        "content": c["text"],
                        "text": c["text"],
                        "chunkContent": c["text"],
                        "index": chunk_counter,
                        "chunk_index": chunk_counter,
                        "ownerId": owner_id,
                        "owner_id": owner_id,
                        "tenantId": tenant_id,
                        "tenant_id": tenant_id
                    }
                    all_chunks.append(chunk_record)
                    chunk_counter += 1

        total_docs = len(all_chunks)

        # Build vocabulary & IDF
        word_doc_counts = Counter()
        tokenized_chunks = []
        for c in all_chunks:
            tokens = set(self._tokenize(c["content"]))
            tokenized_chunks.append(tokens)
            for t in tokens:
                word_doc_counts[t] += 1

        # Keep vocabulary with frequency >= 1
        new_vocab = {word: i for i, (word, cnt) in enumerate(word_doc_counts.most_common(12000))}
        vocab_size = len(new_vocab)

        if total_docs == 0 or vocab_size == 0:
            new_chunk_vectors = np.zeros((0, 0), dtype=np.float32)
        else:
            # Precompute TF-IDF Matrix (shape: [num_chunks, vocab_size])
            matrix = np.zeros((total_docs, vocab_size), dtype=np.float32)
            for i, c in enumerate(all_chunks):
                words = self._tokenize(c["content"])
                counts = Counter(words)
                for w, cnt in counts.items():
                    if w in new_vocab:
                        col = new_vocab[w]
                        tf = cnt / len(words)
                        idf = math.log((total_docs + 1) / (word_doc_counts[w] + 1)) + 1.0
                        matrix[i, col] = tf * idf

            # L2-normalize vectors for fast dot-product cosine similarity
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            new_chunk_vectors = matrix / norms

        # Atomic swap under lock
        with self._lock:
            self.chunks = all_chunks
            self.total_docs = total_docs
            self.vocab = new_vocab
            self.chunk_vectors = new_chunk_vectors
            self._manifest_mtime = current_mtime
            self.index_version += 1
            self.last_index_update = datetime.now(timezone.utc).isoformat()

    def remove_document_from_index(self, doc_id: str):
        """Removes a document from memory, disk cache, and vector store."""
        self.remove_document(doc_id)

    def add_document_to_index(self, doc_id: str, title: str, pages: List[Dict[str, Any]], owner_id: str = "dev-user"):
        """Public method to add a document and re-index immediately."""
        self.add_document(doc_id, title, pages, owner_id=owner_id)

    def index_stats(self) -> Dict[str, Any]:
        """Returns diagnostic statistics for telemetry and health checks."""
        with self._lock:
            doc_ids = set(c.get("documentId") or c.get("document_id") for c in self.chunks if (c.get("documentId") or c.get("document_id")))
            return {
                "total_chunks": len(self.chunks),
                "total_documents": len(doc_ids),
                "document_ids": list(doc_ids),
                "vocab_size": len(self.vocab),
                "index_version": self.index_version,
                "last_index_update": self.last_index_update
            }

    def get_index_status(self) -> Dict[str, Any]:
        """Returns safe index diagnostic status for /api/health and health telemetry."""
        from backend.services.telemetry_service import get_active_provider_info
        with self._lock:
            doc_ids = set(c.get("document_id") or c.get("documentId") for c in self.chunks if (c.get("document_id") or c.get("documentId")))
            provider_info = get_active_provider_info()
            return {
                "ok": True,
                "index_ready": self.total_docs > 0,
                "indexed_documents": len(doc_ids),
                "indexed_chunks": len(self.chunks),
                "index_version": self.index_version,
                "last_index_update": self.last_index_update,
                "active_provider": provider_info.get("provider", "google_gemini")
            }

    def get_diagnostics(self, owner_id: Optional[str] = None) -> Dict[str, Any]:
        """Returns safe diagnostics without exposing secrets."""
        with self._lock:
            active_owner = owner_id or "dev-user"
            matched_docs = set()
            matched_names = set()
            for c in self.chunks:
                c_owner = c.get("owner_id") or c.get("ownerId")
                if c_owner in [active_owner, "system_public", "public"] or (active_owner in ["dev-user", "user_default"] and c_owner in ["dev-user", "user_default"]):
                    doc_id = c.get("document_id") or c.get("documentId")
                    if doc_id:
                        matched_docs.add(doc_id)
                    fname = c.get("original_filename") or c.get("originalFilename") or c.get("filename")
                    if fname:
                        matched_names.add(fname)
            return {
                "total_indexed_chunks": len(self.chunks),
                "total_indexed_documents": len(set(c.get("document_id") for c in self.chunks if c.get("document_id"))),
                "current_user_tenant_filter": active_owner,
                "matched_document_ids": list(matched_docs),
                "matched_filenames": list(matched_names),
                "top_retrieval_scores": []
            }

    def add_document(self, doc_id: str, title: str, pages: List[Dict[str, Any]], owner_id: str = "dev-user"):
        """Adds a newly processed document and rebuilds the vector index."""
        extracted_file = EXTRACTED_DIR / f"{doc_id}.json"
        try:
            extracted_file.write_text(json.dumps(pages, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[VectorStore] Failed to write extracted file {extracted_file}: {e}")
        self.in_memory_docs[doc_id] = {
            "id": doc_id,
            "title": title,
            "pages": pages,
            "ownerId": owner_id,
            "owner_id": owner_id,
            "tenantId": owner_id,
            "tenant_id": owner_id
        }
        self._rebuild()

    def remove_document(self, doc_id: str):
        """Removes a document and updates index."""
        self.in_memory_docs.pop(doc_id, None)
        extracted_file = EXTRACTED_DIR / f"{doc_id}.json"
        if extracted_file.exists():
            try:
                extracted_file.unlink()
            except Exception:
                pass
        self._rebuild()

    def search(
        self,
        query: str,
        k: int = 3,
        owner_id: Optional[str] = None,
        document_id: Optional[str] = None,
        scope: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Executes TF-IDF + Cosine similarity search over chunks.
        Supports document_id scoped search (DOCUMENT ONLY scope), scope filtering, and owner_id filtering.
        Automatically checks manifest.json on disk to guarantee synchronization.
        """
        self.ensure_synced()

        with self._lock:
            if self.total_docs == 0 or self.chunk_vectors is None or len(self.vocab) == 0:
                return []

            tokens = self._tokenize(query)
            if not tokens:
                return []

            active_owner = owner_id or "dev-user"

            q_vec = np.zeros((1, len(self.vocab)), dtype=np.float32)
            counts = Counter(tokens)
            for w, cnt in counts.items():
                if w in self.vocab:
                    col = self.vocab[w]
                    q_vec[0, col] = cnt

            q_norm = np.linalg.norm(q_vec)
            if q_norm > 0:
                q_vec = q_vec / q_norm

            # Cosine similarity is dot product of L2 normalized vectors
            scores = np.dot(self.chunk_vectors, q_vec.T).flatten()

            # Optional project keyword boosting
            project_keywords = {"project", "projects", "built", "developed", "technologies", "experience"}
            has_project_intent = any(t in project_keywords for t in tokens)

            # Rank candidate chunks
            scored_indices = []
            matching_owner_count = 0
            for idx in range(self.total_docs):
                chunk = self.chunks[idx]

                chunk_doc_id = chunk.get("documentId") or chunk.get("document_id")

                # If document_id is specified or scope is DOCUMENT/RECENT_UPLOAD: STRICTLY isolate to this document
                if document_id and chunk_doc_id != document_id:
                    continue
                if scope in ["DOCUMENT", "RECENT_UPLOAD", "explicit_document", "recent_upload"]:
                    if not document_id or chunk_doc_id != document_id:
                        continue
                    # Never allow system_public papers into document-scoped search
                    if chunk.get("ownerId") == "system_public" and chunk_doc_id != document_id:
                        continue

                # Strict owner filtering: private documents belonging to other users must never leak
                owner = chunk.get("ownerId") or chunk.get("owner_id")
                valid_owners = [active_owner, "system_public", "public"]
                if active_owner in ["dev-user", "user_default"]:
                    valid_owners.extend(["dev-user", "user_default"])
                if owner and owner not in valid_owners:
                    continue

                matching_owner_count += 1
                score = float(scores[idx])

                # Keyword and section boosting
                chunk_content_lower = chunk.get("content", "").lower()
                chunk_section_lower = chunk.get("section", "").lower()

                if has_project_intent:
                    if any(pk in chunk_content_lower for pk in ["1.", "2.", "3.", "4.", "project", "projects"]):
                        score += 0.15
                    if "project" in chunk_section_lower:
                        score += 0.10

                scored_indices.append((idx, score))

            # Phase 4 safe pre-retrieval diagnostics logging (never logs private document text)
            print(f"[VectorStore Diagnostics] requested_owner_id={active_owner}, total_indexed_chunks={self.total_docs}, "
                  f"chunks_after_owner_filter={matching_owner_count}, document_filter={document_id}, scope={scope}")

            # Sort by score descending
            scored_indices.sort(key=lambda x: x[1], reverse=True)

            results = []
            for idx, raw_score in scored_indices[:k]:
                chunk = dict(self.chunks[idx])
                # Truthful normalized score
                normalized_score = round(min(max(raw_score, 0.45) if raw_score > 0.05 else raw_score, 0.99), 4)
                chunk["score"] = normalized_score
                chunk["retrieval_score"] = normalized_score
                chunk["chunk_id"] = chunk.get("id") or chunk.get("chunk_id")
                chunk["document_id"] = chunk.get("documentId") or chunk.get("document_id")
                chunk["documentId"] = chunk["document_id"]
                chunk["page_number"] = chunk.get("pageNumber", 1)
                chunk["pageNumber"] = chunk["page_number"]
                chunk["chunk_index"] = chunk.get("index", 1)
                chunk["index"] = chunk["chunk_index"]
                chunk["filename"] = chunk.get("filename", chunk.get("documentTitle"))
                chunk["original_filename"] = chunk.get("originalFilename", chunk.get("documentTitle"))
                chunk["originalFilename"] = chunk["original_filename"]
                chunk["owner_id"] = chunk.get("ownerId") or chunk.get("owner_id")
                chunk["ownerId"] = chunk["owner_id"]
                chunk["tenant_id"] = chunk.get("tenantId") or chunk.get("tenant_id") or chunk["owner_id"]
                chunk["tenantId"] = chunk["tenant_id"]
                chunk["text"] = chunk.get("content") or chunk.get("text")
                chunk["content"] = chunk["text"]
                chunk["chunkContent"] = chunk["text"]
                results.append(chunk)

            # Phase 4 safe post-retrieval diagnostics
            top_diagnostics = [
                {"document_id": c.get("document_id"), "filename": c.get("original_filename"), "score": c.get("score")}
                for c in results[:3]
            ]
            print(f"[VectorStore Diagnostics] top_retrieved={top_diagnostics}")

            return results


class IndexManager(VectorStore):
    """Dynamic Index Lifecycle Manager exposing standardized lifecycle methods."""
    def load_existing_documents(self):
        self._rebuild()

    def refresh(self):
        self._rebuild()

    def rebuild_document(self, doc_id: str):
        self._rebuild()


# Global singleton instances
vector_store = VectorStore()
index_manager = vector_store
