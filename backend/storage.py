"""Cloudflare R2 object storage wrapper."""
import os
import logging
import uuid

APP_NAME = os.environ.get("APP_NAME", "gemsluxury")

logger = logging.getLogger(__name__)

# R2 bucket will be injected via wrangler binding
_bucket = None


def init_storage(bucket=None):
    """Initialize storage with R2 bucket binding."""
    global _bucket
    if bucket:
        _bucket = bucket
    return _bucket


def put_object(path: str, data: bytes, content_type: str) -> dict:
    """Upload object to R2 bucket."""
    if not _bucket:
        raise RuntimeError("R2 bucket not initialized. Call init_storage() first.")
    
    _bucket.put(path, data, custom_metadata={"contentType": content_type})
    return {"path": path, "size": len(data)}


def get_object(path: str) -> tuple[bytes, str]:
    """Download object from R2 bucket."""
    if not _bucket:
        raise RuntimeError("R2 bucket not initialized. Call init_storage() first.")
    
    obj = _bucket.get(path)
    if obj is None:
        raise KeyError(f"Object not found: {path}")
    
    content_type = obj.http_metadata.get("contentType") or "application/octet-stream"
    return obj.body, content_type


def build_path(user_id: str, filename: str, kind: str = "uploads") -> str:
    """Build storage path for an object."""
    ext = filename.split(".")[-1].lower() if "." in filename else "bin"
    if ext not in {"jpg", "jpeg", "png", "gif", "webp"}:
        ext = "bin"
    return f"{APP_NAME}/{kind}/{user_id}/{uuid.uuid4()}.{ext}"
