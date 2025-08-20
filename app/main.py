import asyncio
import os
import sys
import time
import uuid
from typing import List, Optional

# Fix for Windows async event loop compatibility with psycopg
# Only apply this fix when actually running on Windows (not in Docker containers)
if sys.platform == "win32" and not os.getenv("CONTAINER_ENV"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from .core.config import settings
from .core.database import get_db, engine, Base, init_database, check_database_health
from .core.cache import cache
from .core.logging import setup_logging
from .core.metrics import (
    get_metrics, track_request_metrics, 
    CHAT_REQUESTS, CACHE_HITS, TOKENS_USED
)
from .core.providers import parse_provider, get_available_providers, AVAILABLE_PROVIDERS
from .models.chat import ChatSession
from .api.images import router as images_router
from .api.wallet import router as wallet_router
from .dependencies import ChatServiceDependency
from .exceptions import SessionNotFoundError, RateLimitError, OpenRouterAPIError
import structlog

# Setup logging
setup_logging()
logger = structlog.get_logger()

# Database tables will be created on startup

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.API_VERSION,
    debug=settings.DEBUG
)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    await init_database()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_HOSTS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(images_router, prefix="/api/v1")
app.include_router(wallet_router, prefix="/api/v1")

# Models
class SessionRequest(BaseModel):
    pass

class SessionResponse(BaseModel):
    session_id: str
    created_at: str
    expires_in: int

class MessageRequest(BaseModel):
    message: str
    stream: bool = False
    provider: Optional[str] = None  # "backend/model" format (e.g. "lm_studio/gemma-3-1b-it")

class MessageResponse(BaseModel):
    id: str
    content: str
    role: str
    created_at: str
    image_filename: Optional[str] = None

class DeleteSessionResponse(BaseModel):
    message: str

class MessageHistoryItem(BaseModel):
    id: str
    role: str
    content: str
    created_at: str
    image_filename: Optional[str] = None

class MessageHistoryResponse(BaseModel):
    messages: List[MessageHistoryItem]
    total_count: int

class ErrorResponse(BaseModel):
    error: dict
    timestamp: str


# Middleware for request logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Generate request ID
    request_id = str(uuid.uuid4())
    
    logger.info(
        "Request started",
        request_id=request_id,
        method=request.method,
        url=str(request.url),
        client_ip=request.client.host
    )
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    logger.info(
        "Request completed",
        request_id=request_id,
        status_code=response.status_code,
        process_time=process_time
    )
    
    return response

@app.post("/api/v1/sessions", response_model=SessionResponse)
async def create_session(request: SessionRequest, chat_service: ChatServiceDependency):
    try:
        session = await chat_service.create_session()
        created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        
        return SessionResponse(
            session_id=session.session_id,
            created_at=created_at,
            expires_in=3600  # 1 hour
        )
    except Exception as e:
        logger.error("Session creation failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail={
                "error": {"code": "SESSION_CREATION_FAILED", "message": "Failed to create session. Please try again."},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
        )

@app.post("/api/v1/sessions/{session_id}/messages", response_model=MessageResponse)
@track_request_metrics
async def send_message_to_session(session_id: str, request: MessageRequest, chat_service: ChatServiceDependency):
    try:
        # Parse provider selection
        backend, model = parse_provider(request.provider)
        
        result = await chat_service.send_message(
            session_id=session_id,
            message=request.message,
            max_tokens=1000,
            temperature=0.7,
            use_cache=True,
            backend=backend,
            model=model
        )
        
        # Update metrics
        CHAT_REQUESTS.labels(status="success").inc()
        
        return MessageResponse(
            id=result["id"],
            content=result["content"],
            role=result["role"],
            created_at=result["created_at"]
        )
    
    except ValueError as e:
        if "not found" in str(e):
            raise SessionNotFoundError(session_id)
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        CHAT_REQUESTS.labels(status="error").inc()
        logger.error("Message request failed", error=str(e), session_id=session_id)
        
        # Check for specific error types
        if "rate limit" in str(e).lower() or "quota" in str(e).lower():
            raise RateLimitError()
        elif "api key" in str(e).lower() or "unauthorized" in str(e).lower():
            raise HTTPException(
                status_code=401,
                detail={
                    "error": {"code": "UNAUTHORIZED", "message": "API authentication failed. Please check server configuration."},
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                }
            )
        else:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": {"code": "MESSAGE_PROCESSING_FAILED", "message": "Failed to process message. Please try again."},
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                }
            )

@app.get("/api/v1/health")
async def health_check():
    # Check database health
    db_health = await check_database_health()
    
    # Check cache health
    cache_health = cache.health_check()
    
    # Determine overall status
    overall_healthy = (
        db_health.get("healthy", False) and 
        cache_health.get("status") == "healthy"
    )
    
    return {
        "status": "healthy" if overall_healthy else "degraded",
        "version": settings.API_VERSION,
        "components": {
            "database": db_health,
            "cache": cache_health
        }
    }


@app.get("/metrics")
async def metrics():
    return PlainTextResponse(get_metrics(), media_type="text/plain")


@app.get("/api/v1/sessions/{session_id}/messages", response_model=MessageHistoryResponse)
async def get_session_messages(session_id: str, chat_service: ChatServiceDependency):
    try:
        messages = await chat_service.get_message_history(session_id)
        
        message_items = [
            MessageHistoryItem(
                id=msg["id"],
                role=msg["role"],
                content=msg["content"],
                created_at=msg["created_at"],
                image_filename=msg.get("image_filename")
            )
            for msg in messages
        ]
        
        return MessageHistoryResponse(
            messages=message_items,
            total_count=len(message_items)
        )
        
    except ValueError as e:
        if "not found" in str(e):
            raise SessionNotFoundError(session_id)
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error("Failed to get session messages", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve messages")

@app.delete("/api/v1/sessions/{session_id}", response_model=DeleteSessionResponse)
async def delete_session(session_id: str, chat_service: ChatServiceDependency):
    try:
        await chat_service.delete_session(session_id)
        return DeleteSessionResponse(message="Session deleted successfully")
    
    except Exception as e:
        logger.error("Failed to delete session", error=str(e), session_id=session_id)
        raise HTTPException(status_code=500, detail="Failed to delete session")

@app.get("/api/v1/backends")
async def get_available_backends():
    """Get available LLM backends and their models"""
    backends = {
        "openrouter": {
            "enabled": True,
            "models": settings.AVAILABLE_MODELS,
            "default_model": settings.DEFAULT_MODEL
        }
    }
    
    if settings.LM_STUDIO_ENABLED:
        backends["lm_studio"] = {
            "enabled": True,
            "models": settings.LM_STUDIO_AVAILABLE_MODELS,
            "default_model": settings.LM_STUDIO_DEFAULT_MODEL
        }
    
    return {
        "backends": backends,
        "default_backend": settings.DEFAULT_LLM_BACKEND
    }

@app.get("/api/v1/providers")
async def get_available_providers_simple():
    """Get available providers in simplified format"""
    return get_available_providers()

@app.get("/")
async def root():
    return {
        "message": f"{settings.PROJECT_NAME} is running",
        "version": settings.API_VERSION,
        "status": "healthy"
    }

