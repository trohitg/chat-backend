from fastapi import HTTPException
from enum import Enum
from datetime import datetime
from typing import Optional

class ErrorCode(str, Enum):
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    OPENROUTER_API_ERROR = "OPENROUTER_API_ERROR"
    MESSAGE_PROCESSING_FAILED = "MESSAGE_PROCESSING_FAILED"
    SESSION_CREATION_FAILED = "SESSION_CREATION_FAILED"
    UNAUTHORIZED = "UNAUTHORIZED"

class ChatAPIException(HTTPException):
    """Base exception for chat API errors"""
    
    def __init__(
        self, 
        error_code: ErrorCode, 
        message: str, 
        status_code: int = 500, 
        retry_after: Optional[int] = None
    ):
        detail = {
            "error": {
                "code": error_code.value,
                "message": message,
            },
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        
        if retry_after:
            detail["error"]["retry_after"] = retry_after
            
        super().__init__(status_code=status_code, detail=detail)

class SessionNotFoundError(ChatAPIException):
    def __init__(self, session_id: str):
        super().__init__(
            error_code=ErrorCode.SESSION_NOT_FOUND,
            message=f"Session {session_id} not found",
            status_code=404
        )

class RateLimitError(ChatAPIException):
    def __init__(self, retry_after: int = 60):
        super().__init__(
            error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
            message="Too many requests. Please wait before sending another message.",
            status_code=429,
            retry_after=retry_after
        )

class OpenRouterAPIError(ChatAPIException):
    def __init__(self, message: str):
        super().__init__(
            error_code=ErrorCode.OPENROUTER_API_ERROR,
            message=f"OpenRouter API error: {message}",
            status_code=502
        )