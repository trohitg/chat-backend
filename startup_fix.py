import asyncio
import sys

# Fix for Windows async event loop compatibility with psycopg
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Import the FastAPI app after setting the event loop policy
from app.main import app

__all__ = ["app"]