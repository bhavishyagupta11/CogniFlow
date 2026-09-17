"""
CogniFlow Unified Object Storage Abstraction
Provides clean interfaces for local filesystem and Cloudflare R2 object storage.
Decouples application logic from hardcoded physical directory paths.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any, Union
import os
import mimetypes
import logging

from backend.config import (
    DATA_DIR,
    UPLOADS_DIR,
    EXTRACTED_DIR,
    STORAGE_BACKEND,
    R2_ACCOUNT_ID,
    R2_ACCESS_KEY_ID,
    R2_SECRET_ACCESS_KEY,
    R2_BUCKET_NAME,
    R2_ENDPOINT,
)

logger = logging.getLogger("cogniflow.storage_service")


class BaseStorageService(ABC):
    """Abstract Base Class for CogniFlow Object Storage."""

    @abstractmethod
    def put_object(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Stores object bytes at key and returns the normalized key."""
        pass

    @abstractmethod
    def get_object(self, key: str) -> bytes:
        """Retrieves raw bytes for key. Raises FileNotFoundError or KeyError if missing."""
        pass

    @abstractmethod
    def delete_object(self, key: str) -> bool:
        """Deletes object by key. Returns True if deleted or did not exist."""
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Checks whether object exists."""
        pass

    @abstractmethod
    def generate_presigned_url(self, key: str, expires_in_seconds: int = 900) -> str:
        """Generates a temporary signed URL for client download."""
        pass


class LocalStorageService(BaseStorageService):
    """
    Local filesystem implementation of BaseStorageService.
    Used for local development, offline operation, and automated regression testing.
    """

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or (DATA_DIR / "storage")
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, key: str) -> Path:
        clean_key = key.replace("\\", "/").lstrip("/")
        # Backwards-compatibility redirect for legacy upload/extracted paths
        if clean_key.startswith("uploads/"):
            fname = clean_key.split("/", 1)[1]
            legacy_p = UPLOADS_DIR / fname
            if legacy_p.exists():
                return legacy_p
        elif clean_key.startswith("extracted/"):
            fname = clean_key.split("/", 1)[1]
            legacy_p = EXTRACTED_DIR / fname
            if legacy_p.exists():
                return legacy_p

        target = self.base_dir / clean_key
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def put_object(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        path = self._resolve_path(key)
        path.write_bytes(data)
        return key

    def get_object(self, key: str) -> bytes:
        path = self._resolve_path(key)
        if not path.exists():
            raise FileNotFoundError(f"Object not found: {key}")
        return path.read_bytes()

    def delete_object(self, key: str) -> bool:
        path = self._resolve_path(key)
        if path.exists():
            try:
                path.unlink(missing_ok=True)
                return True
            except Exception as e:
                logger.error(f"[LocalStorage] Failed to delete {key}: {e}")
                return False
        return True

    def exists(self, key: str) -> bool:
        path = self._resolve_path(key)
        return path.exists()

    def generate_presigned_url(self, key: str, expires_in_seconds: int = 900) -> str:
        # For local dev, returns local API route that streams file with auth
        clean_key = key.replace("\\", "/").lstrip("/")
        return f"/api/documents/storage/local?key={clean_key}"


class R2StorageService(BaseStorageService):
    """
    Cloudflare R2 Object Storage Service via S3 SigV4 API.
    Private bucket enforcement, presigned GET URLs, zero egress cost.
    """

    def __init__(
        self,
        account_id: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        bucket_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
    ):
        self.account_id = account_id or R2_ACCOUNT_ID
        self.access_key_id = access_key_id or R2_ACCESS_KEY_ID
        self.secret_access_key = secret_access_key or R2_SECRET_ACCESS_KEY
        self.bucket_name = bucket_name or R2_BUCKET_NAME or "cogniflow-storage"
        
        if endpoint_url:
            self.endpoint_url = endpoint_url
        elif self.account_id:
            self.endpoint_url = f"https://{self.account_id}.r2.cloudflarestorage.com"
        else:
            self.endpoint_url = R2_ENDPOINT or ""

        self._client = None

    def _get_client(self):
        if self._client is None:
            import boto3
            from botocore.config import Config

            if not (self.access_key_id and self.secret_access_key and self.endpoint_url):
                raise RuntimeError("Cloudflare R2 credentials or endpoint not fully configured.")

            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                region_name="auto",
                config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
            )
        return self._client

    def put_object(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        client = self._get_client()
        clean_key = key.replace("\\", "/").lstrip("/")
        client.put_object(
            Bucket=self.bucket_name,
            Key=clean_key,
            Body=data,
            ContentType=content_type,
        )
        return clean_key

    def get_object(self, key: str) -> bytes:
        client = self._get_client()
        clean_key = key.replace("\\", "/").lstrip("/")
        try:
            res = client.get_object(Bucket=self.bucket_name, Key=clean_key)
            return res["Body"].read()
        except Exception as e:
            logger.error(f"[R2Storage] get_object failed for {clean_key}: {e}")
            raise FileNotFoundError(f"Object not found in R2: {clean_key}") from e

    def delete_object(self, key: str) -> bool:
        client = self._get_client()
        clean_key = key.replace("\\", "/").lstrip("/")
        try:
            client.delete_object(Bucket=self.bucket_name, Key=clean_key)
            return True
        except Exception as e:
            logger.error(f"[R2Storage] delete_object failed for {clean_key}: {e}")
            return False

    def exists(self, key: str) -> bool:
        client = self._get_client()
        clean_key = key.replace("\\", "/").lstrip("/")
        try:
            client.head_object(Bucket=self.bucket_name, Key=clean_key)
            return True
        except Exception:
            return False

    def generate_presigned_url(self, key: str, expires_in_seconds: int = 900) -> str:
        client = self._get_client()
        clean_key = key.replace("\\", "/").lstrip("/")
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket_name, "Key": clean_key},
            ExpiresIn=expires_in_seconds,
        )


def create_storage_service() -> BaseStorageService:
    """Factory creating the appropriate storage service based on environment configuration."""
    backend_choice = STORAGE_BACKEND.lower().strip()
    r2_ready = bool(R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and (R2_ACCOUNT_ID or R2_ENDPOINT))
    
    if backend_choice == "r2" or (backend_choice != "local" and r2_ready):
        try:
            return R2StorageService()
        except Exception as e:
            logger.warning(f"[Storage] Failed to initialize R2StorageService ({e}); falling back to LocalStorageService.")
            return LocalStorageService()
    return LocalStorageService()


# Global storage service gateway
storage_service = create_storage_service()
