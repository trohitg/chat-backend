import time
from typing import Optional
from fastapi import APIRouter, HTTPException, File, UploadFile, Form
from pydantic import BaseModel
from ..core.metrics import track_request_metrics, CHAT_REQUESTS
from ..dependencies import ChatServiceDependency
from ..exceptions import SessionNotFoundError, RateLimitError
import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/images", tags=["images"])


class ImageMessageResponse(BaseModel):
    id: str
    content: str
    role: str
    created_at: str
    image_filename: Optional[str] = None

@router.post("/sessions/{session_id}/messages", response_model=ImageMessageResponse)
@track_request_metrics
async def send_image_message_to_session(
    session_id: str,
    chat_service: ChatServiceDependency,
    message: str = Form(...),
    image: UploadFile = File(...)
):
    """
    Send a text message to a chat session (image filename is logged but not processed).
    
    - **session_id**: The session ID to send the message to
    - **message**: Text message to send
    - **image**: Image file (filename logged but file not stored or processed)
    
    Returns a MessageResponse with AI response to the text message only.
    """
    try:
        # Send only text message to AI service
        result = await chat_service.send_text_message(
            session_id=session_id,
            message=message,
            image_filename=image.filename,
            max_tokens=1000,
            temperature=0.7,
            use_cache=True
        )
        
        # Update metrics
        CHAT_REQUESTS.labels(status="success").inc()
        
        logger.info(
            "Text message with image reference processed",
            session_id=session_id,
            image_filename=image.filename,
            message_length=len(message)
        )
        
        return ImageMessageResponse(
            id=result["id"],
            content=result["content"],
            role=result["role"],
            created_at=result["created_at"],
            image_filename=result.get("image_filename")
        )
        
    except ValueError as e:
        if "not found" in str(e):
            raise SessionNotFoundError(session_id)
        raise HTTPException(status_code=400, detail=str(e))
    
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
        
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