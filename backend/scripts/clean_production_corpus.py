"""
Clean Production Corpus Script
Removes all unwanted development, test, and demo documents from:
- Supabase documents
- Supabase document_chunks
- Supabase document_embeddings
- Supabase document_summaries
- Cloudflare R2 original objects (uploads/{doc_id}/original)
- Cloudflare R2 extracted objects (extracted/{doc_id}/pages.json)
- data/manifest.json
- in-memory vector store

Ensures production environment starts with Documents = 0, Chunks = 0.
"""

import os
import sys
import json
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.config import MANIFEST_PATH, DATA_DIR, UPLOADS_DIR, EXTRACTED_DIR
from backend.services.db_service import db_service, get_db_connection
from backend.services.storage_service import storage_service
from backend.rag.vector_store import vector_store

TARGET_PATTERNS = [
    "Data Structures Full Notes",
    "Bhavishya_Gupta_Resume",
    "Vinit Khandelwal Projects",
    "Lecture01&02-CS-IT449",
    "test_idempotent_del",
    "public_whitepaper",
    "public_handbook",
    "citation_spec",
    "doc1_facts",
    "doc2_multisection",
    "doc3_retrieval",
    "doc4_multidoc",
    "doc5_conflict",
    "doc6_unanswerable",
]


def clean_corpus():
    print("[CleanCorpus] Inspecting current database documents...")
    all_docs = db_service.list_documents()
    print(f"[CleanCorpus] Found {len(all_docs)} documents in database.")

    to_delete = []
    for d in all_docs:
        doc_id = d.get("id") or d.get("document_id")
        orig_name = d.get("original_filename") or d.get("originalFilename") or ""
        # Match test/dev documents or system_public
        is_match = any(pattern.lower() in orig_name.lower() for pattern in TARGET_PATTERNS)
        if is_match or d.get("owner_id") in ["system_public", "dev-user", "public"]:
            to_delete.append((doc_id, orig_name))

    print(f"[CleanCorpus] Identified {len(to_delete)} documents for complete removal.")

    for doc_id, orig_name in to_delete:
        print(f"  -> Deleting {doc_id} ({orig_name})...")
        # 1. Delete from Supabase / DB
        try:
            db_service.delete_document(doc_id)
        except Exception as e:
            print(f"     DB delete error: {e}")

        # 2. Delete from R2 storage
        try:
            storage_service.delete_object(f"uploads/{doc_id}/original")
            storage_service.delete_object(f"extracted/{doc_id}/pages.json")
        except Exception as e:
            print(f"     Storage delete error: {e}")

        # 3. Delete local disk files
        for p in [
            UPLOADS_DIR / f"{doc_id}.pdf",
            UPLOADS_DIR / f"{doc_id}.txt",
            EXTRACTED_DIR / f"{doc_id}.json"
        ]:
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass

    # Also wipe all orphaned chunks, embeddings, and summaries
    with get_db_connection() as conn:
        cur = conn.cursor() if hasattr(conn, "cursor") else conn
        try:
            cur.execute("DELETE FROM document_chunks")
            cur.execute("DELETE FROM document_embeddings")
            cur.execute("DELETE FROM document_summaries")
            if hasattr(conn, "commit"):
                conn.commit()
            print("[CleanCorpus] Cleaned all chunks, embeddings, and summaries.")
        except Exception as e:
            print(f"[CleanCorpus] Error cleaning chunk tables: {e}")

    # 4. Clean data/manifest.json
    try:
        MANIFEST_PATH.write_text("[]", encoding="utf-8")
        print("[CleanCorpus] Reset manifest.json to empty [].")
    except Exception as e:
        print(f"[CleanCorpus] Manifest cleanup error: {e}")

    # 5. Reset and rebuild vector store
    vector_store.in_memory_docs.clear()
    vector_store._rebuild()
    stats = vector_store.index_stats()
    print(f"[CleanCorpus] Vector store reset. Total chunks: {stats['total_chunks']}, Total documents: {stats['total_documents']}.")

    remaining_docs = db_service.list_documents()
    print(f"[CleanCorpus] Verification complete. Database documents remaining: {len(remaining_docs)}.")


if __name__ == "__main__":
    clean_corpus()
