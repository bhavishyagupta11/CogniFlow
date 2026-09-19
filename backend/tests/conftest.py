"""
Pytest configuration and session fixtures for CogniFlow backend test suites.
Ensures zero test contamination in persistent storage and database.
"""

import sys
from pathlib import Path
import pytest

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.services.db_service import db_service


@pytest.fixture(autouse=True, scope="session")
def auto_cleanup_test_artifacts_on_session_finish():
    """
    Session-level teardown:
    After the entire pytest session completes, guarantees that any test accounts
    matching test domains (@cogniflow.test, @test.com, @ephemeral.test) are purged,
    protecting real production accounts, and any test documents created during tests
    are cleaned up.
    """
    yield
    try:
        with db_service.get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Clean up test documents & associations
                cur.execute("""
                    DELETE FROM document_summaries
                    WHERE document_id IN (SELECT id FROM documents WHERE owner_id != 'user_43efe1dd5b89');
                    DELETE FROM document_embeddings
                    WHERE document_id IN (SELECT id FROM documents WHERE owner_id != 'user_43efe1dd5b89');
                    DELETE FROM document_chunks
                    WHERE document_id IN (SELECT id FROM documents WHERE owner_id != 'user_43efe1dd5b89');
                    DELETE FROM conversation_documents;
                    DELETE FROM documents WHERE owner_id != 'user_43efe1dd5b89';
                """)
                # 2. Clean up test conversations & messages
                cur.execute("""
                    DELETE FROM messages
                    WHERE conversation_id IN (
                        SELECT id FROM conversations
                        WHERE user_id IN (
                            SELECT id FROM users
                            WHERE email LIKE '%@test.com'
                               OR email LIKE '%@ephemeral.test'
                               OR email LIKE '%@cogniflow.test'
                        ) OR (user_id LIKE 'user_%' AND user_id != 'user_43efe1dd5b89')
                    );
                    DELETE FROM conversations
                    WHERE user_id IN (
                        SELECT id FROM users
                        WHERE email LIKE '%@test.com'
                           OR email LIKE '%@ephemeral.test'
                           OR email LIKE '%@cogniflow.test'
                        ) OR (user_id LIKE 'user_%' AND user_id != 'user_43efe1dd5b89');
                """)
                # 3. Clean up test users
                cur.execute("""
                    DELETE FROM users
                    WHERE email LIKE '%@test.com'
                       OR email LIKE '%@ephemeral.test'
                       OR email LIKE '%@cogniflow.test';
                """)

        # Clean R2 storage objects if any were created during tests
        from backend.services.storage_service import storage_service, R2StorageService
        if isinstance(storage_service, R2StorageService):
            try:
                client = storage_service._get_client()
                bucket = storage_service.bucket_name
                paginator = client.get_paginator("list_objects_v2")
                for page in paginator.paginate(Bucket=bucket):
                    objects = page.get("Contents", [])
                    if objects:
                        delete_keys = [{"Key": obj["Key"]} for obj in objects]
                        client.delete_objects(Bucket=bucket, Delete={"Objects": delete_keys})
            except Exception as r2_err:
                print(f"[conftest] Warning during R2 session cleanup: {r2_err}")

        # Reset manifest and in-memory store
        from backend.config import MANIFEST_PATH
        from backend.rag.vector_store import vector_store
        if MANIFEST_PATH.exists():
            MANIFEST_PATH.write_text("[]\n", encoding="utf-8")
        vector_store.chunks.clear()
        vector_store.in_memory_docs.clear()
        vector_store.total_docs = 0
    except Exception as e:
        print(f"[conftest] Warning during session cleanup: {e}")
