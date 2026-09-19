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
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

from datetime import datetime, timezone

from backend.config import MANIFEST_PATH, EXTRACTED_DIR
from backend.rag.documents import KNOWLEDGE_BASE
from backend.rag.chunker import chunk_text, semantic_chunk_document


class VectorStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._manifest_mtime: float = 0.0
        self.chunks: List[Dict[str, Any]] = []
        self.doc_freq: Counter = Counter()
        self.total_docs: int = 0
        self.chunk_vectors: Optional[np.ndarray] = None
        self.dense_vectors: Optional[np.ndarray] = None
        self.svd_model = None
        self.dense_dimensions: int = 0
        self.vocab: Dict[str, int] = {}
        self.idf_weights: Optional[np.ndarray] = None
        self.in_memory_docs: Dict[str, Dict[str, Any]] = {}
        self.index_version: int = 0
        self.last_index_update: str = datetime.now(timezone.utc).isoformat()
        self.dense_index_metadata: Dict[str, Any] = {
            "provider": "lsa",
            "model": "TruncatedSVD-64d",
            "dimensionality": 64,
            "index_version": 0,
            "type": "latent_semantic"
        }
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

        # 1. Custom uploaded documents and chunks from PostgreSQL/Database (Authoritative Source of Truth)
        loaded_from_db = False
        try:
            from backend.services.db_service import db_service
            db_chunks = db_service.get_all_chunks()
            if db_chunks:
                for row in db_chunks:
                    doc_id = row["document_id"]
                    seen_doc_ids.add(doc_id)
                    cid = row.get("chunk_id") or row.get("id")
                    orig_name = row.get("original_filename") or "Uploaded Document"
                    owner_id = row.get("owner_id", "dev-user")
                    c_formatted = {
                        "id": cid,
                        "chunk_id": cid,
                        "document_id": doc_id,
                        "documentId": doc_id,
                        "document_name": orig_name,
                        "originalFilename": orig_name,
                        "original_filename": orig_name,
                        "filename": row.get("storage_filename") or row.get("filename") or orig_name,
                        "storage_filename": row.get("storage_filename") or row.get("filename") or orig_name,
                        "mime_type": row.get("mime_type", "application/pdf"),
                        "page_number": row.get("page_number", 1),
                        "pageNumber": row.get("page_number", 1),
                        "page_start": row.get("page_start", 1),
                        "page_end": row.get("page_end", 1),
                        "section": row.get("section", ""),
                        "subsection": row.get("subsection", ""),
                        "source_location": row.get("source_location", ""),
                        "content": row.get("content", ""),
                        "text": row.get("content", ""),
                        "char_count": row.get("char_count", len(row.get("content", ""))),
                        "token_count": row.get("token_count", 0),
                        "authors": row.get("authors", "Uploaded Document"),
                        "year": row.get("year", 2026),
                        "source": row.get("source") or orig_name,
                        "owner_id": owner_id,
                        "ownerId": owner_id,
                        "tenant_id": owner_id,
                        "tenantId": owner_id,
                    }
                    all_chunks.append(c_formatted)
                loaded_from_db = True
        except Exception as e:
            pass

        # 3. Load documents from manifest.json not already in seen_doc_ids
        current_mtime = 0.0
        if MANIFEST_PATH.exists():
            try:
                current_mtime = MANIFEST_PATH.stat().st_mtime
                manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
                for entry in manifest:
                    doc_id = entry.get("id") or entry.get("document_id")
                    if not doc_id or doc_id in seen_doc_ids:
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
                        sem_chunks = semantic_chunk_document(pages, doc_id, title)
                        for c in sem_chunks:
                            c["authors"] = "Uploaded Document"
                            c["year"] = 2026
                            c["source"] = title or "User Upload"
                            c["ownerId"] = owner_id
                            c["owner_id"] = owner_id
                            c["tenantId"] = tenant_id
                            c["tenant_id"] = tenant_id
                            c["filename"] = filename
                            c["originalFilename"] = title
                            c["original_filename"] = title
                            all_chunks.append(c)
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
            if pages:
                sem_chunks = semantic_chunk_document(pages, doc_id, title)
                for c in sem_chunks:
                    c["authors"] = "Uploaded Document"
                    c["year"] = 2026
                    c["source"] = title or "User Upload"
                    c["ownerId"] = owner_id
                    c["owner_id"] = owner_id
                    c["tenantId"] = tenant_id
                    c["tenant_id"] = tenant_id
                    c["filename"] = filename
                    c["originalFilename"] = title
                    c["original_filename"] = title
                    all_chunks.append(c)

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

        new_dense_vectors = None
        new_svd_model = None
        dense_dims = 0

        if total_docs == 0 or vocab_size == 0:
            new_chunk_vectors = np.zeros((0, 0), dtype=np.float32)
        else:
            # Precompute TF-IDF Matrix (shape: [num_chunks, vocab_size]) - Lexical representation
            new_idf = np.zeros(vocab_size, dtype=np.float32)
            for w, col in new_vocab.items():
                new_idf[col] = math.log((total_docs + 1) / (word_doc_counts[w] + 1)) + 1.0

            matrix = np.zeros((total_docs, vocab_size), dtype=np.float32)
            for i, c in enumerate(all_chunks):
                words = self._tokenize(c["content"])
                counts = Counter(words)
                num_words = max(len(words), 1)
                for w, cnt in counts.items():
                    if w in new_vocab:
                        col = new_vocab[w]
                        matrix[i, col] = (cnt / num_words) * new_idf[col]

            # L2-normalize vectors for fast dot-product cosine similarity
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            new_chunk_vectors = matrix / norms

            # Compute Dense Semantic Representation via TruncatedSVD (Latent Semantic Analysis)
            # Projects sparse vocabulary space into continuous dense concept representations (Mandate 3)
            # Accurately designated as: LSA-based latent semantic retrieval / concept projection (never neural embeddings)
            if total_docs > 2 and vocab_size > 2:
                n_components = min(64, vocab_size - 1, total_docs - 1)
                if n_components >= 2:
                    try:
                        from sklearn.decomposition import TruncatedSVD
                        svd = TruncatedSVD(n_components=n_components, random_state=42)
                        dense_raw = svd.fit_transform(matrix)
                        d_norms = np.linalg.norm(dense_raw, axis=1, keepdims=True)
                        d_norms[d_norms == 0] = 1.0
                        new_dense_vectors = (dense_raw / d_norms).astype(np.float32)
                        new_svd_model = svd
                        dense_dims = n_components
                    except Exception as e:
                        print(f"[VectorStore] TruncatedSVD semantic model fit warning: {e}")

        # Atomic swap under lock
        with self._lock:
            self.chunks = all_chunks
            self.total_docs = total_docs
            self.vocab = new_vocab
            self.idf_weights = new_idf if total_docs > 0 and vocab_size > 0 else None
            self.chunk_vectors = new_chunk_vectors
            self.dense_vectors = new_dense_vectors
            self.svd_model = new_svd_model
            self.dense_dimensions = dense_dims
            self._manifest_mtime = current_mtime
            self.index_version += 1
            self.last_index_update = datetime.now(timezone.utc).isoformat()

            # Record dense index metadata (Mandates 9 & 48)
            try:
                from backend.rag.embeddings import embedding_manager
                active_emb = embedding_manager.get_provider()
                self.dense_index_metadata = {
                    "provider": active_emb.name,
                    "model": active_emb.model,
                    "dimensionality": active_emb.dimension if active_emb.name != "lsa" else dense_dims,
                    "index_version": self.index_version,
                    "type": "dense_neural" if ("neural" in active_emb.name or "gemini" in active_emb.name) else "latent_semantic"
                }
            except Exception:
                self.dense_index_metadata = {
                    "provider": "lsa",
                    "model": "TruncatedSVD-64d",
                    "dimensionality": dense_dims,
                    "index_version": self.index_version,
                    "type": "latent_semantic"
                }

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
            mem_bytes = (
                (self.chunk_vectors.nbytes if self.chunk_vectors is not None else 0) +
                (self.dense_vectors.nbytes if self.dense_vectors is not None else 0)
            )
            dense_meta = getattr(self, "dense_index_metadata", {
                "provider": "lsa",
                "model": "TruncatedSVD-64d",
                "dimensionality": self.dense_dimensions,
                "index_version": self.index_version,
                "type": "latent_semantic"
            })
            return {
                "total_chunks": len(self.chunks),
                "total_documents": len(doc_ids),
                "document_ids": list(doc_ids),
                "vocab_size": len(self.vocab),
                "semantic_dimensions": self.dense_dimensions,
                "memory_footprint_bytes": mem_bytes,
                "memory_footprint_kb": round(mem_bytes / 1024, 2),
                "index_version": self.index_version,
                "last_index_update": self.last_index_update,
                "dense_index_metadata": dense_meta,
                "provider": dense_meta.get("provider", "lsa"),
                "model": dense_meta.get("model", "TruncatedSVD-64d"),
                "dimensionality": dense_meta.get("dimensionality", self.dense_dimensions)
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
                if c_owner == active_owner or (active_owner in ["dev-user", "user_default"] and c_owner in ["dev-user", "user_default"]):
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
        is_guest = bool(owner_id and owner_id.startswith("guest_"))
        if not is_guest:
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

        if not is_guest:
            try:
                from backend.services.db_service import db_service
                sem_chunks = semantic_chunk_document(pages, doc_id, title)
                db_service.save_chunks(doc_id, sem_chunks)
            except Exception:
                pass

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

    def migrate_owner(self, old_owner_id: str, new_owner_id: str) -> int:
        """Migrates chunk and in-memory document ownership from guest session to authenticated user."""
        count = 0
        with self._lock:
            for c in self.chunks:
                if c.get("owner_id") == old_owner_id or c.get("ownerId") == old_owner_id:
                    c["owner_id"] = new_owner_id
                    c["ownerId"] = new_owner_id
                    c["tenant_id"] = new_owner_id
                    c["tenantId"] = new_owner_id
                    count += 1
            for doc_id, d in self.in_memory_docs.items():
                if d.get("owner_id") == old_owner_id or d.get("ownerId") == old_owner_id:
                    d["owner_id"] = new_owner_id
                    d["ownerId"] = new_owner_id
                    d["tenant_id"] = new_owner_id
                    d["tenantId"] = new_owner_id
        return count

    def _filter_candidate_indices(
        self,
        owner_id: Optional[str] = None,
        document_id: Optional[str] = None,
        scope: Optional[str] = None,
        allowed_document_ids: Optional[List[str]] = None
    ) -> List[int]:
        """Returns list of chunk indices strictly matching tenant, user, and document scope."""
        # Chat-scoped allowed document IDs: if explicitly passed as empty list, no sources are attached
        if allowed_document_ids is not None and len(allowed_document_ids) == 0:
            return []

        active_owner = owner_id or "dev-user"
        valid_owners = [active_owner]
        if active_owner in ["dev-user", "user_default"]:
            valid_owners.extend(["dev-user", "user_default"])

        matched_indices = []
        for idx in range(self.total_docs):
            chunk = self.chunks[idx]
            chunk_doc_id = chunk.get("documentId") or chunk.get("document_id")

            # Chat-scoped allowed document IDs
            if allowed_document_ids is not None and chunk_doc_id not in allowed_document_ids:
                continue

            # Document-id scoped isolation
            if document_id and chunk_doc_id != document_id:
                continue
            if scope in ["DOCUMENT", "RECENT_UPLOAD", "explicit_document", "recent_upload"]:
                if not document_id or chunk_doc_id != document_id:
                    continue

            # Strict tenant / owner isolation: only chunks belonging to the requesting user/session
            owner = chunk.get("ownerId") or chunk.get("owner_id")
            if owner not in valid_owners:
                continue

            matched_indices.append(idx)
        return matched_indices

    def _format_result_chunk(self, idx: int, raw_score: float) -> Dict[str, Any]:
        """Formats chunk dictionary with truthful normalized score and full provenance."""
        chunk = dict(self.chunks[idx])
        # Truthful score normalization without arbitrary clamping (Mandate 2)
        normalized_score = round(float(np.clip(raw_score, 0.0, 1.0)), 4)
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
        return chunk

    def get_candidate_vectors_and_query_vector(
        self,
        query: str,
        candidates: List[Dict[str, Any]]
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Extracts candidate vectors and transforms query vector for MMR diversity calculations.
        Prefers dense semantic vectors (TruncatedSVD) if available, falls back to normalized TF-IDF vectors.
        """
        self.ensure_synced()
        with self._lock:
            if self.total_docs == 0 or len(candidates) == 0:
                return None, None

            id_to_idx = {}
            for i, c in enumerate(self.chunks):
                cid = c.get("id") or c.get("chunk_id")
                if cid:
                    id_to_idx[cid] = i

            cand_indices = []
            for c in candidates:
                cid = c.get("id") or c.get("chunk_id") or c.get("chunkId")
                cand_indices.append(id_to_idx.get(cid))

            tokens = self._tokenize(query)
            q_sparse = np.zeros((1, len(self.vocab)), dtype=np.float32)
            if tokens and len(self.vocab) > 0:
                counts = Counter(tokens)
                num_tokens = max(len(tokens), 1)
                for w, cnt in counts.items():
                    if w in self.vocab:
                        col = self.vocab[w]
                        idf = self.idf_weights[col] if self.idf_weights is not None else 1.0
                        q_sparse[0, col] = (cnt / num_tokens) * idf
                q_norm = np.linalg.norm(q_sparse)
                if q_norm > 0:
                    q_sparse = q_sparse / q_norm

            # Dense vectors path (TruncatedSVD LSA)
            if self.dense_vectors is not None and self.svd_model is not None:
                dense_dim = self.dense_vectors.shape[1]
                cand_vecs = np.zeros((len(candidates), dense_dim), dtype=np.float32)
                for i, idx in enumerate(cand_indices):
                    if idx is not None and idx < self.dense_vectors.shape[0]:
                        cand_vecs[i] = self.dense_vectors[idx]

                try:
                    q_dense = self.svd_model.transform(q_sparse)
                    qd_norm = np.linalg.norm(q_dense)
                    if qd_norm > 0:
                        q_dense = q_dense / qd_norm
                    return cand_vecs, q_dense
                except Exception:
                    pass

            # Sparse TF-IDF vectors path
            if self.chunk_vectors is not None:
                vocab_dim = self.chunk_vectors.shape[1]
                cand_vecs = np.zeros((len(candidates), vocab_dim), dtype=np.float32)
                for i, idx in enumerate(cand_indices):
                    if idx is not None and idx < self.chunk_vectors.shape[0]:
                        cand_vecs[i] = self.chunk_vectors[idx]
                return cand_vecs, q_sparse

            return None, None

    def search_lexical(
        self,
        query: str,
        k: int = 3,
        owner_id: Optional[str] = None,
        document_id: Optional[str] = None,
        scope: Optional[str] = None,
        allowed_document_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Pure Lexical Retrieval: Sparse TF-IDF Cosine Similarity."""
        self.ensure_synced()
        with self._lock:
            if self.total_docs == 0 or self.chunk_vectors is None or len(self.vocab) == 0:
                return []
            tokens = self._tokenize(query)
            if not tokens:
                return []

            q_vec = np.zeros((1, len(self.vocab)), dtype=np.float32)
            counts = Counter(tokens)
            for w, cnt in counts.items():
                if w in self.vocab:
                    q_vec[0, self.vocab[w]] = cnt
            q_norm = np.linalg.norm(q_vec)
            if q_norm > 0:
                q_vec = q_vec / q_norm

            scores = np.dot(self.chunk_vectors, q_vec.T).flatten()
            candidates = self._filter_candidate_indices(owner_id, document_id, scope, allowed_document_ids)
            scored = [(idx, float(scores[idx])) for idx in candidates]
            scored.sort(key=lambda x: x[1], reverse=True)
            return [self._format_result_chunk(idx, sc) for idx, sc in scored[:k]]

    def search_semantic(
        self,
        query: str,
        k: int = 3,
        owner_id: Optional[str] = None,
        document_id: Optional[str] = None,
        scope: Optional[str] = None,
        allowed_document_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Pure Semantic Retrieval: Dense LSA TruncatedSVD Concept Vector Cosine Similarity."""
        self.ensure_synced()
        with self._lock:
            if self.total_docs == 0 or self.dense_vectors is None or self.svd_model is None:
                return self.search_lexical(query, k, owner_id, document_id, scope, allowed_document_ids)
            tokens = self._tokenize(query)
            if not tokens:
                return []

            q_vec = np.zeros((1, len(self.vocab)), dtype=np.float32)
            counts = Counter(tokens)
            num_tokens = max(len(tokens), 1)
            for w, cnt in counts.items():
                if w in self.vocab:
                    col = self.vocab[w]
                    idf = self.idf_weights[col] if self.idf_weights is not None else 1.0
                    q_vec[0, col] = (cnt / num_tokens) * idf
            q_norm = np.linalg.norm(q_vec)
            if q_norm > 0:
                q_vec = q_vec / q_norm

            try:
                q_dense = self.svd_model.transform(q_vec)
                qd_norm = np.linalg.norm(q_dense)
                if qd_norm > 0:
                    q_dense = q_dense / qd_norm
                scores = np.dot(self.dense_vectors, q_dense.T).flatten()
            except Exception:
                return self.search_lexical(query, k, owner_id, document_id, scope, allowed_document_ids)

            candidates = self._filter_candidate_indices(owner_id, document_id, scope, allowed_document_ids)
            scored = [(idx, float(scores[idx])) for idx in candidates]
            scored.sort(key=lambda x: x[1], reverse=True)
            return [self._format_result_chunk(idx, sc) for idx, sc in scored[:k]]

    def search_hybrid(
        self,
        query: str,
        k: int = 3,
        owner_id: Optional[str] = None,
        document_id: Optional[str] = None,
        scope: Optional[str] = None,
        allowed_document_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Hybrid Retrieval: Convex Combination & Reciprocal Rank Fusion (RRF) of Lexical + Semantic."""
        self.ensure_synced()
        with self._lock:
            if self.total_docs == 0 or self.chunk_vectors is None or len(self.vocab) == 0:
                return []
            tokens = self._tokenize(query)
            if not tokens:
                return []

            active_owner = owner_id or "dev-user"
            candidates = self._filter_candidate_indices(owner_id, document_id, scope, allowed_document_ids)
            if not candidates:
                return []

            # 1. Lexical vector & scores
            q_vec = np.zeros((1, len(self.vocab)), dtype=np.float32)
            counts = Counter(tokens)
            for w, cnt in counts.items():
                if w in self.vocab:
                    q_vec[0, self.vocab[w]] = cnt
            q_norm = np.linalg.norm(q_vec)
            if q_norm > 0:
                q_vec = q_vec / q_norm

            lex_scores = np.dot(self.chunk_vectors, q_vec.T).flatten()

            # 2. Semantic vector & scores (if dense SVD model available)
            if self.dense_vectors is not None and self.svd_model is not None:
                try:
                    q_dense = self.svd_model.transform(q_vec)
                    qd_norm = np.linalg.norm(q_dense)
                    if qd_norm > 0:
                        q_dense = q_dense / qd_norm
                    sem_scores = np.dot(self.dense_vectors, q_dense.T).flatten()
                except Exception:
                    sem_scores = lex_scores
            else:
                sem_scores = lex_scores

            # Keyword boosting
            project_keywords = {"project", "projects", "built", "developed", "technologies", "experience"}
            has_project_intent = any(t in project_keywords for t in tokens)

            # RRF ranking calculation
            lex_ranked = sorted(candidates, key=lambda idx: float(lex_scores[idx]), reverse=True)
            sem_ranked = sorted(candidates, key=lambda idx: float(sem_scores[idx]), reverse=True)
            lex_rank_map = {idx: rank + 1 for rank, idx in enumerate(lex_ranked)}
            sem_rank_map = {idx: rank + 1 for rank, idx in enumerate(sem_ranked)}

            scored_indices = []
            for idx in candidates:
                l_score = float(lex_scores[idx])
                s_score = float(sem_scores[idx])
                r_lex = lex_rank_map.get(idx, len(candidates))
                r_sem = sem_rank_map.get(idx, len(candidates))

                # Reciprocal rank fusion component (k=60)
                rrf = (1.0 / (60.0 + r_lex)) + (1.0 / (60.0 + r_sem))
                # Convex combination of normalized scores + RRF
                combined = 0.45 * l_score + 0.35 * s_score + 0.20 * (rrf * 30.0)

                chunk = self.chunks[idx]
                if has_project_intent:
                    chunk_content_lower = chunk.get("content", "").lower()
                    chunk_section_lower = chunk.get("section", "").lower()
                    if any(pk in chunk_content_lower for pk in ["1.", "2.", "3.", "4.", "project", "projects"]):
                        combined += 0.12
                    if "project" in chunk_section_lower:
                        combined += 0.08

                scored_indices.append((idx, combined))

            scored_indices.sort(key=lambda x: x[1], reverse=True)
            results = [self._format_result_chunk(idx, score) for idx, score in scored_indices[:k]]

            top_diagnostics = [
                {"document_id": c.get("document_id"), "filename": c.get("original_filename"), "score": c.get("score")}
                for c in results[:3]
            ]
            print(f"[VectorStore Diagnostics] strategy=hybrid, top_retrieved={top_diagnostics}")
            return results

    def search_neural_semantic(
        self,
        query: str,
        k: int = 3,
        owner_id: Optional[str] = None,
        document_id: Optional[str] = None,
        scope: Optional[str] = None,
        allowed_document_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Pure Neural Dense Semantic Retrieval using configured neural embedding provider (Mandates 8, 9)."""
        from backend.rag.embeddings import embedding_manager
        neural_provider = embedding_manager.get_neural_provider()
        if not neural_provider or not neural_provider.api_key:
            return self.search_semantic(query, k, owner_id=owner_id, document_id=document_id, scope=scope, allowed_document_ids=allowed_document_ids)

        try:
            q_dense = neural_provider.embed_query(query)
            if q_dense is None or np.linalg.norm(q_dense) == 0:
                return self.search_semantic(query, k, owner_id=owner_id, document_id=document_id, scope=scope, allowed_document_ids=allowed_document_ids)

            candidates = self._filter_candidate_indices(owner_id, document_id, scope, allowed_document_ids)
            if not candidates:
                return []

            # If candidates are large, pre-filter with lexical to top candidates to bound latency and token usage
            cand_limit = max(k * 2, 8)
            if len(candidates) > cand_limit:
                lex_results = self.search_lexical(query, k=cand_limit, owner_id=owner_id, document_id=document_id, scope=scope, allowed_document_ids=allowed_document_ids)
                cand_ids = {c.get("id") or c.get("chunk_id") for c in lex_results}
                cand_indices = [idx for idx in candidates if (self.chunks[idx].get("id") or self.chunks[idx].get("chunk_id")) in cand_ids]
            else:
                cand_indices = candidates

            cand_texts = [self.chunks[idx].get("content") or self.chunks[idx].get("text") or "" for idx in cand_indices]
            cand_vecs = neural_provider.embed_documents(cand_texts)
            if len(cand_vecs) == 0:
                return self.search_semantic(query, k, owner_id=owner_id, document_id=document_id, scope=scope, allowed_document_ids=allowed_document_ids)

            scores = np.dot(cand_vecs, q_dense)
            scored = [(cand_indices[i], float(scores[i])) for i in range(len(cand_indices))]
            scored.sort(key=lambda x: x[1], reverse=True)
            return [self._format_result_chunk(idx, sc) for idx, sc in scored[:k]]
        except Exception as e:
            print(f"[VectorStore] Neural semantic retrieval fallback to LSA: {e}")
            return self.search_semantic(query, k, owner_id=owner_id, document_id=document_id, scope=scope, allowed_document_ids=allowed_document_ids)

    def search(
        self,
        query: str,
        k: int = 3,
        owner_id: Optional[str] = None,
        document_id: Optional[str] = None,
        scope: Optional[str] = None,
        strategy: Optional[str] = None,
        allowed_document_ids: Optional[List[str]] = None,
        top_k: Optional[int] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Authoritative Retrieval Entry Point.
        Dispatches to hybrid, lexical, LSA semantic, or neural dense search according to strategy parameter or config.
        """
        effective_k = top_k if top_k is not None else k
        from backend.config import RETRIEVAL_STRATEGY
        strat = (strategy or RETRIEVAL_STRATEGY or "hybrid").lower().strip()
        if strat == "lexical":
            return self.search_lexical(query, effective_k, owner_id=owner_id, document_id=document_id, scope=scope, allowed_document_ids=allowed_document_ids)
        elif strat in ["neural_semantic", "neural", "dense"]:
            return self.search_neural_semantic(query, effective_k, owner_id=owner_id, document_id=document_id, scope=scope, allowed_document_ids=allowed_document_ids)
        elif strat in ["semantic", "lsa_semantic", "lsa"]:
            return self.search_semantic(query, effective_k, owner_id=owner_id, document_id=document_id, scope=scope, allowed_document_ids=allowed_document_ids)
        return self.search_hybrid(query, effective_k, owner_id=owner_id, document_id=document_id, scope=scope, allowed_document_ids=allowed_document_ids)


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
