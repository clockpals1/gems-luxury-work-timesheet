"""Cloudflare Workers scheduled task handler for auto punch-out sweep."""
import os
import logging
from datetime import datetime, timezone, timedelta

# Import database and scheduler logic from server
import motor.motor_asyncio
from server import db, now_utc, iso, auto_punch_out_sweep

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scheduled_worker")


async def on_scheduled(event, env, ctx):
    """Cloudflare Workers Cron Trigger handler."""
    logger.info("Scheduled task started: auto punch-out sweep")
    
    # Initialize MongoDB connection
    mongo_url = env.MONGO_URL
    client = motor.motor_asyncio.AsyncIOMotorClient(mongo_url)
    db_client = client[env.DB_NAME]
    
    # Update the global db reference in server module
    server.db = db_client
    
    try:
        # Run the auto punch-out sweep
        await auto_punch_out_sweep()
        logger.info("Auto punch-out sweep completed")
    except Exception as e:
        logger.exception("Auto punch-out sweep failed: %s", e)
        raise
    finally:
        # Close MongoDB connection
        client.close()


# Export the handler for Cloudflare Workers
scheduled_handler = on_scheduled
