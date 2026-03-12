"""
storage.py — Cloud storage abstraction with Google Cloud Storage backend.

Uses gcloud-aio-storage for fully native async I/O — no run_in_executor,
no thread pool, no Windows ProactorEventLoop deadlocks.

Install:
    pip install gcloud-aio-storage

Usage:
    from storage import get_storage_backend

    storage = get_storage_backend()
    url = await storage.upload_image(filename="abc.png", data=img_bytes)
    url = await storage.upload_markdown(filename="post.md", content="# Hello")
    exists = await storage.exists("images/abc.png")
"""

from __future__ import annotations

import abc
import os
import re
import unicodedata
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def slugify(text: str, max_len: int = 80) -> str:
    """
    Convert arbitrary text to a safe, lowercase, hyphen-separated filename.
    'How LangGraph Works (Part 1/2)!' → 'how-langgraph-works-part-1-2'
    """
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    return text[:max_len].strip("-")


# ─────────────────────────────────────────────────────────────────────────────
# Abstract interface
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
        """Release the underlying HTTP session. Call when the app shuts down."""


# ─────────────────────────────────────────────────────────────────────────────
# Google Cloud Storage — gcloud-aio-storage (fully async, no threads)
# ─────────────────────────────────────────────────────────────────────────────

class GCSBackend(StorageBackend):
    """
    Requires:
        pip install gcloud-aio-storage

    Env vars:
        GCS_BUCKET_NAME               — bucket name (required)
        GOOGLE_APPLICATION_CREDENTIALS — path to service-account JSON
                                         (not needed on GCP with Workload Identity)
    """
    

    IMAGE_PREFIX    = "images/"
    MARKDOWN_PREFIX = "blogs/"

    def __init__(self, bucket_name: Optional[str] = None) -> None:
        self._bucket_name = bucket_name or os.environ["GCS_BUCKET_NAME"]
        
        self._storage = None

  

    async def _get_storage(self):
        """Return (and lazily create) the gcloud-aio Storage instance."""
        if self._storage is None:
            from gcloud.aio.storage import Storage  # type: ignore
            self._storage = Storage(
                service_file=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
            )
        return self._storage

  

    async def upload_image(
        self,
        filename: str,
        data: bytes,
        content_type: str = "image/png",
    ) -> str:
        blob_name = f"{self.IMAGE_PREFIX}{filename}"
        await self._upload(blob_name, data, content_type)
        return await self.public_url(blob_name)

    async def upload_markdown(self, filename: str, content: str) -> str:
        blob_name = f"{self.MARKDOWN_PREFIX}{filename}"
        await self._upload(
            blob_name,
            content.encode("utf-8"),
            "text/markdown; charset=utf-8",
        )
        return await self.public_url(blob_name)

    async def exists(self, blob_name: str) -> bool:
        storage = await self._get_storage()
        try:
            await storage.download_metadata(self._bucket_name, blob_name)
            return True
        except Exception:
           
            return False

    async def public_url(self, blob_name: str) -> str:
        return (
            f"https://storage.googleapis.com"
            f"/{self._bucket_name}/{blob_name}"
        )

    async def close(self) -> None:
        if self._storage is not None:
            await self._storage.close()
            self._storage = None

 
    async def _upload(self, blob_name: str, data: bytes, content_type: str) -> None:
        print("Uploading object:", blob_name)
        storage = await self._get_storage()
        await storage.upload(
            self._bucket_name,
            blob_name,
            data
           
        )
        print("Upload complete:", blob_name)


_backend: Optional[GCSBackend] = None


def get_storage_backend() -> GCSBackend:
    """
    Returns the process-level GCSBackend singleton.
    Hook storage.close() into your FastAPI shutdown event to drain the session.
    """
    
    global _backend
    if _backend is None:
        _backend = GCSBackend()
    return _backend