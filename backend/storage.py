"""Supabase Storage wrapper.

Talks to the Supabase Storage REST API directly using ``httpx``. No
S3 client is required and there is no Cloudflare/Workers runtime
dependency.

Required environment variables:
    SUPABASE_URL                 - e.g. https://xxxx.supabase.co
    SUPABASE_SERVICE_ROLE_KEY    - service role key (server-side only)
    SUPABASE_STORAGE_BUCKET      - bucket name (default: ``gems-luxury``)
"""
from __future__ import annotations

import logging
import os
import uuid

import httpx

logger = logging.getLogger(__name__)

APP_NAME = os.environ.get("APP_NAME", "gemsluxury")
BUCKET = os.environ.get("SUPABASE_STORAGE_BUCKET", "gems-luxury")


def _supabase_url() -> str:
    url = os.environ.get("SUPABASE_URL")
    if not url:
        raise RuntimeError("SUPABASE_URL not set")
    return url.rstrip("/")


def _service_key() -> str:
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY not set")
    return key


def _headers() -> dict[str, str]:
    key = _service_key()
    return {"Authorization": f"Bearer {key}", "apikey": key}


def init_storage(*_args, **_kwargs) -> None:
    """No-op kept for backwards compatibility with the previous R2 wrapper."""
    return None


def put_object(path: str, data: bytes, content_type: str) -> dict:
    """Upload an object to Supabase Storage."""
    url = f"{_supabase_url()}/storage/v1/object/{BUCKET}/{path}"
    headers = {
        **_headers(),
        "Content-Type": content_type or "application/octet-stream",
        # Allow overwriting an existing object at the same path
        "x-upsert": "true",
    }
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(url, content=data, headers=headers)
        if resp.status_code >= 300:
            logger.error("supabase upload failed %s: %s", resp.status_code, resp.text)
            resp.raise_for_status()
    return {"path": path, "size": len(data)}


def get_object(path: str) -> tuple[bytes, str]:
    """Download an object from Supabase Storage."""
    url = f"{_supabase_url()}/storage/v1/object/{BUCKET}/{path}"
    with httpx.Client(timeout=60.0) as client:
        resp = client.get(url, headers=_headers())
        if resp.status_code == 404:
            raise KeyError(f"Object not found: {path}")
        if resp.status_code >= 300:
            logger.error("supabase download failed %s: %s", resp.status_code, resp.text)
            resp.raise_for_status()
        ct = resp.headers.get("content-type", "application/octet-stream")
        return resp.content, ct


def build_path(user_id: str, filename: str, kind: str = "uploads") -> str:
    """Build a deterministic, namespaced storage path."""
    ext = filename.split(".")[-1].lower() if filename and "." in filename else "bin"
    if ext not in {"jpg", "jpeg", "png", "gif", "webp"}:
        ext = "bin"
    return f"{APP_NAME}/{kind}/{user_id}/{uuid.uuid4()}.{ext}"
