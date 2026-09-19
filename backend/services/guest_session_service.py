"""
Guest Session Service for CogniFlow
Provides isolated, temporary in-memory session state for guest visitors.
Guest session identifiers are strictly SERVER-ISSUED and validated.
Guests can chat and upload documents with complete privacy and isolation,
without writing unauthenticated or temporary data to durable database tables.
"""

import time
import secrets
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class GuestSession:
    session_id: str
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    conversations: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    documents: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    chunks: List[Dict[str, Any]] = field(default_factory=list)
    migrated: bool = False

    def touch(self) -> None:
        self.last_active = time.time()


class GuestSessionService:
    def __init__(self):
        self._lock = threading.RLock()
        self._sessions: Dict[str, GuestSession] = {}

    def create_server_session(self) -> GuestSession:
        """
        Server-authoritative creation of an opaque, cryptographically random guest session.
        Never relies on client-chosen IDs.
        """
        with self._lock:
            token = f"guest_{secrets.token_urlsafe(24)}"
            session = GuestSession(session_id=token)
            self._sessions[token] = session
            return session

    def resolve_valid_session(self, candidate_id: Optional[str]) -> GuestSession:
        """
        Validates client-provided session token against active server-issued sessions.
        If the candidate token does NOT map to an active session (or was already migrated),
        an arbitrary client ID is NEVER adopted. Instead, a new server-issued session is created.
        """
        with self._lock:
            if candidate_id and candidate_id in self._sessions:
                session = self._sessions[candidate_id]
                if not session.migrated:
                    session.touch()
                    return session
            # Client token was missing, invalid, forged, or already migrated; issue a new server-authoritative session
            return self.create_server_session()

    def get_session(self, session_id: Optional[str]) -> Optional[GuestSession]:
        if not session_id:
            return None
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                if session.migrated:
                    return None
                session.touch()
            return session

    def is_valid_session(self, session_id: Optional[str]) -> bool:
        if not session_id:
            return False
        with self._lock:
            session = self._sessions.get(session_id)
            return bool(session and not session.migrated)

    def mark_migrated(self, session_id: str) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.migrated = True
                session.conversations.clear()
                session.documents.clear()
                session.chunks.clear()

    # Conversations
    def save_conversation(
        self,
        session_id: str,
        conv_id: str,
        title: str,
        mode: str = "adaptive_rag"
    ) -> Dict[str, Any]:
        with self._lock:
            session = self.get_session(session_id)
            if not session:
                session = self.create_server_session()
                session_id = session.session_id

            now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            if conv_id not in session.conversations:
                session.conversations[conv_id] = {
                    "id": conv_id,
                    "title": title,
                    "mode": mode,
                    "created_at": now_iso,
                    "updated_at": now_iso,
                    "messages": [],
                    "sources": []
                }
            else:
                session.conversations[conv_id]["title"] = title
                session.conversations[conv_id]["updated_at"] = now_iso
                if "sources" not in session.conversations[conv_id]:
                    session.conversations[conv_id]["sources"] = []
            return session.conversations[conv_id]

    def get_conversations(self, session_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            session = self.get_session(session_id)
            if not session:
                return []
            convs = list(session.conversations.values())
            result = []
            for c in convs:
                msgs = c.get("messages", [])
                last_preview = msgs[-1]["content"][:60] if msgs else ""
                result.append({
                    "id": c["id"],
                    "title": c["title"],
                    "mode": c.get("mode", "adaptive_rag"),
                    "createdAt": c.get("created_at"),
                    "updatedAt": c.get("updated_at"),
                    "messageCount": len(msgs),
                    "lastMessagePreview": last_preview,
                    "sources": list(c.get("sources", []))
                })
            return sorted(result, key=lambda x: x.get("updatedAt", ""), reverse=True)

    def get_conversation(self, session_id: str, conv_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            session = self.get_session(session_id)
            if not session:
                return None
            conv = session.conversations.get(conv_id)
            if not conv:
                return None
            conv_copy = dict(conv)
            conv_copy["sources"] = list(conv.get("sources", []))
            conv_copy["source_documents"] = self.list_conversation_source_documents(session_id, conv_id)
            return conv_copy

    def delete_conversation(self, session_id: str, conv_id: str) -> bool:
        with self._lock:
            session = self.get_session(session_id)
            if not session or conv_id not in session.conversations:
                return False
            del session.conversations[conv_id]
            return True

    # Conversation Sources
    def get_conversation_sources(self, session_id: str, conv_id: str) -> List[str]:
        with self._lock:
            session = self.get_session(session_id)
            if not session or conv_id not in session.conversations:
                return []
            return list(session.conversations[conv_id].get("sources", []))

    def attach_conversation_source(self, session_id: str, conv_id: str, doc_id: str) -> None:
        with self._lock:
            session = self.get_session(session_id)
            if not session:
                session = self.create_server_session()
                session_id = session.session_id
            if conv_id not in session.conversations:
                self.save_conversation(session_id, conv_id, "New Mission")
            sources = session.conversations[conv_id].setdefault("sources", [])
            if doc_id not in sources:
                sources.append(doc_id)
            session.conversations[conv_id]["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def detach_conversation_source(self, session_id: str, conv_id: str, doc_id: str) -> None:
        with self._lock:
            session = self.get_session(session_id)
            if not session or conv_id not in session.conversations:
                return
            sources = session.conversations[conv_id].get("sources", [])
            if doc_id in sources:
                sources.remove(doc_id)
            session.conversations[conv_id]["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def list_conversation_source_documents(self, session_id: str, conv_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            session = self.get_session(session_id)
            if not session or conv_id not in session.conversations:
                return []
            doc_ids = session.conversations[conv_id].get("sources", [])
            res = []
            for did in doc_ids:
                if did in session.documents:
                    d = dict(session.documents[did])
                    d.pop("raw_bytes", None)
                    d.pop("pages", None)
                    d.pop("chunks", None)
                    res.append(d)
            return res

    # Messages
    def save_message(
        self,
        session_id: str,
        conv_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        msg_id: Optional[str] = None
    ) -> Dict[str, Any]:
        with self._lock:
            session = self.get_session(session_id)
            if not session:
                session = self.create_server_session()
                session_id = session.session_id

            if conv_id not in session.conversations:
                title = content[:45].strip() if role == "user" else "New Mission"
                self.save_conversation(session_id, conv_id, title)

            now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            msg = {
                "id": msg_id or f"msg_{secrets.token_hex(8)}",
                "role": role,
                "content": content,
                "metadata": metadata or {},
                "created_at": now_iso
            }
            session.conversations[conv_id]["messages"].append(msg)
            session.conversations[conv_id]["updated_at"] = now_iso
            return msg

    # Documents
    def add_document(
        self,
        session_id: str,
        doc_dict: Dict[str, Any],
        pages: List[Dict[str, Any]],
        chunks: List[Dict[str, Any]],
        raw_bytes: Optional[bytes] = None
    ) -> None:
        with self._lock:
            session = self.get_session(session_id)
            if not session:
                session = self.create_server_session()
                session_id = session.session_id

            doc_id = doc_dict.get("id") or doc_dict.get("document_id")
            doc_copy = dict(doc_dict)
            doc_copy["pages"] = pages
            doc_copy["chunks"] = chunks
            if raw_bytes is not None:
                doc_copy["raw_bytes"] = raw_bytes
            session.documents[doc_id] = doc_copy
            session.chunks.extend(chunks)

    def get_documents(self, session_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            session = self.get_session(session_id)
            if not session:
                return []
            docs = []
            for d in session.documents.values():
                doc_copy = dict(d)
                doc_copy.pop("raw_bytes", None)
                doc_copy.pop("pages", None)
                doc_copy.pop("chunks", None)
                docs.append(doc_copy)
            return docs

    def get_document(self, session_id: str, doc_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            session = self.get_session(session_id)
            if not session:
                return None
            return session.documents.get(doc_id)

    def delete_document(self, session_id: str, doc_id: str) -> bool:
        with self._lock:
            session = self.get_session(session_id)
            if not session or doc_id not in session.documents:
                return False
            del session.documents[doc_id]
            session.chunks = [c for c in session.chunks if (c.get("documentId") or c.get("document_id")) != doc_id]
            for c in session.conversations.values():
                sources = c.get("sources", [])
                if doc_id in sources:
                    sources.remove(doc_id)
            return True

    def find_document_any_session(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Looks up a document across all active guest sessions.
        Returns the doc dict if found, or None.
        Used for access control to distinguish 403 (unauthorized cross-guest access) from 404.
        """
        with self._lock:
            for s in self._sessions.values():
                if not s.migrated and doc_id in s.documents:
                    return s.documents[doc_id]
            return None

    def get_document_pages(self, session_id: str, doc_id: str) -> Optional[List[Dict[str, Any]]]:
        with self._lock:
            session = self.get_session(session_id)
            if not session or doc_id not in session.documents:
                return None
            return session.documents[doc_id].get("pages")

    def find_document_pages_any_session(self, doc_id: str) -> Optional[List[Dict[str, Any]]]:
        with self._lock:
            for s in self._sessions.values():
                if not s.migrated and doc_id in s.documents:
                    return s.documents[doc_id].get("pages")
            return None

    def cleanup_expired_sessions(self, max_age_seconds: int = 7200) -> int:
        now = time.time()
        expired_ids = []
        with self._lock:
            for s_id, s in self._sessions.items():
                if now - s.last_active > max_age_seconds:
                    expired_ids.append(s_id)
            for s_id in expired_ids:
                del self._sessions[s_id]
        return len(expired_ids)


# Global singleton instance
guest_session_service = GuestSessionService()
