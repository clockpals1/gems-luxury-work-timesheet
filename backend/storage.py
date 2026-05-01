"""Storage adapter — Cloudflare R2 (preferred) with Supabase Storage fallback.

Cloudflare R2 (S3-compatible, generous free tier):
    R2_ACCOUNT_ID        - Cloudflare account ID
    R2_ACCESS_KEY_ID     - R2 API token access key ID
    R2_SECRET_ACCESS_KEY - R2 API token secret
    R2_BUCKET            - bucket name (default: gems-luxury)
    R2_PUBLIC_URL        - optional public bucket base URL for direct image links

Supabase Storage (fallback when R2 env vars are absent):
    SUPABASE_URL                 - e.g. https://xxxx.supabase.co
    SUPABASE_SERVICE_ROLE_KEY    - service role key (server-side only)
    SUPABASE_STORAGE_BUCKET      - bucket name (default: gems-luxury)
"""
from __future__ import annotations

import logging
import os
import uuid

import httpx

logger = logging.getLogger(__name__)

APP_NAME = os.environ.get("APP_NAME", "gemsluxury")
_SB_BUCKET = os.environ.get("SUPABASE_STORAGE_BUCKET", "gems-luxury")


# ---------------------------------------------------------------------------
# R2 helpers
# ---------------------------------------------------------------------------

def _use_r2() -> bool:
    return bool(
        os.environ.get("R2_ACCOUNT_ID")
        and os.environ.get("R2_ACCESS_KEY_ID")
        and os.environ.get("R2_SECRET_ACCESS_KEY")
    )


def _r2_client():
    try:
        import boto3
        from botocore.config import Config
    except ImportError as e:
        raise RuntimeError("boto3 not installed — add it to requirements.txt") from e
    account_id = os.environ["R2_ACCOUNT_ID"]
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def _r2_bucket() -> str:
    return os.environ.get("R2_BUCKET", "gems-luxury-images")


# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------

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


def _sb_headers() -> dict[str, str]:
    key = _service_key()
    return {"Authorization": f"Bearer {key}", "apikey": key}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_storage(*_args, **_kwargs) -> None:
    """No-op kept for backwards compatibility."""
    return None


def put_object(path: str, data: bytes, content_type: str) -> dict:
    """Upload an object. Uses R2 if configured, otherwise Supabase Storage."""
    if _use_r2():
        client = _r2_client()
        client.put_object(
            Bucket=_r2_bucket(),
            Key=path,
            Body=data,
            ContentType=content_type or "application/octet-stream",
        )
        logger.info("r2 upload ok: %s (%d bytes)", path, len(data))
        return {"path": path, "size": len(data)}

    url = f"{_supabase_url()}/storage/v1/object/{_SB_BUCKET}/{path}"
    headers = {
        **_sb_headers(),
        "Content-Type": content_type or "application/octet-stream",
        "x-upsert": "true",
    }
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(url, content=data, headers=headers)
        if resp.status_code >= 300:
            logger.error("supabase upload failed %s: %s", resp.status_code, resp.text)
            resp.raise_for_status()
    return {"path": path, "size": len(data)}


def get_object(path: str) -> tuple[bytes, str]:
    """Download an object. Uses R2 if configured, otherwise Supabase Storage."""
    if _use_r2():
        client = _r2_client()
        resp = client.get_object(Bucket=_r2_bucket(), Key=path)
        data = resp["Body"].read()
        ct = resp.get("ContentType", "application/octet-stream")
        return data, ct

    url = f"{_supabase_url()}/storage/v1/object/{_SB_BUCKET}/{path}"
    with httpx.Client(timeout=60.0) as client:
        resp = client.get(url, headers=_sb_headers())
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


def get_public_url(path: str) -> str | None:
    """Return a direct public URL for the object if R2_PUBLIC_URL is configured."""
    base = os.environ.get("R2_PUBLIC_URL", "").rstrip("/")
    if base:
        return f"{base}/{path}"
    return None
