"""Cloudflare Workers entry point for FastAPI backend.

Note: Cloudflare Workers Python runtime is in beta. For production,
consider using Cloudflare Run (container-based) for the backend while
using Pages for frontend and R2 for storage.
"""
import os
import logging
from fastapi import Request, Response
from fastapi.responses import JSONResponse
import server

logger = logging.getLogger("worker")


async def fetch(request, env, ctx):
    """Cloudflare Workers fetch handler."""
    # Initialize storage with R2 bucket binding
    server.storage.init_storage(env.R2_BUCKET)
    
    # Initialize MongoDB connection if not already done
    if not hasattr(server, 'db') or server.db is None:
        mongo_url = env.MONGO_URL
        db_name = env.DB_NAME
        server.client = server.AsyncIOMotorClient(mongo_url)
        server.db = server.client[db_name]
    
    # Process the request through FastAPI
    # Note: This requires a proper ASGI adapter for Workers
    # For now, we use the standard approach which works with wrangler's Python support
    return await server.app(request.scope, receive=request.receive, send=request.send)


# Export for Cloudflare Workers
fetch_handler = fetch
