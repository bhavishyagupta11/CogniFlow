"""
CogniFlow Destructive Application Data Reset Script
Safely and completely clears all application data:
- conversations
- messages
- conversation_documents
- documents
- document_chunks
- document_embeddings
- document_summaries
- Cloudflare R2 uploaded & extracted objects
- data/manifest.json -> []
- data/neural_embeddings_cache.json -> {}
- local uploads and extracted temporary files
- in-memory vector store

PRESERVES Supabase Auth / users table records.
"""

import sys
import os
import json
import shutil
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.config import MANIFEST_PATH, UPLOADS_DIR, EXTRACTED_DIR, DATA_DIR
from backend.services.db_service import db_service, PostgresDatabaseService
from backend.services.storage_service import storage_service, R2StorageService
from backend.rag.vector_store import vector_store


def reset_all_application_data():
    print("==================================================")
    print("COGNIFLOW COMPLETE APPLICATION DATA RESET")
    print("==================================================")

    # 1. Clear Database Tables
    print("\n[1/5] Resetting database application tables...")
    with db_service.get_connection() as conn:
        with conn.cursor() as cur:
            tables_to_clear = [
                "conversation_documents",
                "messages",
                "conversations",
                "document_summaries",
                "document_embeddings",
                "document_chunks",
                "documents",
            ]
            for table in tables_to_clear:
                cur.execute(f"DELETE FROM {table};")
                print(f"  [OK] Cleared table: {table}")

    # 2. Clear Cloudflare R2 Storage Objects
    print("\n[2/5] Cleaning Cloudflare R2 storage objects...")
    if isinstance(storage_service, R2StorageService):
        try:
            client = storage_service._get_client()
            bucket = storage_service.bucket_name
            paginator = client.get_paginator("list_objects_v2")
            deleted_count = 0
            for page in paginator.paginate(Bucket=bucket):
                objects = page.get("Contents", [])
                if objects:
                    delete_keys = [{"Key": obj["Key"]} for obj in objects]
                    client.delete_objects(Bucket=bucket, Delete={"Objects": delete_keys})
                    deleted_count += len(delete_keys)
            print(f"  [OK] Deleted {deleted_count} objects from R2 bucket '{bucket}'")
        except Exception as e:
            print(f"  [WARN] Note on R2 cleanup: {e}")
    else:
        print("  [OK] R2StorageService not active, local storage in use.")

    # 3. Clear Local Files & Manifest
    print("\n[3/5] Resetting local manifest and caches...")
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text("[]\n", encoding="utf-8")
    print(f"  [OK] Reset {MANIFEST_PATH} to []")

    cache_file = DATA_DIR / "neural_embeddings_cache.json"
    if cache_file.exists():
        cache_file.write_text("{}\n", encoding="utf-8")
        print(f"  [OK] Reset {cache_file} to {{}}")

    summary_cache_file = DATA_DIR / "summary_cache.json"
    if summary_cache_file.exists():
        summary_cache_file.write_text("{}\n", encoding="utf-8")
        print(f"  [OK] Reset {summary_cache_file} to {{}}")

    # Clean local uploads directory
    if UPLOADS_DIR.exists():
        for item in UPLOADS_DIR.iterdir():
            if item.is_file() and item.name != ".gitkeep":
                try:
                    item.unlink()
                except Exception:
                    pass
            elif item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
        print("  [OK] Cleaned local uploads directory")

    # Clean local extracted directory
    if EXTRACTED_DIR.exists():
        for item in EXTRACTED_DIR.iterdir():
            if item.is_file() and item.name != ".gitkeep":
                try:
                    item.unlink()
                except Exception:
                    pass
            elif item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
        print("  [OK] Cleaned local extracted directory")

    # 4. Clear In-Memory Vector Store
    print("\n[4/5] Clearing in-memory vector store...")
    vector_store.in_memory_docs.clear()
    vector_store.reload()
    print("  [OK] Vector store reloaded and empty")

    # 5. Direct DB Verification
    print("\n[5/5] Direct DB Count Verification:")
    counts = {}
    with db_service.get_connection() as conn:
        with conn.cursor() as cur:
            for table in [
                "documents",
                "document_chunks",
                "document_embeddings",
                "document_summaries",
                "conversation_documents",
                "conversations",
                "messages",
            ]:
                cur.execute(f"SELECT COUNT(*) FROM {table};")
                cnt = cur.fetchone()[0]
                counts[table] = cnt
                print(f"  - {table}: {cnt}")

    with db_service.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users;")
            user_cnt = cur.fetchone()[0]
            print(f"  - users (preserved): {user_cnt}")

    print("\n==================================================")
    if all(v == 0 for v in counts.values()):
        print("SUCCESS: All application data reset to ZERO.")
    else:
        print("WARNING: Some tables still have rows:", counts)
    print("==================================================")


if __name__ == "__main__":
    reset_all_application_data()
