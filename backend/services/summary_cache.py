"""
CogniFlow Persistent Document Summary Cache
Supports hierarchical caching of full document summaries and individual batch summaries.
Keys by document ID, file hash/version, page range, and summarization configuration hash.
Invalidates automatically on document deletion or reindexing.
"""

import json
import hashlib
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

from backend.config import DATA_DIR

CACHE_DIR = DATA_DIR / "cache" / "summaries"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class SummaryCache:
    def __init__(self):
        self._in_memory: Dict[str, Dict[str, Any]] = {}
        self._batch_cache: Dict[str, str] = {}

    def _make_key(self, doc_id: str, doc_hash: str, page_range: str, config_hash: str) -> str:
        raw = f"{doc_id}:{doc_hash}:{page_range}:{config_hash}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _make_batch_key(self, doc_id: str, doc_hash: str, batch_id: str) -> str:
        raw = f"batch:{doc_id}:{doc_hash}:{batch_id}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get_summary(
        self,
        doc_id: str,
        doc_hash: str,
        page_range: str = "all",
        config_hash: str = "v1"
    ) -> Optional[Dict[str, Any]]:
        key = self._make_key(doc_id, doc_hash, page_range, config_hash)
        
        # 1. In-memory check (L1 cache)
        if key in self._in_memory:
            entry = self._in_memory[key]
            return entry.get("data")

        # 2. Database check (PostgreSQL / Supabase - Authoritative Persistence across restarts)
        try:
            from backend.services.db_service import db_service
            db_summary = db_service.get_summary(key)
            if db_summary:
                self._in_memory[key] = {"data": db_summary, "cached_at": time.time(), "doc_id": doc_id}
                return db_summary
        except Exception:
            pass

        # 3. Disk cache fallback
        disk_file = CACHE_DIR / f"{key}.json"
        if disk_file.exists():
            try:
                data = json.loads(disk_file.read_text(encoding="utf-8"))
                self._in_memory[key] = {"data": data, "cached_at": time.time(), "doc_id": doc_id}
                return data
            except Exception as e:
                print(f"[SummaryCache] Failed to read disk cache {disk_file}: {e}")

        return None

    def set_summary(
        self,
        doc_id: str,
        doc_hash: str,
        page_range: str,
        config_hash: str,
        data: Dict[str, Any]
    ) -> None:
        key = self._make_key(doc_id, doc_hash, page_range, config_hash)
        
        # 1. In-memory store
        self._in_memory[key] = {
            "doc_id": doc_id,
            "data": data,
            "cached_at": time.time()
        }

        # 2. Database persistent store (Survives Render restarts)
        try:
            from backend.services.db_service import db_service
            db_service.save_summary(key, doc_id, page_range, config_hash, data)
        except Exception as e:
            pass

        # 3. Disk store (for offline local development)
        disk_file = CACHE_DIR / f"{key}.json"
        try:
            payload = dict(data)
            payload["_cache_meta"] = {
                "doc_id": doc_id,
                "doc_hash": doc_hash,
                "page_range": page_range,
                "config_hash": config_hash,
                "cached_at": time.time()
            }
            disk_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as e:
            pass

    def get_batch_summary(self, doc_id: str, doc_hash: str, batch_id: str) -> Optional[str]:
        batch_key = self._make_batch_key(doc_id, doc_hash, batch_id)
        if batch_key in self._batch_cache:
            return self._batch_cache[batch_key]

        disk_file = CACHE_DIR / f"b_{batch_key}.txt"
        if disk_file.exists():
            try:
                content = disk_file.read_text(encoding="utf-8")
                self._batch_cache[batch_key] = content
                return content
            except Exception:
                pass
        return None

    def set_batch_summary(self, doc_id: str, doc_hash: str, batch_id: str, summary: str) -> None:
        batch_key = self._make_batch_key(doc_id, doc_hash, batch_id)
        self._batch_cache[batch_key] = summary

        disk_file = CACHE_DIR / f"b_{batch_key}.txt"
        try:
            disk_file.write_text(summary, encoding="utf-8")
        except Exception:
            pass

    def invalidate_document(self, doc_id: str) -> int:
        """Invalidates all cached summaries for a specific document ID across memory, DB, and disk."""
        invalidated = 0
        
        # 1. Invalidate in-memory
        to_del = [k for k, v in self._in_memory.items() if v.get("doc_id") == doc_id or v.get("data", {}).get("documentId") == doc_id]
        for k in to_del:
            self._in_memory.pop(k, None)
            invalidated += 1

        # 2. Invalidate database summaries
        try:
            from backend.services.db_service import db_service
            db_service.delete_summaries_for_document(doc_id)
        except Exception:
            pass

        # 3. Invalidate disk files
        if CACHE_DIR.exists():
            for f in CACHE_DIR.glob("*.json"):
                try:
                    meta = json.loads(f.read_text(encoding="utf-8")).get("_cache_meta", {})
                    if meta.get("doc_id") == doc_id:
                        f.unlink(missing_ok=True)
                        invalidated += 1
                except Exception:
                    pass

        return invalidated

    def clear(self) -> None:
        """Clears all in-memory and disk summary caches."""
        self._in_memory.clear()
        self._batch_cache.clear()
        if CACHE_DIR.exists():
            for f in CACHE_DIR.iterdir():
                if f.is_file():
                    try:
                        f.unlink(missing_ok=True)
                    except Exception:
                        pass


summary_cache = SummaryCache()
