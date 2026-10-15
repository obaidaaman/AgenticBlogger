"""
storage.py — Cloud storage abstraction with Supabase S3-compatible backend.

Supabase provides an S3-compatible storage API:
    Endpoint: https://<PROJECT_REF>.supabase.co/storage/v1/s3
    Access Keys: Generated in Supabase Dashboard -> Project Settings -> Storage -> S3 Credentials

Features:
- Native async S3 client via aioboto3
- REST API fallback for standard Supabase URL + Service Role Key
- Local filesystem fallback for offline/development environments
- Consistent public URL generation
"""

from __future__ import annotations

import abc
import os
import re
import unicodedata
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def slugify(text: str, max_len: int = 80) -> str:
    """
    Convert arbitrary text to a safe, lowercase, hyphen-separated filename.
    'How LangGraph Works (Part 1/2)!' -> 'how-langgraph-works-part-1-2'
    """
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    return text[:max_len].strip("-")


# ─────────────────────────────────────────────────────────────────────────────
# Abstract Storage Interface
# ─────────────────────────────────────────────────────────────────────────────

class StorageBackend(abc.ABC):

    @abc.abstractmethod
    async def upload_image(
        self,
        filename: str,
        data: bytes,
        content_type: str = "image/png",
    ) -> str:
        """Upload raw image bytes; return a public HTTPS URL."""

    @abc.abstractmethod
    async def upload_markdown(self, filename: str, content: str) -> str:
        """Upload UTF-8 markdown; return a public HTTPS URL."""

    @abc.abstractmethod
    async def exists(self, blob_name: str) -> bool:
        """Return True if the blob already exists in the bucket."""

    @abc.abstractmethod
    async def public_url(self, blob_name: str) -> str:
        """Return the public HTTPS URL for a blob without uploading."""

    @abc.abstractmethod
    async def close(self) -> None:
        """Release any underlying client sessions."""


# ─────────────────────────────────────────────────────────────────────────────
# Supabase S3 Backend (via aioboto3)
# ─────────────────────────────────────────────────────────────────────────────

