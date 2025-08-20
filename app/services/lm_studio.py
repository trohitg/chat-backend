import time
import uuid
from typing import List, Dict, Optional
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.config import settings
from ..core.cache import cache
from ..models.chat import ChatMessage as ChatMessageModel, ApiUsage
import structlog

logger = structlog.get_logger()

class LMStudioService:
    def __init__(self):
        self.base_url = settings.LM_STUDIO_URL
        self.timeout = 30.0
        
    async def chat_completion(
        self, 
        messages: List[Dict[str, str]], 
        session_id: str,
        db: AsyncSession,
        max_tokens: int = 1000, 
        temperature: float = 0.7,
        use_cache: bool = True,
        model: Optional[str] = None
    ) -> Dict:
        start_time = time.time()
        
        try:
            # Check cache first
            if use_cache:
                cached_response = cache.get_chat_response(messages)
                if cached_response:
                    response_time = time.time() - start_time
                    logger.info("Cache hit for chat completion", 
                              session_id=session_id, 
                              response_time=response_time)
                    
                    await self._log_usage(db, session_id, "chat", 0, response_time, "cache_hit")
                    return {"response": cached_response}
            
            # Make API call to LM Studio
            headers = {
                "Content-Type": "application/json"
            }
            
            selected_model = model or settings.LM_STUDIO_DEFAULT_MODEL
            payload = {
                "model": selected_model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": False
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                result = response.json()
                
                response_time = time.time() - start_time
                assistant_response = result["choices"][0]["message"]["content"]
                usage_info = result.get("usage", {})
                tokens_used = usage_info.get("total_tokens", 0)
                
                # Cache the response
                if use_cache:
                    cache.set_chat_response(messages, assistant_response)
                
                # Log to database
                await self._log_usage(db, session_id, "chat", tokens_used, response_time, "success")
                
                # Store chat messages
                await self._store_messages(db, session_id, messages, assistant_response, tokens_used, response_time, selected_model)
                
                logger.info(
                    "LM Studio chat completion successful",
                    session_id=session_id,
                    tokens_used=tokens_used,
                    response_time=response_time
                )
                
                return {
                    "response": assistant_response
                }
                
        except httpx.HTTPStatusError as e:
            response_time = time.time() - start_time
            error_msg = f"LM Studio API error: {e.response.status_code} - {e.response.text}"
            await self._log_usage(db, session_id, "chat", 0, response_time, "api_error", error_msg)
            logger.error("LM Studio API error", session_id=session_id, error=error_msg)
            raise Exception(error_msg)
            
        except httpx.RequestError as e:
            response_time = time.time() - start_time
            error_msg = f"Request error: {str(e)}"
            await self._log_usage(db, session_id, "chat", 0, response_time, "request_error", error_msg)
            logger.error("Request error", session_id=session_id, error=error_msg)
            raise Exception(error_msg)
            
        except Exception as e:
            response_time = time.time() - start_time
            error_msg = f"Unexpected error: {str(e)}"
            await self._log_usage(db, session_id, "chat", 0, response_time, "error", error_msg)
            logger.error("Unexpected error", session_id=session_id, error=error_msg)
            raise Exception(error_msg)
    
    async def _log_usage(
        self, 
        db: AsyncSession, 
        session_id: str, 
        endpoint: str, 
        tokens_used: int, 
        response_time: float, 
        status: str, 
        error_message: Optional[str] = None
    ):
        try:
            usage = ApiUsage(
                session_id=session_id,
                endpoint=endpoint,
                tokens_used=tokens_used,
                response_time=response_time,
                success=status,
                error_message=error_message
            )
            db.add(usage)
            await db.commit()
        except Exception as e:
            logger.error("Failed to log usage", error=str(e))
            await db.rollback()
    
    async def _store_messages(
        self, 
        db: AsyncSession, 
        session_id: str, 
        messages: List[Dict[str, str]], 
        assistant_response: str, 
        tokens_used: int, 
        response_time: float,
        model_used: Optional[str] = None
    ):
        try:
            # Store user message (last message in the list)
            user_message = messages[-1]
            user_msg = ChatMessageModel(
                session_id=session_id,
                role=user_message["role"],
                content=user_message["content"]
            )
            db.add(user_msg)
            
            # Store assistant response
            assistant_msg = ChatMessageModel(
                session_id=session_id,
                role="assistant",
                content=assistant_response,
                tokens_used=tokens_used,
                response_time=response_time,
                model_used=model_used or settings.LM_STUDIO_DEFAULT_MODEL
            )
            db.add(assistant_msg)
            
            await db.commit()
        except Exception as e:
            logger.error("Failed to store messages", error=str(e))
            await db.rollback()

lm_studio_service = LMStudioService()