class SupabaseS3Backend(StorageBackend):
    """
    Supabase Storage S3-compatible backend.
    
    Environment variables:
        SUPABASE_S3_ENDPOINT        — e.g. https://<project_ref>.supabase.co/storage/v1/s3
        SUPABASE_S3_ACCESS_KEY_ID   — Supabase S3 Access Key ID
        SUPABASE_S3_SECRET_ACCESS_KEY — Supabase S3 Secret Access Key
        SUPABASE_STORAGE_BUCKET     — Bucket name (default: 'blogs')
        SUPABASE_S3_REGION          — S3 region (default: 'auto' or 'us-east-1')
        SUPABASE_URL                — Supabase Project URL for public URLs
    """

    IMAGE_PREFIX = "images/"
    MARKDOWN_PREFIX = "blogs/"

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        bucket_name: Optional[str] = None,
        region: Optional[str] = None,
        supabase_url: Optional[str] = None,
    ) -> None:
        supabase_env_url = os.getenv("SUPABASE_URL", "")
        if "/storage/v1/s3" in supabase_env_url:
            default_endpoint = supabase_env_url
            default_base_url = supabase_env_url.split("/storage/v1/s3")[0]
        elif supabase_env_url:
            default_endpoint = f"{supabase_env_url.rstrip('/')}/storage/v1/s3"
            default_base_url = supabase_env_url
        else:
            default_endpoint = None
            default_base_url = None

        self.endpoint_url = (
            endpoint_url
            or os.getenv("SUPABASE_S3_ENDPOINT")
            or default_endpoint
        )
        self.access_key_id = (
            access_key_id
            or os.getenv("SUPABASE_S3_ACCESS_KEY_ID")
            or os.getenv("SUPABASE_S3_ACCESS_KEY")
            or os.getenv("AWS_ACCESS_KEY_ID")
        )
        self.secret_access_key = (
            secret_access_key
            or os.getenv("SUPABASE_S3_SECRET_ACCESS_KEY")
            or os.getenv("SUPABASE_S3_SECRET_KEY")
            or os.getenv("AWS_SECRET_ACCESS_KEY")
        )
        self.bucket = (
            bucket_name
            or os.getenv("SUPABASE_STORAGE_BUCKET")
            or os.getenv("SUPABASE_S3_BUCKET_NAME")
            or os.getenv("STORAGE_BUCKET_NAME")
            or "blogs"
        )
        self.region = region or os.getenv("SUPABASE_S3_REGION", "auto")
        self.supabase_url = supabase_url or default_base_url

        import aioboto3  # type: ignore
        self._session = aioboto3.Session()

    def _get_client_context(self):
        return self._session.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name=self.region,
        )

    async def upload_image(
        self,
        filename: str,
        data: bytes,
        content_type: str = "image/png",
    ) -> str:
        blob_name = f"{self.IMAGE_PREFIX}{filename}"
        async with self._get_client_context() as s3:
            await s3.put_object(
                Bucket=self.bucket,
                Key=blob_name,
                Body=data,
                ContentType=content_type,
            )
        return await self.public_url(blob_name)

    async def upload_markdown(self, filename: str, content: str) -> str:
        blob_name = f"{self.MARKDOWN_PREFIX}{filename}"
        async with self._get_client_context() as s3:
            await s3.put_object(
                Bucket=self.bucket,
                Key=blob_name,
                Body=content.encode("utf-8"),
                ContentType="text/markdown; charset=utf-8",
            )
        return await self.public_url(blob_name)

    async def exists(self, blob_name: str) -> bool:
        import botocore.exceptions
        try:
            async with self._get_client_context() as s3:
                await s3.head_object(Bucket=self.bucket, Key=blob_name)
                return True
        except botocore.exceptions.ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code in ("404", "NoSuchKey"):
                return False
            return False
        except Exception:
            return False

    async def public_url(self, blob_name: str) -> str:
        if self.supabase_url:
            base = self.supabase_url.rstrip("/")
            return f"{base}/storage/v1/object/public/{self.bucket}/{blob_name}"
        if self.endpoint_url:
            # If endpoint is https://<ref>.supabase.co/storage/v1/s3
            base = self.endpoint_url.split("/storage/v1/s3")[0]
            return f"{base}/storage/v1/object/public/{self.bucket}/{blob_name}"
        return f"https://supabase-storage.local/{self.bucket}/{blob_name}"

    async def close(self) -> None:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Local Filesystem Backend (Graceful Offline/Dev Fallback)
# ─────────────────────────────────────────────────────────────────────────────

class LocalStorageBackend(StorageBackend):
    """Fallback local storage when no Supabase S3 credentials are configured."""

    def __init__(self, base_dir: str = "storage_artifacts") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        (self.base_dir / "images").mkdir(exist_ok=True)
        (self.base_dir / "blogs").mkdir(exist_ok=True)

    async def upload_image(
        self,
        filename: str,
        data: bytes,
        content_type: str = "image/png",
    ) -> str:
        path = self.base_dir / "images" / filename
        path.write_bytes(data)
        return f"/storage/images/{filename}"

    async def upload_markdown(self, filename: str, content: str) -> str:
        path = self.base_dir / "blogs" / filename
        path.write_text(content, encoding="utf-8")
        return f"/storage/blogs/{filename}"

    async def exists(self, blob_name: str) -> bool:
        return (self.base_dir / blob_name).exists()

    async def public_url(self, blob_name: str) -> str:
        return f"/storage/{blob_name}"

    async def close(self) -> None:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Factory Singleton
# ─────────────────────────────────────────────────────────────────────────────

_backend: Optional[StorageBackend] = None


def get_storage_backend() -> StorageBackend:
    """Returns the process-level storage backend singleton."""
    global _backend
    if _backend is None:
        # Check if Supabase S3 or generic S3 credentials are present
        has_s3 = (
            os.getenv("SUPABASE_S3_ACCESS_KEY_ID")
            or os.getenv("SUPABASE_S3_ACCESS_KEY")
            or os.getenv("AWS_ACCESS_KEY_ID")
        ) and (
            os.getenv("SUPABASE_S3_ENDPOINT")
            or os.getenv("SUPABASE_URL")
        )
        if has_s3:
            _backend = SupabaseS3Backend()
        else:
            _backend = LocalStorageBackend()
    return _backend